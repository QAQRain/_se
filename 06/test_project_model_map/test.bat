@echo off
setlocal
title Three Kingdoms Map - Tests
cd /d "%~dp0"

where node >nul 2>nul
if not errorlevel 1 goto node_ok
if exist "C:\Program Files\nodejs\node.exe" set "PATH=C:\Program Files\nodejs;%PATH%"
where node >nul 2>nul
if errorlevel 1 goto no_node

:node_ok
if exist "node_modules\express" goto deps_ok
echo [SETUP] Installing npm dependencies...
call npm.cmd install
if errorlevel 1 goto npm_failed

:deps_ok
echo.
echo [SETUP] Checking Playwright Chromium (first run may download ~150 MB)...
call npx.cmd playwright install chromium
if errorlevel 1 goto pw_failed

echo.
echo ==========================================
echo [1/3] Unit tests (server)
echo ==========================================
call npm.cmd run test:unit
if errorlevel 1 goto test_failed

echo.
echo ==========================================
echo [2/3] System tests (Web API)
echo ==========================================
call npm.cmd run test:api
if errorlevel 1 goto test_failed

echo.
echo ==========================================
echo [3/3] E2E tests (Playwright)
echo ==========================================
call npm.cmd run test:e2e
if errorlevel 1 goto test_failed

echo.
echo ==========================================
echo [PASS] All three test layers passed.
echo ==========================================
pause
exit /b 0

:no_node
echo.
echo [ERROR] Node.js was not found.
echo Install Node.js LTS from https://nodejs.org/ and try again.
pause
exit /b 1

:npm_failed
echo.
echo [ERROR] npm install failed.
echo Run "npm.cmd install" in this folder to see the full error.
pause
exit /b 1

:pw_failed
echo.
echo [ERROR] Playwright Chromium installation failed.
echo Check your internet connection, then run "npx.cmd playwright install chromium".
pause
exit /b 1

:test_failed
echo.
echo [FAIL] A test layer failed. See the messages above.
pause
exit /b 1
