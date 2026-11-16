# -*- coding: utf-8 -*-
"""人民日报电子版下载器 · Windows 原生界面

界面全部使用 tkinter/ttk 的标准控件（vista 主题 = Windows 原生视觉），
不做任何自绘装饰；下载在后台线程跑，界面通过队列接收日志与进度。
"""
from __future__ import annotations

import datetime
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import rmrb_core as core

ICON_NAME = "人民日报下载器.ico"
SPEED_MAP = {"礼貌": 0.2, "标准": 0.05, "极速": 0.0}
SPEED_CONCURRENCY = {"礼貌": 4, "标准": 6, "极速": 8}
SPLIT_MAP = {"自动": 0, "关闭": 1, "2 路": 2, "4 路": 4, "8 路": 8}


def enable_dpi_awareness() -> None:
    """必须在创建 Tk 之前调用，否则窗口会被系统位图拉伸（发虚）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # 系统级 DPI 感知
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def windows_text_scale() -> float:
    """读取 Windows「设置 → 辅助功能 → 文本大小」，100 表示 100%。"""
    if sys.platform != "win32":
        return 1.0
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Accessibility") as key:
            value, _ = winreg.QueryValueEx(key, "TextScaleFactor")
        return max(1.0, min(2.0, float(value) / 100.0))
    except Exception:
        return 1.0


def system_ui_font(root: tk.Tk):
    """取系统默认 UI 字体，并按 DPI 与文本缩放换算出实际字号。"""
    import tkinter.font as tkfont
    try:
        base = tkfont.nametofont("TkDefaultFont")
        family = base.actual("family") or "Segoe UI"
        size = int(base.actual("size") or 9)
        if size < 0:                       # 负值表示像素，换算成磅
            size = max(9, round(-size * 72.0 / float(root.winfo_fpixels("1i"))))
    except Exception:
        family, size = "Segoe UI", 9
    scaled = max(9, round(size * windows_text_scale()))
    return family, scaled


def icon_path() -> Optional[str]:
    """打包后图标在 _MEIPASS 里，开发时在脚本目录。"""
    candidates = [
        os.path.join(getattr(sys, "_MEIPASS", ""), ICON_NAME) if getattr(sys, "_MEIPASS", "") else "",
        os.path.join(core.HERE, ICON_NAME),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cfg = core.load_config()
        self.cfg, self.warns = core.validate_config(self.cfg)
        self.ui_state = dict(self.cfg.get("ui") or {})
        self.queue: "queue.Queue[tuple]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.session: Optional[core.Session] = None
        self.last_output = ""

        root.title("%s  v%s" % (core.APP_NAME, core.APP_VERSION))
        self._setup_style()
        root.minsize(int(760 * self.scale), int(620 * self.scale))
        self._build()
        self._load_state()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(80, self._drain)

    # ------------------------------------------------------------------ 样式
    def _setup_style(self) -> None:
        style = ttk.Style()
        for theme in ("vista", "winnative", "xpnative", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        root = self.root
        # Tk 的 scaling 单位是"每磅多少像素"，96 DPI 时 = 96/72 ≈ 1.333。
        # 之前写成 /96 会让整个界面缩小 25%，这是字小的根因。
        dpi = float(root.winfo_fpixels("1i"))
        self.scale = max(0.75, min(3.0, dpi / 96.0))
        try:
            root.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass

        family, size = system_ui_font(root)
        self.font = (family, size)
        self.font_bold = (family, size, "bold")
        self.log_font = (family, size)
        # 让 ttk / 菜单 / 文本控件都用同一套字号
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                     "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
            try:
                tkfont.nametofont(name).configure(family=family, size=size)
            except Exception:
                pass
        try:
            root.option_add("*Font", self.font)
        except Exception:
            pass
        style.configure("TLabel", font=self.font)
        style.configure("TButton", font=self.font)
        style.configure("TCheckbutton", font=self.font)
        style.configure("TRadiobutton", font=self.font)
        style.configure("TLabelframe.Label", font=self.font)
        style.configure("Treeview", font=self.font)
        style.configure("TNotebook.Tab", font=self.font,
                        padding=(int(14 * self.scale), int(5 * self.scale)))
        style.configure("TEntry", padding=(int(4 * self.scale), int(2 * self.scale)))
        style.configure("TCombobox", padding=(int(3 * self.scale), int(1 * self.scale)))

    # ------------------------------------------------------------------ 布局
    def _build(self) -> None:
        root = self.root
        icon = icon_path()
        if icon:
            try:
                root.iconbitmap(default=icon)
            except Exception:
                pass

        outer = ttk.Frame(root, padding=(10, 10, 10, 8))
        outer.pack(fill="both", expand=True)

        # 共享状态：多个页签绑定同一变量，改一处即全同步

        # 共享状态：多个页签绑定同一变量，改一处即全同步
        self.path_var = tk.StringVar()
        self.var_open = tk.BooleanVar(value=True)
        self.var_keep = tk.BooleanVar(value=True)
        self.var_skip = tk.BooleanVar(value=False)
        self.var_engine = tk.StringVar(value="auto")
        self.var_log = tk.StringVar(value="normal")
        self.var_timeout = tk.StringVar(value="30")
        self.var_retry = tk.StringVar(value="3")
        self.var_concurrent = tk.StringVar(value="1")
        self.var_text_concurrent = tk.StringVar(value="1")
        self.var_rate = tk.StringVar(value="0")
        self.var_speed = tk.StringVar(value="标准")
        self.var_split = tk.StringVar(value="自动")
        self.var_proxy = tk.StringVar()

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="x")
        self._build_single_tab()
        self._build_batch_tab()
        self._build_settings_tab()

        # ---- 进度 ----
        progress = ttk.Frame(outer, padding=(0, 10, 0, 6))
        progress.pack(fill="x")
        self.progress = ttk.Progressbar(progress, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)
        self.progress_label = ttk.Label(progress, text="就绪", width=26, anchor="e")
        self.progress_label.pack(side="left", padx=(10, 0))

        # ---- 日志 ----
        logbox = ttk.LabelFrame(outer, text="运行日志", padding=6)
        logbox.pack(fill="both", expand=True)
        self.log = tk.Text(logbox, height=12, wrap="word", relief="solid", borderwidth=1,
                           font=self.log_font, undo=False,
                           background="white", foreground="#1a1a1a",
                           insertwidth=0, padx=6, pady=4)
        scroll = ttk.Scrollbar(logbox, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set, state="disabled")
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.log.tag_configure("warn", foreground="#8a5a00")
        self.log.tag_configure("error", foreground="#a11")
        self.log.tag_configure("debug", foreground="#666666")

        self.status = ttk.Label(outer, text="", anchor="w", foreground="#555")
        self.status.pack(fill="x", pady=(2, 4))

        # ---- 按钮 ----
        actions = ttk.Frame(outer, padding=(0, 2, 0, 0))
        actions.pack(fill="x")
        self.start_btn = ttk.Button(actions, text="开始下载", command=self.on_start, width=14)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="停止", command=self.on_stop, width=10,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="打开输出目录", command=self.on_open, width=14) \
            .pack(side="left", padx=(8, 0))
        self.open_last_btn = ttk.Button(actions, text="打开最近文件", command=self.on_open_last,
                                        width=14, state="disabled")
        self.open_last_btn.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="退出", command=self.on_close, width=10) \
            .pack(side="right")

    def _output_group(self, parent) -> None:
        """输出目录 + 完成后动作。多个页签共用同一组变量，随便在哪改都生效。"""
        box = ttk.LabelFrame(parent, text="输出", padding=10)
        box.pack(fill="x", pady=(12, 0))
        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="目录").pack(side="left")
        ttk.Entry(row, textvariable=self.path_var).pack(side="left", fill="x", expand=True,
                                                       padx=(8, 8))
        ttk.Button(row, text="浏览…", width=8, command=self.on_browse).pack(side="left")
        ttk.Checkbutton(box, text="完成后打开文件位置", variable=self.var_open) \
            .pack(anchor="w", pady=(8, 0))
        ttk.Label(box, text="留空 = 程序所在目录（config.json 旁边）", foreground="#666") \
            .pack(anchor="w", pady=(4, 0))

    def _build_single_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="单日下载")

        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Label(row, text="日期").pack(side="left")
        self.date_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.date_var, width=14, font=self.font)
        entry.pack(side="left", padx=(8, 8))
        ttk.Button(row, text="今天", width=7,
                   command=lambda: self.date_var.set(self._today())).pack(side="left")
        ttk.Button(row, text="昨天", width=7,
                   command=lambda: self.date_var.set(self._yesterday())).pack(side="left", padx=(6, 0))
        ttk.Label(row, text="格式：YYYYMMDD", foreground="#666").pack(side="left", padx=(12, 0))

        fmt = ttk.LabelFrame(tab, text="输出内容", padding=10)
        fmt.pack(fill="x", pady=(12, 0))
        self.single_pdf = tk.BooleanVar(value=True)
        self.single_text = tk.BooleanVar(value=False)
        ttk.Checkbutton(fmt, text="PDF 版面（自动合并为完整版）",
                        variable=self.single_pdf).pack(anchor="w")
        line = ttk.Frame(fmt)
        line.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(line, text="文章正文", variable=self.single_text).pack(side="left")
        ttk.Label(line, text="文字格式").pack(side="left", padx=(16, 6))
        self.single_text_fmt = tk.StringVar(value="TXT")
        ttk.Combobox(line, textvariable=self.single_text_fmt, width=7, state="readonly",
                     values=["TXT", "MD", "DOC", "DOCX"]).pack(side="left")

        edition = ttk.LabelFrame(tab, text="版面筛选", padding=10)
        edition.pack(fill="x", pady=(12, 0))
        erow = ttk.Frame(edition)
        erow.pack(fill="x")
        ttk.Label(erow, text="只下载这些版面（留空 = 全部）").pack(side="left")
        self.edition_var = tk.StringVar()
        ttk.Entry(erow, textvariable=self.edition_var, width=24).pack(side="left", padx=(10, 0))
        ttk.Label(edition, text="示例：1,2,3  表示只下第 1、2、3 版", foreground="#666") \
            .pack(anchor="w", pady=(6, 0))

        self._output_group(tab)

    def _build_batch_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="批量下载")

        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Label(row, text="日期范围").pack(side="left")
        self.batch_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.batch_var, width=38, font=self.font) \
            .pack(side="left", padx=(8, 0))
        ttk.Button(row, text="本周", width=7,
                   command=lambda: self.batch_var.set(self._this_week())).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="本月", width=7,
                   command=lambda: self.batch_var.set(self._this_month())).pack(side="left", padx=(6, 0))
        ttk.Label(tab, text="示例：20260901-20260903,20260905    20260801-（到今天）",
                  foreground="#666").pack(anchor="w", pady=(6, 0))

        mode = ttk.LabelFrame(tab, text="合并方式", padding=10)
        mode.pack(fill="x", pady=(12, 0))
        self.batch_mode = tk.StringVar(value="each")
        ttk.Radiobutton(mode, text="每天单独生成一个文件", value="each",
                        variable=self.batch_mode).pack(anchor="w")
        ttk.Radiobutton(mode, text="全部日期合并成一个文件", value="all",
                        variable=self.batch_mode).pack(anchor="w", pady=(4, 0))

        fmt = ttk.LabelFrame(tab, text="输出内容", padding=10)
        fmt.pack(fill="x", pady=(12, 0))
        self.batch_pdf = tk.BooleanVar(value=True)
        self.batch_text = tk.BooleanVar(value=False)
        ttk.Checkbutton(fmt, text="PDF 版面", variable=self.batch_pdf).pack(anchor="w")
        line = ttk.Frame(fmt)
        line.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(line, text="文章正文", variable=self.batch_text).pack(side="left")
        ttk.Label(line, text="文字格式").pack(side="left", padx=(16, 6))
        self.batch_text_fmt = tk.StringVar(value="TXT")
        ttk.Combobox(line, textvariable=self.batch_text_fmt, width=7, state="readonly",
                     values=["TXT", "MD", "DOC", "DOCX"]).pack(side="left")

        self._output_group(tab)
        ttk.Label(tab, text="无版面的日期（休刊）会自动跳过并计入汇总，不会中断整批任务。",
                  foreground="#666").pack(anchor="w", pady=(10, 0))

    def _build_settings_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="设置")

        out = ttk.LabelFrame(tab, text="输出目录", padding=10)
        out.pack(fill="x")
        row = ttk.Frame(out)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="浏览…", width=8, command=self.on_browse).pack(side="left", padx=(8, 0))
        ttk.Label(out, text="留空 = 程序所在目录（config.json 旁边）", foreground="#666") \
            .pack(anchor="w", pady=(6, 0))

        net = ttk.LabelFrame(tab, text="网络", padding=10)
        net.pack(fill="x", pady=(10, 0))
        grid = ttk.Frame(net)
        grid.pack(fill="x")
        fields = [
            ("超时(秒)", self.var_timeout, 8), ("重试次数", self.var_retry, 8),
            ("PDF 并发", self.var_concurrent, 8), ("正文并发", self.var_text_concurrent, 8),
            ("限速(kbps)", self.var_rate, 10), ("代理", self.var_proxy, 30),
        ]
        for index, (label, var, width) in enumerate(fields):
            column = (index % 3) * 2
            row_index = index // 3
            ttk.Label(grid, text=label).grid(row=row_index, column=column, sticky="w",
                                             padx=(0, 6), pady=4)
            ttk.Entry(grid, textvariable=var, width=width).grid(
                row=row_index, column=column + 1, sticky="w", padx=(0, 18), pady=4)
        ttk.Label(net, text="代理示例：http://127.0.0.1:7890    限速 0 = 不限",
                  foreground="#666").pack(anchor="w", pady=(4, 0))

        more = ttk.LabelFrame(tab, text="行为", padding=10)
        more.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(more, text="合并成功后保留单版 PDF 目录",
                        variable=self.var_keep).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(more, text="完成后打开文件位置",
                        variable=self.var_open).grid(row=0, column=1, sticky="w", padx=(24, 0))
        ttk.Checkbutton(more, text="跳过已下载的版面",
                        variable=self.var_skip).grid(row=1, column=0, sticky="w", pady=2)
        row2 = ttk.Frame(more)
        row2.grid(row=1, column=1, sticky="w", padx=(24, 0))
        ttk.Label(row2, text="PDF 引擎").pack(side="left")
        ttk.Combobox(row2, textvariable=self.var_engine, width=9, state="readonly",
                     values=["auto", "builtin", "pypdf"]).pack(side="left", padx=(6, 0))
        row3 = ttk.Frame(more)
        row3.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(row3, text="下载速度").pack(side="left")
        speed_box = ttk.Combobox(row3, textvariable=self.var_speed, width=10, state="readonly",
                                 values=["礼貌", "标准", "极速"])
        speed_box.pack(side="left", padx=(6, 16))
        speed_box.bind("<<ComboboxSelected>>", self.on_speed_changed)
        ttk.Label(row3, text="分片").pack(side="left")
        ttk.Combobox(row3, textvariable=self.var_split, width=8, state="readonly",
                     values=["自动", "关闭", "2 路", "4 路", "8 路"]).pack(side="left", padx=(6, 0))
        ttk.Label(row3, text="日志级别").pack(side="left")
        ttk.Combobox(row3, textvariable=self.var_log, width=9, state="readonly",
                     values=["quiet", "normal", "debug"]).pack(side="left", padx=(6, 0))
        ttk.Label(row3, text="日志写入 config.json 所在目录", foreground="#666") \
            .pack(side="left", padx=(12, 0))

        foot = ttk.Frame(tab)
        foot.pack(fill="x", pady=(14, 0))
        ttk.Button(foot, text="保存配置", command=self.on_save_config, width=12).pack(side="left")
        ttk.Label(foot, text="保存在 config.json，命令行与界面共用同一份。",
                  foreground="#666").pack(side="left", padx=(12, 0))

    # ------------------------------------------------------------------ 状态
    def _today(self) -> str:
        return datetime.date.today().strftime("%Y%m%d")

    def _yesterday(self) -> str:
        return (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")

    def _this_week(self) -> str:
        today = datetime.date.today()
        start = today - datetime.timedelta(days=today.weekday())
        return "%s-%s" % (start.strftime("%Y%m%d"), today.strftime("%Y%m%d"))

    def _this_month(self) -> str:
        today = datetime.date.today()
        return "%s-%s" % (today.replace(day=1).strftime("%Y%m%d"), today.strftime("%Y%m%d"))

    def _load_state(self) -> None:
        cfg, ui = self.cfg, self.ui_state
        self.date_var.set(str(ui.get("date") or cfg.get("default_date") or self._today()))
        self.batch_var.set(str(ui.get("batch") or ""))
        self.edition_var.set(str(ui.get("edition") or ""))
        self.single_pdf.set(bool(ui.get("pdf", True)))
        self.single_text.set(bool(ui.get("text", False)))
        fmt = str(cfg.get("text_output_format", "TXT")).upper()
        self.single_text_fmt.set(fmt if fmt in ("TXT", "MD", "DOC", "DOCX") else "TXT")
        self.batch_pdf.set(bool(ui.get("pdf", True)))
        self.batch_text.set(bool(ui.get("text", False)))
        self.batch_text_fmt.set(self.single_text_fmt.get())
        self.batch_mode.set(str(cfg.get("batch_merge_mode", "each")))
        self.path_var.set(str(cfg.get("download_path") or ""))
        self.var_timeout.set(str(cfg.get("timeout", 30)))
        self.var_retry.set(str(cfg.get("retry", 3)))
        self.var_concurrent.set(str(cfg.get("concurrent", 1)))
        self.var_text_concurrent.set(str(cfg.get("text_concurrent", 1)))
        self.var_rate.set(str(int(float(cfg.get("rate_limit_kbps", 0)))))
        self.var_proxy.set(str(cfg.get("proxy") or ""))
        self.var_keep.set(bool(cfg.get("keep_singles", True)))
        self.var_open.set(bool(cfg.get("open_folder_after", True)))
        self.var_skip.set(bool(cfg.get("skip_existing", False)))
        self.var_engine.set(str(cfg.get("pdf_engine", "auto")))
        self.var_log.set(str(cfg.get("log_level", "normal")))
        interval = float(cfg.get("request_interval", core.DEFAULT_CONFIG["request_interval"]))
        self.var_speed.set("礼貌" if interval >= 0.15 else ("标准" if interval > 0 else "极速"))
        split = int(cfg.get("split", 0) or 0)
        self.var_split.set({0: "自动", 1: "关闭"}.get(split, "%d 路" % split))
        self.status.configure(text="输出目录：%s" % core.out_root(cfg))
        for warn in self.warns:
            self.append_log("配置警告：%s" % warn, "warn")

    def _collect(self) -> dict:
        """把界面上的选择写回配置（字段名与 config.json 一致）。"""
        cfg = dict(self.cfg)
        try:
            cfg["timeout"] = int(self.var_timeout.get())
            cfg["retry"] = int(self.var_retry.get())
            cfg["concurrent"] = int(self.var_concurrent.get())
            cfg["text_concurrent"] = int(self.var_text_concurrent.get())
            cfg["rate_limit_kbps"] = float(self.var_rate.get() or 0)
        except ValueError:
            pass
        cfg["proxy"] = self.var_proxy.get().strip()
        cfg["download_path"] = self.path_var.get().strip()
        cfg["keep_singles"] = bool(self.var_keep.get())
        cfg["open_folder_after"] = bool(self.var_open.get())
        cfg["skip_existing"] = bool(self.var_skip.get())
        cfg["pdf_engine"] = self.var_engine.get()
        cfg["log_level"] = self.var_log.get()
        cfg["batch_merge_mode"] = self.batch_mode.get()
        cfg["request_interval"] = SPEED_MAP.get(self.var_speed.get(),
                                                core.DEFAULT_CONFIG["request_interval"])
        cfg["split"] = SPLIT_MAP.get(self.var_split.get(), 0)

        raw = self.edition_var.get().replace("，", ",").strip()
        editions = []
        if raw:
            for item in raw.split(","):
                item = item.strip()
                if item.isdigit():
                    editions.append(int(item))
        cfg["edition_filter"] = editions
        return cfg

    # ------------------------------------------------------------------ 日志 / 队列
    def append_log(self, text: str, level: str = "info") -> None:
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        tag = level if level in ("warn", "error", "debug") else ""
        self.log.configure(state="normal")
        self.log.insert("end", "[%s] %s\n" % (stamp, text), tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self.append_log(payload[0], payload[1])
                elif kind == "progress":
                    fraction, text = payload
                    if fraction is None:
                        self.progress.configure(mode="indeterminate")
                        try:
                            self.progress.start(60)
                        except Exception:
                            pass
                    else:
                        try:
                            self.progress.stop()
                        except Exception:
                            pass
                        self.progress.configure(mode="determinate", value=max(0.0, min(1.0, fraction)) * 100)
                    if text:
                        self.progress_label.configure(text=text[:26])
                elif kind == "done":
                    self._finish(payload)
        except queue.Empty:
            pass
        self.root.after(80, self._drain)

    # ------------------------------------------------------------------ 动作
    def on_speed_changed(self, _event=None) -> None:
        """切档位时顺手把并发调到配套值，用户仍可手动改。"""
        self.var_concurrent.set(str(SPEED_CONCURRENCY.get(self.var_speed.get(), 6)))

    def on_browse(self) -> None:
        initial = self.path_var.get().strip() or core.out_root(self.cfg)
        chosen = filedialog.askdirectory(initialdir=initial if os.path.isdir(initial) else core.HERE,
                                         title="选择下载目录")
        if chosen:
            self.path_var.set(chosen)

    def on_save_config(self) -> None:
        cfg = self._collect()
        cfg, warns = core.validate_config(cfg)
        self.cfg = cfg
        path = core.save_config(cfg)
        self.status.configure(text="输出目录：%s" % core.out_root(cfg))
        self.append_log("配置已保存到 %s" % path)
        for warn in warns:
            self.append_log("配置警告：%s" % warn, "warn")

    def on_start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        cfg = self._collect()
        cfg, warns = core.validate_config(cfg)
        self.cfg = cfg
        for warn in warns:
            self.append_log("配置警告：%s" % warn, "warn")

        tab = self.notebook.index(self.notebook.select())
        if tab == 0:
            date = self.date_var.get().strip() or self._today()
            if not (date.isdigit() and len(date) == 8):
                messagebox.showwarning("日期格式", "请输入 8 位日期，例如 %s" % self._today())
                return
            fmt = self._format(self.single_pdf.get(), self.single_text.get())
            if not fmt:
                messagebox.showwarning("输出内容", "请至少勾选 PDF 或文章正文。")
                return
            cfg["text_output_format"] = self.single_text_fmt.get()
            self.ui_state.update({"date": date, "edition": self.edition_var.get().strip(),
                                  "pdf": self.single_pdf.get(), "text": self.single_text.get()})
            task = lambda: self.session.run_single(date, fmt)  # noqa: E731
            label = "单日 %s" % date
        elif tab == 1:
            expr = self.batch_var.get().strip()
            if not expr:
                messagebox.showwarning("日期范围", "请填写日期范围，例如 20260901-20260903")
                return
            fmt = self._format(self.batch_pdf.get(), self.batch_text.get())
            if not fmt:
                messagebox.showwarning("输出内容", "请至少勾选 PDF 或文章正文。")
                return
            cfg["text_output_format"] = self.batch_text_fmt.get()
            self.ui_state.update({"batch": expr, "pdf": self.batch_pdf.get(),
                                  "text": self.batch_text.get()})
            mode = self.batch_mode.get()
            task = lambda: self.session.run_batch(expr, fmt, mode)  # noqa: E731
            label = "批量 %s" % expr
        else:
            messagebox.showinfo("设置", "「设置」页修改后点「保存配置」即可。")
            return

        cfg["ui"] = self.ui_state
        try:
            core.save_config(cfg)
        except OSError as exc:
            self.append_log("配置保存失败：%s" % exc, "warn")

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.append_log("开始 %s（格式 %s）" % (label, fmt))
        self.append_log("输出目录：%s" % core.out_root(cfg), "debug")

        reporter = core.Reporter(
            on_log=lambda msg, level: self.queue.put(("log", (msg, level))),
            on_progress=lambda fraction, text: self.queue.put(("progress", (fraction, text))),
        )
        self.session = core.Session(cfg, reporter)
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_last_btn.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        try:
            self.progress.start(60)
        except Exception:
            pass

        def run() -> None:
            code = 1
            try:
                code = task()
            except core.Stopped:
                self.queue.put(("log", ("已中断", "warn")))
                code = 130
            except Exception as exc:
                self.queue.put(("log", ("未预料的错误：%s" % exc, "error")))
                code = 1
            self.queue.put(("done", (code, getattr(self.session, "last_output", ""))))

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    @staticmethod
    def _format(pdf: bool, text: bool) -> str:
        if pdf and text:
            return "both"
        if pdf:
            return "pdf"
        if text:
            return "text"
        return ""

    def _finish(self, payload) -> None:
        code, path = payload
        try:
            self.progress.stop()
        except Exception:
            pass
        self.progress.configure(mode="determinate", value=100 if code == 0 else 0)
        self.progress_label.configure(text="完成" if code == 0 else "已停止")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.last_output = path or ""
        self.open_last_btn.configure(state="normal" if self.last_output else "disabled")
        if code == 0:
            self.append_log("全部完成")
            core.notify(self.cfg, core.APP_NAME, "人民日报下载完成")
            if path and self.cfg.get("open_folder_after", True):
                core.reveal(path)
        elif code == 130:
            self.append_log("任务已中断", "warn")
        else:
            self.append_log("任务失败，详见上方日志", "error")

    def on_stop(self) -> None:
        if self.session:
            self.session.reporter.stop()
            self.append_log("正在停止…", "warn")
            self.stop_btn.configure(state="disabled")

    def on_open(self) -> None:
        core.open_folder(core.out_root(self._collect()))

    def on_open_last(self) -> None:
        if self.last_output:
            core.reveal(self.last_output)

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("正在下载", "任务尚未结束，确定要退出吗？"):
                return
            if self.session:
                self.session.reporter.stop()
        self.root.destroy()


def main() -> int:
    enable_dpi_awareness()
    try:
        root = tk.Tk()
    except Exception as exc:
        print("[错误] 无法创建窗口：%s" % exc)
        return 1
    try:
        App(root)
    except Exception as exc:
        messagebox.showerror("启动失败", "界面初始化失败：%s" % exc)
        return 1
    root.mainloop()
    return 0


def _crash_report(exc: BaseException) -> None:
    """pythonw 启动时没有控制台，出错必须落盘 + 弹窗，否则用户什么也看不到。"""
    import traceback
    path = os.path.join(core.HERE, "rmrb_ui_error.log")
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n===== %s =====\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            fh.write(traceback.format_exc())
    except OSError:
        path = "(日志写入失败)"
    try:
        messagebox.showerror("启动失败",
                             "界面启动出错：\n%s\n\n详细信息：%s" % (exc, path))
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:      # noqa: BLE001
        _crash_report(exc)
        sys.exit(1)
