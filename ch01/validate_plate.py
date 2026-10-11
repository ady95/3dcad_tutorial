# freecadcmd 안에서 실행: 저장된 플레이트를 열어 측정값을 JSON 한 줄로 출력한다.
# make_plate.py가 환경변수 PLATE_FCSTD로 파일 경로를 넘겨준다.
import json
import os

import FreeCAD as App
import Part

doc = App.openDocument(os.environ["PLATE_FCSTD"])
obj = doc.getObject("Plate")
shape = obj.Shape
bb = shape.BoundBox
# 수직(Z축) 원통면을 반지름별로 센다: 구멍 / 모서리 필렛
cyl = [f for f in shape.Faces if isinstance(f.Surface, Part.Cylinder) and abs(abs(f.Surface.Axis.z) - 1) < 1e-9]
radii = sorted({round(f.Surface.Radius, 3) for f in cyl})
result = {
    "is_valid": shape.isValid(),
    "solids": len(shape.Solids),
    "bbox_mm": [round(bb.XLength, 3), round(bb.YLength, 3), round(bb.ZLength, 3)],
    "volume_mm3": round(shape.Volume, 2),
    "cylinder_faces": {str(r): sorted((round(f.Surface.Center.x, 2), round(f.Surface.Center.y, 2))
                                      for f in cyl if abs(f.Surface.Radius - r) < 1e-6) for r in radii},
}
print("PLATE " + json.dumps(result), flush=True)
