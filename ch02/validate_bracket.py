# (freecadcmd에서 실행) 저장된 브래킷을 열어 요구사항과 비교한다. generate_bracket.py가 호출한다.
# 환경변수: BRACKET_FCSTD = 파일 경로, BRACKET_SPEC = 요구사항 JSON
import json
import math
import os

import FreeCAD as App
import Part

spec = json.loads(os.environ["BRACKET_SPEC"])
doc = App.openDocument(os.environ["BRACKET_FCSTD"])
obj = doc.getObject("Bracket")
s = obj.Shape
bb = s.BoundBox
v = spec
q = lambda r: r * r - math.pi * r * r / 4
expected_volume = (v["width"] * (v["base_len"] * v["base_t"] + v["arm_t"] * v["arm_h"]) + v["width"] * q(v["r_in"])
                   - 2 * v["base_t"] * q(v["r_corner"]) - 4 * math.pi * (v["hole_d"] / 2) ** 2 * v["base_t"])
cyl = [f for f in s.Faces if isinstance(f.Surface, Part.Cylinder)]
holes = sorted([round(f.Surface.Center.x, 2), round(f.Surface.Center.y, 2)] for f in cyl
               if abs(f.Surface.Radius - v["hole_d"] / 2) < 1e-3 and abs(abs(f.Surface.Axis.z) - 1) < 1e-6)
want_holes = sorted([x, y] for x in (v["hole_x1"], v["hole_x2"]) for y in (v["hole_y"], v["width"] - v["hole_y"]))
inner = [f for f in cyl if abs(f.Surface.Radius - v["r_in"]) < 1e-3 and abs(abs(f.Surface.Axis.y) - 1) < 1e-6]
measured = {"bbox_min": [round(bb.XMin, 2), round(bb.YMin, 2), round(bb.ZMin, 2)],
            "bbox_max": [round(bb.XMax, 2), round(bb.YMax, 2), round(bb.ZMax, 2)],
            "volume": round(s.Volume, 1), "expected_volume": round(expected_volume, 1), "holes": holes,
            "inner_fillet_axis_xz": [[round(f.Surface.Center.x, 2), round(f.Surface.Center.z, 2)] for f in inner]}
checks = {
    "valid_single_solid": s.isValid() and len(s.Solids) == 1,
    "bbox": measured["bbox_min"] == [-v["arm_t"], 0, 0] and measured["bbox_max"] == [v["base_len"], v["width"], v["arm_h"]],
    "holes": holes == want_holes,
    "inner_fillet": len(inner) == 1,
    "volume": abs(s.Volume - expected_volume) < 1.0,
}
expected = {"bbox_min": [-v["arm_t"], 0, 0], "bbox_max": [v["base_len"], v["width"], v["arm_h"]],
            "volume": round(expected_volume, 1), "holes": want_holes}
print("CHECK " + json.dumps({"checks": checks, "measured": measured, "expected": expected}), flush=True)
