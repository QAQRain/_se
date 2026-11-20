@echo off
chcp 65001 >nul
setlocal
set PORT=%~1
if "%PORT%"=="" set PORT=9000
set FOUND=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do (
  taskkill /PID %%a /F >nul 2>nul
  set FOUND=1
)
if defined FOUND (
  echo 已停止介面（連接埠 %PORT%）
) else (
  echo 連接埠 %PORT% 沒有在執行
)
