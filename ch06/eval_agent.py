"""06-3 AI 설계 에이전트 성능 평가 (실행 위치 (3)).

ch06/eval_cases.json의 사례마다 06-1 에이전트를 새 프로젝트 폴더에서 실행하고,
기대 행동(complete / ask_then_complete / refuse / report_infeasible)과 실제 행동을 코드로 비교한다.
판정 근거는 에이전트의 말이 아니라 state.json(도구 호출 이력)과 산출물 파일이다.

사용 (저장소 루트에서):
  python ch06/eval_agent.py                 # 전체 (실측 PC에서 약 1시간)
  python ch06/eval_agent.py E6-missing E6b-unanswered     # 일부 사례만 다시 (결과 파일에서 그 사례만 교체)
"""
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ch06.agent import run  # noqa: E402

OUT = Path(os.environ.get("EVAL_OUT", ROOT / "output" / "ch06" / "eval"))     # 부록 A: 모델별로 따로
POC_FULL = ("알루미늄 6061-T6 L자 장착 브래킷을 설계해줘. 바닥판 120×80mm, 세로판은 바닥판 한쪽 끝면 바깥쪽에 붙고 "
            "높이(바닥판 아랫면 기준) 80mm. Ø6 구멍 4개: 세로판 안쪽 면에서 25mm, 반대쪽 끝에서 10mm, 긴 가장자리에서 10mm. "
            "볼트 구멍 4개 내면 고정, 세로판 윗면 전체에 바닥판 반대쪽으로 200N. 안전율 2.0 이상, 최대 처짐 0.5mm 이하에서 "
            "가장 가볍게. 초기안 바닥판·세로판 8mm, 안쪽 필렛 R5. 두께 범위 3~10mm, 필렛 2~8mm, 판재 3·4·5·6·8·10mm, "
            "바깥 모서리 필렛 R5.")


def resolve(v):
    """@파일, @파일#번호, @poc_full 참조를 실제 문자열·목록으로 바꾼다"""
    if isinstance(v, list):
        return [resolve(x) for x in v]
    if v == "@poc_full":
        return POC_FULL
    if isinstance(v, str) and v.startswith("@"):
        path, _, idx = v[1:].partition("#")
        text = (ROOT / path).read_text(encoding="utf-8")
        data = json.loads(text) if path.endswith(".json") else text.strip()
        return data[int(idx)] if idx else data
    return v


def observe(folder, stats):
    """state.json과 산출물로 실제 행동을 판정한다"""
    f = folder / "state.json"
    events = json.loads(f.read_text(encoding="utf-8"))["events"] if f.exists() else []
    ok = lambda name: [e for e in events if e["event"] == name and (e.get("result") or e.get("summary") or {}).get("ok", True)]
    opt_fail = [e for e in events if e["event"] == "optimize" and e.get("result", {}).get("ok") is False]
    final = json.loads(f.read_text(encoding="utf-8")).get("final") if f.exists() else None
    return {"asked": stats["questions"] > 0, "spec_ok": bool(ok("set_spec")), "analyzed": bool(ok("analyze")),
            "optimize_failed": bool(opt_fail), "report": (folder / "report.md").exists(),
            "final_pass": bool(final and final["mesh3"]["pass"]), "final": final and final["design"],
            "final_mass_g": final and final["mesh3"]["mass_g"]}


def behaved(expect, o):
    return {"complete": o["report"] and o["final_pass"],
            "ask_then_complete": o["asked"] and o["report"] and o["final_pass"],
            "refuse": not o["analyzed"] and not o["report"],
            "ask_then_stop": o["asked"] and not o["spec_ok"] and not o["report"],     # 답이 없으면 추측하지 말고 멈춘다
            "report_infeasible": o["optimize_failed"] and not o["report"]}[expect]


def main():
    cases = json.loads((ROOT / "ch06" / "eval_cases.json").read_text(encoding="utf-8"))
    pick = sys.argv[1:]
    res_file = OUT / "eval_results.json"                  # 일부 사례만 다시 돌리면 그 사례만 바꿔 끼운다
    rows = json.loads(res_file.read_text(encoding="utf-8")) if pick and res_file.exists() else []
    for c in cases:
        if pick and c["id"] not in pick:
            continue
        request = resolve(c["request"])
        for a, b in c.get("replace", {}).items():
            assert a in request, f"{c['id']}: 바꿀 문구 없음 {a}"
            request = request.replace(a, b)
        folder = OUT / c["id"]
        folder.mkdir(parents=True, exist_ok=True)
        os.environ["CAE_CACHE_DIR"] = str(folder / "cache")      # 사례끼리 해석 결과를 공유하지 않는다 (시간 측정 공정성)
        lines = []
        log = lambda s: (lines.append(s), print(s, flush=True))
        log(f"\n===== {c['id']} ({c['group']}, 기대: {c['expect']})\n요청: {request}")
        final, stats, _ = asyncio.run(run(request, list(resolve(c["answers"])), folder, log))
        (folder / "agent_log.txt").write_text("\n".join(lines), encoding="utf-8")
        o = observe(folder, stats)
        row = {"id": c["id"], "group": c["group"], "expect": c["expect"], "ok": behaved(c["expect"], o), **o,
               "llm_calls": stats["llm_calls"], "tool_calls": stats["tool_calls"], "tool_errors": stats["tool_errors"],
               "minutes": stats["minutes"], "cost_usd": stats["cost_usd"], "final_message": final}
        rows = [r for r in rows if r["id"] != row["id"]] + [row]
        print("결과:", json.dumps({k: row[k] for k in ("id", "ok", "asked", "report", "final", "final_mass_g", "minutes",
                                                      "cost_usd")}, ensure_ascii=False), flush=True)
        rows.sort(key=lambda r: [c["id"] for c in cases].index(r["id"]))
        res_file.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n기대 행동 일치 {sum(r['ok'] for r in rows)}/{len(rows)}, 총 {sum(r['minutes'] for r in rows):.1f}분, "
          f"${sum(r['cost_usd'] for r in rows):.2f}")


if __name__ == "__main__":
    main()
