"""Build script for Rekordbox Creative executable (PKG-001/PKG-002).

Usage:
    python build.py          # Build for current platform
    python build.py --clean  # Clean build artifacts first
"""

import shutil
import subprocess
import sys
from pathlib import Path


def clean():
    """Remove build artifacts."""
    for d in ["build", "dist"]:
        p = Path(d)
        if p.exists():
            shutil.rmtree(p)
            print(f"Removed {d}/")


def build():
    """Run PyInstaller with the spec file."""
    spec = Path("rekordbox_creative.spec")
    if not spec.exists():
        print("ERROR: rekordbox_creative.spec not found. Run from project root.")
        sys.exit(1)

    cmd = [sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm"]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent))

    if result.returncode == 0:
        if sys.platform == "win32":
            exe = Path("dist/RekordboxCreative/RekordboxCreative.exe")
            print(f"\nBuild successful! Executable at: {exe}")
        elif sys.platform == "darwin":
            app = Path("dist/RekordboxCreative.app")
            print(f"\nBuild successful! App bundle at: {app}")
        else:
            print("\nBuild successful! Output in dist/RekordboxCreative/")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    build()
