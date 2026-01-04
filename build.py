#!/usr/bin/env python3
"""
Kiro Proxy Cross-platform Build Script
Supports: Windows / macOS / Linux

Usage:
    python build.py          # Build for current platform
    python build.py --all    # Show all platform instructions
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

APP_NAME = "KiroProxy"
VERSION = "1.0.0"
MAIN_SCRIPT = "app.py"
ICON_DIR = Path("assets")

def get_platform():
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    else:
        return "linux"

def ensure_pyinstaller():
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__} installed")
    except ImportError:
        print("[..] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

def clean_build():
    for d in ["build", "dist", f"{APP_NAME}.spec"]:
        if os.path.isdir(d):
            shutil.rmtree(d)
        elif os.path.isfile(d):
            os.remove(d)
    print("[OK] Cleaned build directories")

def build_app():
    platform = get_platform()
    print(f"\n{'='*50}")
    print(f"  Building {APP_NAME} v{VERSION} - {platform}")
    print(f"{'='*50}\n")
    
    ensure_pyinstaller()
    clean_build()
    
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--clean",
        "--noconfirm",
    ]
    
    icon_file = None
    if platform == "windows" and (ICON_DIR / "icon.ico").exists():
        icon_file = ICON_DIR / "icon.ico"
    elif platform == "macos" and (ICON_DIR / "icon.icns").exists():
        icon_file = ICON_DIR / "icon.icns"
    elif (ICON_DIR / "icon.png").exists():
        icon_file = ICON_DIR / "icon.png"
    
    if icon_file:
        args.extend(["--icon", str(icon_file)])
        print(f"[OK] Using icon: {icon_file}")
    
    hidden_imports = [
        "uvicorn.logging",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "httpx",
        "httpx._transports",
        "httpx._transports.default",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
    ]
    for imp in hidden_imports:
        args.extend(["--hidden-import", imp])
    
    args.append(MAIN_SCRIPT)
    args = [a for a in args if a]
    
    print(f"[..] Running: {' '.join(args)}\n")
    result = subprocess.run(args)
    
    if result.returncode == 0:
        if platform == "windows":
            output = Path("dist") / f"{APP_NAME}.exe"
        else:
            output = Path("dist") / APP_NAME
        
        if output.exists():
            size_mb = output.stat().st_size / (1024 * 1024)
            print(f"\n{'='*50}")
            print(f"  [OK] Build successful!")
            print(f"  Output: {output}")
            print(f"  Size: {size_mb:.1f} MB")
            print(f"{'='*50}")
            
            create_release_package(platform, output)
        else:
            print("[FAIL] Build failed: output file not found")
            sys.exit(1)
    else:
        print("[FAIL] Build failed")
        sys.exit(1)

def create_release_package(platform, binary_path):
    release_dir = Path("release")
    release_dir.mkdir(exist_ok=True)
    
    if platform == "windows":
        archive_name = f"{APP_NAME}-{VERSION}-Windows"
        shutil.copy(binary_path, release_dir / f"{APP_NAME}.exe")
        shutil.make_archive(
            str(release_dir / archive_name),
            "zip",
            release_dir,
            f"{APP_NAME}.exe"
        )
        (release_dir / f"{APP_NAME}.exe").unlink()
        print(f"  Release: release/{archive_name}.zip")
        
    elif platform == "macos":
        archive_name = f"{APP_NAME}-{VERSION}-macOS"
        shutil.copy(binary_path, release_dir / APP_NAME)
        os.chmod(release_dir / APP_NAME, 0o755)
        shutil.make_archive(
            str(release_dir / archive_name),
            "zip",
            release_dir,
            APP_NAME
        )
        (release_dir / APP_NAME).unlink()
        print(f"  Release: release/{archive_name}.zip")
        
    else:
        archive_name = f"{APP_NAME}-{VERSION}-Linux"
        shutil.copy(binary_path, release_dir / APP_NAME)
        os.chmod(release_dir / APP_NAME, 0o755)
        shutil.make_archive(
            str(release_dir / archive_name),
            "gztar",
            release_dir,
            APP_NAME
        )
        (release_dir / APP_NAME).unlink()
        print(f"  Release: release/{archive_name}.tar.gz")

def show_all_platforms():
    print(f"""
{'='*60}
  Kiro Proxy Cross-platform Build Instructions
{'='*60}

This script must run on the target platform.

[Windows]
  Run on Windows:
    python build.py
  
  Output: release/KiroProxy-{VERSION}-Windows.zip

[macOS]
  Run on macOS:
    python build.py
  
  Output: release/KiroProxy-{VERSION}-macOS.zip

[Linux]
  Run on Linux:
    python build.py
  
  Output: release/KiroProxy-{VERSION}-Linux.tar.gz

[GitHub Actions]
  Push to GitHub and Actions will build all platforms.
  See .github/workflows/build.yml

{'='*60}
""")

if __name__ == "__main__":
    if "--all" in sys.argv or "-a" in sys.argv:
        show_all_platforms()
    else:
        build_app()
