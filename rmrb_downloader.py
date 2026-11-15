# -*- coding: utf-8 -*-
"""人民日报电子版下载器 · 命令行 / 交互式入口

  python rmrb_downloader.py                    进入交互式菜单
  python rmrb_downloader.py --ui               打开图形界面
  python rmrb_downloader.py 20260903 pdf       单日下载（text / pdf / both）
  python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode all
  python rmrb_downloader.py --init | --task-install | --task-remove
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import threading

import rmrb_core as core


# --------------------------------------------------------------------------
# 控制台适配
# --------------------------------------------------------------------------

def fix_console() -> None:
    """仅当控制台代码页是 GBK 且输出被重定向成 UTF-8 时才回落 GBK。

    原实现无条件把 stdout 重开成 GBK，在 Windows Terminal / VS Code（默认 UTF-8）
    里反而会乱码，遇到表情符号还会直接抛 UnicodeEncodeError。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        if ctypes.windll.kernel32.GetConsoleOutputCP() != 936:  # 不是 GBK 控制台
            return
        if not (sys.stdout and sys.stdout.isatty()):
            return
        enc = (getattr(sys.stdout, "encoding", "") or "").lower()
        if enc in ("gbk", "cp936", "mbcs"):
            return
        sys.stdout = open(sys.stdout.fileno(), "w", encoding="gbk",
                          errors="replace", closefd=False, buffering=1)
        sys.stderr = open(sys.stderr.fileno(), "w", encoding="gbk",
                          errors="replace", closefd=False, buffering=1)
    except Exception:
        pass


class ConsoleReporter(core.Reporter):
    """终端输出：普通行 + 单行进度（非 tty 时自动降级为逐条打印）。"""

    def __init__(self, logger=None):
        self._tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        self._dirty = False
        super().__init__(logger=logger, on_log=self._print, on_progress=self._progress)

    def _print(self, msg: str, level: str) -> None:
        if self._dirty:
            sys.stdout.write("\r" + " " * 78 + "\r")
            self._dirty = False
        prefix = {"warn": "[警告] ", "error": "[错误] ", "debug": "[调试] "}.get(level, "")
        print(prefix + msg)

    def _progress(self, fraction, text: str) -> None:
        if not text or not self._tty:
            return
        line = "  %s" % text
        sys.stdout.write("\r" + line[:78].ljust(78))
        sys.stdout.flush()
        self._dirty = True

    def finish_line(self) -> None:
        if self._dirty:
            sys.stdout.write("\r" + " " * 78 + "\r")
            self._dirty = False


# --------------------------------------------------------------------------
# 交互式菜单
# --------------------------------------------------------------------------

def ask(prompt: str):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def menu_single(cfg):
    print("\n" + "-" * 54)
    print("  单日下载")
    print("-" * 54)
    raw = ask("日期（YYYYMMDD，回车=今天）: ")
    if raw is None:
        return 0
    date = raw.strip() or datetime.date.today().strftime("%Y%m%d")
    fmt = menu_format(cfg)
    if fmt is None:
        return 0
    return run_single(cfg, date, fmt)


def menu_format(cfg) -> str:
    default = str(cfg.get("default_format", "pdf")).lower()
    hint = {"text": "T", "pdf": "P", "both": "B"}.get(default, "P")
    raw = ask("格式 [T]文字 / [P]PDF / [B]两者（回车=%s）: " % hint)
    if raw is None:
        return None
    value = raw.strip().upper()
    return {"T": "text", "P": "pdf", "B": "both"}.get(value, default)


def menu_batch(cfg):
    print("\n" + "-" * 54)
    print("  批量下载")
    print("-" * 54)
    print("  例：20260901-20260903,20260905   20260801-（到今天）")
    expr = ask("日期范围（回车=今天）: ")
    if expr is None:
        return 0
    expr = expr.strip() or datetime.date.today().strftime("%Y%m%d")
    raw = ask("合并方式 [E]每天单独 / [A]全部合并（回车=E）: ")
    if raw is None:
        return 0
    mode = "all" if raw.strip().upper() == "A" else "each"
    fmt = menu_format(cfg)
    if fmt is None:
        return 0
    return run_batch(cfg, expr, fmt, mode)


def menu_config(cfg):
    """交互式配置；直接改 dict 并保存，保证当前会话立刻生效。"""
    while True:
        print("\n" + "-" * 54)
        print("  配置")
        print("-" * 54)
        rows = [
            ("默认日期", cfg.get("default_date") or "(今天)"),
            ("默认格式", cfg.get("default_format")),
            ("下载目录", cfg.get("download_path") or "(程序目录)"),
            ("保留单版", "是" if cfg.get("keep_singles", True) else "否"),
            ("完成后打开目录", "是" if cfg.get("open_folder_after", True) else "否"),
            ("文字格式", cfg.get("text_output_format")),
            ("并发", cfg.get("concurrent")),
            ("限速(kbps)", cfg.get("rate_limit_kbps") or "不限"),
            ("PDF 引擎", cfg.get("pdf_engine")),
            ("日志级别", cfg.get("log_level")),
        ]
        for name, value in rows:
            print("    %-14s %s" % (name, value))
        print()
        print("  1. 默认格式    2. 下载目录    3. 保留单版    4. 打开目录")
        print("  5. 文字格式    6. 并发/限速   7. PDF 引擎    8. 日志级别")
        print("  9. 恢复默认    0. 返回")
        print("-" * 54)
        choice = ask("请选择: ")
        if choice is None:
            return
        choice = choice.strip()

        if choice == "1":
            value = ask("默认格式 [text/pdf/both]（当前 %s）: " % cfg.get("default_format"))
            if value and value.strip().lower() in ("text", "pdf", "both"):
                cfg["default_format"] = value.strip().lower()
                core.save_config(cfg)
                print("[配置] 默认格式 = %s" % cfg["default_format"])
        elif choice == "2":
            value = ask("下载目录（空=程序目录，当前 %s）: "
                        % (cfg.get("download_path") or "空"))
            if value is not None:
                cfg["download_path"] = value.strip()
                core.save_config(cfg)
                print("[配置] 下载目录 = %s" % (cfg["download_path"] or "(程序目录)"))
        elif choice == "3":
            cfg["keep_singles"] = not cfg.get("keep_singles", True)
            core.save_config(cfg)
            print("[配置] 保留单版 = %s" % ("是" if cfg["keep_singles"] else "否"))
        elif choice == "4":
            cfg["open_folder_after"] = not cfg.get("open_folder_after", True)
            core.save_config(cfg)
            print("[配置] 完成后打开目录 = %s" % ("是" if cfg["open_folder_after"] else "否"))
        elif choice == "5":
            value = ask("文字格式 [TXT/MD/DOC/DOCX]（当前 %s）: %s" % (cfg.get("text_output_format"), ""))
            if value and value.strip().upper() in ("TXT", "MD", "DOC", "DOCX"):
                cfg["text_output_format"] = value.strip().upper()
                core.save_config(cfg)
        elif choice == "6":
            value = ask("并发 1-16（当前 %s）: " % cfg.get("concurrent"))
            if value and value.strip().isdigit() and 1 <= int(value) <= 16:
                cfg["concurrent"] = int(value.strip())
            value = ask("限速 kbps，0=不限（当前 %s）: " % cfg.get("rate_limit_kbps"))
            if value and value.strip().isdigit():
                cfg["rate_limit_kbps"] = int(value.strip())
            core.save_config(cfg)
        elif choice == "7":
            value = ask("PDF 引擎 [auto/builtin/pypdf]（当前 %s）: %s"
                        % (cfg.get("pdf_engine"), ""))
            if value and value.strip().lower() in ("auto", "builtin", "pypdf"):
                cfg["pdf_engine"] = value.strip().lower()
                core.save_config(cfg)
        elif choice == "8":
            value = ask("日志级别 [quiet/normal/debug]（当前 %s）: %s"
                        % (cfg.get("log_level"), ""))
            if value and value.strip().lower() in ("quiet", "normal", "debug"):
                cfg["log_level"] = value.strip().lower()
                core.save_config(cfg)
        elif choice == "9":
            defaults, _ = core.validate_config(dict(core.DEFAULT_CONFIG))
            cfg.clear()
            cfg.update(defaults)
            core.save_config(cfg)
            print("[配置] 已恢复默认配置（当前会话立即生效）")
        elif choice == "0":
            return


def menu_main(cfg):
    while True:
        print("\n" + "=" * 54)
        print("  %s  v%s" % (core.APP_NAME, core.APP_VERSION))
        print("=" * 54)
        print("  1. 单日下载      2. 批量下载")
        print("  3. 图形界面      4. 配置")
        print("  5. 打开下载目录  6. 退出")
        print("=" * 54)
        choice = ask("请选择 [1-6]: ")
        if choice is None or choice.strip() == "6":
            print("再见！")
            return 0
        choice = choice.strip()
        if choice == "1":
            menu_single(cfg)
            ask("\n回车返回主菜单...")
        elif choice == "2":
            menu_batch(cfg)
            ask("\n回车返回主菜单...")
        elif choice == "3":
            return launch_ui()
        elif choice == "4":
            menu_config(cfg)
        elif choice == "5":
            core.open_folder(core.out_root(cfg))
        else:
            print("[错误] 无效选择")


# --------------------------------------------------------------------------
# 运行封装
# --------------------------------------------------------------------------

def make_reporter(cfg) -> ConsoleReporter:
    log_name = str(cfg.get("log_file") or "").strip()
    logger = None
    if log_name:
        logger = core.Logger(os.path.join(core.HERE, log_name),
                             str(cfg.get("log_level", "normal")),
                             int(cfg.get("log_max_kb", 512) or 0))
    return ConsoleReporter(logger=logger)


def finish(reporter, cfg, code: int, path: str = "") -> int:
    reporter.finish_line()
    core.notify(cfg, core.APP_NAME, "人民日报下载完成" if code == 0 else "人民日报下载失败，详见日志")
    if code == 0 and path and cfg.get("open_folder_after", True):
        core.reveal(path)
        print("[完成] 文件位置已打开：%s" % path)
    elif code == 0:
        print("[完成] 下载完成")
    return code


def run_single(cfg, date: str, fmt: str) -> int:
    reporter = make_reporter(cfg)
    session = core.Session(cfg, reporter)
    try:
        code = session.run_single(date, fmt)
    except core.Stopped:
        reporter.error("已中断")
        return 130
    except KeyboardInterrupt:
        reporter.error("已中断")
        return 130
    except Exception as exc:
        reporter.error("未预料的错误：%s" % core.describe_error(exc))
        return 1
    return finish(reporter, session.cfg, code, session.last_output)


def run_batch(cfg, expr: str, fmt: str, mode: str) -> int:
    reporter = make_reporter(cfg)
    session = core.Session(cfg, reporter)
    try:
        code = session.run_batch(expr, fmt, mode)
    except core.Stopped:
        reporter.error("已中断")
        return 130
    except KeyboardInterrupt:
        reporter.error("已中断")
        return 130
    except Exception as exc:
        reporter.error("未预料的错误：%s" % core.describe_error(exc))
        return 1
    return finish(reporter, session.cfg, code, session.last_output)


def launch_ui() -> int:
    try:
        import rmrb_ui
    except Exception as exc:
        print("[错误] 无法加载图形界面：%s（tkinter 是否已安装？）" % exc)
        return 1
    return rmrb_ui.main()


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rmrb_downloader",
        description="%s v%s —— 人民日报电子版下载器" % (core.APP_NAME, core.APP_VERSION),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例：
  %(prog)s                        进入交互式菜单
  %(prog)s --ui                   打开图形界面
  %(prog)s 20260903 pdf           下载指定日期的全部版面 PDF 并合并
  %(prog)s 20260903 text          抓取当日正文
  %(prog)s --batch "20260901-20260903" pdf --merge-mode all
  %(prog)s --batch "20260801-" both
  %(prog)s --init                 生成/刷新 config.json
  %(prog)s --task-install         注册每日自动下载计划任务
""")
    parser.add_argument("args", nargs="*", metavar="日期 格式",
                        help="[YYYYMMDD] [text|pdf|both]")
    parser.add_argument("--batch", metavar="表达式",
                        help="批量下载，如 20260901-20260903,20260905")
    parser.add_argument("--merge-mode", choices=["each", "all"],
                        help="批量合并方式：each=每天单独，all=全部合并")
    parser.add_argument("--ui", action="store_true", help="打开图形界面")
    parser.add_argument("--init", action="store_true", help="生成/刷新 config.json")
    parser.add_argument("--task-install", action="store_true", help="注册每日自动下载计划任务")
    parser.add_argument("--task-remove", action="store_true", help="删除计划任务")
    parser.add_argument("--engine", choices=["auto", "builtin", "pypdf"], help="PDF 合并引擎")
    parser.add_argument("--force", action="store_true", help="忽略 skip_existing，强制重新下载")
    parser.add_argument("--no-open", action="store_true", help="完成后不打开文件夹")
    parser.add_argument("--concurrent", type=int, metavar="N", help="并发下载数（1-16）")
    parser.add_argument("--text-format", choices=["TXT", "MD", "DOC", "DOCX"],
                        help="文字输出格式")
    parser.add_argument("-V", "--version", action="version",
                        version="%(prog)s " + core.APP_VERSION)
    return parser


def main(argv=None) -> int:
    fix_console()
    parser = build_parser()
    options = parser.parse_args(argv)

    cfg = core.load_config()
    cfg, warns = core.validate_config(cfg)
    if cfg.get("_load_error"):
        print("[警告] 配置文件读取失败：%s" % cfg["_load_error"])
        cfg.pop("_load_error", None)
    for warn in warns:
        print("[配置警告] %s" % warn)
    if warns:
        core.save_config(cfg)

    # 命令行覆盖
    if options.engine:
        cfg["pdf_engine"] = options.engine
    if options.force:
        cfg["skip_existing"] = False
    if options.no_open:
        cfg["open_folder_after"] = False
    if options.concurrent:
        cfg["concurrent"] = max(1, min(16, options.concurrent))
    if options.text_format:
        cfg["text_output_format"] = options.text_format

    if options.init:
        path = core.save_config(cfg)
        print("已生成/更新配置：%s" % path)
        return 0
    if options.task_install:
        return core.install_task(cfg, ConsoleReporter())
    if options.task_remove:
        return core.remove_task(ConsoleReporter())
    if options.ui:
        return launch_ui()

    if options.batch is not None:
        fmt = ""
        if options.args:
            fmt = next((a.lower() for a in options.args if a.lower() in ("text", "pdf", "both")), "")
        fmt = fmt or str(cfg.get("default_format", "pdf"))
        mode = options.merge_mode or str(cfg.get("batch_merge_mode", "each"))
        return run_batch(cfg, options.batch, fmt, mode)

    # 位置参数：兼容 `20260903 pdf` 与 `pdf` 两种写法
    if not options.args:
        return menu_main(cfg)

    date_arg, fmt_arg = "", ""
    first = options.args[0]
    if first.lower() in ("text", "pdf", "both"):
        fmt_arg = first.lower()
    elif first.isdigit():
        if len(first) != 8:
            print("[错误] 日期应为 8 位数字 YYYYMMDD（例如 20260902），当前输入: %s" % first)
            return 1
        date_arg = first
        if len(options.args) > 1:
            fmt_arg = options.args[1]
    else:
        parser.print_help()
        return 1
    return run_single(cfg, date_arg, fmt_arg)


if __name__ == "__main__":
    sys.exit(main())
