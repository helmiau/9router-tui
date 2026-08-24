@echo off
REM 9Router TUI — Double-click launcher (zero-config, no setup needed)
REM Klik 2x file ini untuk membuka TUI — tanpa config awal pun akan muncul Server Picker
REM Jika Python belum ada, akan kasih petunjuk. Jika deps belum ada, auto-install.

setlocal
title 9Router TUI
cd /d "%~dp0"

REM ── Cari Python (coba python, py, python3) ──
set "PY=python"
%PY% --version >nul 2>&1
if errorlevel 1 (
    set "PY=py"
    %PY% --version >nul 2>&1
    if errorlevel 1 (
        set "PY=python3"
        %PY% --version >nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Python tidak ditemukan!
            echo Install Python 3.10+ dari https://python.org
            echo Centang "Add python.exe to PATH" saat install.
            echo.
            echo Alternatif: pakai dist\9Router-TUI.exe (standalone, tanpa Python)
            pause
            exit /b 1
        )
    )
)
echo [INFO] Using %PY% — %PY% --version
%PY% --version

REM ── Auto-install dependencies jika belum ada (zero-config) ──
%PY% -c "import textual" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Dependencies belum ada — installing...
    %PY% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [WARN] pip install gagal, coba pip install manual:
        echo   %PY% -m pip install -r requirements.txt
        pause
    )
)

REM ── Jalankan TUI (tanpa config pun akan muncul Server Picker) ──
echo [INFO] Starting 9Router TUI...
REM Simpan errorlevel app.py sebelum tertimpa echo
%PY% app.py %*
set "APP_EXIT=%ERRORLEVEL%"

REM Jangan langsung close — biar error kelihatan
echo.
echo [INFO] TUI exited with code %APP_EXIT%
if not "%APP_EXIT%"=="0" (
    echo [ERROR] TUI error — cek pesan di atas
    pause
)
endlocal
exit /b %APP_EXIT%
