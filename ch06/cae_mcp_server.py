"""06-1 CAD·CAE 도구를 MCP 서버로 공개한다 (실행 위치 (3), MCP Python SDK 2.x).

03-1의 freecad-mcp(도구 39개)에는 FEM 해석 전용 도구가 없다(execute_python으로 코드를 보낼 수는 있다). 이 서버가 02~05장의 모듈을
"사양 등록·해석·최적화·산출물·보고서" 6개 도구로 묶어 공개한다. MCP를 지원하는 어떤 클라이언트든 붙일 수 있다.

실행: 직접 띄울 일은 없다. ch06/agent.py가 stdio로 띄워 연결한다.
      프로젝트 폴더는 환경변수 CAE_PROJECT_DIR (기본 output/ch06/project)
"""
import contextlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from mcp.server.mcpserver import MCPServer  # noqa: E402   mcp 1.x의 FastMCP가 2.x에서 MCPServer로 바뀌었다
from ch06.cae_tools import CAPABILITIES, SPEC_EXAMPLE, Project  # noqa: E402

project = Project(os.environ.get("CAE_PROJECT_DIR", ROOT / "output" / "ch06" / "project"))
server = MCPServer("cae-tools", instructions="L자 브래킷 설계·구조해석·최적화 도구. 계산과 판정은 도구가 하고, 결과 숫자는 도구 출력만 인용한다.")


def quiet(fn, *args, **kw):
    """stdio MCP에서 표준 출력은 프로토콜 통로다. 05장 함수의 print가 섞이면 연결이 깨지므로 stderr로 돌린다."""
    with contextlib.redirect_stdout(sys.stderr):
        return fn(*args, **kw)


@server.tool()
def get_capabilities() -> dict:
    """지원 범위(부품 유형·재료·하중·구속)와 사양 형식 예시를 돌려준다. 가장 먼저 부른다."""
    return {"capabilities": CAPABILITIES, "spec_example": SPEC_EXAMPLE}


@server.tool()
def set_spec(spec: dict) -> dict:
    """요구사항을 spec_example과 같은 형식의 사양으로 등록한다. 지원 범위 밖이거나 값이 빠지면 거절(ok=false)."""
    return quiet(project.set_spec, spec)


@server.tool()
def analyze(base_t: float, arm_t: float, r_in: float, mesh_mm: float = 4.0) -> dict:
    """설계 하나를 모델 재생성·형상 검증·구조해석하고 사양 기준으로 판정한다 (1회 약 15~25초)."""
    return quiet(project.analyze, base_t, arm_t, r_in, mesh_mm)


@server.tool()
def optimize(x0_base_t: float, x0_arm_t: float, x0_r_in: float, maxfev: int = 40) -> dict:
    """x0에서 출발해 기준을 만족하는 최경량 설계를 찾는다(COBYQA → 판재 규격 → 요소 3 mm 재검증, 5~10분)."""
    return quiet(project.optimize, x0_base_t, x0_arm_t, x0_r_in, maxfev)


@server.tool()
def export_final(base_t: float, arm_t: float, r_in: float) -> dict:
    """최종 설계를 요소 3 mm로 상세 해석하고, 합격일 때만 FCStd·STEP·STL·응력 그림을 만든다. 불합격이면 파일 없이 거절(ok=false)."""
    return quiet(project.export_final, base_t, arm_t, r_in)


@server.tool()
def write_report(ai_summary: str) -> dict:
    """합격한 최종 산출물의 검증 보고서(report.md)를 만든다. ai_summary는 4~6문장 요약이며, 도구 결과에 있는 숫자만 쓸 수 있다."""
    return quiet(project.write_report, ai_summary)


if __name__ == "__main__":
    server.run()          # stdio
