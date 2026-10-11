"""05-2 설계 변수 → 모델 재생성 → 메시 → 해석 → 판정 파이프라인 (실행 위치 (3)).

evaluate({"base_t": 6, "arm_t": 8, "r_in": 8})처럼 부르면 freecadcmd로 04-4의 bracket_fem.py를 실행해
질량·안전율·처짐·판정을 돌려준다. 같은 설계는 캐시에서 바로 돌려주고, 모든 시도는 이력에 남긴다.

사용 (저장소 루트에서):
  python ch05/evaluate.py base_t=7 arm_t=7
  python ch05/evaluate.py --sweep 8,7,6,5,4        # 바닥판·세로판 두께를 같이 바꿔 가며 재해석
"""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")                  # FREECAD_CMD (01-2)
from common.freecad_runner import run_freecad, tagged_line  # noqa: E402

OUT = ROOT / "output" / "ch05"
CACHE = OUT / "cache"
HISTORY = OUT / "history.jsonl"
BRACKET_FEM = ROOT / "ch04" / "bracket_fem.py"
TEMPLATE_DIR = OUT / "template"            # 05장 전용 기준 모델 — 다른 장의 출력 파일을 공유하지 않는다
SRC = TEMPLATE_DIR / "bracket_param.FCStd"


def ensure_template():
    """02-3의 파라메트릭 브래킷을 기본값으로 한 번 만들어 둔다 (설계 변수는 매번 SET으로 덮어쓴다)"""
    if not SRC.exists():
        run_freecad(ROOT / "ch02" / "bracket_parametric.py", env={"OUT_DIR": str(TEMPLATE_DIR)})


def evaluate(x, mesh=4.0, tag=""):
    """설계 변수 dict → 결과 dict. 실패해도 예외 대신 ok=False로 돌려준다 (최적화가 멈추지 않게)."""
    x = {k: round(float(v), 2) for k, v in sorted(x.items())}       # 0.01 mm 단위로 맞춰 캐시
    key = hashlib.md5(json.dumps([x, mesh]).encode()).hexdigest()[:10]
    run_dir = CACHE / key
    cached = run_dir / "result.json"
    if cached.exists():
        return {**json.loads(cached.read_text(encoding="utf-8")), "cached": True}
    run_dir.mkdir(parents=True, exist_ok=True)
    ensure_template()
    env = {"SRC": str(SRC), "SET": ";".join(f"{k}={v}" for k, v in x.items()), "MESH": str(mesh), "OUT_DIR": str(run_dir)}
    t = time.time()
    rc, log = run_freecad(BRACKET_FEM, env=env, timeout=900)
    line = tagged_line(log, "RESULT")
    if line:
        r = json.loads(line)
        res = {"x": x, "mesh_mm": mesh, "ok": True, "mass_g": r["mass_g"], "vm_max_MPa": r["vm_max_MPa"],
               "safety_factor": r["safety_factor"], "u_max_mm": r["u_max_mm"], "pass": r["pass"]}
    else:            # 형상 검증 실패, 메시 실패 등 — bracket_fem.py가 남긴 FAIL 줄을 읽는다
        fail = tagged_line(log, "FAIL")
        res = {"x": x, "mesh_mm": mesh, "ok": False, "pass": False,
               "error": json.loads(fail) if fail else {"stage": "unknown", "detail": log[-200:]}}
    res["sec"] = round(time.time() - t, 1)
    cached.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
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
