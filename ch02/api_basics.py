# 02-1 FreeCAD Python API 기초 (실행 위치 (2): freecadcmd)
# 문서(Document) → 객체(DocumentObject) → 형상(Shape) 구조와 B-Rep 조회를 01-3의 플레이트로 확인한다.
# 사용: freecadcmd ch02/api_basics.py      (먼저 01-3의 make_plate.py를 실행해 FCStd를 만들어 둘 것)
import collections
import os

import FreeCAD as App
import Part

path = os.environ.get("PLATE", "output/ch01/plate_120x80x6.FCStd")
doc = App.openDocument(os.path.abspath(path))

# 1) 문서와 객체
print("문서:", doc.Name, "| 객체 수:", len(doc.Objects))
for obj in doc.Objects:
    print(f"  객체 {obj.Name} ({obj.TypeId}) 레이블={obj.Label}")

# 2) 형상(Shape) — B-Rep: 솔리드 > 셸 > 면 > 모서리 > 꼭짓점
shape = doc.getObject("Plate").Shape
print("형상 종류:", shape.ShapeType, "| 유효:", shape.isValid())
print("솔리드", len(shape.Solids), "· 셸", len(shape.Shells), "· 면", len(shape.Faces),
      "· 모서리", len(shape.Edges), "· 꼭짓점", len(shape.Vertexes))
print("부피(mm³):", round(shape.Volume, 2), "| 겉넓이(mm²):", round(shape.Area, 2))
bb = shape.BoundBox
print("바운딩 박스:", [round(bb.XMin, 2), round(bb.YMin, 2), round(bb.ZMin, 2)], "~",
      [round(bb.XMax, 2), round(bb.YMax, 2), round(bb.ZMax, 2)])

# 3) 면을 곡면 종류별로 세기 — 평면/원통 등
kinds = collections.Counter(type(f.Surface).__name__ for f in shape.Faces)
print("면 종류:", dict(kinds))

# 4) 원통면을 반지름·축 방향·중심으로 분류 — 구멍과 필렛을 구분하는 기준
for f in shape.Faces:
    s = f.Surface
    if isinstance(s, Part.Cylinder):
        print(f"  원통면 r={s.Radius:g} 축={tuple(round(a, 3) for a in s.Axis)} 중심=({s.Center.x:g}, {s.Center.y:g})")

# 5) 새 형상 만들기와 불리언 — 같은 판을 Part 기본 도형으로 다시 만들어 비교
box = Part.makeBox(120, 80, 6)
hole = Part.makeCylinder(3, 8, App.Vector(10, 10, -1))
print("상자 부피:", box.Volume, "| 구멍 하나 뺀 부피:", round(box.cut(hole).Volume, 2))
