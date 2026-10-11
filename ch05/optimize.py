"""05-3 강도·처짐·질량 기반 설계 최적화 (실행 위치 (3)).

목적: 질량 최소 / 제약: 안전율 >= 2.0, 최대 처짐 <= 0.5 mm / 변수: 바닥판·세로판 두께, 안쪽 필렛 반경
SciPy COBYQA(미분 불필요)가 설계 변수를 고르고, 05-2의 evaluate()가 매번 모델 재생성·해석·판정을 한다.
연속 최적해를 시판 판재 두께로 맞춘 후보들을 다시 해석하고, 가장 가벼운 합격안을 요소 크기 3 mm로 재검증한다.
06장 에이전트는 optimize()를 기준·고정 치수·해석 조건을 바꿔 부른다.

사용 (저장소 루트에서):
  python ch05/optimize.py                       # 초기 설계 8/8/R5에서 시작
  python ch05/optimize.py --x0 7,7,7 --tag ai   # 05-1 AI 제안에서 시작
"""
import argparse
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
from scipy.optimize import Bounds, NonlinearConstraint, minimize  # noqa: E402
from ch05.evaluate import evaluate  # noqa: E402

NAMES = ["base_t", "arm_t", "r_in"]
LOWER, UPPER = [3, 3, 2], [10, 10, 8]
SF_MIN, U_MAX = 2.0, 0.5
STOCK = [3, 4, 5, 6, 8, 10]          # 시판 알루미늄 판재 두께 (mm)
FILLET_R = [2, 3, 4, 5, 6, 8]        # 도면에 쓸 표준 필렛 반경 (이 책의 가정, mm)
FAILED = {"mass_g": 1e6, "safety_factor": 0.0, "u_max_mm": 1e3}   # 해석 실패는 아주 나쁜 설계로 취급


def optimize(x0, tag="base", maxfev=40, lower=LOWER, upper=UPPER, sf_min=SF_MIN, u_max=U_MAX, stock=STOCK,
             fixed=None, load=None):
    """x0: [바닥판, 세로판, 필렛]. fixed: 최적화하지 않는 치수(06장), load: 해석 조건(06장). 결과 dict를 돌려준다."""
    hist, t0 = [], time.time()
    ok = lambda r: r["ok"] and r["safety_factor"] >= sf_min and r["u_max_mm"] <= u_max     # 판정은 여기서 기준으로
    var = lambda x: {n: x[n] for n in sorted(NAMES)}                                          # 출력엔 설계 변수만
    ev = lambda x, **kw: evaluate({**(fixed or {}), **x}, load=load, **kw)

    def run(x):
        r = ev(dict(zip(NAMES, x)), tag=f"opt-{tag}")
        if not any(h["x"] == r["x"] for h in hist):
            hist.append(r)
            s = " ".join(f"{n}={r['x'][n]:.2f}" for n in NAMES)
            print(f"{len(hist):3d} {s}  " + (f"질량 {r['mass_g']:.1f} g  안전율 {r['safety_factor']:.2f}  처짐 {r['u_max_mm']:.4f}"
                                              f"  {'OK' if ok(r) else '--'}" if r["ok"] else f"실패 {r['error']}"), flush=True)
        return r if r["ok"] else {**r, **FAILED}

    cons = NonlinearConstraint(lambda x: [run(x)["safety_factor"] - sf_min, u_max - run(x)["u_max_mm"]], 0, np.inf)
    res = minimize(lambda x: run(x)["mass_g"], np.array(x0, float), method="COBYQA", bounds=Bounds(lower, upper),
                   constraints=[cons], options={"maxfev": maxfev, "initial_tr_radius": 1.5, "final_tr_radius": 0.05})
    best = min((h for h in hist if ok(h)), key=lambda h: h["mass_g"])
    minutes = round((time.time() - t0) / 60, 1)
    print(f"\nCOBYQA: {res.message} / 해석 {len(hist)}회 / {minutes}분")
    print(f"연속 최적: {var(best['x'])}  질량 {best['mass_g']} g  안전율 {best['safety_factor']}  처짐 {best['u_max_mm']}")

    # 판재 규격 반영: 각 두께를 바로 아래·바로 위 규격으로 바꾼 모든 조합을 다시 해석 (아래 규격은 제약을 어길 수 있다)
    near = lambda v: [s for s in stock if s <= v + 1e-9][-1:] + [s for s in stock if s > v + 1e-9][:1]
    r_in = min(r for r in FILLET_R if r >= best["x"]["r_in"] - 1e-9)   # 필렛은 올림: 질량 증가는 작고(R5→R7에 1.1 g) 응력·처짐엔 유리
    cands = [ev({"base_t": tb, "arm_t": ta, "r_in": r_in}, tag=f"stock-{tag}")
             for tb, ta in itertools.product(near(best["x"]["base_t"]), near(best["x"]["arm_t"]))]
    start = {n: float(v) for n, v in zip(NAMES, x0)}
    if (start["base_t"] in stock and start["arm_t"] in stock and start["r_in"] in FILLET_R
            and all(var(c["x"]) != var(start) for c in cands)):
        cands.append(ev(start, tag=f"stock-{tag}"))      # 출발점도 규격 설계면 후보로 — 결과가 출발점보다 나빠지지 않게 (06-3)
    for c in cands:
        print(f"규격 후보 {var(c['x'])}  질량 {c.get('mass_g')} g  안전율 {c.get('safety_factor')}  처짐 {c.get('u_max_mm')}  "
              f"{'합격' if ok(c) else '불합격'}{'  (출발점)' if var(c['x']) == var(start) else ''}")
    chosen = min((c for c in cands if ok(c)), key=lambda c: c["mass_g"])
    final = ev(var(chosen["x"]), mesh=3.0, tag=f"final-{tag}")
    print(f"최종(요소 3 mm): {var(final['x'])}  질량 {final['mass_g']} g  안전율 {final['safety_factor']}  처짐 {final['u_max_mm']}  "
          f"{'합격' if ok(final) else '불합격'}")
    return {"x0": list(x0), "nfev": len(hist), "message": str(res.message), "minutes": minutes, "history": hist,
            "best": best, "candidates": cands, "final": final, "final_pass": ok(final)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x0", default="8,8,5")
    ap.add_argument("--tag", default="base")
    ap.add_argument("--maxfev", type=int, default=40)
    a = ap.parse_args()
    result = optimize([float(v) for v in a.x0.split(",")], a.tag, a.maxfev)
    out = ROOT / "output" / "ch05" / f"optimize_{a.tag}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
