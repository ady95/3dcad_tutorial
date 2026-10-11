"""03-3 기존 CAD 모델 수정과 반복 설계 (실행 위치 (3)).

자연어 수정 요청 → GPT-6 Astra가 설계 변수 변경(JSON)으로 번역 → 범위 검사 → freecadcmd로 적용·검증
→ 새 버전 파일로 저장하고 이력에 기록. 검증에 실패하면 현재 버전을 바꾸지 않는다.

사용 (저장소 루트에서):
  python ch03/modify_model.py --init                 # 02-3의 브래킷을 v000으로 등록
  python ch03/modify_model.py "세로판을 2mm 두껍게 해줘"
  python ch03/modify_model.py --undo                 # 직전 버전으로 되돌리기
  python ch03/modify_model.py --history
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from openai import OpenAI  # noqa: E402
from common.freecad_runner import run_freecad, tagged_line  # noqa: E402

VDIR = ROOT / "output" / "ch03" / "versions"
HISTORY = VDIR / "history.jsonl"
CURRENT = VDIR / "current.txt"
APPLY = Path(__file__).with_name("apply_changes.py")

# 바꿀 수 있는 설계 변수와 허용 범위 [mm] — AI가 이 밖의 값을 내면 코드가 거절한다
VARIABLES = {
    "base_t": ("바닥판 두께", 3, 12), "arm_t": ("세로판 두께", 3, 12), "arm_h": ("세로판 높이(바닥면 기준)", 40, 120),
    "r_in": ("안쪽 꺾임부 필렛", 1, 10), "r_corner": ("바닥판 바깥 모서리 필렛", 1, 10),
    "hole_d": ("구멍 지름", 4, 10), "hole_x1": ("세로판 쪽 구멍 X", 15, 60), "hole_x2": ("끝단 쪽 구멍 X", 60, 150),
    "hole_y": ("구멍과 옆면 거리", 6, 30), "base_len": ("바닥판 길이", 80, 160), "width": ("폭", 40, 120),
}

SYSTEM = """기존 브래킷 CAD 모델의 수정 요청을 설계 변수 변경으로 바꾸는 엔지니어입니다.
- 현재 설계 변수와 허용 범위가 주어집니다. 바꿀 변수와 새 값(mm)만 정하세요. 형상을 직접 그리지 마세요.
- 요청이 어느 변수를 뜻하는지 모호하거나(예: 그냥 "두께"), 목표가 수치로 정해지지 않으면(예: "가볍게") 추측하지 말고
  status를 "need_clarification"으로 하고 questions에 선택지를 담아 물으세요.
- 허용 범위 밖의 값이 필요하면 바꾸지 말고 그 이유를 questions에 쓰세요.
- 출력 JSON: {"status": "ok" | "need_clarification", "changes": {변수: 새 값}, "reason": str, "questions": [str]}"""


def current_version():
    return CURRENT.read_text().strip() if CURRENT.exists() else None


def log(entry):
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), **entry}, ensure_ascii=False) + "\n")


def freecad_apply(src, dst=None, changes=None):
    env = {"SRC": str(src), "DST": str(dst or ""), "CHANGES": json.dumps(changes or {})}
    rc, out = run_freecad(APPLY, env=env)
    line = tagged_line(out, "RESULT")
    if line is None:
        raise RuntimeError("freecadcmd 실행 실패:\n" + out[-800:])
    return json.loads(line)


def init():
    VDIR.mkdir(parents=True, exist_ok=True)
    src = ROOT / "output" / "ch02" / "bracket_param.FCStd"
    shutil.copy(src, VDIR / "v000.FCStd")
    CURRENT.write_text("v000")
    r = freecad_apply(VDIR / "v000.FCStd")
    log({"version": "v000", "action": "init", "params": r["after"], "pass": r["pass"], "mass_g": r["mass_g"]})
    print(f"v000 등록: 질량 {r['mass_g']} g, 검증 {'합격' if r['pass'] else '불합격'}")


def modify(request):
    cur = current_version()
    cur_file = VDIR / f"{cur}.FCStd"
    state = freecad_apply(cur_file)                       # 현재 설계 변수 읽기
    table = {k: {"설명": d, "현재": state["after"][k], "범위": [lo, hi]} for k, (d, lo, hi) in VARIABLES.items()}
    t = time.time()
    r = OpenAI().responses.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-6-astra"), instructions=SYSTEM, text={"format": {"type": "json_object"}},
        input=f"현재 설계 변수: {json.dumps(table, ensure_ascii=False)}\n수정 요청: {request}")
    plan = json.loads(r.output_text)
    print(f"[AI {time.time() - t:.1f}초, 토큰 {r.usage.input_tokens}/{r.usage.output_tokens}] {json.dumps(plan, ensure_ascii=False)}")
    if plan.get("status") != "ok":
        log({"version": cur, "action": "question", "request": request, "questions": plan.get("questions")})
        print("확인이 필요합니다:", *plan.get("questions", []), sep="\n  - ")
        return
    for k, v in plan["changes"].items():                  # AI 출력은 코드로 다시 검사한다
        if k not in VARIABLES or not (VARIABLES[k][1] <= v <= VARIABLES[k][2]):
            log({"version": cur, "action": "rejected", "request": request, "changes": plan["changes"]})
            print(f"거절: {k}={v}는 허용 범위 밖이거나 없는 변수입니다.")
            return
    new = f"v{max(int(f.stem[1:]) for f in VDIR.glob('v*.FCStd')) + 1:03d}"   # 실패한 버전 파일도 덮어쓰지 않게
    res = freecad_apply(cur_file, VDIR / f"{new}.FCStd", plan["changes"])
    log({"version": new, "action": "modify", "from": cur, "request": request, "changes": plan["changes"],
         "reason": plan.get("reason"), "pass": res["pass"], "failed": res["failed"], "mass_g": res["mass_g"]})
    if res["pass"]:
        CURRENT.write_text(new)
        print(f"{cur} → {new}: {plan['changes']} | 질량 {state['mass_g']} → {res['mass_g']} g | 검증 합격")
    else:
        print(f"{new} 검증 불합격({', '.join(res['failed'])}) — 현재 버전은 {cur}로 유지합니다.")


def undo():
    cur = current_version()
    entries = [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines()]
    prev = next((e["from"] for e in reversed(entries) if e.get("action") == "modify" and e["version"] == cur), None)
    if prev is None:
        print("되돌릴 이전 버전이 없습니다.")
        return
    CURRENT.write_text(prev)
    log({"version": prev, "action": "undo", "from": cur})
    print(f"{cur} → {prev}로 되돌렸습니다 (파일은 지우지 않음).")


def history():
    for l in HISTORY.read_text(encoding="utf-8").splitlines():
        e = json.loads(l)
        print(e["time"], e["action"], e.get("version"), e.get("request", ""), e.get("changes", ""), e.get("mass_g", ""))
    print("현재 버전:", current_version())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("request", nargs="?")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--history", action="store_true")
    a = ap.parse_args()
    if a.init:
        init()
    elif a.undo:
        undo()
    elif a.history:
        history()
    elif a.request:
        modify(a.request)
