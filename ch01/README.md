# 01. AI 3D 설계 시작하기

| 파일 | 내용 | 도서 위치 |
|---|---|---|
| `check_env.py` | Python 패키지·FreeCAD(번들 Gmsh·CalculiX)·OpenAI API 연결 확인 | 01-2 |
| `make_plate.py` | 자연어 요구사항 → GPT-6 Astra가 FreeCAD 코드 생성 → 실행 → 검증 | 01-3 |
| `validate_plate.py` | (freecadcmd에서 실행) 저장된 플레이트 측정 — `make_plate.py`가 호출 | 01-3 |

## 실행 (저장소 루트에서)

```bash
python ch01/check_env.py
python ch01/make_plate.py
python ch01/make_plate.py --length 100 --width 60 --thickness 5 --hole 5 --edge 8 --fillet 4
```

결과 파일은 `output/ch01/`에 저장됩니다 (FCStd·STEP·생성된 코드).

## 기준 버전 (실측)

Windows 11 · Python 3.12.15 · FreeCAD 1.1.4 (CalculiX 2.22, Gmsh 4.15.0 번들) · openai 3.28.0 · gpt-6-astra
