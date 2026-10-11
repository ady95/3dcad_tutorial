"""FreeCAD 실행 도우미 — 여러 장에서 공통으로 쓴다.

독립 Python 환경(3.12)에서 FreeCAD의 Headless 실행 파일(freecadcmd)을 찾아
스크립트를 실행하고, 결과 줄을 돌려준다.
"""
import locale
import os
import platform
import shutil
import subprocess
from pathlib import Path


def find_freecadcmd():
    """freecadcmd 경로를 찾는다. 순서: .env의 FREECAD_CMD → PATH → 기본 설치 위치."""
    env = os.environ.get("FREECAD_CMD", "").strip()
    if env and Path(env).exists():
        return Path(env)
    for name in ("freecadcmd", "FreeCADCmd"):
        found = shutil.which(name)
        if found:
            return Path(found)
    if platform.system() == "Windows":
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "FreeCAD 1.1" / "bin" / "freecadcmd.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "FreeCAD 1.1" / "bin" / "freecadcmd.exe",
        ]
        for c in candidates:
            if c.exists():
                return c
    raise FileNotFoundError("freecadcmd를 찾지 못했습니다. .env에 FREECAD_CMD 경로를 지정하세요.")


def run_freecad(script_path, env=None, timeout=600):
    """freecadcmd로 파이썬 스크립트를 실행하고 (종료 코드, 표준출력+표준오류)를 돌려준다."""
    cmd = [str(find_freecadcmd()), str(script_path)]
    # freecadcmd는 운영체제 기본 인코딩으로 출력한다 (한국어 Windows: cp949, Linux: UTF-8)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding=locale.getpreferredencoding(False), errors="replace",
                       env={**os.environ, **(env or {})}, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def tagged_line(output, tag):
    """freecadcmd 출력에서 'TAG {...}' 형식의 줄을 찾아 뒷부분을 돌려준다.

    freecadcmd는 출력을 버퍼링하므로 스크립트 쪽에서 print(..., flush=True)로 찍어야 한다.
    결과 JSON은 json.dumps 기본값(ensure_ascii=True)으로 찍으면 출력 인코딩과 무관하게 안전하다.
    """
    for line in output.splitlines():
        if line.startswith(tag + " "):
            return line[len(tag) + 1:]
    return None
