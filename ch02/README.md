# 02. AI 기반 파라메트릭 CAD 자동화

| 파일 | 실행 위치 | 내용 | 도서 위치 |
|---|---|---|---|
| `api_basics.py` | freecadcmd | 문서·객체·형상 구조, B-Rep 조회 (01-3 플레이트 사용) | 02-1 |
| `bracket_partdesign.py` | freecadcmd | PartDesign으로 L자 브래킷 (스케치 → Pad → Pocket → Fillet) | 02-2 |
| `bracket_parametric.py` | freecadcmd | 스프레드시트 설계 변수 + 수식 연결, 값 변경·필렛 재연결·검증 | 02-3, 02-4 |
| `regression_test.py` | Python 3.12 | 설계 변수 조합별 재계산·검증 표 | 02-4 |
| `generate_bracket.py` | Python 3.12 | GPT-6 Astra 코드 생성 → 실행 → 검증 → 피드백 수정 루프 | 02-4 |
| `validate_bracket.py` | freecadcmd | 생성된 브래킷 검증 (generate_bracket.py가 호출) | 02-4 |

## 실행 (저장소 루트에서)

```bash
python fcrun.py ch02/api_basics.py            # 먼저 python ch01/make_plate.py
python fcrun.py ch02/bracket_partdesign.py
python fcrun.py ch02/bracket_parametric.py    # 값 변경: python fcrun.py SET=base_t=6 REBIND=1 ch02/bracket_parametric.py
python ch02/regression_test.py
python ch02/generate_bracket.py               # --verbal: 좌표 없이 말로만 적은 요구사항
```

## 기준 버전 (실측)

Windows 11 · FreeCAD 1.1.4 · Python 3.12.15 · gpt-6-astra
