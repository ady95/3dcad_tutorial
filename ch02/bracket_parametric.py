# 02-3 스프레드시트로 설계 변수를 관리하는 L자 브래킷 (실행 위치 (2): freecadcmd)
# 설계 변수는 Spreadsheet 한 곳에만 두고, 스케치 구속·Pad 길이·필렛 반경은 수식(Expression)으로 연결한다.
# 사용: freecadcmd ch02/bracket_parametric.py
#       환경변수 SET="base_t=6;arm_t=10"을 주면 값을 바꿔 다시 계산하고 검증한다.
#       REBIND=1을 함께 주면 필렛 모서리를 다시 찾아 연결한 결과도 출력한다 (02-4).
import json
import math
import os

import FreeCAD as App
import Part
import Sketcher

PARAMS = {  # 별칭: (값, 단위, 설명)
    "base_len": (120, "mm", "바닥판 길이"), "width": (80, "mm", "폭"), "base_t": (8, "mm", "바닥판 두께"),
    "arm_h": (80, "mm", "세로판 높이(바닥면 기준)"), "arm_t": (8, "mm", "세로판 두께"),
    "r_in": (5, "mm", "안쪽 꺾임부 필렛"), "r_corner": (5, "mm", "바깥 모서리 필렛"),
    "hole_d": (6, "mm", "구멍 지름"), "hole_x1": (25, "mm", "세로판 쪽 구멍 X"),
    "hole_x2": (110, "mm", "끝단 쪽 구멍 X"), "hole_y": (10, "mm", "구멍과 옆면 거리"),
}
OUT = os.path.join(os.environ.get("OUT_DIR", "output/ch02"), "bracket_param.FCStd")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

doc = App.newDocument("BracketParam")
sheet = doc.addObject("Spreadsheet::Sheet", "Params")
for row, (alias, (val, unit, desc)) in enumerate(PARAMS.items(), 1):
    sheet.set(f"A{row}", alias)
    sheet.set(f"B{row}", f"={val} {unit}")
    sheet.set(f"C{row}", desc)
    sheet.setAlias(f"B{row}", alias)
doc.recompute()
P = lambda a: f"Params.{a}"   # 수식에서 쓰는 이름

body = doc.addObject("PartDesign::Body", "Body")

# 1) L자 단면 스케치 — 6개 선분, 모든 치수를 구속으로
prof = body.newObject("Sketcher::SketchObject", "Profile")
prof.AttachmentSupport = [(doc.getObject("XZ_Plane"), "")]
prof.MapMode = "FlatFace"
pts = [(-8, 0), (120, 0), (120, 8), (0, 8), (0, 80), (-8, 80)]   # 초기값 — 구속이 최종 위치를 정한다
V = [App.Vector(x, z, 0) for x, z in pts]
for i in range(6):
    prof.addGeometry(Part.LineSegment(V[i], V[(i + 1) % 6]), False)
for i in range(6):                                    # 선분 끝점끼리 연결 (닫힌 L자)
    prof.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 6, 1))
for i in (0, 2, 4):                                   # 바닥 아랫면, 바닥 윗면, 세로판 윗면: 수평
    prof.addConstraint(Sketcher.Constraint("Horizontal", i))
for i in (1, 3, 5):                                   # 바닥 끝면, 세로판 안쪽면, 세로판 바깥면: 수직
    prof.addConstraint(Sketcher.Constraint("Vertical", i))
# 선분 0 바닥 아랫면 / 1 끝면 / 2 바닥 윗면 / 3 세로판 안쪽 / 4 세로판 윗면 / 5 세로판 바깥. (-1, 1)은 스케치 원점
c_tb = prof.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 3, 1, 8))       # 바닥판 두께: 원점~(0,TB)
prof.addConstraint(Sketcher.Constraint("PointOnObject", 3, 1, -2))                # (0,TB)는 세로축 위
prof.addConstraint(Sketcher.Constraint("PointOnObject", 0, 1, -1))                # 바닥 아랫면 시작점은 가로축 위
c_lb = prof.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 1, 1, 120))     # 원점~바닥판 끝(x=LB)
c_h = prof.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, 4, 2, 80))        # 바닥면~세로판 윗면
c_ta = prof.addConstraint(Sketcher.Constraint("DistanceX", 4, 2, 4, 1, 8))        # 세로판 두께(윗면 선분 길이)
for name, idx in [("base_t", c_tb), ("base_len", c_lb), ("arm_h", c_h), ("arm_t", c_ta)]:
    prof.setExpression(f"Constraints[{idx}]", P(name))
doc.recompute()

pad = body.newObject("PartDesign::Pad", "Pad")
pad.Profile = prof
pad.setExpression("Length", P("width"))
doc.recompute()
if pad.Shape.BoundBox.YMin < -1e-6:
    pad.Reversed = True
    doc.recompute()

# 2) 구멍 4개 — 원 중심 위치와 지름을 모두 구속
hs = body.newObject("Sketcher::SketchObject", "HoleSketch")
hs.AttachmentSupport = [(doc.getObject("XY_Plane"), "")]
hs.MapMode = "FlatFace"
for k, (xa, ya) in enumerate([("hole_x1", "hole_y"), ("hole_x1", "width - Params.hole_y"),
                              ("hole_x2", "hole_y"), ("hole_x2", "width - Params.hole_y")]):
    g = hs.addGeometry(Part.Circle(App.Vector(20 + 30 * k, 20, 0), App.Vector(0, 0, 1), 3), False)
    cx = hs.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, g, 3, 20 + 30 * k))
    cy = hs.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, g, 3, 20))
    cd = hs.addConstraint(Sketcher.Constraint("Diameter", g, 6))
    hs.setExpression(f"Constraints[{cx}]", P(xa))
    hs.setExpression(f"Constraints[{cy}]", "Params." + ya)
    hs.setExpression(f"Constraints[{cd}]", P("hole_d"))
doc.recompute()
pocket = body.newObject("PartDesign::Pocket", "Holes")
pocket.Profile = hs
pocket.Type = "ThroughAll"
pocket.Midplane = True
doc.recompute()


def line_along(e, axis):
    if not isinstance(e.Curve, Part.Line):
        return False
    d = e.Vertexes[-1].Point - e.Vertexes[0].Point
    return abs(abs(getattr(d.normalize(), axis)) - 1) < 1e-9


def find_edges(shape, pred):
    return [f"Edge{i}" for i, e in enumerate(shape.Edges, 1) if pred(e)]


def inner_edges(shape):
    """안쪽 꺾임부 모서리: Y 방향 직선, x=0, z=바닥판 두께 — 현재 스프레드시트 값으로 판단"""
    tb = sheet.base_t.Value
    return find_edges(shape, lambda e: line_along(e, "y") and abs(e.CenterOfMass.x) < 1e-6 and abs(e.CenterOfMass.z - tb) < 1e-6)


def corner_edges(shape):
    """바닥판 끝단의 수직 모서리 2개: Z 방향 직선, x=바닥판 길이"""
    lb = sheet.base_len.Value
    return find_edges(shape, lambda e: line_along(e, "z") and abs(e.CenterOfMass.x - lb) < 1e-6)


f_in = body.newObject("PartDesign::Fillet", "InnerFillet")
f_in.Base = (pocket, inner_edges(pocket.Shape))
f_in.setExpression("Radius", P("r_in"))
doc.recompute()
f_cn = body.newObject("PartDesign::Fillet", "CornerFillet")
f_cn.Base = (f_in, corner_edges(f_in.Shape))
f_cn.setExpression("Radius", P("r_corner"))
doc.recompute()


def rebind_fillets():
    """설계 변수를 바꾼 뒤 필렛이 참조할 모서리를 기하 조건으로 다시 찾아 연결한다 (02-4 TNP 대응)."""
    f_in.Base = (pocket, inner_edges(pocket.Shape))
    doc.recompute()
    f_cn.Base = (f_in, corner_edges(f_in.Shape))
    doc.recompute()


def expected_volume():
    v = {k: getattr(sheet, k).Value for k in PARAMS}
    q = lambda r: r * r - math.pi * r * r / 4          # 필렛 하나가 더하거나 깎는 단면적
    return (v["width"] * (v["base_len"] * v["base_t"] + v["arm_t"] * v["arm_h"])
            + v["width"] * q(v["r_in"])                          # 안쪽 필렛: 재료 추가
            - 2 * v["base_t"] * q(v["r_corner"])                 # 바깥 모서리 2곳: 재료 제거
            - 4 * math.pi * (v["hole_d"] / 2) ** 2 * v["base_t"])  # 구멍 4개


def validate():
    """요구사항 대비 검증 — 항목별 True/False와 측정값 (항목 이름은 영문 키)"""
    v = {k: getattr(sheet, k).Value for k in PARAMS}
    s = body.Shape
    bb = s.BoundBox
    cyl = [f for f in s.Faces if isinstance(f.Surface, Part.Cylinder)]
    holes = sorted((round(f.Surface.Center.x, 2), round(f.Surface.Center.y, 2)) for f in cyl
                   if abs(f.Surface.Radius - v["hole_d"] / 2) < 1e-6 and abs(abs(f.Surface.Axis.z) - 1) < 1e-9)
    want = sorted((x, y) for x in (v["hole_x1"], v["hole_x2"]) for y in (v["hole_y"], v["width"] - v["hole_y"]))
    bad = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
    exp_v = expected_volume()
    checks = {
        "no_error_objects": not bad,                     # 재계산 실패한 피처가 없는가
        "valid_single_solid": s.isValid() and len(s.Solids) == 1,
        "bbox": [round(x, 2) for x in (bb.XLength, bb.YLength, bb.ZLength)] == [v["base_len"] + v["arm_t"], v["width"], v["arm_h"]],
        "holes": holes == want,                          # 구멍 4개가 요구 위치에
        "volume": abs(s.Volume - exp_v) < 1.0,           # 설계 변수로 계산한 부피와 일치
    }
    return checks, {"volume": round(s.Volume, 1), "expected_volume": round(exp_v, 1), "holes": holes, "error_objects": bad,
                    "fully_constrained": getattr(prof, "FullyConstrained", None)}


def report(tag):
    checks, info = validate()
    # 결과는 ASCII JSON으로 — 한글이 이스케이프되어 freecadcmd 출력 인코딩과 무관하게 안전하다
    print(tag, json.dumps({"pass": all(checks.values()), "failed": [k for k, ok in checks.items() if not ok], **info}),
          flush=True)


report("BASE")
if os.environ.get("SET"):
    for kv in os.environ["SET"].split(";"):
        k, val = kv.split("=")
        sheet.set(f"B{list(PARAMS).index(k) + 1}", f"={val} mm")
    doc.recompute()
    report("CHANGED")
    if os.environ.get("REBIND") == "1":
        rebind_fillets()
        report("REBOUND")
doc.saveAs(OUT)
