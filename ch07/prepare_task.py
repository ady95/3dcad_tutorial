# 07-2 화면 조작 과제 준비 (실행 위치 (2): freecadcmd)
# 05장 최종 설계(6/8/R8) 브래킷과 해석 컨테이너(Analysis, 재료, CalculiX 솔버)까지 코드로 만들어 둔다.
# 화면 조작에 맡기는 것은 "볼트 구멍 4개 내면에 Fixed 구속 지정" 한 가지뿐이다.
# 사용: python fcrun.py OUT_DIR=output/ch07 ch02/bracket_parametric.py   (기준 모델을 07장 폴더에 따로 만든다)
#       python fcrun.py ch07/prepare_task.py                             → output/ch07/T2_input.FCStd
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import FreeCAD as App  # noqa: E402
import ObjectsFem  # noqa: E402
from common.bracket_fc import rebind_fillets, set_params, validate  # noqa: E402

SRC = os.path.abspath(os.environ.get("SRC", "output/ch07/bracket_param.FCStd"))
OUT = os.path.abspath(os.environ.get("OUT", "output/ch07/T2_input.FCStd"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)

src = App.openDocument(SRC)
set_params(src, {"base_t": 6, "arm_t": 8, "r_in": 8})
rebind_fillets(src)
checks, geo = validate(src)
assert all(checks.values()), checks
shape = src.getObject("Body").Shape.copy()
App.closeDocument(src.Name)

# 새 문서에 형상만 Part::Feature로 담는다 — 화면에서 고를 면 번호가 바뀌지 않게 (04-4와 같은 이유)
doc = App.newDocument("BracketT2")
part = doc.addObject("Part::Feature", "Bracket")
part.Shape = shape
an = ObjectsFem.makeAnalysis(doc, "Analysis")
an.addObject(ObjectsFem.makeSolverCalculiXCcxTools(doc, "CalculiX"))
mat = ObjectsFem.makeMaterialSolid(doc, "Al6061T6")
m = mat.Material
m.update({"Name": "Al6061-T6", "YoungsModulus": "68900 MPa", "PoissonRatio": "0.33", "Density": "2700 kg/m^3"})
mat.Material = m
an.addObject(mat)
doc.recompute()
doc.saveAs(OUT)
print("PREP " + json.dumps({"file": os.path.relpath(OUT), "faces": len(shape.Faces),
                            "volume": round(shape.Volume, 1), "objects": [o.Name for o in doc.Objects]}), flush=True)
