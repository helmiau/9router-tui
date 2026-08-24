@echo off
REM 9Router TUI — PowerShell launcher wrapper (fixes .ps1 Notepad association)
REM Double-click this .cmd instead of .ps1 if .ps1 opens in Notepad
REM This bypasses the broken ftype Microsoft.PowerShellScript.1 -> notepad.exe

setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp09Router-TUI.ps1" %*
endlocal
