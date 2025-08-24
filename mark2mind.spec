# -*- mode: python ; coding: utf-8 -*-

import os
from glob import glob
from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

# --- App data (prompts & recipes bundled from your package) ---
datas = collect_data_files(
    "mark2mind",
    includes=["prompts/**/*.txt", "recipes/*.toml"],
)

# --- Vendored tokenizer files (offline) ---
vm_base = "vendor_models/gpt2"
if os.path.isdir(vm_base):
    for p in glob(f"{vm_base}/**/*", recursive=True):
        if os.path.isfile(p):
            rel = os.path.relpath(p, vm_base)
            datas.append((p, os.path.join(vm_base, rel)))

# --- Native/binary deps and hidden imports ---
binaries = []
hiddenimports = []

# scikit-learn depends on numpy+scipy; tokenizers has a Rust extension; HF hub has data files; semchunk is pure-Python
for pkg in ("numpy", "scipy", "sklearn", "tokenizers", "huggingface_hub", "semchunk"):
    cd, cb, ch = collect_all(pkg)
    datas += cd
    binaries += cb
    hiddenimports += ch

# --- Trim unused heavy backends ---
excludes = [
    "dask",
    "torch",
    "tensorflow",
    "flax",
    "jax",
    "transformers",  # ensure it's not pulled in accidentally
]

a = Analysis(
    ["mark2mind/main.py"],              # forward slashes
    pathex=[os.path.abspath(".")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mark2mind",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
