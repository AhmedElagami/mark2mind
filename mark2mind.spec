# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

# --- App data (your prompts & recipes) ---
# These live inside the 'mark2mind' package, so collect them from there.
datas = collect_data_files(
    'mark2mind',
    includes=['prompts/**/*.txt', 'recipes/*.toml']
)

# --- Scientific stack: pull in EVERYTHING (code, data, hidden imports) ---
binaries = []
hiddenimports = []

for pkg in ('numpy', 'scipy', 'sklearn'):
    collected_datas, collected_bins, collected_hidden = collect_all(pkg)
    datas += collected_datas
    binaries += collected_bins
    hiddenimports += collected_hidden

# Optional: if you see issues with spaCy tokenizers on some setups, uncomment:
# for pkg in ('spacy', 'srsly', 'cymem', 'preshed', 'thinc', 'blis', 'murmurhash'):
#     cd, cb, ch = collect_all(pkg)
#     datas += cd; binaries += cb; hiddenimports += ch

# --- Trim unused heavy backends (smaller & faster) ---
excludes = [
    # optional/scientific backends we don't use
    'dask',
    'scipy._lib.array_api_compat.dask',
    'scipy._lib.array_api_compat.dask.array',
    'sklearn.externals.array_api_compat.dask',
    'sklearn.externals.array_api_compat.dask.array',

    # deep learning frameworks (not needed if you only use transformers tokenizers / APIs)
    'torch',
    'tensorflow',
    'flax',
]

a = Analysis(
    ['mark2mind/main.py'],        # use forward slashes to avoid escape issues
    pathex=[os.path.abspath('.')],  # ensure local package is discoverable
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,                    # small shrink, safe (use 0 if you prefer)
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='mark2mind',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                     # keep False on Windows to avoid DLL issues
    upx_exclude=[],
    runtime_tmpdir=None,           # keep default temp location
    console=True,                  # CLI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
