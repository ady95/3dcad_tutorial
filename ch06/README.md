# 06. 나만의 AI 설계 엔지니어 완성하기

| 파일 | 실행 위치 | 내용 | 도서 위치 |
|---|---|---|---|
| `cae_tools.py` | Python 3.12 | 02~05장 모듈을 묶은 도구 계층: 사양 검사·해석·최적화·산출물·보고서, 상태(state.json) | 06-1 |
| `cae_mcp_server.py` | Python 3.12 (MCP 2.x) | 위 도구 6개를 MCP stdio 서버로 공개 | 06-1 |
| `check_server.py` | Python 3.12 | LLM 없이 MCP 서버 점검 (도구 목록, 순서 위반 호출) | 06-1 |
| `agent.py` | Python 3.12 | GPT-6 Astra + MCP 도구 + ask_user로 요구사항 → 보고서 | 06-1, 06-2 |
| `eval_cases.json` | — | 평가셋 9건 (기준·변형·조건 누락·범위 밖·불가능 기준) | 06-3 |
| `eval_agent.py` | Python 3.12 | 평가 실행과 기대 행동 판정 (state.json·산출물 기준) | 06-3 |

전체 실행은 `poc_bracket/run_poc.py` (06-2).

## 실행 (저장소 루트에서)

```bash
python ch06/check_server.py
python ch06/agent.py --request "요구사항 문장"
python ch06/eval_agent.py                       # 전체 평가, 약 1시간 반
python ch06/eval_agent.py E7-material E8-parttype
```

`mcp` 2.x에서는 `FastMCP`가 `MCPServer`(`mcp.server.mcpserver`)로 바뀌었습니다. stdio MCP 서버에서는 표준 출력에 print하면 안 됩니다(`quiet()` 참고).

## 기준 버전 (실측)

Windows 11 · FreeCAD 1.1.4 (CalculiX 2.22, Gmsh 4.15.0) · Python 3.12.15 · SciPy 1.18.1 · mcp 2.2.0 · gpt-6-astra
