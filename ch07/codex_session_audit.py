"""07-2 Codex 세션 기록 감사 — 화면 조작만 했는지 코드로 확인한다 (실행 위치 (3)).

Codex 앱은 세션마다 rollout-*.jsonl 기록을 남긴다(Windows: 사용자 폴더의 .codex/sessions/연/월/일/).
이 스크립트는 기록에서 (1) 시간·토큰, (2) 화면 조작 동작 종류별 횟수, (3) 셸 명령과 그 분류,
(4) 입력한 텍스트 전부, (5) FreeCAD를 스크립트로 건드린 흔적을 뽑는다. 출력의 사용자 폴더 이름은 가린다.

사용: python ch07/codex_session_audit.py <rollout.jsonl> [...]
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_HINT = re.compile(r"freecadcmd|FreeCADGui|import FreeCAD|\.FCMacro|Gui\.runCommand|App\.ActiveDocument", re.I)


def clean(s):
    """JSON 안의 JS 문자열이라 겹친 역슬래시를 하나로 줄이고, 사용자 폴더 이름을 가린다"""
    while "\\\\" in s:
        s = s.replace("\\\\", "\\")
    return re.sub(r"(Users[\\/]+)[^\\/'\"]+", r"\1<user>", s)


def audit(path):
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    stamps = [datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")) for r in rows if r.get("timestamp")]
    model, usage, cells = None, None, 0
    actions, shells, typed, script_hits = {}, [], [], []
    for r in rows:
        p = r.get("payload") or {}
        if r.get("type") == "turn_context" and not model:
            model = p.get("model")
        if p.get("type") == "token_count":
            usage = (p.get("info") or {}).get("total_token_usage") or usage
        if p.get("type") not in ("function_call", "custom_tool_call"):
            continue
        cells += 1
        code = p.get("arguments") or p.get("input") or ""
        code = code if isinstance(code, str) else json.dumps(code, ensure_ascii=False)
        for act in re.findall(r"sky\.([a-z_]+)\(", code):                 # 화면 조작 동작
            actions[act] = actions.get(act, 0) + 1
        for cmd in re.findall(r"exec_command\(\{cmd:\s*\"((?:[^\"\\]|\\.)*)\"", code):      # 셸 명령
            kind = "문서 읽기" if cmd.startswith("Get-Content") and ".codex" in cmd else "기타 셸"
            shells.append({"kind": kind, "cmd": clean(cmd)[:120]})
        typed += [clean(t) for t in re.findall(r"type_text\(\{[^}]*?text:\s*'((?:[^'\\]|\\.)*)'", code)]
        if SCRIPT_HINT.search(code):
            script_hits.append(clean(code)[:160])
    u = usage or {}
    return {"file": Path(path).name, "model": model,
            "minutes": round((stamps[-1] - stamps[0]).total_seconds() / 60, 1) if stamps else None,
            "code_cells": cells, "screen_actions": dict(sorted(actions.items(), key=lambda kv: -kv[1])),
            "input_tokens": u.get("input_tokens"), "cached_pct": round(100 * u.get("cached_input_tokens", 0) / u["input_tokens"])
            if u.get("input_tokens") else None, "output_tokens": u.get("output_tokens"),
            "shell": shells, "typed_text": typed, "freecad_script_suspects": script_hits}


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(json.dumps(audit(f), ensure_ascii=False, indent=1))
