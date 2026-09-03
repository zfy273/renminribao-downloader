@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PYCMD=py -3"
%PYCMD% --version >nul 2>nul
if errorlevel 1 set "PYCMD=python"
if not exist config.json (
    %PYCMD% "rmrb_downloader.py" --init >nul 2>nul
)
:: 读取配置：颜色 / 标题 / 批量开关 / 合并模式
for /f "delims=" %%i in ('%PYCMD% -c "import json,io;c=json.load(io.open('config.json',encoding='utf-8'));print(c.get('color_background','0')+c.get('color_foreground','A'))"') do set CLR=%%i
if defined CLR color !CLR!
for /f "delims=" %%i in ('%PYCMD% -c "import json,io;c=json.load(io.open('config.json',encoding='utf-8'));print(c.get('window_title','人民日报电子版下载器'))"') do set WT=%%i
if defined WT title !WT!
for /f "delims=" %%i in ('%PYCMD% -c "import json,io;c=json.load(io.open('config.json',encoding='utf-8'));print('1' if c.get('batch_enable') else '0')"') do set BATCH=%%i
for /f "delims=" %%i in ('%PYCMD% -c "import json,io;c=json.load(io.open('config.json',encoding='utf-8'));print(c.get('batch_merge_mode','each'))"') do set DEFMODE=%%i

if "!BATCH!"=="1" goto :batch_mode

:single_mode
echo ============================================================
echo           人民日报电子版 PDF/文字 下载工具（单日模式）
echo ============================================================
echo.
echo  提示: 批量下载请先在 config.json 设置 batch_enable=true
echo.
echo  1. 输入日期（格式 YYYYMMDD，例如 20260902），回车=今日
echo  2. 选择格式: T=文字版  PDF=PDF版面  B=两者
echo.
set /p rdate=请输入日期(回车=今日):
echo.
set /p rfmt=请选择格式(T/PDF/B，回车=PDF):
echo.
if /i "!rfmt!"=="T" set FMT=text
if /i "!rfmt!"=="B" set FMT=both
if not defined FMT set FMT=pdf
echo [信息] 日期=!rdate!  格式=!FMT!
echo.
%PYCMD% "rmrb_downloader.py" !rdate! !FMT!
if errorlevel 1 goto :err
echo.
echo [完成] 下载完成！文件位置已自动打开。
pause
exit /b 0

:batch_mode
echo ============================================================
echo           人民日报电子版 PDF/文字 下载工具（批量模式）
echo ============================================================
echo.
echo  日期范围格式（逗号分隔多个）:
echo    起始-结束  例: 20260901-20260903
echo    单日      例: 20260905
echo    日期-(留空) 表示从该日期到今天
echo    组合示例: 20260901-20260903,20260905  或  20260801-
echo.
set /p rrange=请输入日期范围:
echo.
echo  合并模式:  1 = 每日期单独合并
echo             2 = 全部日期合并成一个
echo             回车 = 使用配置默认(!DEFMODE!)
set /p rmode=请选择合并模式(1/2，回车=默认):
echo.
set /p rfmt=请选择格式(T/PDF/B，回车=PDF):
echo.
if "!rmode!"=="2" (set MODE=all) else if "!rmode!"=="1" (set MODE=each) else (set MODE=!DEFMODE!)
if /i "!rfmt!"=="T" set FMT=text
if /i "!rfmt!"=="B" set FMT=both
if not defined FMT set FMT=pdf
echo [信息] 范围=!rrange!  格式=!FMT!  合并=!MODE!
echo.
if "!rrange!"=="" (
    echo [错误] 日期范围不能为空
    pause
    exit /b 1
)
%PYCMD% "rmrb_downloader.py" --batch "!rrange!" !FMT! --merge-mode !MODE!
if errorlevel 1 goto :err
echo.
echo [完成] 批量下载完成！文件位置已自动打开。
pause
exit /b 0

:err
echo.
echo [错误] 运行失败，具体原因请查看上方提示。
echo        常见原因：网络不通 / 日期无报 / 日期格式错误 / 无法安装合并库。
echo        按任意键退出。
pause >nul
exit /b 1
