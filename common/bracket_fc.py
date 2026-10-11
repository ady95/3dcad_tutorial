"""브래킷 FCStd를 다루는 FreeCAD 쪽 공용 함수 (freecadcmd 안에서 import).

02-3·02-4의 파라메트릭 브래킷(문서 안에 Params 스프레드시트, Body, Holes, InnerFillet, CornerFillet)을
열어 설계 변수를 읽고·바꾸고·필렛을 다시 연결하고·검증한다. 03장 이후 여러 곳에서 재사용한다.
"""
import math

import Part

NAMES = ["base_len", "width", "base_t", "arm_h", "arm_t", "r_in", "r_corner", "hole_d", "hole_x1", "hole_x2", "hole_y"]


def get_params(doc):
    sheet = doc.getObject("Params")
    return {n: round(getattr(sheet, n).Value, 4) for n in NAMES}


def set_params(doc, changes):
    """Params 스프레드시트의 값을 바꾼다. A열의 이름으로 행을 찾는다."""
    sheet = doc.getObject("Params")
    rows = {sheet.get(f"A{r}"): r for r in range(1, len(NAMES) + 1)}
    for name, value in changes.items():
        if name not in rows:
            raise KeyError(f"알 수 없는 설계 변수: {name}")
        sheet.set(f"B{rows[name]}", f"={value} mm")
    doc.recompute()


def _line_along(e, axis):
    if not isinstance(e.Curve, Part.Line):
        return False
    d = e.Vertexes[-1].Point - e.Vertexes[0].Point
    return abs(abs(getattr(d.normalize(), axis)) - 1) < 1e-9


def _edges(shape, pred):
    return [f"Edge{i}" for i, e in enumerate(shape.Edges, 1) if pred(e)]


def rebind_fillets(doc):
    """필렛이 걸릴 모서리를 기하 조건으로 다시 찾아 연결한다 (02-4의 TNP 대응)."""
    p = get_params(doc)
    pocket, f_in, f_cn = doc.getObject("Holes"), doc.getObject("InnerFillet"), doc.getObject("CornerFillet")
    f_in.Base = (pocket, _edges(pocket.Shape, lambda e: _line_along(e, "y") and abs(e.CenterOfMass.x) < 1e-6
                                and abs(e.CenterOfMass.z - p["base_t"]) < 1e-6))
    doc.recompute()
    f_cn.Base = (f_in, _edges(f_in.Shape, lambda e: _line_along(e, "z") and abs(e.CenterOfMass.x - p["base_len"]) < 1e-6))
    doc.recompute()


def expected_volume(p):
    q = lambda r: r * r - math.pi * r * r / 4
    return (p["width"] * (p["base_len"] * p["base_t"] + p["arm_t"] * p["arm_h"]) + p["width"] * q(p["r_in"])
            - 2 * p["base_t"] * q(p["r_corner"]) - 4 * math.pi * (p["hole_d"] / 2) ** 2 * p["base_t"])


def validate(doc):
    """02-4와 같은 검증. (항목별 True/False, 측정값) 반환."""
    p = get_params(doc)
    s = doc.getObject("Body").Shape
    bb = s.BoundBox
    cyl = [f for f in s.Faces if isinstance(f.Surface, Part.Cylinder)]
    holes = sorted([round(f.Surface.Center.x, 2), round(f.Surface.Center.y, 2)] for f in cyl
                   if abs(f.Surface.Radius - p["hole_d"] / 2) < 1e-6 and abs(abs(f.Surface.Axis.z) - 1) < 1e-9)
    want = sorted([x, y] for x in (p["hole_x1"], p["hole_x2"]) for y in (p["hole_y"], p["width"] - p["hole_y"]))
    bad = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
    exp_v = expected_volume(p)
    checks = {
        "no_error_objects": not bad,
        "valid_single_solid": s.isValid() and len(s.Solids) == 1,
        "bbox": [round(x, 2) for x in (bb.XLength, bb.YLength, bb.ZLength)] == [p["base_len"] + p["arm_t"], p["width"], p["arm_h"]],
        "holes": holes == want,
        "volume": abs(s.Volume - exp_v) < 1.0,
    }
    return checks, {"volume": round(s.Volume, 1), "expected_volume": round(exp_v, 1), "mass_g": round(s.Volume * 2.70e-3, 1),
                    "holes": holes, "error_objects": bad}
