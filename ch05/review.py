"""05-1 AI가 구조해석 결과를 이해하는 방법 (실행 위치 (3)).

초기 설계 해석과 변수 하나씩 바꾼 민감도 해석을 구조화해 GPT-6 Astra에 넘기고 개선안을 받는다.
코드는 (1) AI가 인용한 숫자가 입력에 있는지, (2) 제안 값이 변수 범위 안인지 검사하고,
(3) 제안을 실제로 재해석해 AI의 예상과 결과를 비교한다.
사용 (저장소 루트에서): python ch05/review.py
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from openai import OpenAI  # noqa: E402
from ch05.evaluate import evaluate  # noqa: E402

BASE = {"base_t": 8.0, "arm_t": 8.0, "r_in": 5.0}
RANGES = {"base_t": [3, 10], "arm_t": [3, 10], "r_in": [2, 8]}
CRITERIA = {"safety_factor_min": 2.0, "max_deflection_mm": 0.5}

SYSTEM = """구조해석 결과를 읽고 브래킷 설계 개선 방향을 제안하는 엔지니어입니다.
- 판단 근거는 입력에 있는 수치만 그대로 인용하세요. 입력에 없는 수치를 만들거나 계산해 쓰지 마세요.
- 응력·처짐 값을 직접 예측해 확정하지 마세요. 새 설계는 반드시 재해석이 필요하다고 표시하세요.
- 어떤 기준이 먼저 한계에 닿을지(지배 제약), 질량 대비 효과가 큰 변수가 무엇인지 판단하세요.
- 제안은 최대 3개, 각 변수는 허용 범위 안의 값으로만 하세요.
출력 JSON: {"governing_constraint": str, "evidence": [str], "proposals": [{"change": {변수: 값}, "rationale": str}], "warnings": [str]}"""


def compact(r):
    return {k: r[k] for k in ("mass_g", "vm_max_MPa", "safety_factor", "u_max_mm", "pass")}


def main():
    cases = {"초기 설계": BASE, "바닥판 1mm 얇게": {**BASE, "base_t": 7.0},
             "세로판 1mm 얇게": {**BASE, "arm_t": 7.0}, "안쪽 필렛 R7": {**BASE, "r_in": 7.0}}
    results = {name: {"design": x, **compact(evaluate(x, tag="review"))} for name, x in cases.items()}
    payload = {"criteria": CRITERIA, "variable_ranges_mm": RANGES,
               "load_case": "세로판 윗면 200 N(−X), 볼트 구멍 4개 내면 고정, Al 6061-T6 항복 276 MPa, 요소 크기 4 mm",
               "max_stress_location": "세로판 쪽 볼트 구멍 가장자리 (고정 경계)", "results": results}
    print(json.dumps(results, ensure_ascii=False, indent=1))

    r = OpenAI().responses.create(model=os.environ.get("OPENAI_MODEL", "gpt-6-astra"), instructions=SYSTEM,
                                  input=json.dumps(payload, ensure_ascii=False), text={"format": {"type": "json_object"}})
    ans = json.loads(r.output_text)
    print(f"\n[AI 토큰 {r.usage.input_tokens}/{r.usage.output_tokens}]\n" + json.dumps(ans, ensure_ascii=False, indent=1))

    # (1) 인용 숫자 검사: AI 문장의 숫자가 입력 JSON의 숫자 목록에 있는가
    given = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(payload)))
    said = set(re.findall(r"\d+(?:\.\d+)?", " ".join(ans.get("evidence", []) + [p["rationale"] for p in ans.get("proposals", [])])))
    print("\n입력에 없는 숫자:", sorted(said - given, key=float) or "없음")
    # (2) 범위 검사 → (3) 재해석으로 확인
    for p in ans.get("proposals", []):
        x = {**BASE, **{k: float(v) for k, v in p["change"].items()}}
        bad = [k for k, v in p["change"].items() if k not in RANGES or not RANGES[k][0] <= float(v) <= RANGES[k][1]]
        if bad:
            print(f"제안 {p['change']}: 범위 밖 {bad} → 거절")
            continue
        res = evaluate(x, tag="review-proposal")
        print(f"제안 {p['change']} → 재해석: 질량 {res['mass_g']} g, 안전율 {res['safety_factor']}, "
              f"처짐 {res['u_max_mm']} mm, {'합격' if res['pass'] else '불합격'}")


if __name__ == "__main__":
    main()
