# 07-2 화면 조작 결과 채점 (실행 위치 (2): freecadcmd)
# 화면 조작 에이전트의 "완료했습니다"를 믿지 않고, 저장된 파일을 열어 코드로 판정한다.
# 사용: MODE=T2 FILE=결과.FCStd freecadcmd ch07/grade.py   — 볼트 구멍 4면 Fixed 구속
#       MODE=T1 FILE=결과.FCStd freecadcmd ch07/grade.py   — 01-3 플레이트 (07-3)
#       MODE=selftest freecadcmd ch07/grade.py              — 채점기부터 검증: 정답은 합격, 오답은 불합격이어야 한다
import json
import math
import os

import FreeCAD as App
import ObjectsFem
import Part

HOLES = [(25, 10), (25, 70), (110, 10), (110, 70)]           # 브래킷 볼트 구멍 중심 (02장)
PLATE_HOLES = [(10.0, 10.0), (10.0, 70.0), (110.0, 10.0), (110.0, 70.0)]


def is_hole(face):
    s = face.Surface
    return (isinstance(s, Part.Cylinder) and abs(s.Radius - 3) < 1e-3 and abs(abs(s.Axis.z) - 1) < 1e-9
            and any(abs(s.Center.x - x) < 1e-3 and abs(s.Center.y - y) < 1e-3 for x, y in HOLES))


def grade_t2(doc):
    an = doc.getObject("Analysis")
    fixed = [o for o in doc.Objects if o.TypeId == "Fem::ConstraintFixed"]
    faces = [(obj.Shape.getElement(n), n) for o in fixed for obj, subs in o.References for n in subs]
    hit = {(round(f.Surface.Center.x), round(f.Surface.Center.y)) for f, _ in faces if is_hole(f)}
    r = {"fixed_constraints": len(fixed), "in_analysis": bool(fixed) and all(o in an.Group for o in fixed),
         "faces": [{"name": n, "hole": is_hole(f)} for f, n in faces]}
    r["pass"] = len(faces) == 4 and all(x["hole"] for x in r["faces"]) and r["in_analysis"] and hit == set(HOLES)
    return r


def grade_t1(doc):
    objs = [o for o in doc.Objects if o.Label == "Plate" and hasattr(o, "Shape")]
    if not objs:
        return {"label_ok": False, "pass": False}
    s = objs[-1].Shape
    expected = 120 * 80 * 6 - 4 * math.pi * 9 * 6 - 4 * (25 - math.pi * 25 / 4) * 6
    holes = sorted((round(f.Surface.Center.x, 2), round(f.Surface.Center.y, 2)) for f in s.Faces
                   if isinstance(f.Surface, Part.Cylinder) and abs(f.Surface.Radius - 3) < 1e-3)
    fillets = [f for f in s.Faces if isinstance(f.Surface, Part.Cylinder) and abs(f.Surface.Radius - 5) < 1e-3]
    r = {"label_ok": True, "valid": s.isValid(), "solids": len(s.Solids), "volume": round(s.Volume, 2),
         "expected": round(expected, 2), "holes": holes, "fillets": len(fillets)}
    r["pass"] = (r["valid"] and r["solids"] == 1 and abs(r["volume"] - expected) < 1.0 and holes == PLATE_HOLES
                 and len(fillets) == 4)
    return r


def selftest():
    """정답·오답 파일을 코드로 만들어 채점기가 구분하는지 확인한다"""
    src = os.path.abspath(os.environ.get("SRC", "output/ch07/T2_input.FCStd"))
    out = {}
    for case in ("정답", "필렛 면 섞임", "구멍 3개", "구속 없음"):
        doc = App.openDocument(src)
        part = doc.getObject("Bracket")
        holes = [f"Face{i + 1}" for i, f in enumerate(part.Shape.Faces) if is_hole(f)]
        fillet = next(f"Face{i + 1}" for i, f in enumerate(part.Shape.Faces)
                      if isinstance(f.Surface, Part.Cylinder) and abs(f.Surface.Radius - 8) < 1e-3)
        refs = {"정답": holes, "필렛 면 섞임": holes[:3] + [fillet], "구멍 3개": holes[:3], "구속 없음": None}[case]
        if refs:
            c = ObjectsFem.makeConstraintFixed(doc, "ConstraintFixed")
            c.References = [(part, refs)]
            doc.getObject("Analysis").addObject(c)
            doc.recompute()
        out[case] = grade_t2(doc)["pass"]
        App.closeDocument(doc.Name)
    out["채점기 정상"] = out == {"정답": True, "필렛 면 섞임": False, "구멍 3개": False, "구속 없음": False}
    return out


MODE = os.environ.get("MODE", "T2")
if MODE == "selftest":
    result = selftest()
else:
    f = os.path.abspath(os.environ["FILE"])
    if not os.path.exists(f):
        result = {"file": os.path.basename(f), "exists": False, "pass": False}
    else:
        d = App.openDocument(f)
        result = {"file": os.path.basename(f), "exists": True, **(grade_t2(d) if MODE == "T2" else grade_t1(d))}
print("GRADE " + json.dumps(result, ensure_ascii=False), flush=True)
