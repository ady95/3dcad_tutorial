"""FreeCAD FEM(Headless) 공용 함수 — freecadcmd 안에서 import (04장 이후).

해석 객체(Analysis) 구성 → Gmsh 메시 → CalculiX 실행 → 결과 추출을 함수로 묶었다.
면은 이름(Face3)이 아니라 조건 함수로 고른다 (02-4의 TNP 교훈).
"""
import FreeCAD as App
import ObjectsFem
import Part
from femmesh.gmshtools import GmshTools
from femtools import ccxtools

AL6061 = {"Name": "Al6061-T6", "YoungsModulus": "68900 MPa", "PoissonRatio": "0.33", "Density": "2700 kg/m^3"}


def face_names(shape, pred):
    return [f"Face{i}" for i, f in enumerate(shape.Faces, 1) if pred(f)]


def edge_along(shape, vec):
    """vec 방향과 나란한 직선 모서리 하나의 이름 — 하중 방향 지정용"""
    for i, e in enumerate(shape.Edges, 1):
        if isinstance(e.Curve, Part.Line):
            d = (e.Vertexes[-1].Point - e.Vertexes[0].Point).normalize()
            if d.isEqual(vec, 1e-9) or d.isEqual(-vec, 1e-9):
                return f"Edge{i}"
    raise RuntimeError("방향 기준 모서리를 찾지 못함")


def build_analysis(doc, obj, fixed_faces, load_faces, force_n, direction, mesh_mm, material=AL6061):
    """해석 컨테이너, 재료, 고정, 하중, 메시 객체를 만든다. direction은 App.Vector(단위 벡터)."""
    an = ObjectsFem.makeAnalysis(doc, "Analysis")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "CalculiX")
    solver.AnalysisType = "static"
    an.addObject(solver)
    mat = ObjectsFem.makeMaterialSolid(doc, "Material")
    m = mat.Material
    m.update(material)
    mat.Material = m
    an.addObject(mat)
    fix = ObjectsFem.makeConstraintFixed(doc, "Fixed")
    fix.References = [(obj, fixed_faces)]
    an.addObject(fix)
    load = ObjectsFem.makeConstraintForce(doc, "Load")
    load.References = [(obj, load_faces)]
    load.Force = f"{force_n} N"
    load.Direction = (obj, [edge_along(obj.Shape, direction)])
    an.addObject(load)
    doc.recompute()
    if load.DirectionVector.dot(direction) < 0:      # 기준 모서리의 방향이 반대면 뒤집는다
        load.Reversed = not load.Reversed
        doc.recompute()
    mesh = ObjectsFem.makeMeshGmsh(doc, "Mesh")
    mesh.Shape = obj
    mesh.CharacteristicLengthMax = f"{mesh_mm} mm"
    mesh.ElementOrder = "2nd"            # 2차 사면체(C3D10): 굽힘을 정확히 표현
    mesh.OptimizeNetgen = True           # 얇은 판의 납작한 요소(sliver) 제거 — nonpositive jacobian 방지
    an.addObject(mesh)
    doc.recompute()
    return an, solver, mesh


def solve(doc, an, solver, mesh, workdir):
    """메시 생성 → ccx 실행 → 결과 객체 반환. 실패하면 None."""
    err = GmshTools(mesh).create_mesh()
    if err:
        print("GMSH:", err, flush=True)
    fea = ccxtools.FemToolsCcx(an, solver)
    fea.purge_results()
    fea.update_objects()
    fea.setup_working_dir(workdir)
    fea.setup_ccx()
    msg = fea.check_prerequisites()
    if msg:
        raise RuntimeError("해석 준비 실패: " + msg)
    fea.write_inp_file()
    fea.ccx_run()
    fea.load_results()
    return next((o for o in doc.Objects if o.isDerivedFrom("Fem::FemResultObject") and o.Mesh), None)


def summarize(res, mesh, fixed_shape_faces=None, exclude_mm=0.0):
    """최대 von Mises 응력(위치), 최대 변위, 고정면에서 exclude_mm 떨어진 곳의 최대 응력"""
    nodes = res.Mesh.FemMesh.Nodes
    ids = list(res.NodeNumbers)
    vm = list(res.vonMises)
    disp = res.DisplacementVectors
    k = max(range(len(vm)), key=vm.__getitem__)
    out = {"nodes": mesh.FemMesh.NodeCount, "elements": mesh.FemMesh.VolumeCount,
           "vm_max_MPa": round(vm[k], 2), "vm_max_at": [round(c, 1) for c in nodes[ids[k]]],
           "u_max_mm": round(max(d.Length for d in disp), 4)}
    if fixed_shape_faces and exclude_mm > 0:
        for j in sorted(range(len(vm)), key=vm.__getitem__, reverse=True)[:3000]:
            v = Part.Vertex(nodes[ids[j]])
            if all(f.distToShape(v)[0] >= exclude_mm for f in fixed_shape_faces):
                out["vm_away_MPa"] = round(vm[j], 2)
                out["vm_away_at"] = [round(c, 1) for c in nodes[ids[j]]]
                break
    return out
