# AI 브래킷 설계 PoC (06-2)

01-1에서 미리 본 프로젝트를 06-1의 통합 에이전트(`ch06/agent.py`)로 처음부터 끝까지 실행합니다.

| 파일 | 내용 |
|---|---|
| `request.txt` | 자연어 요청 (일부 조건을 일부러 빠뜨림) |
| `answers.json` | AI가 되묻는 질문에 차례로 쓸 답 (재현용) |
| `run_poc.py` | 실행기. `--ask`를 주면 질문에 직접 답한다 |

```bash
python poc_bracket/run_poc.py          # 약 12분 (구조해석 약 40회), .env에 OPENAI_API_KEY 필요
```

산출물(`output/poc_bracket/`): `bracket.FCStd`·`bracket.step`·`bracket.stl`, `fem/`(요소 3 mm 해석, result.json·result.vtk), `contour.png`, `report.md`, `state.json`(사양·도구 호출 이력), `agent_log.txt`, `agent_stats.json`

> 이 결과는 학습용 공학 검증이며 안전 인증을 대체하지 않습니다.
