"""03-1 MCP로 GPT-6 Astra와 FreeCAD 연결하기 (실행 위치 (3)).

freecad-mcp(blwfish/freecad-mcp)의 Headless 서버를 띄우고, MCP 브리지에 연결해 도구 목록을 받은 뒤,
GPT-6 Astra가 도구를 호출하며 플레이트를 만들게 한다. 결과는 코드로 다시 검증한다.

준비: git clone https://github.com/blwfish/freecad-mcp.git  → .env에 FREECAD_MCP_DIR=클론 경로
      pip install -r <FREECAD_MCP_DIR>/requirements.txt
사용 (저장소 루트에서): python ch03/mcp_agent.py
"""
import asyncio
import json
import math
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from openai import OpenAI  # noqa: E402
from common.freecad_runner import find_freecadcmd  # noqa: E402

MCP_DIR = Path(os.environ["FREECAD_MCP_DIR"])
PORT = int(os.environ.get("FREECAD_MCP_PORT", "23456"))      # Windows에서 Headless 서버가 듣는 TCP 포트
ALLOWED = ["check_freecad_connection", "view_control", "part_operations", "execute_python"]   # 필요한 도구만 넘긴다
MAX_STEPS = 20
DOC = "AgentPlate"

SYSTEM = f"""FreeCAD를 MCP 도구로 다루는 CAD 에이전트입니다.
- 먼저 check_freecad_connection, 그다음 view_control(operation="create_document", name="{DOC}")로 문서를 만드세요.
- 형상은 가능하면 part_operations 전용 연산을 쓰고, 전용 연산이 없는 작업(필렛 등)만 execute_python으로 처리하세요.
- 이 FreeCAD는 화면이 없는 Headless입니다. ViewObject(색·표시 여부)는 None이므로 건드리지 마세요.
- 도구 인자는 필요한 것만 넣고 나머지는 생략하세요.
- 최종 솔리드 객체 이름은 "Plate"로 하세요. 끝나면 결과 객체의 유효성·부피를 확인하고 한 문단으로 보고하세요."""
PROMPT = ("가로 120mm, 세로 80mm, 두께 6mm의 알루미늄 장착 플레이트를 만들어줘. "
          "네 모서리에서 10mm 떨어진 위치에 직경 6mm의 체결 구멍을 만들고, 모서리에는 R5 필렛을 적용해줘.")
EXPECTED_VOLUME = 120 * 80 * 6 - 4 * math.pi * 9 * 6 - 4 * (25 - math.pi * 25 / 4) * 6

CHECK = f"""import FreeCAD, Part
s = FreeCAD.getDocument('{DOC}').getObject('Plate').Shape
holes = [f for f in s.Faces if isinstance(f.Surface, Part.Cylinder) and abs(f.Surface.Radius - 3) < 1e-6]
result = {{'valid': s.isValid(), 'solids': len(s.Solids), 'volume': round(s.Volume, 2),
          'holes': sorted((round(f.Surface.Center.x, 2), round(f.Surface.Center.y, 2)) for f in holes)}}"""


LIST = f"import FreeCAD\nresult = [(o.Name, o.Label, o.TypeId) for o in FreeCAD.getDocument('{DOC}').Objects]"


def start_headless_server():
    """freecadcmd로 freecad-mcp의 Headless 서버를 띄우고 포트가 열릴 때까지 기다린다."""
    proc = subprocess.Popen([str(find_freecadcmd()), str(MCP_DIR / "AICopilot" / "headless_server.py")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=1).close()
            return proc
        except OSError:
            time.sleep(1)
    proc.kill()
    raise RuntimeError("Headless 서버가 열리지 않았습니다")


def to_openai(tool):
    return {"type": "function", "function": {"name": tool.name, "description": (tool.description or "")[:1500],
                                             "parameters": tool.input_schema}}


def text_of(result):
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def run_agent():
    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
    bridge = StdioServerParameters(command=sys.executable, args=[str(MCP_DIR / "freecad_mcp_server.py")],
                                   env={**os.environ, "PYTHONUTF8": "1"})     # 브리지 로그의 특수문자 대비
    async with stdio_client(bridge) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            all_tools = (await session.list_tools()).tools
            tools = [to_openai(t) for t in all_tools if t.name in ALLOWED]
            print(f"MCP 도구 {len(all_tools)}개 중 {len(tools)}개 사용, 스키마 {len(json.dumps(tools))}자")
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": PROMPT}]
            usage, calls, errors, t0 = [0, 0], 0, 0, time.time()
            for step in range(MAX_STEPS):
                resp = client.chat.completions.create(model=model, messages=messages, tools=tools)
                usage[0] += resp.usage.prompt_tokens
                usage[1] += resp.usage.completion_tokens
                msg = resp.choices[0].message
                messages.append(msg.model_dump(exclude_none=True))
                if not msg.tool_calls:
                    print("에이전트 보고:", (msg.content or "")[:300])
                    break
                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    args = {k: v for k, v in args.items() if v not in ("", [], {}, None)}   # 빈 인자 제거
                    out = text_of(await session.call_tool(tc.function.name, args))
                    calls += 1
                    errors += out.lstrip().startswith('{"error"')
                    print(f"  [{step}] {tc.function.name} {json.dumps(args, ensure_ascii=False)[:90]} → {out[:80]!r}")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": out[:4000]})
            check = json.loads(text_of(await session.call_tool("execute_python", {"code": CHECK})))
            if "result" in check:
                print(f"독립 검증: {check['result']}\n기대 부피: {EXPECTED_VOLUME:.2f}")
            else:                                       # Plate가 없거나 검사 코드가 실패한 경우 — 원인을 보여 준다
                names = text_of(await session.call_tool("execute_python", {"code": LIST}))
                print("독립 검증 실패:", check.get("error", check), "| 문서 객체:", names[:300])
            print(f"도구 호출 {calls}회(오류 {errors}), {time.time() - t0:.1f}초, 토큰 {usage[0]}/{usage[1]}, "
                  f"비용 약 ${usage[0] * 10e-6 + usage[1] * 50e-6:.2f}")


if __name__ == "__main__":
    server = start_headless_server()
    try:
        asyncio.run(run_agent())
    finally:
        server.kill()      # execute_python이 열려 있는 서버를 남겨 두지 않는다
