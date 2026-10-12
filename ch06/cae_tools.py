"""06-1 통합 CAD·CAE 도구 (실행 위치 (3)).

02~05장에서 만든 모듈을 에이전트가 부를 수 있는 도구 함수로 묶는다. 모든 도구는
(1) 예외 대신 {"ok": False, "stage", "detail", "hint"}를 돌려주고, (2) 결과를 프로젝트 폴더의 state.json에 남긴다.
계산·판정은 전부 여기(코드·FreeCAD·CalculiX)서 하고, AI는 도구를 고르고 결과를 해석한다.
"""
import json
import math
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common.freecad_runner import run_freecad, tagged_line  # noqa: E402
from ch05.evaluate import evaluate  # noqa: E402
from ch05.optimize import FILLET_R, optimize as run_optimize  # noqa: E402

DENSITY = 2.70e-3        # g/mm³ — 04-4 bracket_fem.py와 같은 재료(Al 6061-T6)만 지원
CAPABILITIES = {
    "part_types": ["l_bracket (02장 파라메트릭 L자 브래킷: 바닥판 + 바닥판 끝 바깥쪽 세로판, 구멍 4개)"],
    "materials": ["Al6061-T6 (E 68,900 MPa, 항복 276 MPa, 밀도 2.70 g/cm³)"],
    "load": "세로판 윗면(arm_top) 전체에 고르게 분포, 방향은 away_from_base(바닥판 반대쪽, −X)만",
    "fixture": ["bolt_holes (볼트 구멍 4개 내면 고정, 보수적)", "base_bottom (바닥면 전체 고정)"],
    "variables": "base_t, arm_t, r_in (나머지 치수는 요구사항 값으로 고정)",
    "defaults_if_missing": {"variable_ranges_mm": {"base_t": [3, 10], "arm_t": [3, 10], "r_in": [2, 8]},
                            "stock_thickness_mm": [3, 4, 5, 6, 8, 10], "outer_corner_fillet_mm": 5},
    "must_be_given_by_user": ["치수", "구멍 위치", "하중 크기·방향", "구속 조건", "재료", "판정 기준", "초기 두께·필렛"],
}
SPEC_EXAMPLE = {
    "part_type": "l_bracket", "material": "Al6061-T6",
    "base": {"length_mm": 120, "width_mm": 80}, "arm": {"height_from_base_bottom_mm": 80},
    "holes": {"diameter_mm": 6, "x1_from_arm_inner_face_mm": 25, "x2_from_base_end_mm": 10, "y_from_long_edge_mm": 10},
    "load": {"force_N": 200, "face": "arm_top", "direction": "away_from_base"}, "fixture": "bolt_holes",
    "criteria": {"safety_factor_min": 2.0, "max_deflection_mm": 0.5},
    "initial": {"base_t": 8, "arm_t": 8, "r_in": 5}, "outer_corner_fillet_mm": 5,
    "variable_ranges_mm": {"base_t": [3, 10], "arm_t": [3, 10], "r_in": [2, 8]}, "stock_thickness_mm": [3, 4, 5, 6, 8, 10],
}


REQUIRED_NUMBERS = ["base.length_mm", "base.width_mm", "arm.height_from_base_bottom_mm", "holes.diameter_mm",
                    "holes.x1_from_arm_inner_face_mm", "holes.x2_from_base_end_mm", "holes.y_from_long_edge_mm",
                    "load.force_N", "criteria.safety_factor_min", "criteria.max_deflection_mm",
                    "initial.base_t", "initial.arm_t", "initial.r_in"]
_MISSING = object()


class _Stop(Exception):
    """검사를 더 진행할 수 없을 때 (이미 모은 오류로 거절)"""


def _get(d, path):
    for key in path.split("."):
        if not isinstance(d, dict) or key not in d:
            return _MISSING
        d = d[key]
    return d


def _positive(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def fail(stage, detail, hint=""):
    return {"ok": False, "stage": stage, "detail": detail, "hint": hint}


class Project:
    """한 설계 프로젝트의 상태. 도구 호출 결과가 state.json에 쌓인다 (에이전트가 죽어도 이어서 볼 수 있게)."""

    def __init__(self, folder):
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        f = self.dir / "state.json"
        self.state = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"spec": None, "events": []}

    def save(self, event, data):
        self.state["events"].append({"time": time.strftime("%H:%M:%S"), "event": event, **data})
        (self.dir / "state.json").write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ 1. 사양
    def set_spec(self, spec):
        """사양을 검사해 저장한다. 지원 범위 밖이거나 빠진 값이 있으면 거절한다 (추측해서 채우지 않는다)."""
        errors, applied = [], []
        try:
            if spec.get("part_type") != "l_bracket":
                errors.append(f"지원하지 않는 부품 유형: {spec.get('part_type')} (l_bracket만 지원)")
            if spec.get("material") != "Al6061-T6":
                errors.append(f"지원하지 않는 재료: {spec.get('material')} (Al6061-T6만 지원)")
            ld = spec["load"]
            if ld.get("face") != "arm_top" or ld.get("direction") != "away_from_base":
                errors.append("하중은 세로판 윗면(arm_top), 바닥판 반대쪽(away_from_base)만 지원")
            if spec.get("fixture") not in ("bolt_holes", "base_bottom"):
                errors.append("구속은 bolt_holes 또는 base_bottom만 지원")
            n_before = len(errors)
            for path in REQUIRED_NUMBERS:                      # 빠진 값·잘못된 값은 추측하지 않고 거절
                v = _get(spec, path)
                if v is _MISSING:
                    errors.append(f"필수 항목 없음: {path} — 사용자에게 물으세요")
                elif not _positive(v):
                    errors.append(f"{path}={v!r}: 유한한 양수여야 함")
            if "variable_ranges_mm" not in spec:
                spec["variable_ranges_mm"] = CAPABILITIES["defaults_if_missing"]["variable_ranges_mm"]
                applied.append("variable_ranges_mm 기본값")
            if "stock_thickness_mm" not in spec:
                spec["stock_thickness_mm"] = CAPABILITIES["defaults_if_missing"]["stock_thickness_mm"]
                applied.append("stock_thickness_mm 기본값")
            if "outer_corner_fillet_mm" not in spec:
                spec["outer_corner_fillet_mm"] = CAPABILITIES["defaults_if_missing"]["outer_corner_fillet_mm"]
                applied.append("outer_corner_fillet_mm 기본값")
            if not _positive(spec["outer_corner_fillet_mm"]):
                errors.append(f"outer_corner_fillet_mm={spec['outer_corner_fillet_mm']!r}: 유한한 양수여야 함")
            if len(errors) > n_before:                          # 숫자가 빠지거나 틀리면 아래의 관계 검사는 의미가 없다
                raise _Stop
            n_before = len(errors)
            rng, init, h = spec["variable_ranges_mm"], spec["initial"], spec["holes"]
            for k in ("base_t", "arm_t", "r_in"):
                r = rng.get(k) if isinstance(rng, dict) else None
                if not (isinstance(r, list) and len(r) == 2 and all(_positive(x) for x in r) and r[0] < r[1]):
                    errors.append(f"variable_ranges_mm.{k}={r!r}: [최소, 최대] 두 양수, 최소 < 최대")
                elif not r[0] <= init[k] <= r[1]:
                    errors.append(f"초기값 {k}={init[k]}이 범위 {r} 밖")
            stock = spec["stock_thickness_mm"]
            if not (isinstance(stock, list) and stock and all(_positive(x) for x in stock)):
                errors.append(f"stock_thickness_mm={stock!r}: 양수 목록이어야 함")
            if len(errors) > n_before:
                raise _Stop
            if rng["r_in"][1] > max(FILLET_R):
                errors.append(f"r_in 상한은 {max(FILLET_R)} mm 이하 (표준 필렛 반경 목록)")
            if h["x1_from_arm_inner_face_mm"] - h["diameter_mm"] / 2 <= rng["r_in"][1]:
                errors.append("세로판 쪽 구멍이 필렛 최대 반경과 겹침")
            if spec["base"]["length_mm"] - h["x2_from_base_end_mm"] <= h["x1_from_arm_inner_face_mm"]:
                errors.append("끝단 쪽 구멍이 세로판 쪽 구멍보다 안쪽에 있음")
        except _Stop:
            pass
        except (KeyError, TypeError, AttributeError, IndexError, ValueError) as e:
            errors.append(f"형식 오류: {e!r} — get_capabilities의 spec_example 형식을 따르세요")
        if errors:
            return fail("spec", errors, "지원 범위 밖이면 사용자에게 알리고, 값이 빠졌으면 사용자에게 물으세요")
        self.state["spec"] = spec
        self.save("set_spec", {"applied_defaults": applied})
        return {"ok": True, "applied_defaults": applied, "fixed_params": self.fixed()}

    def fixed(self):
        """사양 → 최적화하지 않는 02장 설계 변수"""
        s = self.state["spec"]
        return {"base_len": s["base"]["length_mm"], "width": s["base"]["width_mm"],
                "arm_h": s["arm"]["height_from_base_bottom_mm"], "r_corner": s["outer_corner_fillet_mm"],
                "hole_d": s["holes"]["diameter_mm"], "hole_x1": s["holes"]["x1_from_arm_inner_face_mm"],
                "hole_x2": s["base"]["length_mm"] - s["holes"]["x2_from_base_end_mm"],
                "hole_y": s["holes"]["y_from_long_edge_mm"]}

    def load(self):
        s = self.state["spec"]
        return {"LOAD_N": str(float(s["load"]["force_N"])), "FIX": {"bolt_holes": "holes", "base_bottom": "bottom"}[s["fixture"]]}

    def judge(self, r):
        c = self.state["spec"]["criteria"]
        return r["safety_factor"] >= c["safety_factor_min"] and r["u_max_mm"] <= c["max_deflection_mm"]

    # ------------------------------------------------------------------ 2. 모델·해석
    def analyze(self, base_t, arm_t, r_in, mesh=4.0):
        """모델 재생성 → 형상 검증 → 해석 → 사양 기준으로 판정 (05-2 evaluate)"""
        if not self.state["spec"]:
            return fail("order", "사양이 없습니다", "먼저 set_spec")
        x = {"base_t": base_t, "arm_t": arm_t, "r_in": r_in}
        r = evaluate({**self.fixed(), **x}, mesh=mesh, tag="ch06", load=self.load())
        if not r["ok"]:
            out = fail(r["error"]["stage"], r["error"]["detail"],
                       "geometry: 치수끼리 간섭(필렛·구멍) 여부 확인 / solve: 요소 크기를 바꿔 재시도")
        else:
            out = {"ok": True, "design": x, "mesh_mm": mesh, "mass_g": r["mass_g"], "vm_max_MPa": r["vm_max_MPa"],
                   "safety_factor": r["safety_factor"], "u_max_mm": r["u_max_mm"], "pass": self.judge(r),
                   "note": "최대 응력은 고정 경계(볼트 구멍 가장자리)에 생기며 메시에 민감함 (04-5)"}
        self.save("analyze", {"result": out})
        return out

    def optimize(self, x0_base_t, x0_arm_t, x0_r_in, maxfev=40):
        """질량 최소화 (05-3). 긴 이력은 state.json에만 두고, 에이전트에는 요약만 돌려준다 (토큰 절약)."""
        s = self.state["spec"]
        if not s:
            return fail("order", "사양이 없습니다", "먼저 set_spec")
        rng = s["variable_ranges_mm"]
        try:
            res = run_optimize([x0_base_t, x0_arm_t, x0_r_in], tag="ch06", maxfev=maxfev,
                               lower=[rng[k][0] for k in ("base_t", "arm_t", "r_in")],
                               upper=[rng[k][1] for k in ("base_t", "arm_t", "r_in")],
                               sf_min=s["criteria"]["safety_factor_min"], u_max=s["criteria"]["max_deflection_mm"],
                               stock=sorted(s["stock_thickness_mm"]), fixed=self.fixed(), load=self.load())
        except ValueError as e:                     # 합격점이나 합격 규격 후보가 하나도 없을 때
            out = fail("optimize", str(e), "기준을 만족하는 설계가 범위 안에 없음. 범위·규격을 넓힐지 사용자에게 확인")
            self.save("optimize", {"result": out})
            return out
        pick = lambda r: {k: r.get(k) for k in ("mass_g", "safety_factor", "u_max_mm")}
        var = lambda x: {k: x[k] for k in ("base_t", "arm_t", "r_in")}
        out = {"ok": True, "n_analyses": res["nfev"], "minutes": res["minutes"], "stop_reason": res["message"],
               "continuous_best": {"design": var(res["best"]["x"]), **pick(res["best"])},
               "stock_candidates": [{"design": var(c["x"]), **pick(c), "pass": c["ok"] and self.judge(c)}
                                    for c in res["candidates"]],
               "final_mesh3": {"design": var(res["final"]["x"]), **pick(res["final"]), "pass": res["final_pass"]}}
        self.state["optimization"] = {**out, "history": [{**var(h["x"]), **pick(h)} for h in res["history"] if h["ok"]]}
        self.save("optimize", {"summary": out})
        return out

    # ------------------------------------------------------------------ 3. 산출물
    def export_final(self, base_t, arm_t, r_in):
        """최종 설계의 FCStd·STEP·STL + 요소 3 mm 상세 해석(VTK)·응력 그림을 프로젝트 폴더에 만든다."""
        if not self.state["spec"]:
            return fail("order", "사양이 없습니다", "먼저 set_spec")
        x = {"base_t": base_t, "arm_t": arm_t, "r_in": r_in}
        params = {**self.fixed(), **x}
        cad = self.dir / "cad"
        rc, log = run_freecad(ROOT / "ch02" / "bracket_parametric.py",
                              env={"SET": ";".join(f"{k}={v}" for k, v in params.items()), "REBIND": "1", "OUT_DIR": str(cad)})
        geo = json.loads(tagged_line(log, "REBOUND") or "{}")
        if not geo.get("pass"):
            return fail("geometry", geo.get("failed", log[-200:]), "필렛·구멍 간섭 여부 확인")
        fcstd = self.dir / "bracket.FCStd"
        shutil.copy(cad / "bracket_param.FCStd", fcstd)
        (cad / "export_result.json").unlink(missing_ok=True)
        run_freecad(ROOT / "ch03" / "export_formats.py", env={"SRC": str(fcstd), "OUT_DIR": str(cad)})
        # STL 저장 중 진행 표시가 줄바꿈 없이 EXPORT 줄 앞에 붙는다 → 태그 줄 대신 결과 파일을 읽는다
        exp = json.loads((cad / "export_result.json").read_text(encoding="utf-8"))
        shutil.copy(cad / "bracket.step", self.dir / "bracket.step")
        shutil.copy(cad / "bracket_default.stl", self.dir / "bracket.stl")
        fem = self.dir / "fem"
        rc, log = run_freecad(ROOT / "ch04" / "bracket_fem.py",
                              env={"SRC": str(fcstd), "MESH": "3", "VTK": "1", "OUT_DIR": str(fem), **self.load()})
        line = tagged_line(log, "RESULT")
        if not line:
            return fail("solve", tagged_line(log, "FAIL") or log[-200:], "요소 크기를 바꿔 재시도")
        r = json.loads(line)
        import pyvista as pv                             # PyVista는 그림이 필요할 때만 불러온다
        from ch04.report import render_contour
        render_contour(str(fem / "result.vtk"), str(self.dir / "contour.png"))
        pv.close_all()      # MCP 서버는 도구를 작업 스레드에서 실행한다 — 창을 같은 스레드에서 닫아야 종료 때 OpenGL 오류가 없다
        out = {"ok": True, "design": x, "files": ["bracket.FCStd", "bracket.step", "bracket.stl", "fem/result.json",
                                                  "fem/result.vtk", "contour.png"],
               "step_volume_diff": exp.get("step", {}).get("volume_diff"),
               "mesh3": {"mass_g": r["mass_g"], "vm_max_MPa": r["vm_max_MPa"], "vm_max_at": r["vm_max_at"],
                         "safety_factor": r["safety_factor"], "u_max_mm": r["u_max_mm"], "nodes": r["nodes"],
                         "pass": self.judge(r)}}
        self.state["final"] = out
        self.save("export_final", {"result": out})
        return out

    def write_report(self, ai_summary):
        """보고서는 코드가 state.json으로 쓰고, AI는 요약 문단만 쓴다. 요약 속 숫자가 보고서에 없으면 거절한다."""
        st = self.state
        if not st.get("final"):
            return fail("order", "최종 산출물이 없습니다", "먼저 export_final")
        body = self._report_body()
        nums = lambda s: {float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)}     # 값으로 비교: "2"와 "2.0"은 같은 숫자
        unknown = sorted(nums(ai_summary) - nums(body))
        if unknown:
            return fail("summary", f"보고서에 없는 숫자: {unknown}", "보고서 표에 있는 숫자만 그대로 인용해 다시 쓰세요")
        text = body.replace("{{AI_SUMMARY}}", ai_summary.strip())
        (self.dir / "report.md").write_text(text, encoding="utf-8")
        self.save("write_report", {"chars": len(text)})
        return {"ok": True, "file": "report.md", "chars": len(text)}

    def _report_body(self):
        s, st = self.state["spec"], self.state
        c, f = s["criteria"], st["final"]
        ini = next((e["result"] for e in st["events"] if e["event"] == "analyze" and e["result"].get("ok")
                    and e["result"]["design"] == s["initial"]), None)
        rows = []
        if ini:
            rows.append(("초기 설계 (요소 4 mm)", ini["design"], ini))
        if st.get("optimization"):
            o = st["optimization"]
            rows.append(("연속 최적 (요소 4 mm)", o["continuous_best"]["design"], o["continuous_best"]))
            rows += [("판재 규격 후보 (요소 4 mm)", k["design"], k) for k in o["stock_candidates"]]
        rows.append(("최종 설계 (요소 3 mm)", f["design"], f["mesh3"]))
        ok = lambda r: r["safety_factor"] >= c["safety_factor_min"] and r["u_max_mm"] <= c["max_deflection_mm"]
        L = ["# AI 브래킷 설계 검증 보고서", "",
             "> 이 결과는 학습용 공학 검증이며 안전 인증을 대체하지 않습니다. 실무 적용에는 전문가 검토, 설계 규격·제조공차 검토, "
             "필요 시 실물 시험이 필요합니다.", "", "## 요약 (AI 작성, 숫자는 코드가 대조)", "", "{{AI_SUMMARY}}", "",
             "## 1. 요구사항과 해석 조건", "",
             f"- 형상: L자 브래킷, 바닥판 {s['base']['length_mm']}×{s['base']['width_mm']} mm, 세로판 높이 "
             f"{s['arm']['height_from_base_bottom_mm']} mm(바닥면 기준), 구멍 Ø{s['holes']['diameter_mm']} 4개",
             f"- 재료: {s['material']} (항복강도 276 MPa, 밀도 2.70 g/cm³)",
             f"- 하중: 세로판 윗면 {s['load']['force_N']} N, 바닥판 반대쪽",
             f"- 구속: {'볼트 구멍 4개 내면 고정 (벽 접촉 무시, 처짐을 크게 보는 가정)' if s['fixture'] == 'bolt_holes' else '바닥면 전체 고정'}",
             f"- 판정 기준: 안전율 {c['safety_factor_min']} 이상, 최대 처짐 {c['max_deflection_mm']} mm 이하",
             f"- 설계 변수 범위: {s['variable_ranges_mm']}, 판재 두께 규격: {s['stock_thickness_mm']}", "",
             "## 2. 설계 비교", "", "| 단계 | 바닥판 / 세로판 / 필렛 (mm) | 질량 (g) | 안전율 | 최대 처짐 (mm) | 판정 |",
             "|---|---|---|---|---|---|"]
        L += [f"| {n} | {d['base_t']} / {d['arm_t']} / R{d['r_in']} | {r['mass_g']} | {r['safety_factor']} | {r['u_max_mm']} | "
              f"{'합격' if ok(r) else '불합격'} |" for n, d, r in rows]
        if ini:
            L += ["", f"질량 변화: {ini['mass_g']} g → {f['mesh3']['mass_g']} g "
                      f"({(f['mesh3']['mass_g'] / ini['mass_g'] - 1) * 100:.1f}%)"]
        if st.get("optimization"):
            o = st["optimization"]
            L += ["", f"최적화: SciPy COBYQA, 해석 {o['n_analyses']}회, {o['minutes']}분, 종료 사유: {o['stop_reason']}"]
        L += ["", "## 3. 최종 설계 상세 (요소 3 mm)", "", f"- 절점 {f['mesh3']['nodes']}개, 최대 von Mises 응력 "
              f"{f['mesh3']['vm_max_MPa']} MPa (위치 {f['mesh3']['vm_max_at']}, 고정 경계)", "",
              "![von Mises 응력 분포](contour.png)", "",
              "## 4. 산출물", ""] + [f"- {x}" for x in f["files"]] + ["- state.json (사양·모든 도구 호출 이력)", "",
              "## 5. 가정과 한계", "",
              "- 선형 정적 해석, 볼트 체결·접촉·예압 미반영, 정적 하중 하나만 고려(피로·충격·온도 제외).",
              "- 최대 응력은 고정 경계에 생겨 메시에 따라 달라집니다(04-5). 제조 공차와 재료 편차는 반영하지 않았습니다.",
              "- 최종 채택 전 전문가 검토와 필요 시 실물 시험이 필요합니다."]
        return "\n".join(L) + "\n"
