# 人民日报电子版下载器 / People's Daily Downloader

> 中文 | [English](docs/README_EN.md) | [日本語](docs/README_JA.md) | [한국어](docs/README_KO.md) | [Français](docs/README_FR.md) | [Deutsch](docs/README_DE.md) | [Italiano](docs/README_IT.md) | [हिन्दी](docs/README_HI.md) | [ไทย](docs/README_TH.md) | [العربية](docs/README_AR.md) | [Русский](docs/README_RU.md) | [Español](docs/README_ES.md)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

一个纯 Python 编写的《人民日报》电子版自动下载与合并工具。支持 PDF 版面下载、文章正文抓取（TXT/DOC/DOCX）、批量日期下载、全配置化，无需浏览器与驱动。

---

## 功能特性

- **PDF 模式**：自动下载当日全部版面 PDF 并合并为一个完整版文件
- **文字模式**：抓取全部版面文章正文，输出为 `TXT` / `DOC` / `DOCX`（零额外依赖）
- **both 模式**：PDF 与文字版同时生成
- **批量下载**：支持日期范围表达式，可每日期单独合并或全部合并为一个跨日期大文件
- **全配置化**：30+ 配置项（网络、界面、输出、限速、代理、调度等）通过 `config.json` 调节
- **自动依赖安装**：首次运行自动安装 `pypdf` 合并库（官方源 → 清华镜像回退）
- **实时进度**：下载进度条、速率显示、完成后自动打开文件所在位置
- **健壮错误处理**：网络重试、文件占用自动重试、未来日期/非法日期/无效表达式拦截、中文友好报错

---

## 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10 / 11（cmd 批处理启动器为 Windows 专用；核心脚本可跨平台） |
| Python | **3.8 及以上**（推荐 3.10+，已在 3.13 / 3.14 验证） |
| 网络 | 需能访问 `paper.people.com.cn` |
| 浏览器 | **不需要** Chrome / Edge / 任何浏览器驱动 |

### 依赖库

| 库 | 用途 | 安装方式 |
|---|---|---|
| `pypdf` | PDF 合并 | **首次运行自动安装**；也可手动 `pip install pypdf` |
| （无） | 文字版 TXT/DOC/DOCX | 纯标准库实现（`zipfile` 手写 OOXML），零依赖 |
| `PyMuPDF`（可选） | 仅用于测试时渲染 PDF 预览截图 | `pip install pymupdf`，普通使用不需要 |

---

## 快速开始

### 方式零：使用 exe（推荐，无需安装 Python）

1. 从 [Releases](https://github.com/zfy273/renminribao-downloader/releases) 下载最新版 ZIP 并解压
2. 确保 `人民日报下载器.exe` 和 `下载人民日报.bat`、`config.json` 在同一目录
3. 双击 `下载人民日报.bat`（自动优先调用 exe），或直接双击 `人民日报下载器.exe`
4. 按提示输入日期（回车 = 今日）、选择格式（T / PDF / B）
5. 等待下载与合并，完成后自动打开文件所在文件夹

> exe 版本已内置 Python 运行时和 pypdf 库，无需安装任何依赖。首次启动可能稍慢（需解压临时文件）。

### 方式一：双击 BAT（需安装 Python）

1. 确保已安装 Python 并加入 PATH（或安装了 `py` 启动器）
2. 双击 `下载人民日报.bat`
3. 按提示输入日期（回车 = 今日）、选择格式（T / PDF / B）
4. 等待下载与合并，完成后自动打开文件所在文件夹

### 方式二：命令行

```bash
# 单日 PDF（默认今日）
python rmrb_downloader.py

# 指定日期 + 格式
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# 批量下载（日期范围，每日期单独合并）
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# 批量下载（全部合并为一个跨日期大文件）
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# 从某日期到今日（右端留空）
python rmrb_downloader.py --batch "20260801-" pdf

# 生成/刷新默认配置
python rmrb_downloader.py --init

# 注册/删除每日自动下载计划任务
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## 配置说明（config.json）

首次运行自动生成 `config.json`。所有配置项及含义如下：

### 抓取与网络

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | 人民日报电子版基础地址 |
| `rate_limit_kbps` | number | `0` | 下载速率上限（KB/s），`0` = 不限速 |
| `timeout` | int | `30` | 单次网络请求超时（秒） |
| `retry` | int | `3` | 失败重试次数 |
| `retry_interval` | float | `2.0` | 重试间隔（秒） |
| `request_interval` | float | `0.2` | 每次请求间隔（秒），防止访问过频被封 |
| `concurrent` | int | `1` | 并发下载线程数（1–16） |
| `proxy` | string | `""` | HTTP/HTTPS 代理地址，空 = 不使用代理 |
| `user_agent` | string | Chrome UA | 请求 User-Agent |

### 界面

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `color_foreground` | string | `"A"` | cmd 前景色（0–F 十六进制） |
| `color_background` | string | `"0"` | cmd 背景色（0–F 十六进制） |
| `window_title` | string | `人民日报电子版下载器` | 控制台窗口标题 |
| `show_progress` | bool | `true` | 是否显示下载进度条 |

### 日期与内容

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `default_date` | string | `""` | 默认日期 `YYYYMMDD`，空 = 今日 |
| `default_format` | string | `"pdf"` | 默认格式：`pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **版面白名单**：非空时只下载列出的版面号（如 `[1,2]` 只下第1、2版）；空 = 全部版面 |
| `holiday_skip` | bool | `false` | 单日模式下无版面时是否静默跳过（返回 0 而非报错） |

### 批量下载

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `batch_enable` | bool | `false` | `true` 时双击 BAT 显示**批量下载界面** |
| `batch_merge_mode` | string | `"each"` | `each` = 每日期单独合并；`all` = 全部日期合并为一个大文件 |
| `download_path` | string | `""` | 下载根目录；空 = 脚本所在文件夹；相对路径相对脚本目录，也可填绝对路径 |

### 输出与合并

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | 单版 PDF 存放目录模板，`{date}` 替换为日期 |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | 合并 PDF 文件名模板（不含扩展名） |
| `auto_merge` | bool | `true` | 单日模式是否自动合并 |
| `keep_singles` | bool | `true` | 合并后是否保留单版 PDF 目录；`false` 合并成功后自动删除 |
| `open_folder_after` | bool | `true` | 完成后是否自动打开文件所在文件夹 |

### 文字输出

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | 文字版输出格式：`TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | 文字版文件名模板（不含扩展名） |
| `text_include_edition` | bool | `true` | 文字版是否包含版面标题分隔 |

### 日志与通知

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | 日志文件名；空 = 不记录日志 |
| `log_level` | string | `"normal"` | 日志级别：`quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | 完成时蜂鸣提示 |
| `msg_on_done` | bool | `false` | 完成时弹出 Windows 消息框 |

### 调度

| 键 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `auto_run` | bool | `false` | 是否启用每日自动下载（需先 `--task-install` 注册计划任务） |
| `auto_run_time` | string | `"08:00"` | 每日自动运行时间 `HH:MM` |

> 配置非法值（如负数限速、越界并发、非法颜色码）会在启动时自动回退为默认值并打印警告，不会导致崩溃。

---

## 批量下载详解

### 日期范围表达式

在 BAT 批量界面或 `--batch` 参数中输入，逗号分隔多个段：

| 表达式 | 含义 |
|---|---|
| `20260901-20260903` | 2026-09-01 至 2026-09-03（含两端） |
| `20260905` | 仅 2026-09-05 单日 |
| `20260801-` | 2026-08-01 至**今日**（右端留空） |
| `20260901-20260903,20260905` | 范围 + 单日组合（自动去重、按日期排序） |

- 日期必须为真实存在的日期（如 `20260134`、`20261301` 会被拦截并报错）
- 起始日期晚于结束日期会报错
- 无版面的日期（休刊/未出版）自动跳过并计入汇总

### 合并模式

| 模式 | 行为 | 产物文件名示例 |
|---|---|---|
| `each` | 每个日期单独下载、单独合并 | `人民日报-2026-09-02-完整版.pdf`、`人民日报-2026-09-03-完整版.pdf` |
| `all` | 所有日期的版面全部合并为**一个跨日期大文件** | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

文字版同样支持 `each` / `all`。

### 开启 BAT 批量界面

编辑 `config.json`，将 `"batch_enable"` 改为 `true`，双击 BAT 即进入批量下载界面（输入范围 → 选合并模式 → 选格式）。

---

## 文字版输出格式

| 格式 | 说明 | 依赖 |
|---|---|---|
| `TXT` | UTF-8 纯文本，含版面标题与文章正文 | 无 |
| `DOC` | HTML 内容存为 `.doc`，Microsoft Word / WPS 可直接打开 | 无 |
| `DOCX` | 标准 OOXML（用 `zipfile` 手写最小文档结构），Word/WPS/LibreOffice 均可打开 | 无 |

在 `config.json` 中设置 `"text_output_format": "DOCX"` 等切换。

---

## 常见报错与解决方案

| 报错信息 | 原因 | 解决方法 |
|---|---|---|
| `未来日期，人民日报尚未出版` | 输入了今天之后的日期 | 检查日期，或修改 `default_date` |
| `日期不存在（月份或日期越界）` | 如 `20261301`、`20260134` | 输入真实存在的日期 |
| `日期应为 8 位数字 YYYYMMDD` | 日期位数不对 | 按 `YYYYMMDD` 格式输入，如 `20260903` |
| `未找到任何版面` | 该日期未出版/休刊，或 `edition_filter` 把版面过滤为空，或网络异常 | 换一个工作日日期；检查 `edition_filter`；查看上方 `[网络]` 提示 |
| `无法安装合并库 pypdf` | 网络不通，无法通过 pip 安装 | 手动执行 `pip install pypdf`，或配置代理后重试 |
| `合并失败：目标文件正被占用` | 同名 PDF 正在 PDF 阅读器/资源管理器预览中打开 | 关闭已打开的同名文件后重试，或修改 `merged_filename` / `download_path` |
| `域名解析失败 / 网络连接失败` | 网络未连接、DNS 异常或代理错误 | 检查网络；检查 `config.json` 的 `proxy` 配置 |
| `连接/读取超时` | 网络慢或服务器响应慢 | 增大 `timeout`（如 60），稍后重试 |
| `服务器返回 HTTP 403/429` | 访问过于频繁被限流 | 增大 `request_interval`（如 1.0），降低 `concurrent` |
| `日期表达式错误：无效日期` | 批量表达式含非法日期 | 按 `YYYYMMDD` 格式输入，逗号分隔多个范围 |
| `格式参数应为 text / pdf / both` | 格式参数错误 | 使用 `text` / `pdf` / `both`（BAT 界面用 T / PDF / B） |
| `--merge-mode 应为 each / all` | 合并模式参数错误 | 使用 `each` 或 `all` |

---

## 项目结构

```
rmrb_download/
├── rmrb_downloader.py      # 主脚本（全配置 + 批量 + PDF/文字 + exe 兼容）
├── 下载人民日报.bat          # Windows 双击启动器（优先 exe，回退 Python）
├── 人民日报下载器.exe        # 打包后的可执行文件（无需 Python，Release 提供）
├── build_bat.py             # BAT 生成器（GBK 编码）
├── config.json              # 配置文件（首次运行自动生成）
├── create_shortcut.ps1      # 桌面快捷方式生成脚本（含 ICO）
├── 人民日报下载器.ico        # 多尺寸图标（16–256）
├── icon_src.png             # 图标源图
├── test_errors.py           # 错误处理与边界测试
├── test_download.py         # 真实下载全量测试
├── rmrb_download.log        # 运行日志（自动生成）
└── pdfs_YYYYMMDD/           # 单版 PDF 目录（keep_singles=true 时保留）
```

---

## 从源码打包 exe

如需自行打包单文件 exe：

```bash
# 安装 PyInstaller（推荐国内镜像）
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

# 打包（单文件 + 控制台 + 图标 + 内置 pypdf）
pyinstaller --onefile --console --name "人民日报下载器" --icon "人民日报下载器.ico" --hidden-import pypdf --clean rmrb_downloader.py

# 产物在 dist/人民日报下载器.exe，复制到项目根目录即可
```

打包后的 exe 已内置 Python 运行时和 pypdf 库，用户无需安装 Python。首次启动因需解压临时文件可能稍慢。

---

## 测试

```bash
# 错误处理与边界测试（不下载，秒级）
python test_errors.py

# 真实下载全量测试（用 edition_filter 只留第1版加速，覆盖单日/批量/各格式）
python test_download.py
```

测试覆盖：未来日期/非法日期/非法格式/批量表达式解析/config 校验/单日 PDF/TXT/DOC/DOCX/both/批量 each/all/到今日语法/keep_singles/文件名与页数校验。

---

## 免责声明

- 本工具**仅供个人学习与研究使用**，不得用于任何商业活动。
- 《人民日报》版权归人民日报社所有，下载内容请遵守相关法律法规与网站使用条款。
- 请合理控制访问频率（`request_interval`），避免对官网造成压力。
- 官网结构若发生变化，本工具可能需要相应调整。

---

## License

MIT License
