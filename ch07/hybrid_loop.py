"""07-2 화면 조작 + 코드 채점 하이브리드 루프 (실행 위치 (3)). 이 장만 Codex 데스크톱 앱이 필요하다.

코드가 하는 일: 과제 파일 준비 → FreeCAD 창 띄우기 → Codex 앱에 붙여 넣을 프롬프트 출력 →
              (사람이 Codex 앱 새 스레드에 붙여 넣고, 끝나면 Enter) → 저장 파일 채점 → 불합격이면 채점 결과를 담아 재시도 프롬프트.
Codex의 화면 조작은 앱 스레드에서만 동작하므로(codex exec에서는 꺼져 있음) 붙여 넣기는 사람이 한다.

사용 (저장소 루트에서):
  python ch07/hybrid_loop.py --task T2            # 볼트 구멍 4면 Fixed 구속 (07-2)
  python ch07/hybrid_loop.py --task T1            # 플레이트 전체를 화면 조작으로 (07-3)
  python ch07/hybrid_loop.py --task T2 --grade-only 결과.FCStd    # 채점만
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.freecad_runner import find_freecadcmd, run_freecad, tagged_line  # noqa: E402

OUT = ROOT / "output" / "ch07"


def grade(task, path):
    rc, log = run_freecad(ROOT / "ch07" / "grade.py", env={"MODE": task, "FILE": str(path)})
    return json.loads(tagged_line(log, "GRADE") or '{"pass": false, "error": "채점 실패"}')


def feedback(task, g):
    """채점 결과를 사람이 읽는 문장으로 — 재시도 프롬프트에 붙인다"""
    if not g.get("exists", True):
        return "지정한 경로에 파일이 저장되지 않았습니다. 저장 경로를 확인하세요."
    if task == "T2":
        wrong = [f["name"] for f in g.get("faces", []) if not f["hole"]]
        return (f"Fixed 구속 {g.get('fixed_constraints')}개, 지정된 면 {len(g.get('faces', []))}개"
                + (f", 구멍이 아닌 면 {wrong}" if wrong else "") + (", Analysis에 포함되지 않음" if not g.get("in_analysis") else "")
                + ". 구멍 4개의 원통 내면만 정확히 4개 지정해야 합니다.")
    return (f"레이블 Plate {'있음' if g.get('label_ok') else '없음'}, 부피 {g.get('volume')} (기대 {g.get('expected')}), "
            f"구멍 {len(g.get('holes', []))}개, 필렛 면 {g.get('fillets')}개. 확인하지 못한 단계는 다시 하세요.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["T1", "T2"], default="T2")
    ap.add_argument("--tries", type=int, default=2)
    ap.add_argument("--grade-only")
    a = ap.parse_args()
    if a.grade_only:
        print(json.dumps(grade(a.task, Path(a.grade_only).resolve()), ensure_ascii=False, indent=1))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    if a.task == "T2" and not (OUT / "T2_input.FCStd").exists():          # 해석 컨테이너까지는 코드가 만든다
        run_freecad(ROOT / "ch02" / "bracket_parametric.py", env={"OUT_DIR": str(OUT)})
        rc, log = run_freecad(ROOT / "ch07" / "prepare_task.py")
        print(tagged_line(log, "PREP"))
    template = (ROOT / "ch07" / "prompts" / f"{'T2_fixed' if a.task == 'T2' else 'T1_plate'}.txt").read_text(encoding="utf-8")
    gui = find_freecadcmd().with_name("FreeCAD.exe" if sys.platform == "win32" else "FreeCAD")
    note = ""
    for k in range(1, a.tries + 1):
        name = f"{a.task}_try{k}"
        save = OUT / f"result_{name}.FCStd"
        if a.task == "T2":                                   # 회차마다 입력 사본 → 창 제목으로 대상 창을 특정
            shutil.copy(OUT / "T2_input.FCStd", OUT / f"{name}.FCStd")
            proc = subprocess.Popen([str(gui), str(OUT / f"{name}.FCStd")])
            title = f"{name} - FreeCAD 1.1.4"
        else:
            proc = subprocess.Popen([str(gui)])
            title = "FreeCAD 1.1.4"
        prompt = template.format(window_title=title, save_path=save) + note
        (OUT / f"prompt_{name}.txt").write_text(prompt, encoding="utf-8")
        print(f"\n===== {k}회차: Codex 앱 새 스레드에 붙여 넣을 프롬프트 (output/ch07/prompt_{name}.txt)\n{prompt}\n")
        input("Codex 작업이 끝나면 Enter (실행 중에는 마우스·키보드를 건드리지 말고 화면 잠금을 끄세요) > ")
        g = grade(a.task, save)
        print("채점:", json.dumps(g, ensure_ascii=False))
        proc.terminate()
        if g.get("pass"):
            print(f"합격 ({k}회차)")
            return
        note = f"\n\n참고 — 이전 시도의 채점 결과: {feedback(a.task, g)} 새로 연 문서에서 처음부터 다시 하라."
    print("불합격 — 사람이 확인하세요")


if __name__ == "__main__":
    main()
