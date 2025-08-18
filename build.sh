#!/usr/bin/env bash
set -euo pipefail

rm -rf build

python -m nuitka \
  --onefile \
  --standalone \
  --output-dir=build \
  --output-filename=mark2mind \
  --include-data-dir=mark2mind/prompts=mark2mind/prompts \
  --include-data-dir=mark2mind/recipes=mark2mind/recipes \
  --nofollow-import-to=dask \
  --nofollow-import-to=scipy._lib.array_api_compat.dask \
  --nofollow-import-to=sklearn.externals.array_api_compat.dask \
  --nofollow-import-to=torch \
  --nofollow-import-to=tensorflow \
  --nofollow-import-to=flax \
  --nofollow-import-to=transformers \
  --assume-yes-for-downloads \
  mark2mind/main.py

echo "Build finished: build/mark2mind"
