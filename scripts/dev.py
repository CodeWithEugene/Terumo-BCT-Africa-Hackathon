"""Start the backend (port 8000) and the frontend (port 5173) together.

Run from the repo root:  python scripts/dev.py
Stop both with Ctrl+C.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("npm was not found. Install Node.js, then run this again.")
        return 1
    if not (ROOT / "frontend" / "node_modules").exists():
        print("Installing frontend packages (first run only)...")
        subprocess.run([npm, "install"], cwd=ROOT / "frontend", check=True)

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--port", "8000", "--reload",
         "--reload-dir", "backend"],
        cwd=ROOT,
    )
    frontend = subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "frontend")
    print("\nBackend:  http://localhost:8000/api/health\nFrontend: http://localhost:5173\n")
    try:
        frontend.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (backend, frontend):
            process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
