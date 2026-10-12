"""부록 A 로컬 LLM과 GPT-6 Astra 비교 — 책의 예제를 같은 조건으로 반복 실행해 표로 정리한다 (실행 위치 (3)).

모델은 환경변수로 바꾼다. 코드는 그대로다.
  GPT-6 Astra : OPENAI_API_KEY만 설정 (.env)
  로컬 LLM    : OPENAI_BASE_URL=http://localhost:11434/v1  OPENAI_API_KEY=ollama  OPENAI_MODEL=qwen3.8:27b

사용 (저장소 루트에서):
  python appendix_a/benchmark.py --tag astra --runs 3
  python appendix_a/benchmark.py --tag qwen --runs 3
  python appendix_a/benchmark.py --report astra qwen          # 두 결과를 비교표로
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "appendix_a"
TASKS = {   # 이름: (책 위치, 명령 인자)
    "plate": ("01-3 플레이트 코드 생성", ["ch01/make_plate.py"]),
    "bracket": ("02-4 생성→검증→수정 (좌표 명시)", ["ch02/generate_bracket.py"]),
    "bracket_verbal": ("02-4 생성→검증→수정 (말로만)", ["ch02/generate_bracket.py", "--verbal"]),
    "spec": ("03-2 사양 정리·되묻기", ["ch03/design_agent.py", "--answers", "ch03/answers.json"]),
    "review": ("05-1 해석 결과 검토", ["ch05/review.py"]),
}


def parse(task, out):
    """예제가 출력한 줄에서 합격 여부·토큰·횟수를 읽는다"""
    nums = lambda pat: [int(x) for x in re.findall(pat, out)]
    tin = sum(nums(r"토큰 입력 (\d+)")) + sum(nums(r"AI 토큰 (\d+)/"))
    tout = sum(nums(r"·출력 (\d+)")) + sum(nums(r"AI 토큰 \d+/(\d+)"))
    r = {"tokens_in": tin, "tokens_out": tout}
    if task == "plate":
        r["pass"] = "판정: 합격" in out
    elif task.startswith("bracket"):
        rounds = re.findall(r"\[(\d+)회차\].*?→ (합격|불합격|실행 실패)", out)
        r.update(rounds=len(rounds), first_pass=bool(rounds) and rounds[0][1] == "합격",
                 **{"pass": bool(rounds) and rounds[-1][1] == "합격"})
    elif task == "spec":
        r.update(turns=len(re.findall(r"^\[\d+턴", out, re.M)), questions=len(re.findall(r"^  질문:", out, re.M)),
                 **{"pass": "검증: 합격" in out})
    elif task == "review":
        m = re.search(r"입력에 없는 숫자: (.*)", out)
        props = re.findall(r"^제안 .*", out, re.M)
        r.update(invented_numbers=(m.group(1) if m else "파싱 실패"), proposals=len(props),
                 proposals_pass=sum("합격" in p and "불합격" not in p for p in props),
                 rejected=sum("거절" in p for p in props),
                 **{"pass": bool(m) and m.group(1) == "없음" and len(props) > 0})
    return r


def run(tag, runs, only):
    model = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
    rows_file = OUT / tag / "results.json"
    rows = json.loads(rows_file.read_text(encoding="utf-8")) if rows_file.exists() else []
    for task, (title, args) in TASKS.items():
        if only and task not in only:
            continue
        for i in range(1, runs + 1):
            folder = OUT / tag / f"{task}_{i}"
            folder.mkdir(parents=True, exist_ok=True)
            extra = ["--out", str(folder)] if task != "review" else []
            t = time.time()
            p = subprocess.run([sys.executable, "-u", *args, *extra], cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            sec = round(time.time() - t, 1)
            (folder / "stdout.txt").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr[-4000:], encoding="utf-8")
            row = {"task": task, "title": title, "run": i, "model": model, "sec": sec, "rc": p.returncode, **parse(task, p.stdout)}
            rows = [r for r in rows if not (r["task"] == task and r["run"] == i)] + [row]
            rows_file.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps(row, ensure_ascii=False), flush=True)


def report(tags):
    data = {t: json.loads((OUT / t / "results.json").read_text(encoding="utf-8")) for t in tags}
    print("| 과제 | " + " | ".join(f"{t} 합격" for t in tags) + " | " + " | ".join(f"{t} 평균 시간" for t in tags) + " |")
    print("|---|" + "---|" * (2 * len(tags)))
    for task, (title, _) in TASKS.items():
        cells, times = [], []
        for t in tags:
            rs = [r for r in data[t] if r["task"] == task]
            cells.append(f"{sum(r['pass'] for r in rs)}/{len(rs)}" if rs else "-")
            times.append(f"{sum(r['sec'] for r in rs) / len(rs):.0f}초" if rs else "-")
        print(f"| {title} | " + " | ".join(cells) + " | " + " | ".join(times) + " |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--report", nargs="*")
    a = ap.parse_args()
    if a.report:
        report(a.report)
    else:
        run(a.tag, a.runs, a.only)
