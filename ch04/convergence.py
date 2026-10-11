"""04-5 메시 수렴성 분석 (실행 위치 (3)).

같은 브래킷을 메시 크기만 바꿔 해석하고, 최대 응력·최대 처짐이 메시에 따라 어떻게 변하는지 표와 그래프로 본다.
사용 (저장소 루트에서): python ch04/convergence.py      (--plot-only: 저장된 결과로 그래프만 다시 그림)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from common.freecad_runner import run_freecad, tagged_line  # noqa: E402

MESHES = [8, 6, 4, 3, 2.2]                                     # 요소 크기 mm (작을수록 촘촘)
DESIGNS = {"초기 설계 8/8/R5": "", "최종 설계 6/8/R8": "base_t=6;arm_t=8;r_in=8"}
COLORS = {"초기 설계 8/8/R5": "#2a78d6", "최종 설계 6/8/R8": "#eb6834"}   # 범주 색 1·2번 (색각 이상 검사 통과)
OUT = ROOT / "output" / "ch04" / "convergence"
OUT.mkdir(parents=True, exist_ok=True)

rows = []
for name, change in ([] if "--plot-only" in sys.argv else DESIGNS.items()):
    for m in MESHES:
        env = {"SET": change, "MESH": str(m), "OUT_DIR": str(OUT / f"{name[:5]}_m{m:g}")}
        rc, log = run_freecad(ROOT / "ch04" / "bracket_fem.py", env=env, timeout=900)
        r = json.loads(tagged_line(log, "RESULT"))
        rows.append({"design": name, "mesh_mm": m, "nodes": r["nodes"], "vm_max": r["vm_max_MPa"],
                     "vm_away": r["vm_away_MPa"], "u_max": r["u_max_mm"], "sf": r["safety_factor"]})
        print(f"{name}  메시 {m:>4} mm  절점 {r['nodes']:>6}  최대응력 {r['vm_max_MPa']:>6.2f}  "
              f"고정부 3mm 밖 {r['vm_away_MPa']:>6.2f}  최대처짐 {r['u_max_mm']:.4f}  안전율 {r['safety_factor']}", flush=True)
if rows:
    json.dump(rows, open(OUT / "convergence.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
else:
    rows = json.load(open(OUT / "convergence.json", encoding="utf-8"))

# 그래프: 응력과 처짐은 단위가 다르므로 축 두 개를 겹치지 않고 그림 두 개로 나란히 그린다
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 10})
fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), facecolor="#fcfcfb")
# 기준선: 안전율 2.0 → 허용 응력 276/2 = 138 MPa, 처짐 0.5 mm
for ax, key, title, unit, limit, limit_label in [(axes[0], "vm_max", "최대 von Mises 응력", "MPa", 138, "허용 138 MPa (안전율 2.0)"),
                                                 (axes[1], "u_max", "최대 처짐", "mm", 0.5, "기준 0.5 mm")]:
    ax.set_facecolor("#fcfcfb")
    for name in DESIGNS:
        pts = [r for r in rows if r["design"] == name]
        x, y = [r["nodes"] / 1000 for r in pts], [r[key] for r in pts]
        ax.plot(x, y, color=COLORS[name], linewidth=2, marker="o", markersize=5, label=name)
        ax.annotate(f"{y[-1]:g}", (x[-1], y[-1]), textcoords="offset points", xytext=(6, -3), color="#52514e", fontsize=9)
    ax.set_title(f"{title} ({unit})", loc="left", color="#0b0b0b", fontsize=11)
    ax.set_xlabel("절점 수 (천 개) → 촘촘한 메시", color="#52514e")
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.8)
    ax.tick_params(colors="#898781")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.set_ylim(0, max(max(r[key] for r in rows), limit) * 1.15)       # 기준선이 그래프 안에 들어오게
    ax.axhline(limit, color="#898781", linewidth=1, linestyle="--")
    ax.annotate(limit_label, (ax.get_xlim()[1], limit), xytext=(-4, 4), textcoords="offset points",
                ha="right", color="#52514e", fontsize=9)
axes[0].legend(frameon=False, loc="lower right", fontsize=9)
fig.tight_layout()
fig.savefig(OUT / "convergence.png", dpi=150, facecolor=fig.get_facecolor())
print("그래프 저장:", OUT / "convergence.png")
