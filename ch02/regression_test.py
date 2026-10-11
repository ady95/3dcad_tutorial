"""02-4 회귀 테스트: 설계 변수 조합마다 브래킷을 다시 계산하고 검증한다 (실행 위치 (3)).

각 조합을 freecadcmd로 bracket_parametric.py에 넘겨 (1) 값만 바꾼 결과와
(2) 필렛 모서리를 다시 연결한 결과를 비교한다.
사용 (저장소 루트에서): python ch02/regression_test.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.freecad_runner import run_freecad, tagged_line  # noqa: E402

CASES = [
    ("기본값", ""),
    ("바닥판 두께 8→6", "base_t=6"),
    ("세로판 두께 8→10", "arm_t=10"),
    ("세로판 쪽 구멍 x 25→30", "hole_x1=30"),
    ("안쪽 필렛 5→3", "r_in=3"),
    ("05장 최종 설계 6/8/R8", "base_t=6;arm_t=8;r_in=8"),
    ("바닥판 길이 120→100", "base_len=100"),
]
script = Path(__file__).with_name("bracket_parametric.py")
LABEL = {"no_error_objects": "오류 객체", "valid_single_solid": "형상 유효", "bbox": "외곽 치수",
         "holes": "구멍 위치", "volume": "부피"}
print(f"{'변경':<24}{'값만 변경':<28}{'필렛 다시 연결'}")
for i, (name, change) in enumerate(CASES):
    out_dir = ROOT / "output" / "ch02" / "regression" / f"case{i}"      # 경우마다 따로 저장 — 공유 파일을 덮어쓰지 않게
    rc, log = run_freecad(script, env={"SET": change, "REBIND": "1", "OUT_DIR": str(out_dir)})
    if not change:
        base = json.loads(tagged_line(log, "BASE"))
        print(f"{name:<24}{'합격' if base['pass'] else '불합격':<28}-")
        continue
    a, b = json.loads(tagged_line(log, "CHANGED")), json.loads(tagged_line(log, "REBOUND"))
    fmt = lambda r: "합격" if r["pass"] else "불합격: " + ", ".join(LABEL[k] for k in r["failed"])
    print(f"{name:<24}{fmt(a):<28}{fmt(b)}   (부피 {b['volume']} / 기대 {b['expected_volume']})")
