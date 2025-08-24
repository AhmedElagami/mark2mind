# -*- mode: python ; coding: utf-8 -*-

import os
from glob import glob
from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

# --- App data ---
datas = collect_data_files(
    "mark2mind",
    includes=["prompts/**/*.txt", "recipes/*.toml"],
)

# --- Vendored tokenizer (offline) ---
vm_base = "vendor_models/gpt2"
if os.path.isdir(vm_base):
    for p in glob(f"{vm_base}/**/*", recursive=True):
        if os.path.isfile(p):
            rel = os.path.relpath(p, vm_base)
            datas.append((p, os.path.join(vm_base, rel)))

# --- Deps ---
binaries = []
hiddenimports = []
for pkg in ("numpy", "scipy", "sklearn", "tokenizers", "huggingface_hub", "semchunk"):
    cd, cb, ch = collect_all(pkg)
    datas += cd
    binaries += cb
    hiddenimports += ch

# --- Excludes ---
excludes = [
    "dask", "torch", "tensorflow", "flax", "jax", "transformers",
]

a = Analysis(
    ["mark2mind/main.py"],
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
    [],
    exclude_binaries=True,   # let COLLECT handle binaries/data
    name="mark2mind",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

# *** REQUIRED for onedir builds ***
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="mark2mind",
)
