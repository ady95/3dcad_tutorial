"""03-2 자연어 기반 CAD 설계 에이전트 (실행 위치 (3)).

요구사항 문장 → [GPT-6 Astra] 고정 형식의 사양 JSON (빠진 조건은 되묻기) → [코드] 사양 검증
→ 설계 변수로 변환 → [freecadcmd] 02-3의 파라메트릭 브래킷 생성·필렛 재연결·검증 → FCStd 저장

사용 (저장소 루트에서):
  python ch03/design_agent.py                          # 질문이 나오면 직접 답한다
  python ch03/design_agent.py --answers ch03/answers.json   # 미리 적어 둔 답으로 재현 실행
"""
import argparse
import json
import os
import shutil
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

REQUEST = ("알루미늄 L자 장착 브래킷을 만들어줘. 바닥판은 120×80mm, 두께 8mm이고 Ø6 체결 구멍 4개로 벽에 고정해. "
           "세로판은 두께 8mm, 높이 80mm로 바닥판 끝에 붙여. 꺾이는 안쪽과 바깥 모서리에는 필렛을 넣어줘.")

# 입력 규격: AI가 채워야 할 사양 형식. 키 이름과 단위를 고정해 두면 코드가 그대로 받을 수 있다
SPEC_FORMAT = {
    "base": {"length_mm": "num", "width_mm": "num", "thickness_mm": "num"},
    "arm": {"thickness_mm": "num", "height_from_base_bottom_mm": "num", "position": "outside_base_end | on_base"},
    "fillet": {"inner_mm": "num", "outer_corner_mm": "num"},
    "holes": {"diameter_mm": "num", "count": 4, "x1_from_arm_inner_face_mm": "num", "x2_from_base_end_mm": "num",
              "y_from_long_edge_mm": "num"},
}
SYSTEM = f"""기계 부품 요구사항을 아래 형식의 CAD 사양으로 정리합니다.
- 요구사항에 없는 치수·위치·기준은 추측하지 마세요. 확정되지 않은 항목이 하나라도 있으면
  status="need_clarification", questions에 항목별 질문(가능하면 선택지 포함), spec=null로 답하세요.
- 모두 확정되면 status="ready", questions=[], spec을 아래 형식 그대로 채우세요(키 이름 변경·추가 금지, 단위 mm).
- 형식: {json.dumps(SPEC_FORMAT, ensure_ascii=False)}
출력 JSON: {{"status": "ready" | "need_clarification", "questions": [str], "spec": {{...}} | null}}"""


def check_spec(s):
    """AI가 낸 사양을 코드로 다시 검사한다 — 형식, 양수, 서로 맞지 않는 값."""
    errors = []
    try:
        if s["arm"]["position"] != "outside_base_end":
            errors.append("이 템플릿은 세로판이 바닥판 끝면 바깥(outside_base_end)인 경우만 지원")
        nums = [s["base"]["length_mm"], s["base"]["width_mm"], s["base"]["thickness_mm"], s["arm"]["thickness_mm"],
                s["arm"]["height_from_base_bottom_mm"], s["fillet"]["inner_mm"], s["fillet"]["outer_corner_mm"],
                s["holes"]["diameter_mm"]]
        if any(not isinstance(v, (int, float)) or v <= 0 for v in nums):
            errors.append("치수는 모두 양수여야 함")
        if s["holes"]["count"] != 4:
            errors.append("구멍은 4개만 지원")
        r = s["holes"]["diameter_mm"] / 2
        if s["holes"]["x1_from_arm_inner_face_mm"] - r <= s["fillet"]["inner_mm"]:
            errors.append("세로판 쪽 구멍이 안쪽 필렛과 겹침")
    except (KeyError, TypeError) as e:
        errors.append(f"형식 오류: {e!r}")
    return errors


def to_params(s):
    """사양 → 02-3 브래킷의 설계 변수"""
    return {"base_len": s["base"]["length_mm"], "width": s["base"]["width_mm"], "base_t": s["base"]["thickness_mm"],
            "arm_t": s["arm"]["thickness_mm"], "arm_h": s["arm"]["height_from_base_bottom_mm"],
            "r_in": s["fillet"]["inner_mm"], "r_corner": s["fillet"]["outer_corner_mm"], "hole_d": s["holes"]["diameter_mm"],
            "hole_x1": s["holes"]["x1_from_arm_inner_face_mm"],
            "hole_x2": s["base"]["length_mm"] - s["holes"]["x2_from_base_end_mm"], "hole_y": s["holes"]["y_from_long_edge_mm"]}


def get_spec(answers):
    client, model = OpenAI(), os.environ.get("OPENAI_MODEL", "gpt-6-astra")
    msgs = [{"role": "user", "content": REQUEST}]
    usage = [0, 0]
    for turn in range(1, 6):
        t = time.time()
        r = client.responses.create(model=model, instructions=SYSTEM, input=msgs, text={"format": {"type": "json_object"}})
        usage[0] += r.usage.input_tokens
        usage[1] += r.usage.output_tokens
        js = json.loads(r.output_text)
        msgs.append({"role": "assistant", "content": r.output_text})
        print(f"[{turn}턴 {time.time() - t:.1f}초] status={js['status']}")
        if js["status"] == "ready":
            errs = check_spec(js["spec"])
            if not errs:
                return js["spec"], usage
            print("  사양 검사 실패:", errs)
            msgs.append({"role": "user", "content": "사양 검사 실패: " + "; ".join(errs) + ". 고쳐서 다시 답하세요."})
            continue
        for q in js["questions"]:
            print("  질문:", q)
        reply = answers.pop(0) if answers else input("답변> ")
        print("  답변:", reply)
        msgs.append({"role": "user", "content": reply})
    raise SystemExit("사양을 확정하지 못했습니다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", help="질문에 차례로 쓸 답변 목록(JSON 배열 파일)")
    ap.add_argument("--out", default=str(ROOT / "output" / "ch03" / "design_agent"))
    a = ap.parse_args()
    answers = json.loads(Path(a.answers).read_text(encoding="utf-8")) if a.answers else []
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    spec, usage = get_spec(answers)
    params = to_params(spec)
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("설계 변수:", params)

    # 02-3의 파라메트릭 브래킷을 만들고, 사양 값으로 바꾼 뒤 필렛을 다시 연결해 검증한다
    env = {"SET": ";".join(f"{k}={v}" for k, v in params.items()), "REBIND": "1", "OUT_DIR": str(out)}
    rc, log = run_freecad(ROOT / "ch02" / "bracket_parametric.py", env=env)
    res = json.loads(tagged_line(log, "REBOUND"))
    shutil.copy(out / "bracket_param.FCStd", out / "bracket_from_request.FCStd")
    print("검증:", "합격" if res["pass"] else "불합격 " + str(res["failed"]),
          f"| 부피 {res['volume']} (기대 {res['expected_volume']}) | 질량 {res['volume'] * 2.70e-3:.1f} g")
    print(f"AI 토큰 {usage[0]}/{usage[1]}, 비용 약 ${usage[0] * 10e-6 + usage[1] * 50e-6:.3f} → {out / 'bracket_from_request.FCStd'}")


if __name__ == "__main__":
    main()
