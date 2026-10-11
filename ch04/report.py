"""04-5 해석 결과 시각화와 보고서 생성 (실행 위치 (3)).

bracket_fem.py가 남긴 result.json·result.vtk와 convergence.py의 수렴 결과로
응력 분포 그림(PyVista)과 해석 보고서(Markdown)를 만든다. --summarize를 주면 GPT-6 Astra가 요약 문단을 쓰고,
요약에 나온 숫자가 보고서에 실제로 있는지 코드가 대조한다.

사용 (저장소 루트에서):
  freecadcmd ch04/bracket_fem.py   (환경변수 SET="base_t=6;arm_t=8;r_in=8" MESH=3 VTK=1 OUT_DIR=output/ch04/report_final)
  python ch04/report.py --run output/ch04/report_final [--summarize]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyvista as pv  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

# 응력 크기는 한 가지 색의 밝기로 표현한다 (연한 파랑 → 진한 파랑). 무지개색은 쓰지 않는다
BLUE_RAMP = ListedColormap(["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])


def render_contour(vtk_path, png_path):
    grid = pv.read(vtk_path)
    # FreeCAD의 VTK 내보내기는 결과를 SI 단위로 저장한다: 응력 Pa, 변위 m (좌표는 mm 그대로) → MPa, mm로 바꾼다
    grid["von Mises (MPa)"] = grid["von Mises Stress"] / 1e6
    grid["Displacement (mm)"] = grid["Displacement Magnitude"] * 1e3
    vm = grid["von Mises (MPa)"]
    k = int(vm.argmax())
    pl = pv.Plotter(off_screen=True, window_size=(1400, 1000))
    pl.set_background("#fcfcfb")
    # 조명을 끈다: 그림자가 색을 어둡게 만들면 낮은 응력이 높은 응력처럼 보인다. 형상은 모서리 선으로 보여 준다
    pl.add_mesh(grid.extract_feature_edges(feature_angle=30), color="#52514e", line_width=1.5)
    pl.add_mesh(grid, scalars="von Mises (MPa)", cmap=BLUE_RAMP, show_edges=False, lighting=False,
                scalar_bar_args={"title": "von Mises (MPa)", "color": "#0b0b0b", "fmt": "%.0f", "vertical": True,
                                 "position_x": 0.86, "position_y": 0.15, "height": 0.7, "width": 0.05})
    pl.add_point_labels([grid.points[k]], [f"최대 {vm[k]:.1f} MPa"], font_size=22, text_color="#0b0b0b",
                        point_color="#eb6834", point_size=18, shape_color="#fcfcfb", shape_opacity=0.85,
                        font_family="arial", always_visible=True)
    pl.camera_position = [(230, -130, 170), (45, 40, 20), (0, 0, 1)]    # 바닥판 윗면과 세로판 안쪽 면이 보이는 쪽
    pl.screenshot(png_path)
    return {"vm_max": float(vm[k]), "at": [round(float(c), 1) for c in grid.points[k]],
            "u_max": float(grid["Displacement (mm)"].max())}


def write_report(run, r, conv, contour):
    p = r["params"]
    lines = [
        "# 브래킷 구조해석 보고서", "",
        "> 이 결과는 학습용 공학 검증이며 안전 인증을 대체하지 않습니다. 실무 적용에는 전문가 검토, 설계 규격·제조공차 검토, "
        "필요 시 실물 시험이 필요합니다.", "",
        "## 1. 해석 조건", "",
        f"- 형상: 바닥판 {p['base_len']}×{p['width']}×{p['base_t']} mm, 세로판 두께 {p['arm_t']} mm·높이 {p['arm_h']} mm, "
        f"안쪽 필렛 R{p['r_in']}, 구멍 Ø{p['hole_d']} 4개",
        "- 재료: 알루미늄 6061-T6 (E 68,900 MPa, ν 0.33, 항복강도 276 MPa, 밀도 2.70 g/cm³)",
        f"- 하중: 세로판 윗면 {r['load_N']} N, 바닥판 반대쪽(−X)",
        f"- 구속: {'볼트 구멍 4개 내면 고정 (벽 접촉 무시 — 처짐을 크게 보는 가정)' if r['fix'] == 'holes' else '바닥면 전체 고정'}",
        f"- 해석: FreeCAD 1.1.4 FEM, Gmsh 2차 사면체(요소 크기 {r['mesh_mm']} mm, 절점 {r['nodes']}개), CalculiX 선형 정적",
        "", "## 2. 결과와 판정", "",
        "| 항목 | 결과 | 기준 | 판정 |", "|---|---|---|---|",
        f"| 최대 von Mises 응력 | {r['vm_max_MPa']} MPa (위치 {r['vm_max_at']}) | 138 MPa 이하 | - |",
        f"| 안전율 (276 / 최대 응력) | {r['safety_factor']} | 2.0 이상 | {'합격' if r['pass_strength'] else '불합격'} |",
        f"| 최대 처짐 | {r['u_max_mm']} mm | 0.5 mm 이하 | {'합격' if r['pass_deflection'] else '불합격'} |",
        f"| 질량 | {r['mass_g']} g | - | - |",
        "", f"종합 판정: **{'합격' if r['pass'] else '불합격'}**", "",
        "![von Mises 응력 분포](contour.png)", "",
        f"최대 응력은 볼트 구멍 가장자리(고정 경계)에 나타납니다. 고정 경계에서 3 mm 이상 떨어진 곳의 최대 응력은 {r.get('vm_away_MPa')} MPa입니다.",
        "", "## 3. 메시 수렴성", "",
        "| 요소 크기 (mm) | 절점 수 | 최대 응력 (MPa) | 최대 처짐 (mm) | 안전율 |", "|---|---|---|---|---|",
    ]
    lines += [f"| {c['mesh_mm']} | {c['nodes']} | {c['vm_max']} | {c['u_max']} | {c['sf']} |" for c in conv]
    vms = [c["vm_max"] for c in conv]
    us = [c["u_max"] for c in conv]
    lines += ["", f"- 최대 처짐은 {min(us)}~{max(us)} mm로 수렴했습니다.",
              f"- 최대 응력은 {min(vms)}~{max(vms)} MPa 사이에서 오르내립니다. 고정 경계의 응력은 메시에 민감하므로, "
              f"가장 불리한 값({max(vms)} MPa, 안전율 {round(276 / max(vms), 2)})으로도 기준을 만족하는지 확인했습니다.",
              "", "![메시 수렴](convergence.png)", "",
              "## 4. 가정과 한계", "",
              "- 선형 정적 해석: 재료는 탄성 범위, 변형은 작다고 가정합니다.",
              "- 볼트 구멍 내면 완전 고정: 실제 볼트 체결·접촉·예압을 모델링하지 않았습니다.",
              "- 정적 하중 200 N 하나만 고려했습니다. 반복 하중(피로), 충격, 온도는 다루지 않습니다.",
              "- 용접·가공에 의한 재료 물성 변화와 제조 공차는 반영하지 않았습니다."]
    (run / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize(report_md):
    """Astra가 요약 문단을 쓰고, 코드가 요약 속 숫자를 보고서와 대조한다."""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from openai import OpenAI
    instr = ("구조해석 보고서를 읽고 설계 검토 회의용 요약 한 문단(4~5문장)을 쓰세요. 보고서에 있는 숫자만 그대로 인용하고, "
             "새 숫자를 계산하거나 만들지 마세요. 가정과 한계 중 가장 중요한 것 하나를 포함하세요.")
    r = OpenAI().responses.create(model=os.environ.get("OPENAI_MODEL", "gpt-6-astra"), instructions=instr, input=report_md)
    text = r.output_text.strip()
    nums = set(re.findall(r"\d+(?:\.\d+)?", text))
    report_nums = set(re.findall(r"\d+(?:\.\d+)?", report_md))     # 보고서에 나온 숫자 목록과 정확히 대조
    return text, sorted(nums - report_nums, key=float), r.usage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(ROOT / "output" / "ch04" / "report_final"))
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args()
    run = Path(a.run)
    r = json.loads((run / "result.json").read_text(encoding="utf-8"))
    conv_all = json.loads((ROOT / "output" / "ch04" / "convergence" / "convergence.json").read_text(encoding="utf-8"))
    design = "최종 설계 6/8/R8" if r["params"]["base_t"] == 6 else "초기 설계 8/8/R5"
    conv = [c for c in conv_all if c["design"] == design]
    contour = render_contour(str(run / "result.vtk"), str(run / "contour.png"))
    (run / "convergence.png").write_bytes((ROOT / "output" / "ch04" / "convergence" / "convergence.png").read_bytes())
    write_report(run, r, conv, contour)
    print("보고서:", run / "report.md", f"| 그림 최대 응력 {contour['vm_max']:.2f} MPa {contour['at']}, "
          f"최대 변위 {contour['u_max']:.4f} mm (result.json: {r['vm_max_MPa']} MPa, {r['u_max_mm']} mm)")
    if a.summarize:
        text, unknown, usage = summarize((run / "report.md").read_text(encoding="utf-8"))
        print("AI 요약:", text)
        print("보고서에 없는 숫자:", unknown or "없음", f"| 토큰 {usage.input_tokens}/{usage.output_tokens}")


if __name__ == "__main__":
    main()
