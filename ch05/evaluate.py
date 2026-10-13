"""05-2 설계 변수 → 모델 재생성 → 메시 → 해석 → 판정 파이프라인 (실행 위치 (3)).

evaluate({"base_t": 6, "arm_t": 8, "r_in": 8})처럼 부르면 freecadcmd로 04-4의 bracket_fem.py를 실행해
질량·안전율·처짐·판정을 돌려준다. 같은 설계는 캐시에서 바로 돌려주고, 모든 시도는 이력에 남긴다.

사용 (저장소 루트에서):
  python ch05/evaluate.py base_t=7 arm_t=7
  python ch05/evaluate.py --sweep 8,7,6,5,4        # 바닥판·세로판 두께를 같이 바꿔 가며 재해석
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")                  # FREECAD_CMD (01-2)
from common.freecad_runner import run_freecad, tagged_line  # noqa: E402

OUT = ROOT / "output" / "ch05"
CACHE = Path(os.environ.get("CAE_CACHE_DIR", OUT / "cache"))     # 06-3 평가는 사례마다 따로
HISTORY = OUT / "history.jsonl"
BRACKET_FEM = ROOT / "ch04" / "bracket_fem.py"
TEMPLATE_DIR = OUT / "template"            # 05장 전용 기준 모델 — 다른 장의 출력 파일을 공유하지 않는다
SRC = TEMPLATE_DIR / "bracket_param.FCStd"


def ensure_template(timeout=600):
    """02-3의 파라메트릭 브래킷을 기본값으로 한 번 만들어 둔다 (설계 변수는 매번 SET으로 덮어쓴다). 만들어졌으면 True"""
    if not SRC.exists():
        run_freecad(ROOT / "ch02" / "bracket_parametric.py", env={"OUT_DIR": str(TEMPLATE_DIR)}, timeout=timeout)
    return SRC.exists()


def evaluate(x, mesh=4.0, tag="", load=None, timeout=900):
    """설계 변수 dict → 결과 dict. 실패해도 예외 대신 ok=False로 돌려준다 (최적화가 멈추지 않게).
    load: 해석 조건을 바꿀 때만 준다 (06장). 예: {"LOAD_N": "300", "FIX": "bottom"}
    timeout: 해석 1회의 최대 시간(초). 넘으면 stage timeout으로 돌려주고 캐시하지 않는다(다음에 다시 시도)."""
    x = {k: round(float(v), 2) for k, v in sorted(x.items())}       # 0.01 mm 단위로 맞춰 캐시
    key = hashlib.md5(json.dumps([x, mesh] + ([load] if load else [])).encode()).hexdigest()[:10]
    run_dir = CACHE / key
    cached = run_dir / "result.json"
    if cached.exists():
        return {**json.loads(cached.read_text(encoding="utf-8")), "cached": True}
    run_dir.mkdir(parents=True, exist_ok=True)
    # 해석 조건을 모두 직접 지정한다 — 셸에 남은 FIX·LOAD_N 같은 환경변수가 섞이지 않게
    env = {"SRC": str(SRC), "SET": ";".join(f"{k}={v}" for k, v in x.items()), "MESH": str(mesh), "OUT_DIR": str(run_dir),
           "FIX": "holes", "LOAD_N": "200", "VTK": "0", **(load or {})}
    t = time.time()
    err = None
    try:                                    # 기준 모델 생성(처음 한 번)과 해석 모두 같은 실패 경로로
        if ensure_template(timeout):
            rc, log = run_freecad(BRACKET_FEM, env=env, timeout=timeout)
        else:
            err = {"stage": "template", "detail": "기준 모델을 만들지 못함 (ch02/bracket_parametric.py)"}
    except subprocess.TimeoutExpired:
        err = {"stage": "timeout", "detail": f"{timeout}초 안에 끝나지 않음"}
    except OSError as e:                    # freecadcmd를 찾지 못하거나 실행할 수 없음
        err = {"stage": "run", "detail": str(e)}
    if err:                                 # 실패는 캐시하지 않는다 (다음에 다시 시도)
        return _record({"x": x, "mesh_mm": mesh, "ok": False, "pass": False, "error": err}, t, tag, None)
    line = tagged_line(log, "RESULT")
    if line:
        r = json.loads(line)
        res = {"x": x, "mesh_mm": mesh, "ok": True, "mass_g": r["mass_g"], "vm_max_MPa": r["vm_max_MPa"],
               "safety_factor": r["safety_factor"], "u_max_mm": r["u_max_mm"], "pass": r["pass"]}
    else:            # 형상 검증 실패, 메시 실패 등 — bracket_fem.py가 남긴 FAIL 줄을 읽는다
        fail = tagged_line(log, "FAIL")
        res = {"x": x, "mesh_mm": mesh, "ok": False, "pass": False,
               "error": json.loads(fail) if fail else {"stage": "unknown", "detail": log[-200:]}}
    return _record(res, t, tag, cached)


def _record(res, t, tag, cached):
    """결과를 이력에 남기고, cached 경로가 있으면 캐시한다 (시간 초과·실행 오류는 캐시하지 않음)"""
    res["sec"] = round(time.time() - t, 1)
    if cached:
        cached.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    HISTORY.parent.mkdir(parents=True, exist_ok=True)     # import해서 부르면 __main__의 OUT.mkdir를 거치지 않는다
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"tag": tag, **res}, ensure_ascii=False) + "\n")
    return res


def show(r):
    if not r["ok"]:
        return f"{r['x']}  실패: {r['error']}"
    return (f"{r['x']}  질량 {r['mass_g']:6.1f} g  최대응력 {r['vm_max_MPa']:6.2f} MPa  안전율 {r['safety_factor']:5.2f}  "
            f"처짐 {r['u_max_mm']:.4f} mm  {'합격' if r['pass'] else '불합격'}  ({r['sec']}초{', 캐시' if r.get('cached') else ''})")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args and args[0] == "--sweep":
        for t in [float(v) for v in args[1].split(",")]:
            print(show(evaluate({"base_t": t, "arm_t": t}, tag="sweep")), flush=True)
    else:
        print(show(evaluate({k: float(v) for k, v in (a.split("=") for a in args)}, tag="cli")))
