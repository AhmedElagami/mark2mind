# -*- mode: python ; coding: utf-8 -*-

import os
from glob import glob
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

# ----- paths -----
HERE = os.getcwd()                                  # dir you run pyinstaller from
PKG_ROOT = os.path.join(HERE, "mark2mind")
VM_ROOT  = os.path.join(PKG_ROOT, "vendor_models")  # vendored models inside package

def dir_to_datas(src_dir, prefix):
    """Return list[(abs_src, rel_dest)] for all files under src_dir."""
    pairs = []
    if not os.path.isdir(src_dir):
        return pairs
    for root, _, files in os.walk(src_dir):
        for f in files:
            abs_src = os.path.join(root, f)
            rel = os.path.relpath(abs_src, src_dir)
            dest = os.path.join(prefix, rel).replace("\\", "/")
            pairs.append((abs_src, dest))
    return pairs

# ----- datas -----
datas = []
# package-local data under _internal/mark2mind/...
datas += dir_to_datas(os.path.join(PKG_ROOT, "prompts"), "_internal/mark2mind/prompts")
datas += dir_to_datas(os.path.join(PKG_ROOT, "recipes"), "_internal/mark2mind/recipes")
# vendored models NEXT TO exe: dist/mark2mind/vendor_models/...
datas += dir_to_datas(VM_ROOT, "vendor_models")

# package metadata
datas += copy_metadata("numpy")
datas += copy_metadata("scipy")
datas += copy_metadata("scikit-learn")
datas += copy_metadata("tokenizers")
datas += copy_metadata("huggingface_hub")

# ----- binaries / hidden imports -----
binaries = []
hiddenimports = []

# only native libs for numpy/scipy; DO NOT include their submodules
binaries += collect_dynamic_libs("numpy")
binaries += collect_dynamic_libs("scipy")

# sklearn needs its python submodules
hiddenimports += collect_submodules("sklearn")

# tokenizers has a rust/native ext + python modules
binaries += collect_dynamic_libs("tokenizers")
hiddenimports += collect_submodules("tokenizers")

# pure-python packages
hiddenimports += collect_submodules("huggingface_hub")
hiddenimports += collect_submodules("semchunk")

excludes = ["dask", "torch", "tensorflow", "flax", "jax", "transformers"]

a = Analysis(
    [os.path.join(PKG_ROOT, "main.py")],
    pathex=[HERE],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir: place DLLs next to the exe
    name="mark2mind",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

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
