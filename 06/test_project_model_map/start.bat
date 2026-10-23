@echo off
setlocal
title Three Kingdoms Map
cd /d "%~dp0"

where node >nul 2>nul
if not errorlevel 1 goto node_ok
if exist "C:\Program Files\nodejs\node.exe" set "PATH=C:\Program Files\nodejs;%PATH%"
where node >nul 2>nul
if errorlevel 1 goto no_node

:node_ok
if exist "node_modules\express" goto run
echo [SETUP] Installing dependencies, please wait...
call npm.cmd install
if errorlevel 1 goto npm_failed

:run
echo.
echo [OK] Starting server: http://localhost:8000
echo [INFO] Press Ctrl+C in this window to stop the server.
echo.
start "" http://localhost:8000
call npm.cmd start
echo.
echo [STOPPED] Server has stopped.
pause
exit /b 0

:no_node
echo.
echo [ERROR] Node.js was not found.
echo Install Node.js LTS from https://nodejs.org/ and try again.
echo.
pause
exit /b 1

:npm_failed
echo.
echo [ERROR] npm install failed.
echo Try running "npm.cmd install" in this folder to see the full error.
echo.
pause
exit /b 1
