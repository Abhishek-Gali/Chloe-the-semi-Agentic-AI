"""
Project Chloe 2.0 - All-in-One Standalone Installer Builder
Compiles backend runtime into Chloe.exe, bundles models and static assets into a payload,
and produces a single standalone Chloe_Setup_v2.0_AllInOne.exe (~400-500 MB).
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
INSTALLER_DIR = ROOT_DIR / "installer"
DIST_DIR = ROOT_DIR / "dist"

def run_cmd(cmd, cwd=None):
    print(f"[*] Executing: {' '.join(cmd) if isinstance(cmd, list) else cmd}", flush=True)
    res = subprocess.run(cmd, cwd=str(cwd or ROOT_DIR), shell=isinstance(cmd, str))
    if res.returncode != 0:
        print(f"[!] Command failed with exit code: {res.returncode}", flush=True)
        sys.exit(res.returncode)

def main():
    print("=" * 65, flush=True)
    print("PROJECT CHLOE 2.0 // ALL-IN-ONE STANDALONE INSTALLER BUILD PIPELINE", flush=True)
    print("=" * 65, flush=True)

    payload_zip = INSTALLER_DIR / "chloe_payload.zip"
    icon_path = BACKEND_DIR / "app" / "static" / "favicon.ico"

    # Ensure favicon.ico exists
    if not icon_path.exists():
        try:
            from PIL import Image
            avatar = BACKEND_DIR / "app" / "static" / "assets" / "avatar" / "chloe_idle.png"
            if avatar.exists():
                img = Image.open(avatar)
                img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
                print(f"[+] Auto-generated favicon at: {icon_path}", flush=True)
        except Exception as e:
            print(f"[!] Warning: Could not auto-generate favicon: {e}", flush=True)

    # 1 & 2. Check if payload archive already exists
    if payload_zip.exists() and payload_zip.stat().st_size > 100 * 1024 * 1024:
        size_mb = payload_zip.stat().st_size / (1024 * 1024)
        print(f"\n[+] Found existing verified payload archive: {payload_zip} ({size_mb:.1f} MB)", flush=True)
        print("[*] Reusing existing payload archive to save build time...", flush=True)
    else:
        # 1. Compile Core Backend into dist/Chloe
        print("\n[STEP 1/3] Compiling Chloe Core Runtime via PyInstaller...", flush=True)
        spec_path = BACKEND_DIR / "chloe.spec"
        run_cmd([sys.executable, "-m", "PyInstaller", str(spec_path), "--noconfirm", "--clean"], cwd=BACKEND_DIR)

        compiled_chloe_dir = BACKEND_DIR / "dist" / "Chloe"
        if not compiled_chloe_dir.exists():
            print(f"[!] Error: Compiled directory {compiled_chloe_dir} not found!", flush=True)
            sys.exit(1)

        print(f"[+] Successfully compiled Core Runtime at: {compiled_chloe_dir}", flush=True)

        if (ROOT_DIR / "run.bat").exists():
            shutil.copy2(ROOT_DIR / "run.bat", compiled_chloe_dir / "run.bat")

        # 2. Package into installer/chloe_payload.zip
        print("\n[STEP 2/3] Compressing Core Runtime & Models into chloe_payload.zip...", flush=True)
        if payload_zip.exists():
            payload_zip.unlink()

        with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(compiled_chloe_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(compiled_chloe_dir)
                    z.write(file_path, arcname)

        size_mb = payload_zip.stat().st_size / (1024 * 1024)
        print(f"[+] Payload Archive created: {payload_zip} ({size_mb:.1f} MB)", flush=True)

    # 3. Compile the All-in-One Standalone Setup Wizard
    print("\n[STEP 3/3] Compiling Standalone Chloe_Setup_v2.0_AllInOne.exe...", flush=True)
    setup_script = INSTALLER_DIR / "setup_wizard.py"

    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--noconfirm",
        "--paths", str(INSTALLER_DIR),
        "--name", "Chloe_Setup_v2.0_AllInOne",
        "--add-data", f"{payload_zip};.",
        str(setup_script)
    ]
    if icon_path.exists():
        pyinstaller_args.extend(["--add-data", f"{icon_path};app/static"])
        pyinstaller_args.extend(["--icon", str(icon_path)])

    run_cmd(pyinstaller_args, cwd=ROOT_DIR)

    final_exe = DIST_DIR / "Chloe_Setup_v2.0_AllInOne.exe"
    if final_exe.exists():
        final_size_mb = final_exe.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 65, flush=True)
        print(f"[SUCCESS] ALL-IN-ONE STANDALONE INSTALLER CREATED!", flush=True)
        print(f"[*] Executable Location: {final_exe}", flush=True)
        print(f"[*] File Size:           {final_size_mb:.1f} MB", flush=True)
        print("=" * 65, flush=True)
    else:
        print("[!] Warning: Final installer executable was not found in dist/", flush=True)

if __name__ == "__main__":
    main()
