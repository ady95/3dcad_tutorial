# 05. AI 기반 설계 최적화

| 파일 | 실행 위치 | 내용 | 도서 위치 |
|---|---|---|---|
| `review.py` | Python 3.12 | 민감도 해석 결과를 GPT-6 Astra에 넘겨 개선안 받기, 인용 숫자·범위 검사 후 재해석 | 05-1 |
| `evaluate.py` | Python 3.12 | 설계 변수 → 모델 재생성 → 해석 → 판정 (캐시·이력·실패 처리, `--sweep`) | 05-2 |
| `optimize.py` | Python 3.12 | SciPy COBYQA 질량 최소화 (안전율 ≥ 2.0, 처짐 ≤ 0.5 mm), 판재 규격 반영, 요소 3 mm 재검증 (`--x0`, `--tag`) | 05-3 |

내부에서 `ch04/bracket_fem.py`(freecadcmd)와 `ch02/bracket_parametric.py`를 호출합니다. 기준 모델은 `output/ch05/template`에 따로 만들어 씁니다.

## 실행 (저장소 루트에서)

```bash
python ch05/review.py                          # .env에 OPENAI_API_KEY 필요
python ch05/evaluate.py --sweep 8,7,6,5,4,3
python ch05/evaluate.py r_in=0                 # 재생성 실패 처리 확인
python ch05/optimize.py                        # 초기 설계 8/8/R5에서 출발
python ch05/optimize.py --x0 7,7,7 --tag ai    # 05-1 AI 제안에서 출발
```

결과는 `output/ch05/`(cache, history.jsonl, optimize_*.json)에 남습니다. 코드를 고친 뒤 처음부터 다시 해석하려면 `output/ch05/cache`를 지웁니다.

## 기준 버전 (실측)

Windows 11 · FreeCAD 1.1.4 (CalculiX 2.22, Gmsh 4.15.0) · Python 3.12.15 · SciPy 1.18.1 · gpt-6-astra
