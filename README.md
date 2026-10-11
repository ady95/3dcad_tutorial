# 3D CAD와 공학 설계 AI 자동화 따라하기 — 예제 코드

위키독스 도서 **《3D CAD와 공학 설계 AI 자동화 따라하기》**(부제: GPT-6 Astra와 FreeCAD로 배우는 CAD 모델링·공학 해석·설계 최적화)의 실습 예제 코드 저장소입니다.

- 📖 도서: https://wikidocs.net/book/21578

> "말로 설계하고, AI가 모델링하며, 시뮬레이션으로 검증하고, 해석 결과를 바탕으로 설계를 개선한다."

> ⚠️ 이 저장소는 집필과 함께 채워지는 중입니다. 장별 코드는 해당 장이 공개되는 시점에 추가됩니다.

## 폴더 구성

| 폴더 | 내용 | 도서 위치 |
|---|---|---|
| `ch01/` | 개발환경 확인, 자연어로 첫 번째 3D 부품 만들기 | 01. AI 3D 설계 시작하기 |
| `ch02/` | FreeCAD Python API, Sketch·Pad·Pocket·Fillet 자동화, 모델 검증 | 02. AI 기반 파라메트릭 CAD 자동화 |
| `ch03/` | MCP 연동, 자연어 CAD 설계 에이전트, FCStd·STEP·STL 내보내기 | 03. CAD 에이전트 구현 |
| `ch04/` | Gmsh·CalculiX 구조해석, 외팔보·브래킷 해석, 메시 수렴성 | 04. 공학적 해석 자동화 |
| `ch05/` | 해석 결과 해석, 파라미터 재해석, SciPy 설계 최적화 | 05. AI 기반 설계 최적화 |
| `ch06/` | 통합 CAD·CAE 에이전트, 자연어 → 검증 보고서 | 06. 나만의 AI 설계 엔지니어 완성하기 |
| `common/` | 여러 장에서 공유하는 유틸리티 | — |
| `poc_bracket/` | 대표 프로젝트: AI 브래킷 설계 및 구조해석 자동화 | 책 전체 |

## 실습 환경

| 항목 | 권장 |
|---|---|
| 운영체제 | Windows 또는 Linux |
| 메모리 | 16GB 이상 |
| GPU | 필요 없음 |
| CAD/CAE | FreeCAD 1.1.x (Gmsh, CalculiX 포함) |
| AI | OpenAI API (GPT-6 Astra) |
| Python | FreeCAD 번들 Python 또는 3.11 이상 |

정확한 버전은 각 장 폴더의 README에 기재합니다.

## 시작하기

```bash
git clone https://github.com/ady95/3dcad_tutorial.git
cd 3dcad_tutorial
cp .env.example .env   # OPENAI_API_KEY 입력
```

## 주의 사항

- 이 저장소의 구조해석 결과는 **학습용 공학 검증**이며 안전 인증을 대체하지 않습니다. 실무 적용에는 전문가 검토, 설계 규격·제조공차 검토, 필요 시 실물 시험이 필요합니다.
- MCP 서버는 FreeCAD의 Python 환경과 운영체제 자원에 접근할 수 있으므로, 격리된 환경에서 실행하기를 권장합니다.
- API 키가 담긴 `.env` 파일은 커밋하지 마세요.
