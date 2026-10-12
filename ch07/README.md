# 07. API 없는 소프트웨어 다루기 — 화면 조작 (Codex 앱 필요)

> 이 장만 Codex 데스크톱 앱(ChatGPT 요금제 로그인, Computer Use 플러그인)이 필요합니다. Codex CLI의 `codex exec`에서는 화면 조작이 동작하지 않습니다.

| 파일 | 실행 위치 | 내용 | 도서 위치 |
|---|---|---|---|
| `prepare_task.py` | freecadcmd | 05장 최종 설계 브래킷 + 해석 컨테이너(Analysis·재료·CalculiX) 준비 | 07-2 |
| `grade.py` | freecadcmd | 화면 조작 결과 채점 (`MODE=T2` 구멍 4면 Fixed, `MODE=T1` 플레이트, `MODE=selftest` 채점기 검증) | 07-2, 07-3 |
| `hybrid_loop.py` | Python 3.12 | 준비 → FreeCAD 창 → Codex 프롬프트 출력 → 채점 → 재시도 프롬프트 (`--task T1/T2`, `--grade-only`) | 07-2 |
| `codex_session_audit.py` | Python 3.12 | Codex 세션 기록(rollout jsonl) 감사: 화면 동작·셸 명령·입력 텍스트·스크립트 흔적 | 07-2 |
| `prompts/` | — | Codex 앱에 붙여 넣을 과제 프롬프트 (`{window_title}`, `{save_path}`는 루프가 채움) | 07-2, 07-3 |

## 실행 (저장소 루트에서)

```bash
python fcrun.py OUT_DIR=output/ch07 ch02/bracket_parametric.py
python fcrun.py ch07/prepare_task.py
python fcrun.py MODE=selftest ch07/grade.py
python ch07/hybrid_loop.py --task T2      # 프롬프트를 Codex 앱 새 스레드에 붙여 넣고, 끝나면 Enter
python ch07/codex_session_audit.py <rollout-*.jsonl>
```

실행 중에는 마우스·키보드를 쓰지 말고, 화면 잠금·화면 보호기·절전을 끄세요(잠기면 GetCursorPos 접근 거부로 멈춥니다).

## 기준 버전 (실측)

Windows 11 · FreeCAD 1.1.4 · Codex 데스크톱 앱 26.1007 (Computer Use 26.1007) · Codex CLI 0.162.1 · gpt-6-astra
