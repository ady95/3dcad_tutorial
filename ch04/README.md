# 04. 공학적 해석 자동화

| 파일 | 실행 위치 | 내용 | 도서 위치 |
|---|---|---|---|
| `cantilever_fem.py` | freecadcmd | 외팔보 해석과 이론해 비교 (MESH로 요소 크기) | 04-3 |
| `bracket_fem.py` | freecadcmd | 02-3 브래킷 FCStd 해석·판정 (SET, FIX, MESH, LOAD_N, VTK) | 04-4 |
| `convergence.py` | Python 3.12 | 초기·최종 설계의 메시 수렴성 표와 그래프 (`--plot-only`) | 04-5 |
| `report.py` | Python 3.12 | 응력 분포 그림(PyVista), 해석 보고서(Markdown), AI 요약과 숫자 대조 (`--summarize`) | 04-5 |

공용: `common/fem_fc.py` (FEM 해석 구성·실행·결과 요약)

## 실행 (저장소 루트에서)

```bash
freecadcmd ch02/bracket_parametric.py          # 해석할 브래킷 준비
freecadcmd ch04/cantilever_fem.py
freecadcmd ch04/bracket_fem.py                 # FIX=bottom, SET="base_t=6;arm_t=8;r_in=8"
python ch04/convergence.py
SET="base_t=6;arm_t=8;r_in=8" MESH=3 VTK=1 OUT_DIR=output/ch04/report_final freecadcmd ch04/bracket_fem.py
python ch04/report.py --summarize
```

FreeCAD의 VTK 내보내기는 응력을 Pa, 변위를 m로 저장합니다(좌표는 mm). report.py가 MPa·mm로 바꿉니다.

## 기준 버전 (실측)

Windows 11 · FreeCAD 1.1.4 (CalculiX 2.22, Gmsh 4.15.0) · Python 3.12.15 · PyVista 0.49.0 · Matplotlib 3.11.2 · gpt-6-astra
