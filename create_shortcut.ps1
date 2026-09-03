# 创建人民日报下载器快捷方式并设置ICO图标（可移植版：自动使用脚本所在目录）
$ErrorActionPreference = 'Stop'
$dir = $PSScriptRoot
if (-not $dir) { $dir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$bat = Join-Path $dir '下载人民日报.bat'
$ico = Join-Path $dir '人民日报下载器.ico'
$desktop = [Environment]::GetFolderPath('Desktop')

Write-Output ("项目目录: " + $dir)
Write-Output ("桌面路径: " + $desktop)
Write-Output ("BAT存在: " + (Test-Path $bat) + "  ICO存在: " + (Test-Path $ico))

$ws = New-Object -ComObject WScript.Shell

# 1) 项目目录内快捷方式
$l1 = $ws.CreateShortcut((Join-Path $dir '下载人民日报.lnk'))
$l1.TargetPath = $bat
$l1.WorkingDirectory = $dir
$l1.IconLocation = "$ico,0"
$l1.Description = '人民日报电子版PDF自动下载合并工具'
$l1.Save()
Write-Output ("已创建: " + (Join-Path $dir '下载人民日报.lnk'))

# 2) 桌面快捷方式
$l2 = $ws.CreateShortcut((Join-Path $desktop '下载人民日报.lnk'))
$l2.TargetPath = $bat
$l2.WorkingDirectory = $dir
$l2.IconLocation = "$ico,0"
$l2.Description = '人民日报电子版PDF自动下载合并工具'
$l2.Save()
Write-Output ("已创建: " + (Join-Path $desktop '下载人民日报.lnk'))
