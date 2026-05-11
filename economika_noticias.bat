@echo off
chcp 65001 > nul
title Economika Noticias - Reel Automation
cd /d "%~dp0"
echo ========================================
echo   ECONOMIKA NOTICIAS - REEL GENERATOR
echo ========================================
echo.
echo Lanzando interfaz grafica...
python main.py
pause
