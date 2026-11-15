@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

if /i "%~1"=="--cli" goto :cli
if /i "%~1"=="-c" goto :cli

rem ---- 1) 打包好的 exe 优先 ----
if exist "人民日报下载器.exe" (
    start "" "人民日报下载器.exe"
    exit /b 0
)

rem ---- 2) 找 Python ----
set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
    where python >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD goto :nopython

rem ---- 3) 图形界面需要 tkinter ----
%PYCMD% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo [提示] 当前 Python 未包含 tkinter，自动改用命令行界面。
    echo        如需图形界面，请安装 python.org 官方版 Python。
    timeout /t 3 >nul
    goto :cli
)

rem ---- 4) 用 pythonw 启动，避免残留控制台窗口 ----
set "PYW="
where pyw >nul 2>nul && set "PYW=pyw -3"
if not defined PYW (
    where pythonw >nul 2>nul && set "PYW=pythonw"
)
if defined PYW (
    start "" %PYW% "%~dp0rmrb_ui.py"
    exit /b 0
)
start "" %PYCMD% "%~dp0rmrb_ui.py"
exit /b 0

:cli
if not exist config.json (
    %PYCMD% "rmrb_downloader.py" --init >nul 2>nul
)
title 人民日报电子版下载器
%PYCMD% "rmrb_downloader.py"
if errorlevel 130 exit /b 130
echo.
echo 按任意键关闭窗口...
pause >nul
exit /b 0

:nopython
echo ============================================================
echo   未检测到可用的 Python
echo ============================================================
echo.
echo   请任选一种方式：
echo     1. 安装 Python 3.8+（python.org 官方版，自带 tkinter）
echo     2. 使用打包好的 人民日报下载器.exe（无需安装 Python）
echo.
pause
exit /b 1
