#!/usr/bin/env python3
# build.py  — create venv (py 3.12), pip install ., vendor tokenizer, run PyInstaller

import subprocess, sys, os, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PYLAUNCHER = ["py", "-3.12"]  # requires Python 3.12 installed via Windows launcher
VENV_PY = VENV / "Scripts" / "python.exe"

TOKENIZER_DST = ROOT / "mark2mind" / "vendor_models" / "gpt2" / "tokenizer.json"
TOKENIZER_URL = "https://huggingface.co/gpt2/resolve/main/tokenizer.json"
SPEC = ROOT / "mark2mind.spec"

def run(cmd, **kw):
    print("> " + " ".join(str(c) for c in cmd))
    subprocess.check_call(cmd, **kw)

def ensure_python312():
    try:
        run(PYLAUNCHER + ["-V"])
    except subprocess.CalledProcessError as e:
        raise SystemExit("Python 3.12 not found via 'py -3.12'. Install it.")

def make_venv():
    if not VENV.exists():
        run(PYLAUNCHER + ["-m", "venv", str(VENV)])
    run([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

def pip_install_project():
    # install your package (uses setup.py / pyproject metadata)
    run([str(VENV_PY), "-m", "pip", "install", "-e", ".[dev]"])  # editable is convenient for local builds

def ensure_vendor_models():
    if TOKENIZER_DST.exists():
        print(f"[vendor] exists: {TOKENIZER_DST}")
        return
    TOKENIZER_DST.parent.mkdir(parents=True, exist_ok=True)

    # Try huggingface_hub first (already in install_requires), fall back to urllib
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
        path = hf_hub_download(repo_id="gpt2", filename="tokenizer.json")
        shutil.copyfile(path, TOKENIZER_DST)
        print(f"[vendor] copied tokenizer → {TOKENIZER_DST}")
        return
    except Exception as e:
        print(f"[vendor] huggingface_hub failed: {e}. Falling back to direct download.")

    try:
        import urllib.request  # stdlib
        tmp = TOKENIZER_DST.with_suffix(".download")
        urllib.request.urlretrieve(TOKENIZER_URL, tmp)
        shutil.move(tmp, TOKENIZER_DST)
        print(f"[vendor] downloaded tokenizer → {TOKENIZER_DST}")
    except Exception as e:
        raise SystemExit(f"[vendor] FAILED to obtain tokenizer.json: {e}")

def run_pyinstaller():
    if not SPEC.exists():
        raise SystemExit(f"Spec not found: {SPEC}")
    run([str(VENV_PY), "-m", "pip", "install", "pyinstaller==6.6.0"])  # pin if you want
    run([str(VENV_PY), "-m", "PyInstaller", "--clean", str(SPEC)])

def main():
    os.chdir(ROOT)
    ensure_python312()
    make_venv()
    pip_install_project()
    ensure_vendor_models()      # put files under mark2mind/vendor_models/...
    run_pyinstaller()

if __name__ == "__main__":
    main()
