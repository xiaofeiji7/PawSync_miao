from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parent
SPEC_FILE = PROJECT_DIR / "PawSync_miao.spec"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
OLD_EXE_FILE = DIST_DIR / "PawSync.exe"
EXE_FILE = DIST_DIR / "PawSync_miao.exe"
MASCOT_FILE = PROJECT_DIR / "miao.png"
ICON_FILE = PROJECT_DIR / "miao.ico"


def generate_icon() -> None:
    if not MASCOT_FILE.exists():
        return
    source = Image.open(MASCOT_FILE).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    source.save(ICON_FILE, format="ICO", sizes=sizes)


def clean_outputs() -> None:
    for exe_file in (OLD_EXE_FILE, EXE_FILE):
        if exe_file.exists():
            exe_file.unlink()
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)


def main() -> int:
    if not SPEC_FILE.exists():
        print(f"未找到构建配置：{SPEC_FILE}")
        return 1

    generate_icon()
    clean_outputs()
    command = [sys.executable, "-m", "PyInstaller", "--clean", str(SPEC_FILE)]
    return subprocess.call(command, cwd=PROJECT_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
