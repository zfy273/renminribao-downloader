# People's Daily Downloader / 人民日报电子版下载器

> [中文](../README.md) | English | [日本語](README_JA.md) | [한국어](README_KO.md) | [Français](README_FR.md) | [Deutsch](README_DE.md) | [Italiano](README_IT.md) | [हिन्दी](README_HI.md) | [ไทย](README_TH.md) | [العربية](README_AR.md) | [Русский](README_RU.md) | [Español](README_ES.md)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

A pure-Python tool for automatically downloading and merging the electronic edition of **People's Daily (人民日报)**. Supports PDF page download, article text extraction (TXT/DOC/DOCX), batch date downloading, and full configuration — no browser or driver required.

---

## Features

- **PDF mode**: downloads all page PDFs of the day and merges them into one complete file
- **Text mode**: extracts article body text from all pages, outputs as `TXT` / `DOC` / `DOCX` (zero extra dependencies)
- **both mode**: generates PDF and text versions simultaneously
- **Batch download**: supports date-range expressions; either merge per date or merge everything into one cross-date file
- **Fully configurable**: 30+ options (network, UI, output, rate limit, proxy, scheduling) via `config.json`
- **Auto dependency install**: automatically installs `pypdf` on first run (official PyPI → Tsinghua mirror fallback)
- **Real-time progress**: download progress bar, speed display, auto-open file location when done
- **Robust error handling**: network retries, file-in-use auto-retry, future/invalid date and expression interception, friendly Chinese error messages

---

## Requirements

| Item | Requirement |
|---|---|
| OS | Windows 10 / 11 (the `.bat` launcher is Windows-specific; the core script is cross-platform) |
| Python | **3.8+** (3.10+ recommended; verified on 3.13 / 3.14) |
| Network | Must be able to reach `paper.people.com.cn` |
| Browser | **None** — no Chrome / Edge / WebDriver needed |

### Dependencies

| Library | Purpose | Installation |
|---|---|---|
| `pypdf` | PDF merging | **Auto-installed on first run**; or manually `pip install pypdf` |
| (none) | Text output TXT/DOC/DOCX | Pure standard library (`zipfile` hand-writes OOXML), zero dependencies |
| `PyMuPDF` (optional) | Only for rendering PDF preview screenshots in tests | `pip install pymupdf`, not needed for normal use |

---

## Quick Start

### Option 1: Double-click the BAT (recommended for Windows users)

1. Make sure Python is installed and on PATH (or the `py` launcher is available)
2. Double-click `下载人民日报.bat`
3. Enter a date (Enter = today), choose a format (T / PDF / B)
4. Wait for download and merge; the file location opens automatically when done

### Option 2: Command line

```bash
# Single-day PDF (today by default)
python rmrb_downloader.py

# Specific date + format
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# Batch (date range, merge per date)
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# Batch (merge everything into one cross-date file)
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# From a date to today (leave the right end empty)
python rmrb_downloader.py --batch "20260801-" pdf

# Generate / refresh default config
python rmrb_downloader.py --init

# Register / remove daily auto-download scheduled task
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## Configuration (config.json)

`config.json` is generated automatically on first run. All options:

### Network & Fetching

| Key | Type | Default | Description |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | Base URL of the electronic edition |
| `rate_limit_kbps` | number | `0` | Download rate limit in KB/s; `0` = unlimited |
| `timeout` | int | `30` | Per-request timeout in seconds |
| `retry` | int | `3` | Retry count on failure |
| `retry_interval` | float | `2.0` | Retry interval in seconds |
| `request_interval` | float | `0.2` | Interval between requests (seconds), avoids rate-limiting |
| `concurrent` | int | `1` | Concurrent download threads (1–16) |
| `proxy` | string | `""` | HTTP/HTTPS proxy address; empty = no proxy |
| `user_agent` | string | Chrome UA | Request User-Agent |

### UI

| Key | Type | Default | Description |
|---|---|---|---|
| `color_foreground` | string | `"A"` | cmd foreground color (hex 0–F) |
| `color_background` | string | `"0"` | cmd background color (hex 0–F) |
| `window_title` | string | `人民日报电子版下载器` | Console window title |
| `show_progress` | bool | `true` | Show download progress bar |

### Date & Content

| Key | Type | Default | Description |
|---|---|---|---|
| `default_date` | string | `""` | Default date `YYYYMMDD`; empty = today |
| `default_format` | string | `"pdf"` | Default format: `pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **Edition whitelist**: when non-empty, only listed edition numbers are downloaded (e.g. `[1,2]` = only pages 1 and 2); empty = all editions |
| `holiday_skip` | bool | `false` | In single-day mode, silently skip (exit 0) when no editions are found |

### Batch Download

| Key | Type | Default | Description |
|---|---|---|---|
| `batch_enable` | bool | `false` | When `true`, double-clicking the BAT shows the **batch download interface** |
| `batch_merge_mode` | string | `"each"` | `each` = merge per date; `all` = merge all dates into one big file |
| `download_path` | string | `""` | Download root directory; empty = script folder; relative paths resolve against the script folder, absolute paths also accepted |

### Output & Merging

| Key | Type | Default | Description |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | Single-page PDF directory template, `{date}` replaced with the date |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | Merged PDF filename template (without extension) |
| `auto_merge` | bool | `true` | Auto-merge in single-day mode |
| `keep_singles` | bool | `true` | Keep single-page PDF directory after merging; `false` deletes it after a successful merge |
| `open_folder_after` | bool | `true` | Auto-open the file location when done |

### Text Output

| Key | Type | Default | Description |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | Text output format: `TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | Text filename template (without extension) |
| `text_include_edition` | bool | `true` | Include edition title separators in the text output |

### Logging & Notifications

| Key | Type | Default | Description |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | Log filename; empty = no logging |
| `log_level` | string | `"normal"` | Log level: `quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | Beep when done |
| `msg_on_done` | bool | `false` | Pop up a Windows message box when done |

### Scheduling

| Key | Type | Default | Description |
|---|---|---|---|
| `auto_run` | bool | `false` | Enable daily auto-download (requires `--task-install` first) |
| `auto_run_time` | string | `"08:00"` | Daily auto-run time `HH:MM` |

> Invalid config values (e.g. negative rate limit, out-of-range concurrency, invalid color codes) are automatically reset to defaults with a warning at startup — no crash.

---

## Batch Download Details

### Date-range expression

Enter in the BAT batch interface or the `--batch` argument; comma-separated segments:

| Expression | Meaning |
|---|---|
| `20260901-20260903` | 2026-09-01 to 2026-09-03 (inclusive) |
| `20260905` | Only 2026-09-05 |
| `20260801-` | 2026-08-01 to **today** (empty right end) |
| `20260901-20260903,20260905` | Range + single day (auto-dedup, sorted by date) |

- Dates must be real (e.g. `20260134`, `20261301` are intercepted with an error)
- Start date later than end date raises an error
- Dates with no editions (holidays / unpublished) are automatically skipped and counted in the summary

### Merge modes

| Mode | Behavior | Example output filename |
|---|---|---|
| `each` | Each date downloaded and merged separately | `人民日报-2026-09-02-完整版.pdf`, `人民日报-2026-09-03-完整版.pdf` |
| `all` | All editions across all dates merged into **one cross-date file** | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

Text output supports `each` / `all` as well.

### Enable the BAT batch interface

Edit `config.json`, set `"batch_enable"` to `true`, then double-click the BAT to enter the batch interface (enter range → choose merge mode → choose format).

---

## Text Output Formats

| Format | Description | Dependencies |
|---|---|---|
| `TXT` | UTF-8 plain text with edition titles and article body | none |
| `DOC` | HTML content saved as `.doc`, opens directly in Microsoft Word / WPS | none |
| `DOCX` | Standard OOXML (minimal document structure hand-written with `zipfile`), opens in Word/WPS/LibreOffice | none |

Switch by setting `"text_output_format": "DOCX"` etc. in `config.json`.

---

## Common Errors & Solutions

| Error message | Cause | Solution |
|---|---|---|
| `未来日期，人民日报尚未出版` (future date) | Entered a date after today | Check the date, or fix `default_date` |
| `日期不存在（月份或日期越界）` (date does not exist) | e.g. `20261301`, `20260134` | Enter a real date |
| `日期应为 8 位数字 YYYYMMDD` (date must be 8 digits) | Wrong date length | Use `YYYYMMDD`, e.g. `20260903` |
| `未找到任何版面` (no editions found) | Date unpublished/holiday, `edition_filter` filtered everything out, or network error | Try a workday; check `edition_filter`; see the `[网络]` hint above |
| `无法安装合并库 pypdf` (cannot install pypdf) | No network for pip | Run `pip install pypdf` manually, or configure a proxy and retry |
| `合并失败：目标文件正被占用` (merge failed: file in use) | The same-named PDF is open in a reader / Explorer preview | Close the open file and retry, or change `merged_filename` / `download_path` |
| `域名解析失败 / 网络连接失败` (DNS / network failure) | No network, DNS issue, or wrong proxy | Check network; check `proxy` in `config.json` |
| `连接/读取超时` (timeout) | Slow network or slow server | Increase `timeout` (e.g. 60), retry later |
| `服务器返回 HTTP 403/429` (rate-limited) | Too frequent requests | Increase `request_interval` (e.g. 1.0), lower `concurrent` |
| `日期表达式错误：无效日期` (invalid batch expression) | Batch expression contains an invalid date | Use `YYYYMMDD`, comma-separated ranges |
| `格式参数应为 text / pdf / both` (wrong format) | Invalid format argument | Use `text` / `pdf` / `both` (BAT interface uses T / PDF / B) |
| `--merge-mode 应为 each / all` (wrong merge mode) | Invalid merge mode argument | Use `each` or `all` |

---

## Project Structure

```
rmrb_download/
├── rmrb_downloader.py      # Main script (full config + batch + PDF/text)
├── 下载人民日报.bat          # Windows double-click launcher (single/batch UI)
├── build_bat.py             # BAT generator (GBK encoding)
├── config.json              # Config file (auto-generated on first run)
├── create_shortcut.ps1      # Desktop shortcut generator (with ICO)
├── 人民日报下载器.ico        # Multi-size icon (16–256)
├── icon_src.png             # Icon source image
├── test_errors.py           # Error-handling & boundary tests
├── test_download.py         # Real-download full test suite
├── rmrb_download.log        # Runtime log (auto-generated)
└── pdfs_YYYYMMDD/           # Single-page PDF directory (kept when keep_singles=true)
```

---

## Testing

```bash
# Error-handling & boundary tests (no download, instant)
python test_errors.py

# Real-download full tests (uses edition_filter to keep only page 1 for speed;
# covers single-day/batch/all formats)
python test_download.py
```

Coverage: future date / invalid date / invalid format / batch expression parsing / config validation / single-day PDF / TXT / DOC / DOCX / both / batch each / batch all / to-today syntax / keep_singles / filename & page-count verification.

---

## Disclaimer

- This tool is **for personal learning and research only**; any commercial use is prohibited.
- People's Daily is copyrighted by People's Daily Press. Downloaded content must comply with applicable laws and the website's terms of use.
- Please keep access frequencies reasonable (`request_interval`) to avoid stressing the official site.
- If the official site structure changes, this tool may need corresponding adjustments.

---

## License

MIT License
