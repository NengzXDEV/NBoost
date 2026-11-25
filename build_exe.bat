@echo off
REM Nboost - build_exe.bat
REM Builds a standalone Nboost.exe on Windows. Run from the project root
REM (the folder that contains main.py and nboost.spec).

echo === Nboost build ===

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.10+ from python.org and retry.
    exit /b 1
)

echo [1/3] Creating virtual environment (.venv)...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [2/3] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo [3/3] Building Nboost.exe with PyInstaller...
pyinstaller nboost.spec --noconfirm

echo.
echo === Done ===
echo Output: dist\Nboost.exe
echo Run it once from a normal shell first to confirm it starts, then right-click
echo it and "Run as administrator" for full functionality (Event Logs, Windows
echo Update cache, standby RAM purge).
pause
