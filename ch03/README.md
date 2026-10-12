# 03. CAD 에이전트 구현

| 파일 | 실행 위치 | 내용 | 도서 위치 |
|---|---|---|---|
| `mcp_agent.py` | Python 3.12 | freecad-mcp Headless 서버 + MCP 브리지 연결, Astra가 도구로 플레이트 생성, 독립 검증 | 03-1 |
| `design_agent.py` | Python 3.12 | 요구사항 → 입력 규격 사양(빠진 조건 되묻기) → 설계 변수 → 브래킷 생성·검증 | 03-2 |
| `answers.json` | - | design_agent 재현 실행용 답변 | 03-2 |
| `modify_model.py` | Python 3.12 | 자연어 수정 요청 → 설계 변수 변경 → 적용·검증 → 버전·이력·되돌리기 | 03-3 |
| `apply_changes.py` | freecadcmd | 기존 FCStd의 설계 변수 변경·필렛 재연결·검증·저장 | 03-3 |
| `export_formats.py` | freecadcmd | FCStd·STEP·STL 내보내기와 재불러오기 비교 | 03-4 |

공용: `common/bracket_fc.py` (브래킷 설계 변수 읽기·쓰기, 필렛 재연결, 검증 — freecadcmd에서 import)

## 준비 (03-1)

```bash
git clone https://github.com/blwfish/freecad-mcp.git
pip install -r freecad-mcp/requirements.txt     # mcp==2.2.0
```

`.env`에 `FREECAD_MCP_DIR=<클론 경로>`를 추가합니다.

## 실행 (저장소 루트에서)

```bash
python ch03/mcp_agent.py
python ch03/design_agent.py --answers ch03/answers.json
python ch03/modify_model.py --init
python ch03/modify_model.py "세로판만 2mm 두껍게 해줘"
python fcrun.py ch03/export_formats.py
```

## 기준 버전 (실측)

Windows 11 · FreeCAD 1.1.4 · Python 3.12.15 · freecad-mcp 8.2.3 · mcp 2.2.0 · gpt-6-astra
