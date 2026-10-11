"""06-1 통합 CAD·CAE 에이전트 (실행 위치 (3)).

GPT-6 Astra가 MCP 서버(ch06/cae_mcp_server.py)의 도구 6개와 ask_user(사용자에게 묻기)를 골라 부르며
요구사항 → 사양 → 초기 해석 → 최적화 → 산출물 → 보고서까지 진행한다. 계산·판정은 전부 도구가 한다.

사용 (저장소 루트에서):
  python ch06/agent.py --request "요구사항 문장"                     # 질문이 나오면 직접 답한다
  python ch06/agent.py --request-file 요청.txt --answers 답변.json --project output/ch06/run1
"""
import argparse
import asyncio
import json
import os
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

MAX_STEPS = 30                  # LLM 호출 상한 — 무한 반복과 비용 폭주 방지
PRICE_IN, PRICE_OUT = 10e-6, 50e-6     # GPT-6 Astra 정가 기준 달러/토큰 (01-2)
SYSTEM = """CAD·CAE 도구로 L자 브래킷을 설계하는 AI 설계 엔지니어입니다.
작업 순서: get_capabilities → 요구사항을 사양으로 정리해 set_spec → 초기 설계 analyze → 결과를 보고 최적화 출발점 결정 → optimize
→ export_final(최종 설계) → write_report → 사용자에게 최종 보고.
규칙:
- 치수·구멍 위치·하중 크기와 방향·구속 조건·재료·판정 기준·초기 두께가 요구사항에 분명하지 않으면 추측하지 말고 ask_user로 물으세요. 질문은 한 번에 모아서 하세요.
- 지원 범위 밖 요구(다른 부품 유형·재료·하중 방향 등)는 비슷한 것으로 바꿔 진행하지 말고, 무엇이 지원되지 않는지 알린 뒤 멈추세요.
- 응력·처짐·질량·안전율을 직접 계산하거나 예측하지 마세요. 숫자는 도구 결과에서만 인용하세요.
- 도구가 ok=false를 돌려주면 detail과 hint를 읽고 고쳐 다시 시도하세요. 같은 도구가 두 번 연속 실패하면 멈추고 보고하세요.
- set_spec이 기본값을 적용했다면(applied_defaults) 최종 보고에 밝히세요.
- 최종 보고는 5줄 이내: 최종 설계, 판정, 질량 변화, 산출물 폴더, 사람이 검토할 점."""
ASK_USER = {"type": "function", "function": {
    "name": "ask_user", "description": "요구사항에서 확정할 수 없는 조건을 사용자에게 묻는다. 답을 받을 때까지 다른 도구를 부르지 않는다.",
    "parameters": {"type": "object", "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
                   "required": ["questions"]}}}


def to_openai(tool):
    return {"type": "function", "function": {"name": tool.name, "description": tool.description or "",
                                             "parameters": tool.input_schema}}


def text_of(result):
    return "\n".join(getattr(c, "text", "") for c in result.content)


async def run(request, answers, project, log):
    client, model = OpenAI(), os.environ.get("OPENAI_MODEL", "gpt-6-astra")
    server = StdioServerParameters(command=sys.executable, args=[str(ROOT / "ch06" / "cae_mcp_server.py")],
                                   env={**os.environ, "CAE_PROJECT_DIR": str(project), "PYTHONUTF8": "1"})
    stats = {"llm_calls": 0, "tokens_in": 0, "tokens_out": 0, "tool_calls": {}, "tool_errors": 0, "questions": 0}
    t0 = time.time()
    async with stdio_client(server) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = [to_openai(t) for t in (await session.list_tools()).tools] + [ASK_USER]
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": request}]
            final = None
            for step in range(1, MAX_STEPS + 1):
                resp = client.chat.completions.create(model=model, messages=messages, tools=tools)
                stats["llm_calls"] += 1
                stats["tokens_in"] += resp.usage.prompt_tokens
                stats["tokens_out"] += resp.usage.completion_tokens
                msg = resp.choices[0].message
                messages.append(msg.model_dump(exclude_none=True))
                if not msg.tool_calls:
                    final = msg.content or ""
                    log(f"[{step}] 최종 보고\n{final}")
                    break
                for tc in msg.tool_calls:
                    name, args = tc.function.name, json.loads(tc.function.arguments or "{}")
                    stats["tool_calls"][name] = stats["tool_calls"].get(name, 0) + 1
                    t = time.time()
                    if name == "ask_user":                      # 사용자에게 묻는 도구는 에이전트 쪽에서 처리
                        stats["questions"] += len(args["questions"])
                        for q in args["questions"]:
                            log(f"   질문: {q}")
                        reply = answers.pop(0) if answers is not None and answers else (
                            "추가로 드릴 답이 없습니다. 확정할 수 없으면 작업을 멈추고 보고하세요." if answers is not None
                            else input("답변> "))
                        log(f"   답변: {reply}")
                        out = json.dumps({"answer": reply}, ensure_ascii=False)
                    else:
                        out = text_of(await session.call_tool(name, args, read_timeout_seconds=1800))
                    stats["tool_errors"] += '"ok": false' in out
                    shown = json.dumps(args, ensure_ascii=False)
                    log(f"[{step}] {name} {shown[:150]}{'…' if len(shown) > 150 else ''} ({time.time() - t:.0f}초)\n"
                        f"    → {out[:300]}{'…' if len(out) > 300 else ''}")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": out[:6000]})
            stats["minutes"] = round((time.time() - t0) / 60, 1)
            stats["cost_usd"] = round(stats["tokens_in"] * PRICE_IN + stats["tokens_out"] * PRICE_OUT, 3)
            stats["finished"] = final is not None
            return final, stats, messages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request")
    ap.add_argument("--request-file")
    ap.add_argument("--answers", help="ask_user 질문에 차례로 쓸 답변(JSON 배열 파일). 없으면 직접 입력")
    ap.add_argument("--project", default=str(ROOT / "output" / "ch06" / "project"))
    a = ap.parse_args()
    request = a.request or Path(a.request_file).read_text(encoding="utf-8").strip()
    answers = json.loads(Path(a.answers).read_text(encoding="utf-8")) if a.answers else None
    project = Path(a.project)
    project.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(s):
        lines.append(s)
        print(s, flush=True)

    log(f"요청: {request}")
    final, stats, messages = asyncio.run(run(request, answers, project, log))
    log(f"\n통계: {json.dumps(stats, ensure_ascii=False)}")
    (project / "agent_log.txt").write_text("\n".join(lines), encoding="utf-8")
    (project / "agent_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    (project / "messages.json").write_text(json.dumps(messages, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
