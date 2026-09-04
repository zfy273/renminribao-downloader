@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "EXE=人民日报下载器.exe"
set "SCRIPT=rmrb_downloader.py"

if exist "%EXE%" goto :run_exe

echo [信息] 未找到 %EXE%，尝试使用 Python 脚本...
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYCMD=py -3"
    goto :run_py
)
where python >nul 2>nul
if %errorlevel%==0 (
    set "PYCMD=python"
    goto :run_py
)

echo [错误] 未找到 %EXE%，也未检测到 Python 环境。
echo        请确保 %EXE% 与本 BAT 在同一目录，或安装 Python 3.8+。
echo        按任意键退出。
pause >nul
exit /b 1

:run_exe
if not exist config.json (
    "%EXE%" --init >nul 2>nul
)
"%EXE%"
exit /b %errorlevel%

:run_py
if not exist config.json (
    %PYCMD% "%SCRIPT%" --init >nul 2>nul
)
%PYCMD% "%SCRIPT%"
exit /b %errorlevel%
