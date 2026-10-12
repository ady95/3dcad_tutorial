"""freecadcmd 실행기 — PowerShell·명령 프롬프트·bash 어디서나 같은 명령으로 FreeCAD 스크립트를 실행한다 (01-2).

사용 (저장소 루트에서, 실습 Python 3.12 환경):
  python fcrun.py ch02/api_basics.py
  python fcrun.py FIX=bottom ch04/bracket_fem.py
  python fcrun.py "SET=base_t=6;arm_t=8;r_in=8" MESH=3 ch04/bracket_fem.py

- 이름=값 인자는 이번 실행에만 환경변수로 넘긴다. 셸에 남지 않으므로 다음 실습에 영향을 주지 않는다.
- freecadcmd는 .env의 FREECAD_CMD → PATH → 기본 설치 위치 순서로 찾는다. PATH에 없어도 된다.
- freecadcmd는 스크립트에서 예외가 나도 종료 코드 0을 돌려줄 때가 있어, 출력의 예외 줄을 보고 실패(1)로 끝낸다.
"""
import locale
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from common.freecad_runner import find_freecadcmd  # noqa: E402


def main(argv):
    env, rest = {}, list(argv)
    while rest and "=" in rest[0] and not rest[0].endswith(".py"):     # 앞쪽의 이름=값은 환경변수
        name, value = rest.pop(0).split("=", 1)
        env[name] = value
    if not rest:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(errors="replace")       # 콘솔이 표시하지 못하는 문자는 ?로 (cp949 콘솔에서도 멈추지 않게)
    if env:
        print("이번 실행에만 적용:", " ".join(f"{k}={v}" for k, v in env.items()), flush=True)
    p = subprocess.Popen([str(find_freecadcmd()), *rest], env={**os.environ, **env},
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    failed = False
    for raw in p.stdout:            # freecadcmd는 운영체제 기본 인코딩으로 출력한다 (한국어 Windows: cp949)
        line = raw.decode(locale.getpreferredencoding(False), errors="replace")
        failed |= "Exception while processing file" in line
        sys.stdout.write(line)
        sys.stdout.flush()
    rc = p.wait()
    if failed and rc == 0:
        print("[fcrun] 스크립트 실행 중 예외가 발생했습니다 (위 Exception 줄 참고).")
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
