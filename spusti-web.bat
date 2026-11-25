@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Hrackarska poradna
".venv\Scripts\python.exe" app.py
pause
