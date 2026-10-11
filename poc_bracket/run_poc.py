"""06-2 자연어에서 검증 보고서까지 — AI 브래킷 설계 PoC 전체 실행 (실행 위치 (3)).

01-1에서 미리 본 프로젝트를 06-1의 에이전트로 처음부터 끝까지 실행한다.
요청 문장은 request.txt, AI가 되묻는 질문에 쓸 답은 answers.json (--ask를 주면 직접 답한다).
산출물: output/poc_bracket/ — bracket.FCStd·step·stl, fem/(요소 3 mm 해석), contour.png, report.md,
        state.json(사양·도구 호출 이력), agent_log.txt, agent_stats.json

사용 (저장소 루트에서): python poc_bracket/run_poc.py [--ask]
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
cmd = [sys.executable, str(ROOT / "ch06" / "agent.py"), "--request-file", str(HERE / "request.txt"),
       "--project", str(ROOT / "output" / "poc_bracket")]
if "--ask" not in sys.argv:
    cmd += ["--answers", str(HERE / "answers.json")]
sys.exit(subprocess.call(cmd))
