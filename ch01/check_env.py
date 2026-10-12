"""01-2 개발환경 확인: Python 패키지, FreeCAD(번들 Gmsh·CalculiX), OpenAI API 연결.

사용: python ch01/check_env.py   (저장소 루트에서, .env 설정 후)
"""
import importlib
import importlib.metadata
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from common.freecad_runner import find_freecadcmd  # noqa: E402

rows = []


def check(name, ok, detail):
    rows.append((name, "OK" if ok else "불가", detail))


# 1. Python
v = sys.version_info
check("Python", (3, 11) <= (v.major, v.minor) < (3, 14), platform.python_version())

# 2. 패키지
for pkg, mod in [("openai", "openai"), ("python-dotenv", "dotenv"), ("numpy", "numpy"), ("scipy", "scipy"),
                 ("matplotlib", "matplotlib"), ("pyvista", "pyvista"), ("gmsh", "gmsh"), ("build123d", "build123d"),
                 ("mcp", "mcp")]:                                   # mcp는 03-1·06장에서 쓴다
    try:
        m = importlib.import_module(mod)
        check(pkg, True, getattr(m, "__version__", None) or importlib.metadata.version(pkg))
    except Exception as e:  # 설치 안 됨, DLL 오류 등
        check(pkg, False, type(e).__name__)

# 3. FreeCAD (Headless)
try:
    fc = find_freecadcmd()
    out = subprocess.run([str(fc), "-c", "import FreeCAD; print('FCVER', '.'.join(FreeCAD.Version()[:3]))"],
                         capture_output=True, text=True, errors="replace", timeout=120).stdout
    ver = next((l.split()[1] for l in out.splitlines() if l.startswith("FCVER")), "?")
    check("FreeCAD (freecadcmd)", ver.startswith("1.1"), ver)
    bin_dir = fc.parent
except Exception as e:
    check("FreeCAD (freecadcmd)", False, str(e))
    bin_dir = None

# 4. 번들 CalculiX·Gmsh (Windows 설치본에 포함. Linux는 PATH에서 찾는다)
import shutil  # noqa: E402

suffix = ".exe" if platform.system() == "Windows" else ""
for name, exe_name, args, key in [("CalculiX (ccx)", "ccx", ["-v"], "Version"), ("Gmsh", "gmsh", ["-version"], "")]:
    bundled = bin_dir / (exe_name + suffix) if bin_dir else None
    exe = bundled if bundled and bundled.exists() else shutil.which(exe_name)
    if exe is None:
        check(name, False, "찾지 못함")
        continue
    out = subprocess.run([str(exe), *args], capture_output=True, text=True, errors="replace", timeout=60)
    text = (out.stdout + out.stderr).strip()
    line = next((l.strip() for l in text.splitlines() if key in l and l.strip()), text.splitlines()[0] if text else "")
    check(name, bool(line), line)

# 5. OpenAI API
try:
    import os
    from openai import OpenAI
    model = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
    r = OpenAI().responses.create(model=model, input="Reply with exactly: OK")
    check("OpenAI API", r.output_text.strip().startswith("OK"),
          f"{model} 응답 '{r.output_text.strip()[:20]}' (토큰 입력 {r.usage.input_tokens}·출력 {r.usage.output_tokens})")
except Exception as e:
    check("OpenAI API", False, f"{type(e).__name__}: {str(e)[:80]}")

w = max(len(r[0]) for r in rows)
for name, st, detail in rows:
    print(f"{name:<{w}}  {st:<3}  {detail}")
print(f"\n결과: {sum(r[1] == 'OK' for r in rows)}/{len(rows)} 통과")
