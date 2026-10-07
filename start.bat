@echo off
rem One-click set-up and launch of the desktop app. Safe to run again: every
rem step is skipped when it is already done. The first run needs internet
rem (pip packages and model weights); later runs are offline.
rem
rem   start.bat                 open the app, pick a file / folder / camera in it
rem   start.bat path\clip.mp4   open the app on a video (or drag a file onto this one)
cd /d "%~dp0"
set PY=venv\Scripts\python

if not exist "%PY%.exe" (
    echo [1/4] Creating the Python 3.11 environment...
    py -3.11 -m venv venv
    if errorlevel 1 (
        echo Cannot create venv: install Python 3.11 and the "py" launcher first.
        pause
        exit /b 2
    )
)

"%PY%" -c "import PySide6, openvino, ultralytics" >nul 2>&1
if errorlevel 1 (
    echo [2/4] Installing dependencies - this takes a few minutes...
    "%PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo pip install failed.
        pause
        exit /b 1
    )
)

if not exist "models\yolo26n.pt" (
    echo [3/4] Downloading model weights...
    "%PY%" scripts\fetch_models.py
    if errorlevel 1 (
        echo Model download failed.
        pause
        exit /b 1
    )
)

if not exist "models\yolo26n_openvino_model\*.xml" (
    echo [4/4] Exporting the OpenVINO model...
    "%PY%" scripts\export_openvino.py
    if errorlevel 1 (
        echo OpenVINO export failed.
        pause
        exit /b 1
    )
)

if "%~1"=="" (
    "%PY%" app.py
) else (
    "%PY%" app.py --source "%~1"
)
if errorlevel 1 pause
