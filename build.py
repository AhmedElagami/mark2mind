#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ==== config ====
PY_TAG = "3.12"                     # <- force Python 3.12 (full install)
VENV_DIR = Path(".venv")
ONEFILE = False                     # onefile EXE can trigger AV heuristics; off by default
OUTNAME = "mark2mind.exe"
BUILD_DIR = Path("build")
ENTRY = Path("mark2mind/main.py")

# ==== find VS2022 with vswhere ====
vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
if not vswhere.exists():
    sys.exit("[!] vswhere.exe not found. Install Visual Studio Build Tools 2022 (Desktop C++ + Windows SDK).")

print("[i] Detecting Visual Studio Build Tools with vswhere...")
try:
    vsinstall = subprocess.check_output(
        [str(vswhere), "-latest", "-products", "*",
         "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
         "-property", "installationPath"],
        text=True
    ).strip()
except subprocess.CalledProcessError:
    sys.exit("[!] vswhere failed. Is VS Build Tools 2022 installed?")

if not vsinstall:
    sys.exit("[!] No VS Build Tools 2022 (MSVC v143+) found.")

vsdevcmd = Path(vsinstall) / "Common7/Tools/VsDevCmd.bat"
if not vsdevcmd.exists():
    sys.exit(f"[!] VsDevCmd.bat not found at {vsdevcmd}")

print(f"[i] Using Visual Studio at: {vsinstall}")

# ==== pick a **full** CPython 3.12 via the 'py' launcher ====
def pick_full_python(tag: str = "3.12") -> str | None:
    """
    Return a path to a full CPython (not embeddable/WindowsApps) for the given version tag.
    Prefers 64-bit tag if present.
    """
    try:
        out = subprocess.check_output(["py", "-0p"], text=True, errors="ignore")
    except Exception:
        return None

    lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("-V:")]
    # e.g. "-V:3.12  C:\\Users\\...\\Python312\\python.exe"
    def parse(line: str):
        m = re.match(r"-V:([^\s]+)\s+(.+python\.exe)", line, re.I)
        if not m:
            return None
        found_tag, path = m.group(1), m.group(2)
        return found_tag, path

    # rank: prefer exact 3.12-64, then 3.12, then anything else not suspicious
    ranked: list[tuple[int, str]] = []
    for ln in lines:
        p = parse(ln)
        if not p:
            continue
        found_tag, path = p
        lower = path.lower()
        suspicious = ("windowsapps" in lower) or ("embeddable" in lower) or ("portable" in lower) or lower.endswith(".zip")
        if suspicious:
            continue
        score = 0
        if found_tag.startswith(tag):
            score += 10
        if found_tag.endswith("-64"):
            score += 2
        ranked.append((score, path))

    ranked.sort(reverse=True)
    return ranked[0][1] if ranked else None

chosen_py = pick_full_python(PY_TAG)
if not chosen_py:
    sys.exit(f"[!] No suitable full CPython {PY_TAG} found. Install 64-bit Python {PY_TAG} from python.org and retry.")
print(f"[i] Base interpreter: {chosen_py}")

# ==== ensure venv (recreate if wrong major.minor) ====
venv_python = VENV_DIR / "Scripts" / "python.exe"

def venv_version(py_exe: Path) -> tuple[int, int] | None:
    try:
        out = subprocess.check_output([str(py_exe), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"], text=True)
        major, minor = out.strip().split(".")
        return int(major), int(minor)
    except Exception:
        return None

def recreate_venv():
    if VENV_DIR.exists():
        print("[i] Removing old virtual environment ...")
        shutil.rmtree(VENV_DIR)
    print(f"[i] Creating venv with {chosen_py} ...")
    subprocess.check_call([chosen_py, "-m", "venv", str(VENV_DIR)])

# create if missing, or recreate if wrong version
if not venv_python.exists():
    recreate_venv()
else:
    ver = venv_version(venv_python)
    if ver != (3, 12):
        print(f"[i] Existing venv is Python {ver}, recreating for 3.12 ...")
        recreate_venv()

# ==== deps + your package ====
subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"])
subprocess.check_call([str(venv_python), "-m", "pip", "install", "--upgrade",
                       "nuitka", "ordered-set", "zstandard", "dill", "pefile", "pywin32"])
subprocess.check_call([str(venv_python), "-m", "pip", "install", "-e", "."])

# ==== clean old build ====
if BUILD_DIR.exists():
    shutil.rmtree(BUILD_DIR)

# ==== build flags ====
flags = [
    "--msvc=latest",
    "--standalone",
    f"--output-dir={BUILD_DIR}",
    f"--output-filename={OUTNAME}",
    "--include-data-dir=mark2mind/prompts=mark2mind/prompts",
    "--include-data-dir=mark2mind/recipes=mark2mind/recipes",
    "--include-package-data=mark2mind",
    "--nofollow-import-to=dask",
    "--nofollow-import-to=scipy._lib.array_api_compat.dask",
    "--nofollow-import-to=sklearn.externals.array_api_compat.dask",
    "--nofollow-import-to=torch",
    "--nofollow-import-to=tensorflow",
    "--nofollow-import-to=flax",
    "--nofollow-import-to=transformers",
    "--assume-yes-for-downloads",
]
if ONEFILE:
    flags.append("--onefile")

# ==== build ====
print(f"[i] Building with Nuitka using {venv_python} ...")
cmd = [str(venv_python), "-m", "nuitka"] + flags + [str(ENTRY)]

# Wrap in VsDevCmd.bat so MSVC env is loaded
full_cmd = f'call "{vsdevcmd}" -arch=x64 && ' + " ".join(f'"{c}"' if " " in c else c for c in cmd)
ret = subprocess.call(full_cmd, shell=True)
if ret != 0:
    sys.exit(f"[!] Nuitka build failed with code {ret}")

if ONEFILE:
    print(f"[OK] One-file EXE: {BUILD_DIR/OUTNAME}")
    print("[!] Heads up: One-file can trip Windows Defender heuristics.")
else:
    dist = BUILD_DIR / "mark2mind.dist"
    print(f"[OK] Standalone folder ready: {dist}")
    print(f"    Run: {dist/OUTNAME}")

# ==== show bundled VC runtime ====
if not ONEFILE:
    for f in (dist.glob("*vcruntime*.dll")):
        print(f"[i] Bundled VC runtime: {f.name}")
