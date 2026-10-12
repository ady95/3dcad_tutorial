# 03-4 FCStd·STEP·STL 내보내기와 재검증 (실행 위치 (2): freecadcmd)
# 02-3의 파라메트릭 브래킷을 세 형식으로 내보내고, 다시 불러와 원본과 비교한다.
# 사용: python fcrun.py ch03/export_formats.py     (먼저 python fcrun.py ch02/bracket_parametric.py 실행)
import json
import os

import FreeCAD as App
import Mesh
import MeshPart
import Part

SRC = os.path.abspath(os.environ.get("SRC", "output/ch02/bracket_param.FCStd"))
OUT = os.path.abspath(os.environ.get("OUT_DIR", "output/ch03/export"))
os.makedirs(OUT, exist_ok=True)

doc = App.openDocument(SRC)
shape = doc.getObject("Body").Shape          # PartDesign Body의 최종 형상
ref = {"volume": shape.Volume, "area": shape.Area, "faces": len(shape.Faces), "bbox": shape.BoundBox}
result = {"source": {"volume": round(ref["volume"], 2), "area": round(ref["area"], 2), "faces": ref["faces"]}}


def size_kb(path):
    return round(os.path.getsize(path) / 1024, 1)


def bbox_diff(a, b):
    return round(max(abs(a.XMin - b.XMin), abs(a.YMin - b.YMin), abs(a.ZMin - b.ZMin),
                     abs(a.XMax - b.XMax), abs(a.YMax - b.YMax), abs(a.ZMax - b.ZMax)), 4)


# 1) FCStd — 문서 전체(스프레드시트·스케치·피처 이력 포함)를 그대로 저장
fcstd = os.path.join(OUT, "bracket.FCStd")
doc.saveAs(fcstd)
re_doc = App.openDocument(fcstd)
re_shape = re_doc.getObject("Body").Shape
result["fcstd"] = {"kb": size_kb(fcstd), "objects": len(re_doc.Objects),
                   "has_params": re_doc.getObject("Params") is not None,
                   "volume_diff": round(re_shape.Volume - ref["volume"], 4)}
App.closeDocument(re_doc.Name)

# 2) STEP — 다른 CAD와 주고받는 중립 형식. 정확한 B-Rep 형상만 담기고 이력·변수는 빠진다
step = os.path.join(OUT, "bracket.step")
shape.exportStep(step)
s2 = Part.read(step)
result["step"] = {"kb": size_kb(step), "solids": len(s2.Solids), "faces": len(s2.Faces),
                  "volume_diff": round(s2.Volume - ref["volume"], 4), "bbox_diff": bbox_diff(s2.BoundBox, ref["bbox"])}

# 3) STL — 삼각형 메시. 3D 프린팅·시각화용. 곡면은 근사되므로 정밀도에 따라 크기·오차가 달라진다
result["stl"] = []
for name, lin, ang in [("coarse", 0.5, 0.5), ("default", 0.1, 0.2618), ("fine", 0.01, 0.1)]:
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)
    stl = os.path.join(OUT, f"bracket_{name}.stl")
    m.write(stl)
    m2 = Mesh.Mesh(stl)
    result["stl"].append({"quality": name, "linear_deflection": lin, "angular_deflection": ang,
                          "kb": size_kb(stl), "facets": m2.CountFacets, "solid": m2.isSolid(),
                          "volume_err_pct": round((m2.Volume - ref["volume"]) / ref["volume"] * 100, 4),
                          "area_err_pct": round((m2.Area - ref["area"]) / ref["area"] * 100, 4)})

with open(os.path.join(OUT, "export_result.json"), "w") as f:   # 결과는 파일로도 남긴다
    json.dump(result, f, indent=1)
print("EXPORT " + json.dumps(result), flush=True)
