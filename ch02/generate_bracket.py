"""02-4 생성 → 검증 → 수정 루프: GPT-6 Astra가 쓴 브래킷 코드를 검증하고, 실패하면 결과를 되돌려 고치게 한다.

사용 (저장소 루트에서): python ch02/generate_bracket.py [--max-rounds 3]
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(errors="replace")   # 콘솔이 못 쓰는 문자(−, — 등)는 ?로 — 한국어 Windows(cp949)에서 멈추지 않게
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from openai import OpenAI  # noqa: E402
from common.freecad_runner import run_freecad, tagged_line  # noqa: E402

SPEC = {"base_len": 120, "width": 80, "base_t": 8, "arm_h": 80, "arm_t": 8, "r_in": 5, "r_corner": 5,
        "hole_d": 6, "hole_x1": 25, "hole_x2": 110, "hole_y": 10}

REQUEST = f"""L자 알루미늄 브래킷을 FreeCAD 1.1 Python(Part 모듈)으로 만들어라. 단위 mm, 설계 변수 = {json.dumps(SPEC)}
- 바닥판: x 0~base_len, y 0~width, z 0~base_t
- 세로판: 바닥판의 x=0 끝면 바깥쪽에 붙는다. x -arm_t~0, y 0~width, z 0~arm_h (바닥면 기준 전체 높이)
- 안쪽 꺾임부(x=0, z=base_t를 지나는 Y 방향 모서리)에 반경 r_in 필렛
- 바닥판 끝단(x=base_len)의 수직 모서리 2개에 반경 r_corner 필렛
- 지름 hole_d 관통 구멍 4개: 중심 (hole_x1, hole_y), (hole_x1, width-hole_y), (hole_x2, hole_y), (hole_x2, width-hole_y)"""

# 좌표 없이 말로만 적은 요구사항 — 현장에서 흔한 형태. 해석의 여지가 있어 검증·수정 루프가 필요하다
REQUEST_VERBAL = """L자 알루미늄 브래킷을 FreeCAD 1.1 Python(Part 모듈)으로 만들어라. 단위 mm.
- 바닥판 120 x 80, 두께 8. 바닥판 한쪽 끝(짧은 변)에 세로판을 붙인다. 세로판은 두께 8, 바닥면에서 잰 전체 높이 80, 폭 80.
- 세로판과 바닥판이 만나는 안쪽 모서리에 R5 필렛, 세로판 반대쪽 끝의 바닥판 세로 모서리 2개에 R5 필렛.
- 지름 6 관통 구멍 4개: 세로판 쪽 2개는 세로판 안쪽 면에서 25 떨어진 곳, 나머지 2개는 반대쪽 끝에서 10 떨어진 곳. 모두 긴 변에서 10 안쪽."""

SYSTEM = """FreeCAD 1.1 Python 코드를 작성하는 CAD 엔지니어입니다.
- freecadcmd(GUI 없음)에서 실행됩니다. FreeCADGui는 쓰지 마세요.
- 설계 변수는 맨 위에 상수로 두세요. 모서리는 Edge 번호가 아니라 위치·방향 조건으로 고르세요.
- 결과는 새 문서에 Part::Feature 이름 "Bracket"으로 추가하고 doc.saveAs(OUT_FCSTD) 하세요. OUT_FCSTD는 미리 정의되어 있습니다.
- 코드만 출력하세요 (```python 블록 하나)."""


def ask(client, model, messages):
    t = time.time()
    r = client.responses.create(model=model, instructions=SYSTEM, input=messages)
    m = re.search(r"```(?:python)?\n(.*?)```", r.output_text, re.S)
    return (m.group(1) if m else r.output_text), r, time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--verbal", action="store_true", help="좌표 없이 말로만 적은 요구사항 사용")
    ap.add_argument("--out", default=str(ROOT / "output" / "ch02" / "gen"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    client, model = OpenAI(), os.environ.get("OPENAI_MODEL", "gpt-6-astra")
    messages = [{"role": "user", "content": REQUEST_VERBAL if a.verbal else REQUEST}]
    tokens = [0, 0]
    for rnd in range(1, a.max_rounds + 1):
        code, r, sec = ask(client, model, messages)
        tokens[0] += r.usage.input_tokens
        tokens[1] += r.usage.output_tokens
        fcstd = out / f"bracket_r{rnd}.FCStd"
        if fcstd.exists():
            fcstd.unlink()
        runner = out / f"bracket_r{rnd}_run.py"
        runner.write_text(f"OUT_FCSTD = r'{fcstd}'\n" + code, encoding="utf-8")
        rc, log = run_freecad(runner)
        if not fcstd.exists():
            feedback = "실행 실패. 마지막 출력:\n" + log[-1200:]
            print(f"[{rnd}회차] 코드 {code.count(chr(10)) + 1}줄, {sec:.0f}초 → 실행 실패")
        else:
            rc, log2 = run_freecad(Path(__file__).with_name("validate_bracket.py"),
                                   env={"BRACKET_FCSTD": str(fcstd), "BRACKET_SPEC": json.dumps(SPEC)})
            res = json.loads(tagged_line(log2, "CHECK"))
            failed = [k for k, ok in res["checks"].items() if not ok]
            print(f"[{rnd}회차] 코드 {code.count(chr(10)) + 1}줄, {sec:.0f}초 → "
                  + ("합격" if not failed else "불합격: " + ", ".join(failed)))
            print("        측정:", json.dumps(res["measured"]))
            if not failed:
                break
            # 실패 항목만이 아니라 측정값과 기대값을 나란히 준다 — 차이에서 원인을 찾게
            feedback = ("검증 실패 항목: " + ", ".join(failed)
                        + "\n측정값: " + json.dumps(res["measured"])
                        + "\n기대값: " + json.dumps(res["expected"])
                        + "\n요구사항과 비교해 원인을 찾아 코드를 고쳐라.")
        messages += [{"role": "assistant", "content": f"```python\n{code}```"}, {"role": "user", "content": feedback}]
    cost = tokens[0] * 10e-6 + tokens[1] * 50e-6
    print(f"토큰 입력 {tokens[0]}·출력 {tokens[1]}, 비용 약 ${cost:.3f}")


if __name__ == "__main__":
    main()
