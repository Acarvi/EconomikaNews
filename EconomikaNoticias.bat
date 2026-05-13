@echo off
chcp 65001 > nul
title Economika Noticias - MVP Launcher
cd /d "%~dp0"

echo ========================================
echo   ECONOMIKA NOTICIAS - MVP LAUNCHER
echo ========================================
echo.

if not exist "main.py" (
  echo [ERROR] main.py was not found. Run this launcher from the EconomikaNoticias repo root.
  echo Current directory: %CD%
  pause
  exit /b 1
)

where python > nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  pause
  exit /b 1
)

if exist ".\scripts\start_economika.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start_economika.ps1"
) else (
  echo [WARN] scripts\start_economika.ps1 not found. Launching GUI directly.
  python main.py
)

if errorlevel 1 (
  echo.
  echo Error launching EconomikaNoticias.
  pause
)
