@echo off
setlocal

REM Optional: set your API key here so the EXE inherits it
REM set DEEPSEEK_API_KEY=...

REM Ensure required packages are available
python -m pip install --upgrade pip
pip install --upgrade nuitka ordered-set zstandard dill pefile pywin32
pip install -e .

REM Clean old build artifacts
if exist build rmdir /s /q build

python -m nuitka ^
  --standalone ^
  --onefile ^
  --output-dir=build ^
  --output-filename=mark2mind.exe ^
  --include-data-dir=mark2mind\prompts=mark2mind\prompts ^
  --include-data-dir=mark2mind\recipes=mark2mind\recipes ^
  --nofollow-import-to=dask ^
  --nofollow-import-to=scipy._lib.array_api_compat.dask ^
  --nofollow-import-to=sklearn.externals.array_api_compat.dask ^
  --nofollow-import-to=torch ^
  --nofollow-import-to=tensorflow ^
  --nofollow-import-to=flax ^
  --nofollow-import-to=transformers ^
  --assume-yes-for-downloads ^
  mark2mind\main.py

echo.
echo Build finished: build\mark2mind.exe
pause
