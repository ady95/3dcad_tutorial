# 02-2 PartDesign으로 L자 브래킷 만들기 (실행 위치 (2): freecadcmd)
# Body → L자 단면 스케치(XZ 평면) → Pad(폭 방향) → 구멍 스케치 → Pocket → Fillet
# 사용: freecadcmd ch02/bracket_partdesign.py      (결과: output/ch02/bracket_pd.FCStd)
import os

import FreeCAD as App
import Part
import Sketcher

# 설계 변수 [mm] — 01-3 플레이트(120×80)에 세로판을 붙인다
LB, W, TB = 120.0, 80.0, 8.0       # 바닥판 길이(X)·폭(Y)·두께(Z)
H, TA = 80.0, 8.0                  # 세로판 높이(바닥면 기준)·두께
R_IN, R_CORNER = 5.0, 5.0          # 안쪽 꺾임부 필렛, 바닥판 바깥 모서리 필렛
HOLE_D = 6.0
HOLES = [(25.0, 10.0), (25.0, 70.0), (110.0, 10.0), (110.0, 70.0)]

OUT = os.path.join(os.environ.get("OUT_DIR", "output/ch02"), "bracket_pd.FCStd")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

doc = App.newDocument("BracketPD")
body = doc.addObject("PartDesign::Body", "Body")

# 1) L자 단면: XZ 평면 스케치. 세로판은 바닥판 끝면(x=0) 바깥쪽 x∈[-TA, 0]
prof = body.newObject("Sketcher::SketchObject", "Profile")
prof.AttachmentSupport = [(doc.getObject("XZ_Plane"), "")]
prof.MapMode = "FlatFace"
pts = [(-TA, 0), (LB, 0), (LB, TB), (0, TB), (0, H), (-TA, H)]
V = [App.Vector(x, z, 0) for x, z in pts]          # 스케치 좌표 (u=X, v=Z)
for i in range(len(V)):
    prof.addGeometry(Part.LineSegment(V[i], V[(i + 1) % len(V)]), False)
for i in range(len(V)):                            # 선분 끝점끼리 연결
    prof.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % len(V), 1))
doc.recompute()

# 2) Pad: 폭 W만큼 돌출. XZ 평면의 법선 방향이 -Y이므로 결과가 y∈[0,W]가 되게 Reversed를 확인
pad = body.newObject("PartDesign::Pad", "Pad")
pad.Profile = prof
pad.Length = W
doc.recompute()
if pad.Shape.BoundBox.YMin < -1e-6:
    pad.Reversed = True
    doc.recompute()

# 3) 구멍: 바닥판 아랫면(XY 평면)에 원 4개 → Pocket 관통
holes = body.newObject("Sketcher::SketchObject", "HoleSketch")
holes.AttachmentSupport = [(doc.getObject("XY_Plane"), "")]
holes.MapMode = "FlatFace"
for x, y in HOLES:
    holes.addGeometry(Part.Circle(App.Vector(x, y, 0), App.Vector(0, 0, 1), HOLE_D / 2), False)
doc.recompute()
pocket = body.newObject("PartDesign::Pocket", "Holes")
pocket.Profile = holes
pocket.Type = "ThroughAll"
pocket.SideType = "Symmetric"       # 스케치 평면(z=0) 양쪽으로 관통 (1.1에서 Midplane 대체)
doc.recompute()


# 4) 필렛: 모서리를 이름이 아니라 기하 조건으로 찾는다 (01-3에서 본 습관)
def edges_where(shape, pred):
    return [f"Edge{i}" for i, e in enumerate(shape.Edges, 1) if pred(e)]


def is_line_along(e, axis):
    if not isinstance(e.Curve, Part.Line):
        return False
    d = e.Vertexes[-1].Point - e.Vertexes[0].Point
    return abs(abs(getattr(d.normalize(), axis)) - 1) < 1e-9


s = pocket.Shape
inner = edges_where(s, lambda e: is_line_along(e, "y") and abs(e.CenterOfMass.x) < 1e-6 and abs(e.CenterOfMass.z - TB) < 1e-6)
f_in = body.newObject("PartDesign::Fillet", "InnerFillet")
f_in.Base = (pocket, inner)
f_in.Radius = R_IN
doc.recompute()
f_cn = body.newObject("PartDesign::Fillet", "CornerFillet")
s = f_in.Shape                      # 바깥 모서리는 안쪽 필렛이 적용된 형상에서 찾는다
corner = edges_where(s, lambda e: is_line_along(e, "z") and abs(e.CenterOfMass.x - LB) < 1e-6)
f_cn.Base = (f_in, corner)
f_cn.Radius = R_CORNER
doc.recompute()

tip = body.Shape
bb = tip.BoundBox
print("BODY", {"valid": tip.isValid(), "solids": len(tip.Solids), "volume": round(tip.Volume, 1),
               "bbox": [round(v, 2) for v in (bb.XMin, bb.YMin, bb.ZMin, bb.XMax, bb.YMax, bb.ZMax)],
               "inner_edges": inner, "corner_edges": corner,
               "features": [o.Name for o in body.Group if o.TypeId.startswith("PartDesign::") and "Feature" not in o.TypeId]},
      flush=True)
doc.saveAs(OUT)
