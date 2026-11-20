@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
start "offline-mirror 介面" cmd /k python -X utf8 webui.py
ping -n 3 127.0.0.1 >nul
start "" http://127.0.0.1:9000
