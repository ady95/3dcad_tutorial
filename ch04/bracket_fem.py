# 04-4 브래킷 구조해석과 자동 판정 (실행 위치 (2): freecadcmd)
# 02-3의 파라메트릭 브래킷 FCStd를 열어(필요하면 설계 변수를 바꾸고) 해석하고, 안전율·처짐 기준으로 판정한다.
# 환경변수: SRC(기본 output/ch02/bracket_param.FCStd), SET="base_t=6;arm_t=8", MESH(기본 4), FIX=holes|bottom,
#           LOAD_N(기본 200), VTK=1 이면 응력 결과를 .vtk로도 저장 (04-5 시각화용)
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
from common.bracket_fc import get_params, rebind_fillets, set_params, validate  # noqa: E402
from common.fem_fc import build_analysis, face_names, solve, summarize  # noqa: E402

YIELD_MPA, SF_MIN, U_MAX_MM, DENSITY = 276.0, 2.0, 0.5, 2.70e-3    # Al 6061-T6, 판정 기준, g/mm³
MESH = float(os.environ.get("MESH", "4"))
FIX = os.environ.get("FIX", "holes")
LOAD_N = float(os.environ.get("LOAD_N", "200"))
OUT = os.path.abspath(os.environ.get("OUT_DIR", "output/ch04/bracket"))
os.makedirs(OUT, exist_ok=True)

def fail(stage, detail):
    """실패 원인을 태그 줄로 남기고 끝낸다 — 바깥 Python(05장 최적화)이 읽는다"""
    print("FAIL " + json.dumps({"stage": stage, "detail": detail}), flush=True)
    raise SystemExit(1)


doc = App.openDocument(os.path.abspath(os.environ.get("SRC", "output/ch02/bracket_param.FCStd")))
if os.environ.get("SET"):
    set_params(doc, {k: float(v) for k, v in (kv.split("=") for kv in os.environ["SET"].split(";"))})
    rebind_fillets(doc)
checks, geo = validate(doc)                      # 해석 전에 형상부터 검증 (02-4)
if not all(checks.values()):
    fail("geometry", [k for k, ok in checks.items() if not ok])
p = get_params(doc)

# 해석용 형상: Body의 최종 형상을 Part::Feature로 복사해 면 번호를 고정한다
part = doc.addObject("Part::Feature", "AnalysisShape")
part.Shape = doc.getObject("Body").Shape.copy()
doc.recompute()
s = part.Shape
holes = [(x, y) for x in (p["hole_x1"], p["hole_x2"]) for y in (p["hole_y"], p["width"] - p["hole_y"])]


def is_hole(f):
    c = f.Surface
    return (isinstance(c, Part.Cylinder) and abs(c.Radius - p["hole_d"] / 2) < 1e-6 and abs(abs(c.Axis.z) - 1) < 1e-9
            and any(abs(c.Center.x - x) < 1e-6 and abs(c.Center.y - y) < 1e-6 for x, y in holes))


if FIX == "holes":       # 볼트 구멍 4개의 내면을 고정 — 벽과의 접촉은 무시(처짐을 크게 보는 보수적 가정)
    fixed = face_names(s, is_hole)
    assert len(fixed) == 4, f"고정면이 4개가 아님: {fixed}"      # 고정면 개수 검증 (04-4 사례)
else:                    # 바닥면 전체를 고정 — 벽에 완전히 붙어 있다는 가정
    fixed = face_names(s, lambda f: abs(f.CenterOfMass.z) < 1e-6)
loaded = face_names(s, lambda f: abs(f.CenterOfMass.z - p["arm_h"]) < 1e-6)    # 세로판 윗면
assert len(loaded) == 1, f"하중면이 1개가 아님: {loaded}"

an, solver, mesh = build_analysis(doc, part, fixed, loaded, LOAD_N, App.Vector(-1, 0, 0), MESH)
res = solve(doc, an, solver, mesh, OUT)
if res is None:
    fail("solve", "결과 없음 (메시 오류 가능)")
r = summarize(res, mesh, [s.getElement(n) for n in fixed], exclude_mm=3.0)

sf = YIELD_MPA / r["vm_max_MPa"]
out = {"params": p, "fix": FIX, "load_N": LOAD_N, "mesh_mm": MESH, "mass_g": round(s.Volume * DENSITY, 1), **r,
       "safety_factor": round(sf, 2),
       "pass_strength": sf >= SF_MIN, "pass_deflection": r["u_max_mm"] <= U_MAX_MM}
out["pass"] = out["pass_strength"] and out["pass_deflection"]
if os.environ.get("VTK") == "1":
    import feminout.importVTKResults as vtkio
    vtkio.export([res], os.path.join(OUT, "result.vtk"))
    out["vtk"] = os.path.join(OUT, "result.vtk")
json.dump(out, open(os.path.join(OUT, "result.json"), "w"), indent=1)
print("RESULT " + json.dumps(out), flush=True)
