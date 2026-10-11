# 04-3 외팔보 해석 자동화와 이론해 비교 (실행 위치 (2): freecadcmd)
# 200×20×10mm 알루미늄 보의 한쪽 끝을 고정하고 반대쪽 끝에 200N을 아래로 가한다.
# 사용: freecadcmd ch04/cantilever_fem.py     (환경변수 MESH=요소 크기 mm, 기본 5)
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import FreeCAD as App  # noqa: E402
from common.fem_fc import build_analysis, face_names, solve, summarize  # noqa: E402

L, B, H, F = 200.0, 20.0, 10.0, 200.0           # 길이(X)·폭(Y)·높이(Z) mm, 하중 N
E, NU = 68900.0, 0.33                           # MPa, -
MESH = float(os.environ.get("MESH", "5"))
OUT = os.path.abspath(os.path.join(os.environ.get("OUT_DIR", "output/ch04"), f"cantilever_m{MESH:g}"))
os.makedirs(OUT, exist_ok=True)

doc = App.newDocument("Cantilever")
beam = doc.addObject("Part::Box", "Beam")
beam.Length, beam.Width, beam.Height = L, B, H
doc.recompute()
fixed = face_names(beam.Shape, lambda f: abs(f.CenterOfMass.x) < 1e-6)          # x=0 끝면
loaded = face_names(beam.Shape, lambda f: abs(f.CenterOfMass.x - L) < 1e-6)     # x=L 끝면
an, solver, mesh = build_analysis(doc, beam, fixed, loaded, F, App.Vector(0, 0, -1), MESH)
res = solve(doc, an, solver, mesh, OUT)
r = summarize(res, mesh)

# 이론해 비교: 처짐은 끝단, 응력은 고정단 특이점을 피해 중간 단면(x=L/2) 윗면에서
nodes, ids = res.Mesh.FemMesh.Nodes, list(res.NodeNumbers)
tip = [res.DisplacementVectors[k].z for k, n in enumerate(ids) if abs(nodes[n].x - L) < 1e-6]
mid = [res.NodeStressXX[k] for k, n in enumerate(ids) if abs(nodes[n].x - L / 2) < MESH * 0.6 and abs(nodes[n].z - H) < 1e-6]
I = B * H ** 3 / 12
G = E / (2 * (1 + NU))
theory = {"tip_bending_mm": F * L ** 3 / (3 * E * I),                      # 굽힘 처짐 FL³/3EI
          "tip_shear_mm": F * L / (5 / 6 * G * B * H),                     # 전단 처짐 (티모셴코 보정)
          "sigma_mid_MPa": F * (L / 2) * (H / 2) / I,                      # 굽힘 응력 My/I, x=L/2
          "sigma_root_MPa": F * L * (H / 2) / I}                           # 고정단 굽힘 응력
fem_tip = -sum(tip) / len(tip)
out = {"mesh_mm": MESH, **r, "tip_mm": round(fem_tip, 4), "sigma_mid_MPa": round(sum(mid) / len(mid), 2),
       "theory": {k: round(v, 4) for k, v in theory.items()},
       "tip_err_pct": round((fem_tip / (theory["tip_bending_mm"] + theory["tip_shear_mm"]) - 1) * 100, 2)}
json.dump(out, open(os.path.join(OUT, "result.json"), "w"), indent=1)
print("RESULT " + json.dumps(out), flush=True)
