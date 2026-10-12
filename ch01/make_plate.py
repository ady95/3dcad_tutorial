"""01-3 자연어로 첫 번째 3D 부품 만들기.

요구사항 문장 → GPT-6 Astra가 FreeCAD Python 코드 생성 → freecadcmd로 실행(FCStd·STEP 저장)
→ 저장된 파일을 다시 열어 측정 → 요구사항과 비교해 합격/불합격.

사용 (저장소 루트에서):
  python ch01/make_plate.py
  python ch01/make_plate.py --length 100 --width 60 --thickness 5 --hole 5 --edge 8 --fillet 4
"""
import argparse
import json
import math
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

SYSTEM = """FreeCAD 1.1 Python 코드를 작성하는 CAD 엔지니어입니다.
- freecadcmd(GUI 없음)에서 실행됩니다. FreeCADGui, Part.show는 쓰지 마세요.
- 맨 위에 설계 변수를 상수로 두고, 형상은 Part 모듈로 만드세요.
- 결과는 새 문서에 Part::Feature 이름 "Plate"로 추가하고, 변수 OUT_FCSTD 경로에 doc.saveAs, OUT_STEP 경로에 exportStep 하세요.
  두 변수는 실행할 때 미리 정의되어 있으니 다시 정의하지 마세요.
- 좌표: 판의 한 모서리를 원점, 길이=X, 폭=Y, 두께=Z.
- 코드만 출력하세요 (```python 블록 하나)."""


def build_request(a):
    return (f"가로 {a.length:g}mm, 세로 {a.width:g}mm, 두께 {a.thickness:g}mm의 알루미늄 장착 플레이트를 만들어줘. "
            f"네 모서리에서 {a.edge:g}mm 떨어진 위치에 직경 {a.hole:g}mm의 체결 구멍을 만들고, "
            f"모서리에는 R{a.fillet:g} 필렛을 적용해줘.")


def expected(a):
    """요구사항에서 계산한 기대값 — 검증 기준."""
    r, R = a.hole / 2, a.fillet
    volume = (a.length * a.width - 4 * math.pi * r ** 2 - 4 * (R ** 2 - math.pi * R ** 2 / 4)) * a.thickness
    holes = sorted((x, y) for x in (a.edge, a.length - a.edge) for y in (a.edge, a.width - a.edge))
    return {"bbox_mm": [a.length, a.width, a.thickness], "volume_mm3": round(volume, 2), "holes": holes,
            "hole_r": r, "fillet_r": R}


def judge(m, e):
    cyl = m["cylinder_faces"]
    holes = [tuple(c) for c in cyl.get(str(round(e["hole_r"], 3)), [])]
    checks = {
        "형상 유효(isValid)": m["is_valid"],
        "솔리드 1개": m["solids"] == 1,
        "외곽 치수": m["bbox_mm"] == e["bbox_mm"],
        "구멍 4개 위치": sorted(holes) == e["holes"],
        "필렛 4개": len(cyl.get(str(round(e["fillet_r"], 3)), [])) == 4,
        "부피(±1mm³)": abs(m["volume_mm3"] - e["volume_mm3"]) <= 1.0,
    }
    return checks


def main():
    ap = argparse.ArgumentParser()
    for k, v in [("length", 120), ("width", 80), ("thickness", 6), ("hole", 6), ("edge", 10), ("fillet", 5)]:
        ap.add_argument(f"--{k}", type=float, default=float(v))
    ap.add_argument("--out", default=str(ROOT / "output" / "ch01"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = f"plate_{a.length:g}x{a.width:g}x{a.thickness:g}"
    fcstd, step = out / f"{tag}.FCStd", out / f"{tag}.step"

    # 1) 자연어 요구사항 → FreeCAD 코드
    request = build_request(a)
    print("요구사항:", request)
    model = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
    t = time.time()
    r = OpenAI().responses.create(model=model, instructions=SYSTEM, input=request)
    m = re.search(r"```(?:python)?\n(.*?)```", r.output_text, re.S)
    code = m.group(1) if m else r.output_text
    (out / f"{tag}_generated.py").write_text(code, encoding="utf-8")
    print(f"코드 생성: {model}, {time.time() - t:.1f}초, 토큰 입력 {r.usage.input_tokens}·출력 {r.usage.output_tokens}, "
          f"{code.count(chr(10)) + 1}줄 → {tag}_generated.py")

    # 2) freecadcmd로 실행 — 저장 경로 변수를 앞에 붙인다
    runner = out / f"{tag}_run.py"
    runner.write_text(f"OUT_FCSTD = r'{fcstd}'\nOUT_STEP = r'{step}'\n" + code, encoding="utf-8")
    rc, log = run_freecad(runner)
    if not fcstd.exists():
        print("실행 실패 — FCStd가 만들어지지 않았습니다.\n", log[-1500:])
        sys.exit(1)
    print(f"실행: {fcstd.name}, {step.name} 저장")

    # 3) 저장된 파일을 다시 열어 측정하고 요구사항과 비교
    rc, log = run_freecad(Path(__file__).with_name("validate_plate.py"), env={"PLATE_FCSTD": str(fcstd)})
    measured = json.loads(tagged_line(log, "PLATE"))
    checks = judge(measured, expected(a))
    print("측정:", json.dumps(measured, ensure_ascii=False))
    for k, ok in checks.items():
        print(f"  {'OK ' if ok else '불가'}  {k}")
    print("판정:", "합격" if all(checks.values()) else "불합격")


if __name__ == "__main__":
    main()
