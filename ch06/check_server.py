"""06-1 MCP 서버 점검 — LLM 없이 도구 목록을 받고, 순서를 어긴 호출이 어떻게 돌아오는지 본다 (실행 위치 (3)).

사용 (저장소 루트에서): python ch06/check_server.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


async def main():
    server = StdioServerParameters(command=sys.executable, args=[str(ROOT / "ch06" / "cae_mcp_server.py")],
                                   env={**os.environ, "CAE_PROJECT_DIR": str(ROOT / "output" / "ch06" / "check"),
                                        "PYTHONUTF8": "1"})
    async with stdio_client(server) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            for t in (await session.list_tools()).tools:
                print(f"{t.name:17s} 입력: {', '.join(t.input_schema.get('properties', {})) or '없음'}")
            res = await session.call_tool("analyze", {"base_t": 8, "arm_t": 8, "r_in": 5})
            print("사양 없이 analyze →", json.dumps(json.loads(res.content[0].text), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
