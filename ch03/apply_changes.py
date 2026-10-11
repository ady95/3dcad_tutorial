# 03-3 (freecadcmd) 기존 브래킷 FCStd를 열어 설계 변수를 바꾸고, 필렛을 다시 연결하고, 검증한 뒤 새 파일로 저장한다.
# 환경변수: SRC = 원본 FCStd, DST = 저장할 FCStd(비우면 저장 안 함), CHANGES = {"base_t": 10, ...} JSON
# CHANGES를 비우면 현재 설계 변수와 검증 결과만 출력한다.
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import FreeCAD as App  # noqa: E402
from common.bracket_fc import get_params, rebind_fillets, set_params, validate  # noqa: E402

doc = App.openDocument(os.path.abspath(os.environ["SRC"]))
before = get_params(doc)
changes = json.loads(os.environ.get("CHANGES") or "{}")
if changes:
    set_params(doc, changes)
    rebind_fillets(doc)
checks, info = validate(doc)
if os.environ.get("DST"):
    doc.saveAs(os.path.abspath(os.environ["DST"]))
print("RESULT " + json.dumps({"before": before, "after": get_params(doc), "pass": all(checks.values()),
                              "failed": [k for k, ok in checks.items() if not ok], **info}), flush=True)
