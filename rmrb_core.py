# -*- coding: utf-8 -*-
"""人民日报电子版下载器 · 核心引擎

设计原则：
  * 只用标准库，零第三方依赖（PDF 合并由 rmrb_pdf 用标准库完成）
  * 所有 I/O 通过 Reporter 回调向外汇报，CLI 和 GUI 共用同一套流程
  * 所有删除操作都做边界校验，绝不动下载根目录之外的东西
"""
from __future__ import annotations

import datetime
import html as html_mod
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlsplit

import rmrb_pdf

APP_NAME = "人民日报电子版下载器"
APP_VERSION = "2.3.0"

# 打包成 exe 后，config.json / 下载目录 / 日志都放在 exe 同级
def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


HERE = app_dir()
CONFIG_PATH = os.path.join(HERE, "config.json")

DEFAULT_CONFIG = {
    # ---- 抓取与网络 ----
    "base_url": "http://paper.people.com.cn/rmrb/pc",
    "rate_limit_kbps": 0,
    "timeout": 30,
    "retry": 3,
    "retry_interval": 2,
    "request_interval": 0.05,
    "concurrent": 6,
    "proxy": "",
    "user_agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    # ---- 界面 ----
    "color_foreground": "A",
    "color_background": "0",
    "window_title": "人民日报电子版下载器",
    "show_progress": True,
    # ---- 日期与内容 ----
    "default_date": "",
    "default_format": "pdf",
    "edition_filter": [],
    "holiday_skip": False,
    # ---- 批量下载 ----
    "batch_enable": False,
    "batch_merge_mode": "each",
    "download_path": "",
    # ---- 输出与合并 ----
    "download_dir": "pdfs_{date}",
    "merged_filename": "人民日报-{date}-完整版",
    "auto_merge": True,
    "keep_singles": True,
    "open_folder_after": False,   # 默认不抢焦点，界面给「打开」按钮
    "skip_existing": False,
    "split": 0,                    # 0=自动（版面<=3 时分片）1=关闭 2-8=固定路数
    "pdf_engine": "auto",          # auto / builtin / pypdf
    # ---- 文字输出 ----
    "text_output_format": "TXT",   # TXT / DOC / DOCX / MD
    "text_filename": "人民日报-{date}-文字版",
    "text_include_edition": True,
    "text_concurrent": 6,          # 正文抓取并发（1 = 顺序）
    # ---- 日志与通知 ----
    "log_file": "rmrb_download.log",
    "log_level": "normal",         # quiet / normal / debug
    "log_max_kb": 512,
    "beep_on_done": False,
    "msg_on_done": False,
    # ---- 调度 ----
    "auto_run": False,
    "auto_run_time": "08:00",
}

LEVELS = {"debug": 0, "info": 1, "warn": 2, "error": 3}
LOG_LEVEL_ALIAS = {
    "quiet": "error", "silent": "error",
    "normal": "info", "info": "info",
    "debug": "debug", "trace": "debug",
    "warn": "warn", "warning": "warn", "error": "error",
}


# --------------------------------------------------------------------------
# 日志
# --------------------------------------------------------------------------

class Logger:
    """按 config 的 log_file / log_level 写文件，超过上限自动轮转一次。"""

    def __init__(self, path: str, level: str = "normal", max_kb: int = 512) -> None:
        self.path = path
        self.level = LEVELS.get(LOG_LEVEL_ALIAS.get(str(level).lower(), "info"), 1)
        self.max_bytes = max(0, int(max_kb)) * 1024
        self._lock = threading.Lock()

    def write(self, msg: str, level: str = "info") -> None:
        if not self.path or LEVELS.get(level, 1) < self.level:
            return
        line = "[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
        try:
            with self._lock:
                if self.max_bytes and os.path.exists(self.path) \
                        and os.path.getsize(self.path) > self.max_bytes:
                    try:
                        os.replace(self.path, self.path + ".1")
                    except OSError:
                        pass
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line)
        except OSError:
            pass


class Reporter:
    """把日志和进度汇报给前端（CLI 打印 / GUI 队列）。"""

    def __init__(self, logger: Optional[Logger] = None,
                 on_log: Optional[Callable[[str, str], None]] = None,
                 on_progress: Optional[Callable[[Optional[float], str], None]] = None,
                 stop_event: Optional[threading.Event] = None) -> None:
        self.logger = logger
        self.on_log = on_log
        self.on_progress = on_progress
        self.stop_event = stop_event or threading.Event()
        self._last_progress = 0.0

    # ---- 日志 ----
    def log(self, msg: str, level: str = "info") -> None:
        if self.logger:
            self.logger.write(msg, level)
        if self.on_log:
            try:
                self.on_log(msg, level)
            except Exception:
                pass

    def info(self, msg: str) -> None:
        self.log(msg, "info")

    def warn(self, msg: str) -> None:
        self.log(msg, "warn")

    def error(self, msg: str) -> None:
        self.log(msg, "error")

    def debug(self, msg: str) -> None:
        self.log(msg, "debug")

    # ---- 进度 ----
    def progress(self, fraction: Optional[float], text: str = "") -> None:
        if not self.on_progress:
            return
        now = time.time()
        if fraction is not None and fraction < 1.0 and now - self._last_progress < 0.1:
            return
        self._last_progress = now
        try:
            self.on_progress(fraction, text)
        except Exception:
            pass

    # ---- 中断 ----
    def stop(self) -> None:
        self.stop_event.set()

    def stopped(self) -> bool:
        return self.stop_event.is_set()

    def check_stop(self) -> None:
        if self.stop_event.is_set():
            raise Stopped()


class Stopped(Exception):
    """用户主动中断。"""


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------

def load_config(path: Optional[str] = None) -> Dict[str, object]:
    path = path or CONFIG_PATH
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                user = json.load(fh)
            if isinstance(user, dict):
                cfg.update(user)
        except Exception as exc:  # 配置坏了不能直接崩
            bad = path + ".bad"
            try:
                shutil.copyfile(path, bad)
            except OSError:
                pass
            cfg["_load_error"] = "%s（已备份为 %s）" % (exc, os.path.basename(bad))
    return cfg


def save_config(cfg: Dict[str, object], path: Optional[str] = None) -> str:
    """原子写入：先写临时文件再替换，避免断电写坏配置。"""
    path = path or CONFIG_PATH
    data = {k: v for k, v in cfg.items() if not k.startswith("_")}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return path


def validate_config(cfg: Dict[str, object]) -> Tuple[Dict[str, object], List[str]]:
    """修正非法配置，保证后续流程拿到的值都是可用的。"""
    warns: List[str] = []

    def _num(key, cast, default, lo=None, hi=None):
        try:
            value = cast(cfg.get(key, default))
            if lo is not None and value < lo:
                warns.append("%s=%s 小于下限 %s，回退为 %s" % (key, cfg.get(key), lo, default))
                value = default
            if hi is not None and value > hi:
                warns.append("%s=%s 超过上限 %s，回退为 %s" % (key, cfg.get(key), hi, default))
                value = default
            cfg[key] = value
        except (TypeError, ValueError):
            warns.append("%s=%r 非法，回退为 %s" % (key, cfg.get(key), default))
            cfg[key] = default

    _num("rate_limit_kbps", float, 0, 0, 102400)
    _num("timeout", int, DEFAULT_CONFIG["timeout"], 1, 86400)
    _num("retry", int, DEFAULT_CONFIG["retry"], 0, 20)
    _num("retry_interval", float, DEFAULT_CONFIG["retry_interval"], 0, 300)
    _num("request_interval", float, DEFAULT_CONFIG["request_interval"], 0, 300)
    _num("concurrent", int, DEFAULT_CONFIG["concurrent"], 1, 16)
    _num("text_concurrent", int, DEFAULT_CONFIG["text_concurrent"], 1, 16)
    _num("log_max_kb", int, 512, 0, 1024 * 1024)
    _num("split", int, 0, 0, 8)

    if str(cfg.get("default_format", "pdf")).lower() not in ("text", "pdf", "both"):
        warns.append("default_format=%r 非法，回退为 pdf" % cfg.get("default_format"))
        cfg["default_format"] = "pdf"
    if str(cfg.get("text_output_format", "TXT")).upper() not in ("TXT", "DOC", "DOCX", "MD"):
        warns.append("text_output_format=%r 非法，回退为 TXT" % cfg.get("text_output_format"))
        cfg["text_output_format"] = "TXT"
    if str(cfg.get("batch_merge_mode", "each")).lower() not in ("each", "all"):
        warns.append("batch_merge_mode=%r 非法，回退为 each" % cfg.get("batch_merge_mode"))
        cfg["batch_merge_mode"] = "each"
    if str(cfg.get("pdf_engine", "auto")).lower() not in ("auto", "builtin", "pypdf"):
        warns.append("pdf_engine=%r 非法，回退为 auto" % cfg.get("pdf_engine"))
        cfg["pdf_engine"] = "auto"
    if str(cfg.get("log_level", "normal")).lower() not in LOG_LEVEL_ALIAS:
        warns.append("log_level=%r 非法，回退为 normal" % cfg.get("log_level"))
        cfg["log_level"] = "normal"

    # 代理：没写 scheme 就补 http://，否则 urllib 会当成主机名直接失败
    proxy = str(cfg.get("proxy", "") or "").strip()
    if proxy and "://" not in proxy:
        proxy = "http://" + proxy
        warns.append("proxy 已自动补全为 %s" % proxy)
    if proxy and not re.match(r"^https?://", proxy):
        warns.append("proxy 只支持 http/https，已清空")
        proxy = ""
    cfg["proxy"] = proxy

    # 控制台颜色
    colors = str(cfg.get("color_background", "0")) + str(cfg.get("color_foreground", "A"))
    if not re.fullmatch(r"[0-9A-Fa-f]{2}", colors):
        warns.append("颜色配置非法（应为两位十六进制，如 0A），回退为 0A")
        cfg["color_background"], cfg["color_foreground"] = "0", "A"

    # 版面白名单
    editions = cfg.get("edition_filter", [])
    if not isinstance(editions, list):
        warns.append("edition_filter 应为列表，已清空（=全部版面）")
        cfg["edition_filter"] = []
    else:
        good = []
        for item in editions:
            try:
                number = int(item)
            except (TypeError, ValueError):
                warns.append("edition_filter 含非法值 %r，已忽略" % (item,))
                continue
            if number > 0:
                good.append(number)
        cfg["edition_filter"] = good

    # 单版目录模板：必须是相对子目录，不能是绝对路径/盘符/父目录
    tpl = str(cfg.get("download_dir", "pdfs_{date}") or "").strip()
    if not _is_safe_relative(tpl):
        warns.append("download_dir 必须是下载目录下的相对子目录，已回退为 pdfs_{date}")
        tpl = "pdfs_{date}"
    cfg["download_dir"] = tpl

    for key in ("merged_filename", "text_filename"):
        value = str(cfg.get(key, DEFAULT_CONFIG[key]) or "").strip()
        if not _is_safe_relative(value) or "/" in value or "\\" in value:
            warns.append("%s 非法，已回退为默认值" % key)
            cfg[key] = DEFAULT_CONFIG[key]

    return cfg, warns


DONE_MARKER = ".done"


def load_done(out_dir: str) -> set:
    """读取"上次已下完的版面"清单（停止/中断后下次不再重下）。"""
    path = os.path.join(out_dir, DONE_MARKER)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return {line.strip() for line in fh if line.strip()}
    except OSError:
        return set()


def mark_done(out_dir: str, edition: str) -> None:
    try:
        with open(os.path.join(out_dir, DONE_MARKER), "a", encoding="utf-8") as fh:
            fh.write(edition + "\n")
    except OSError:
        pass


def clear_done(out_dir: str) -> None:
    try:
        os.remove(os.path.join(out_dir, DONE_MARKER))
    except OSError:
        pass


def _is_safe_relative(value: str) -> bool:
    """判断一个配置值能否安全地拼到下载根目录下。

    拒绝空值、绝对路径（含 Windows 盘符与 /tmp 这类 rooted 路径）、
    以及任何 `..` 片段——它们会让 os.path.join 直接跳出输出目录。
    """
    if not value:
        return False
    norm = value.replace("\\", "/")
    if norm.startswith("/") or ":" in norm:
        return False
    return ".." not in norm.split("/")


def out_root(cfg: Dict[str, object]) -> str:
    """下载根目录：空 = 程序所在目录，相对路径相对程序目录。"""
    raw = str(cfg.get("download_path", "") or "").strip()
    if not raw:
        return HERE
    if os.path.isabs(raw):
        return raw
    return os.path.join(HERE, raw)


def safe_rmtree(target: str, root: str) -> str:
    """只删除 root 的真子目录，防止 download_dir 配错把整个输出目录删掉。

    返回空字符串表示已删除，否则返回无法删除的原因。
    """
    real_target = os.path.realpath(target)
    real_root = os.path.realpath(root)
    if real_target == real_root:
        return "单版目录与下载根目录重合"
    if not real_target.startswith(real_root + os.sep):
        return "单版目录不在下载根目录内"
    shutil.rmtree(real_target, ignore_errors=True)
    return ""


# --------------------------------------------------------------------------
# 错误翻译
# --------------------------------------------------------------------------

def describe_error(exc: BaseException) -> str:
    if isinstance(exc, HttpStatusError):
        if exc.code == 404:
            return "页面不存在(HTTP 404)：该日期可能未出版，或官网版面结构已变化"
        if exc.code in (403, 429):
            return "服务器拒绝(HTTP %s)：访问过于频繁，可增大 request_interval 后重试" % exc.code
        if 500 <= exc.code < 600:
            return "人民日报服务器异常(HTTP %s)，请稍后重试" % exc.code
        return "服务器返回 HTTP %s" % exc.code
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return "页面不存在(HTTP 404)：该日期可能未出版，或官网版面结构已变化"
        if exc.code in (403, 429):
            return "服务器拒绝(HTTP %s)：访问过于频繁，可增大 request_interval 后重试" % exc.code
        if 500 <= exc.code < 600:
            return "人民日报服务器异常(HTTP %s)，请稍后重试" % exc.code
        return "服务器返回 HTTP %s" % exc.code
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        text = str(reason).lower()
        if "name or service not known" in text or "getaddrinfo" in text or "name resolution" in text:
            return "域名解析失败：网络未连接或 DNS 异常，请检查网络后重试"
        if "refused" in text:
            return "连接被拒绝：目标服务器不可达，请检查网络/代理(proxy)"
        return "网络连接失败(%s)：请检查网络或代理设置" % reason
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in str(exc).lower():
        return "连接/读取超时：可在配置里增大 timeout，或稍后重试"
    if isinstance(exc, ConnectionError):
        return "连接中断(%s)：网络不稳定，请重试" % exc
    return str(exc)


# --------------------------------------------------------------------------
# 网络
# --------------------------------------------------------------------------

class Pacer:
    """全局请求节流：并发下载时也能保证平均间隔不小于 request_interval。"""

    def __init__(self, interval: float) -> None:
        self.interval = max(0.0, float(interval))
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + self.interval
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)


class HttpStatusError(Exception):
    """服务器返回 4xx/5xx。"""

    def __init__(self, url: str, code: int, reason: str = "") -> None:
        super().__init__("HTTP %s %s: %s" % (code, reason, url))
        self.code = code
        self.url = url


MIN_SPLIT_BYTES = 1500 * 1024        # 小于 1.5 MB 的文件分片不划算


class RangeUnsupported(Exception):
    """服务器或文件不支持分片下载。"""


def parse_content_range(value: Optional[str]) -> int:
    """从 `bytes 0-1023/24106` 中取出文件总长度。"""
    if not value:
        return 0
    match = re.search(r"/\s*(\d+)\s*$", value)
    return int(match.group(1)) if match else 0


def plan_ranges(total: int, split: int) -> List[Tuple[int, int]]:
    """把 [0, total) 切成 split 个闭区间，每段长度尽量相等。"""
    if total <= 0:
        return []
    split = max(1, min(int(split), total))
    if split == 1:
        return [(0, total - 1)]
    chunk = total // split
    ranges: List[Tuple[int, int]] = []
    start = 0
    for index in range(split):
        end = total - 1 if index == split - 1 else start + chunk - 1
        ranges.append((start, end))
        start = end + 1
    return ranges


def _permanent(exc: BaseException) -> bool:
    """4xx（限流 429 与超时 408 除外）属于永久性错误，重试没有意义。"""
    return isinstance(exc, HttpStatusError) and 400 <= exc.code < 500 \
        and exc.code not in (408, 429)


class _UrllibResponse:
    """把 urllib 的响应包装成和 http.client 一样的读法（代理 / 异协议时使用）。"""

    def __init__(self, raw) -> None:
        self._raw = raw

    def read(self, size: int = -1) -> bytes:
        return self._raw.read() if size is None or size < 0 else self._raw.read(size)

    def getheader(self, name: str, default=None):
        return self._raw.headers.get(name, default)

    @property
    def will_close(self) -> bool:
        return True

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass


class Downloader:
    """线程安全的下载器。

    默认走 http.client 并**复用连接**（urllib 每个请求都会重新握手，慢一倍以上）；
    设置了代理时回退到 urllib，由它处理代理隧道。
    """

    def __init__(self, cfg: Dict[str, object], reporter: Reporter) -> None:
        self.cfg = cfg
        self.reporter = reporter
        self.ua = str(cfg.get("user_agent") or DEFAULT_CONFIG["user_agent"])
        self.base_url = str(cfg.get("base_url") or DEFAULT_CONFIG["base_url"])
        self.timeout = int(cfg.get("timeout", 30))
        self.retry = int(cfg.get("retry", 3))
        self.retry_interval = float(cfg.get("retry_interval", 2))
        self.rate_kbps = float(cfg.get("rate_limit_kbps", 0))
        self.proxy = str(cfg.get("proxy") or "").strip()
        self.pacer = Pacer(float(cfg.get("request_interval", 0.2)))
        self._local = threading.local()
        self._bw_lock = threading.Lock()

    # ---- 连接池（urllib 的 opener 不是线程安全的，这里每线程一组连接）----
    def _conns(self) -> Dict[tuple, http.client.HTTPConnection]:
        cache = getattr(self._local, "conns", None)
        if cache is None:
            cache = {}
            self._local.conns = cache
        return cache

    def _conn(self, parts, timeout: float):
        key = (parts.scheme, parts.netloc)
        conn = self._conns().get(key)
        if conn is None:
            cls = (http.client.HTTPSConnection if parts.scheme == "https"
                   else http.client.HTTPConnection)
            conn = cls(parts.hostname, parts.port, timeout=timeout)
            self._conns()[key] = conn
        conn.timeout = timeout
        if conn.sock is not None:
            try:
                conn.sock.settimeout(timeout)
            except OSError:
                pass
        return conn

    def _drop(self, parts) -> None:
        conn = self._conns().pop((parts.scheme, parts.netloc), None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _open_urllib(self, url: str, timeout: float, headers: Optional[dict] = None):
        handlers = []
        if self.proxy:
            handlers.append(urllib.request.ProxyHandler({"http": self.proxy,
                                                         "https": self.proxy}))
        opener = urllib.request.build_opener(*handlers)
        merged = {"User-Agent": self.ua, "Referer": self.base_url,
                  "Accept-Encoding": "identity"}
        merged.update(headers or {})
        req = urllib.request.Request(url, headers=merged)
        try:
            return _UrllibResponse(opener.open(req, timeout=timeout)), None
        except urllib.error.HTTPError as exc:
            raise HttpStatusError(url, exc.code, str(exc.reason)) from exc

    def _open(self, url: str, timeout: float, depth: int = 0, headers: Optional[dict] = None):
        """打开一个 URL，返回 (响应对象, 连接标识)；调用方读完必须 _release()。"""
        parts = urlsplit(url)
        if self.proxy or parts.scheme not in ("http", "https") or depth > 5:
            return self._open_urllib(url, timeout, headers)

        path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
        last_error: Optional[BaseException] = None
        for attempt in (0, 1):
            conn = self._conn(parts, timeout)
            try:
                conn.putrequest("GET", path, skip_accept_encoding=True)
                conn.putheader("User-Agent", self.ua)
                conn.putheader("Referer", self.base_url)
                conn.putheader("Accept-Encoding", "identity")
                conn.putheader("Connection", "keep-alive")
                for name, value in (headers or {}).items():
                    conn.putheader(name, value)
                conn.endheaders()
                response = conn.getresponse()
                break
            except (http.client.RemoteDisconnected, http.client.BadStatusLine,
                    ConnectionResetError, BrokenPipeError) as exc:
                last_error = exc
                self._drop(parts)          # 服务端关了空闲连接，换一条重试
                if attempt == 1:
                    raise
            except Exception:
                self._drop(parts)
                raise
        else:                               # pragma: no cover
            raise last_error or RuntimeError("请求失败")

        if response.status in (301, 302, 303, 307, 308):
            location = response.getheader("Location")
            response.read()
            self._release(parts, response)
            if not location:
                raise HttpStatusError(url, response.status, "重定向缺少 Location")
            return self._open(urljoin(url, location), timeout, depth + 1, headers)
        if response.status >= 400:
            response.read()
            self._release(parts, response)
            raise HttpStatusError(url, response.status, response.reason or "")
        return response, parts

    def _release(self, parts, response) -> None:
        if parts is not None and getattr(response, "will_close", True):
            self._drop(parts)

    def _request(self, url: str, timeout: Optional[float] = None,
                 headers: Optional[dict] = None):
        self.pacer.wait()
        self.reporter.check_stop()
        return self._open(url, timeout or self.timeout, headers=headers)

    def fetch(self, url: str, timeout: Optional[float] = None) -> bytes:
        last: Optional[BaseException] = None
        for attempt in range(self.retry + 1):
            try:
                response, parts = self._request(url, timeout)
                try:
                    return response.read()
                finally:
                    self._release(parts, response)
            except Stopped:
                raise
            except Exception as exc:
                last = exc
                if _permanent(exc) or attempt >= self.retry:
                    break
                self.reporter.warn("请求失败（%s/%s）：%s" % (
                    attempt + 1, self.retry, describe_error(exc)))
                time.sleep(self.retry_interval)
        raise last if last else RuntimeError("请求失败")

    def _throttle(self, chunk_size: int, started: float, done: int) -> None:
        if self.rate_kbps <= 0:
            return
        expected = done / (self.rate_kbps * 1024.0)
        delay = expected - (time.monotonic() - started)
        if delay > 0:
            time.sleep(min(delay, 5.0))

    def download_file(self, url: str, path: str, label: str,
                      on_bytes: Optional[Callable[[int, int], None]] = None,
                      split: int = 1) -> int:
        """下载到文件。split > 1 时按 HTTP Range 分片多连接下载，失败自动退回单连接。"""
        if split and split > 1:
            try:
                return self._download_split(url, path, label, on_bytes, split)
            except Stopped:
                raise
            except RangeUnsupported as exc:
                self.reporter.debug("%s 未使用分片：%s" % (label, exc))
            except Exception as exc:
                if _permanent(exc):
                    raise
                self.reporter.warn("%s 分片下载失败（%s），改用单连接"
                                   % (label, describe_error(exc)))
        return self._download_single(url, path, label, on_bytes)

    def _download_single(self, url: str, path: str, label: str,
                         on_bytes: Optional[Callable[[int, int], None]] = None) -> int:
        last: Optional[BaseException] = None
        tmp = path + ".part"
        for attempt in range(self.retry + 1):
            try:
                response, parts = self._request(url, max(self.timeout, 120))
                total = int(response.getheader("Content-Length") or 0)
                done = 0
                started = time.monotonic()
                try:
                    with open(tmp, "wb") as fh:
                        while True:
                            self.reporter.check_stop()      # 每 256 KB 响应一次停止
                            chunk = response.read(262144)
                            if not chunk:
                                break
                            fh.write(chunk)
                            done += len(chunk)
                            self._throttle(len(chunk), started, done)
                            if on_bytes:
                                on_bytes(done, total)
                finally:
                    self._release(parts, response)
                os.replace(tmp, path)
                return done
            except Stopped:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
                raise
            except Exception as exc:
                last = exc
                permanent = _permanent(exc)
                for leftover in (tmp, path):
                    try:
                        if os.path.exists(leftover):
                            os.remove(leftover)
                    except OSError:
                        pass
                if permanent or attempt >= self.retry:
                    break
                self.reporter.warn("第%s版下载失败（%s/%s）：%s" % (
                    label, attempt + 1, self.retry, describe_error(exc)))
                time.sleep(self.retry_interval)
        raise last if last else RuntimeError("下载失败")

    def _download_split(self, url: str, path: str, label: str,
                        on_bytes: Optional[Callable[[int, int], None]], split: int) -> int:
        """HTTP Range 分片下载（类似 aria2 的 -x/-s），用于版面很少的大文件。"""
        timeout = max(self.timeout, 120)
        probe, parts = self._request(url, timeout, headers={"Range": "bytes=0-0"})
        try:
            status = probe.status
            total = parse_content_range(probe.getheader("Content-Range"))
            probe.read()
        finally:
            self._release(parts, probe)
        if status != 206 or total <= 0:
            raise RangeUnsupported("服务器返回 HTTP %s，不支持 Range" % status)
        if total < MIN_SPLIT_BYTES:
            raise RangeUnsupported("文件仅 %.1f MB" % (total / 1048576))

        ranges = plan_ranges(total, split)
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            fh.truncate(total)
        counts = [0] * len(ranges)
        lock = threading.Lock()

        def report() -> None:
            if on_bytes:
                on_bytes(sum(counts), total)

        def worker(index: int, start: int, end: int) -> None:
            expected = end - start + 1
            last: Optional[BaseException] = None
            for attempt in range(self.retry + 1):
                written = 0
                try:
                    response, parts = self._request(
                        url, timeout, headers={"Range": "bytes=%d-%d" % (start, end)})
                    try:
                        if response.status != 206:
                            raise RangeUnsupported("分片返回 HTTP %s" % response.status)
                        with open(tmp, "r+b") as fh:
                            fh.seek(start)
                            while True:
                                self.reporter.check_stop()
                                chunk = response.read(262144)
                                if not chunk:
                                    break
                                fh.write(chunk)
                                written += len(chunk)
                                with lock:
                                    counts[index] = written
                                    report()
                    finally:
                        self._release(parts, response)
                    if written != expected:
                        raise IOError("分片 #%d 长度不符 %d/%d" % (index, written, expected))
                    return
                except Stopped:
                    raise
                except Exception as exc:
                    last = exc
                    with lock:
                        counts[index] = 0
                    if _permanent(exc) or attempt >= self.retry:
                        raise
                    time.sleep(self.retry_interval)
            raise last if last else RuntimeError("分片下载失败")

        try:
            with ThreadPoolExecutor(max_workers=len(ranges)) as pool:
                futures = [pool.submit(worker, i, s, e) for i, (s, e) in enumerate(ranges)]
                for future in futures:
                    future.result()
            if os.path.getsize(tmp) != total:
                raise IOError("分片拼接后大小不符")
            os.replace(tmp, path)
            self.reporter.debug("%s 已用 %d 路分片下载 %.1f MB" % (label, len(ranges), total / 1048576))
            return total
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            raise


# --------------------------------------------------------------------------
# 版面 / 文章解析
# --------------------------------------------------------------------------

def get_nodes(dl: Downloader, ym: str, dd: str,
              cache: Optional[Dict[str, str]] = None) -> Tuple[List[str], bool]:
    """获取某日全部版面号，返回 (版面号列表, 头版是否访问成功)。"""
    cfg = dl.cfg
    base = str(cfg.get("base_url") or DEFAULT_CONFIG["base_url"])
    nodes: List[str] = []
    net_ok = False
    try:
        node1 = dl.fetch("%s/layout/%s/%s/node_01.html" % (base, ym, dd)).decode("utf-8", "ignore")
        net_ok = True
        if cache is not None:
            cache["01"] = node1
        nodes = sorted({n for n in re.findall(r'href="node_(\d+)\.html"', node1)}, key=int)
    except Stopped:
        raise
    except Exception as exc:
        dl.reporter.warn("读取头版失败：%s" % describe_error(exc))
    if not nodes:
        try:
            index = dl.fetch("%s/layout/index.html" % base).decode("utf-8", "ignore")
            nodes = sorted({n for n in re.findall(r"%s/%s/node_(\d+)\.html" % (ym, dd), index)},
                           key=int)
        except Stopped:
            raise
        except Exception:
            pass
    wanted = [int(x) for x in cfg.get("edition_filter", []) or []]
    if wanted:
        before = len(nodes)
        nodes = [n for n in nodes if int(n) in wanted]
        dl.reporter.debug("edition_filter %s：%d -> %d 版" % (wanted, before, len(nodes)))
    return nodes, net_ok


def parse_article(html: str) -> Tuple[str, List[str]]:
    """抽取正文页的标题与段落。"""
    title = ""
    match = re.search(r"<h1[^>]*>\s*<p>(.*?)</p>\s*</h1>", html, re.S)
    if match:
        title = html_mod.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
    if not title:
        match = re.search(r"<title>\s*(.*?)\s*</title>", html, re.S)
        if match:
            title = html_mod.unescape(match.group(1)).strip()
    body = ""
    match = re.search(r"<!--enpcontent-->(.*?)<!--/enpcontent-->", html, re.S)
    if match:
        body = match.group(1)
    paras: List[str] = []
    for para in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.S):
        text = re.sub(r"<[^>]+>", "", para.group(1))
        text = html_mod.unescape(text).replace("\u3000", "　").strip()
        if text:
            paras.append(text)
    return title, paras


def get_article_links(node_html: str) -> List[str]:
    ids = re.findall(r"content/(\d{6})/(\d{2})/content_(\d+)\.html", node_html)
    return [cid for _, _, cid in sorted(set(ids), key=lambda x: int(x[2]))]


def build_text_content(date_disp: str, data: Sequence[Tuple[str, str, List[Tuple[str, List[str]]]]],
                       show_edition: bool = True) -> List[str]:
    lines = ["人民日报  %s" % date_disp, "=" * 46]
    for _number, edition_name, articles in data:
        if not articles:
            continue
        if show_edition:
            lines.extend(["", "【%s】" % edition_name, "-" * 46])
        for title, paras in articles:
            lines.extend(["", title, ""])
            lines.extend(paras)
    return lines


# --------------------------------------------------------------------------
# 文字输出
# --------------------------------------------------------------------------

def write_txt(lines: Sequence[str], path: str) -> int:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    return len(lines)


def write_md(lines: Sequence[str], path: str) -> int:
    out: List[str] = []
    for line in lines:
        if re.fullmatch(r"[=\-]{20,}", line.strip()):
            continue
        if line.startswith("【") and line.endswith("】"):
            out.extend(["", "## %s" % line[1:-1]])
        elif line.startswith("人民日报  "):
            out.append("# %s" % line.strip())
        else:
            out.append(line)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out).strip() + "\n")
    return len(out)


def write_doc(lines: Sequence[str], path: str) -> int:
    body = ['<html><head><meta http-equiv="Content-Type" '
            'content="text/html; charset=utf-8"></head><body>']
    for line in lines:
        text = html_mod.escape(line)
        if re.fullmatch(r"[=\-]{20,}", line.strip()):
            body.append("<hr>")
        elif line.startswith("【") and line.endswith("】"):
            body.append('<h2 style="margin:18px 0 6px;">%s</h2>' % text)
        elif not line:
            body.append("<p>&nbsp;</p>")
        elif line.startswith("人民日报  "):
            body.append('<h1 style="font-family:黑体;font-size:18pt;">%s</h1>' % text)
        elif line == text and len(line) < 40 and not line.endswith("。"):
            body.append('<p style="font-family:黑体;font-size:13pt;">%s</p>' % text)
        else:
            body.append('<p style="font-family:宋体;font-size:12pt;line-height:1.8;">%s</p>' % text)
    body.append("</body></html>")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(body))
    return len(lines)


def write_docx(lines: Sequence[str], path: str) -> int:
    paras: List[str] = []
    for line in lines:
        if re.fullmatch(r"[=\-]{20,}", line.strip()) or not line:
            continue
        if line.startswith("【") and line.endswith("】"):
            run = ('<w:r><w:rPr><w:rFonts w:ascii="微软雅黑" w:eastAsia="微软雅黑"/>'
                   '<w:b/><w:sz w:val="32"/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>'
                   % html_mod.escape(line))
        elif line.startswith("人民日报  "):
            run = ('<w:r><w:rPr><w:rFonts w:ascii="黑体" w:eastAsia="黑体"/>'
                   '<w:b/><w:sz w:val="40"/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>'
                   % html_mod.escape(line))
        elif len(line) < 40 and not line.endswith("。"):
            run = ('<w:r><w:rPr><w:rFonts w:ascii="黑体" w:eastAsia="黑体"/>'
                   '<w:b/><w:sz w:val="28"/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>'
                   % html_mod.escape(line))
        else:
            run = ('<w:r><w:rPr><w:rFonts w:ascii="宋体" w:eastAsia="宋体"/>'
                   '<w:sz w:val="24"/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>'
                   % html_mod.escape(line))
        paras.append('<w:p><w:pPr><w:spacing w:line="360" w:lineRule="auto"/>'
                     '<w:ind w:firstLine="480"/></w:pPr>%s</w:p>' % run)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>%s<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        '</w:body></w:document>'
    ) % "".join(paras)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)
    return len(lines)


WRITERS = {"TXT": (write_txt, "txt"), "MD": (write_md, "md"),
           "DOC": (write_doc, "doc"), "DOCX": (write_docx, "docx")}


def write_text_file(lines: Sequence[str], path: str, fmt: str) -> int:
    writer, _ = WRITERS.get(fmt.upper(), WRITERS["TXT"])
    writer(lines, path)
    return os.path.getsize(path)


# --------------------------------------------------------------------------
# PDF 合并
# --------------------------------------------------------------------------

def _merge_with_pypdf(files: List[str], out_path: str) -> int:
    from pypdf import PdfReader, PdfWriter  # type: ignore

    writer = PdfWriter()
    pages = 0
    for path in files:
        reader = PdfReader(path)
        pages += len(reader.pages)
        for page in reader.pages:
            writer.add_page(page)
    tmp = out_path + ".part"
    with open(tmp, "wb") as fh:
        writer.write(fh)
    os.replace(tmp, out_path)
    return pages


def merge_pdfs(files: List[str], out_path: str, engine: str = "auto",
               reporter: Optional[Reporter] = None) -> Dict[str, object]:
    """合并 PDF。auto = 先内置引擎，结构不支持时回退 pypdf。"""
    if not files:
        raise RuntimeError("没有可合并的 PDF")
    files = sorted(files)
    order = {"auto": ["builtin", "pypdf"], "builtin": ["builtin"], "pypdf": ["pypdf"]}
    errors: List[str] = []
    for name in order.get(str(engine).lower(), ["builtin"]):
        try:
            if name == "builtin":
                result = rmrb_pdf.merge(files, out_path)
            else:
                pages = _merge_with_pypdf(files, out_path)
                result = {"pages": pages, "engine": "pypdf"}
        except ImportError:
            errors.append("pypdf 未安装")
            continue
        except (rmrb_pdf.Unsupported, rmrb_pdf.PdfError) as exc:
            errors.append("内置引擎：%s" % exc)
            continue
        info = rmrb_pdf.probe(out_path) if name == "builtin" else {}
        if info and info.get("pages") != result["pages"]:
            errors.append("内置引擎自检页数不一致")
            continue
        return result
    raise RuntimeError("PDF 合并失败（%s）" % "；".join(errors) if errors else "PDF 合并失败")


# --------------------------------------------------------------------------
# 任务
# --------------------------------------------------------------------------

class Session:
    """一次运行上下文：共享配置、下载器、版面 HTML 缓存。"""

    def __init__(self, cfg: Dict[str, object], reporter: Optional[Reporter] = None,
                 stop_event: Optional[threading.Event] = None) -> None:
        self.cfg, self.warns = validate_config(dict(cfg))
        logger = None
        log_name = str(self.cfg.get("log_file") or "").strip()
        if log_name:
            logger = Logger(os.path.join(HERE, log_name),
                            str(self.cfg.get("log_level", "normal")),
                            int(self.cfg.get("log_max_kb", 512) or 0))
        self.reporter = reporter or Reporter(logger=logger, stop_event=stop_event)
        if self.reporter.logger is None:
            self.reporter.logger = logger
        if stop_event is not None:
            self.reporter.stop_event = stop_event
        self.dl = Downloader(self.cfg, self.reporter)
        self._node_cache: Dict[str, str] = {}
        self.last_output = ""       # 最近一次产物路径，供 CLI/GUI 打开
        self.last_failed: List[str] = []   # 批量里失败的日期，供"重试失败"用

    # ---- 工具 ----
    def _disp(self, date: str) -> str:
        return "%s-%s-%s" % (date[:4], date[4:6], date[6:])

    def effective_split(self, file_count: int) -> int:
        """0=自动：只在版面很少（下载目标少、整条线路用不满）时分片。"""
        raw = int(self.cfg.get("split", 0) or 0)
        if raw <= 0:
            return 4 if file_count <= 3 else 1
        return max(1, min(8, raw))

    def _node_html(self, date: str, edition: str) -> str:
        """版面页 HTML 缓存：PDF 与文字模式共用，避免重复请求。"""
        key = "%s/%s" % (date, edition)
        cached = self._node_cache.get(key)
        if cached is not None:
            return cached
        base = str(self.cfg.get("base_url") or DEFAULT_CONFIG["base_url"])
        html = self.dl.fetch("%s/layout/%s/%s/node_%s.html"
                             % (base, date[:6], date[6:], edition)).decode("utf-8", "ignore")
        self._node_cache[key] = html
        return html

    # ---- PDF ----
    def download_pdfs(self, date: str, nodes: Sequence[str], root: str
                      ) -> Tuple[List[str], List[str], str]:
        total = len(nodes)
        self.reporter.info("共 %d 个版面，开始下载 PDF" % total)
        self.reporter.progress(0.0, "准备下载 PDF")
        out_dir = os.path.join(root, str(self.cfg.get("download_dir", "pdfs_{date}"))
                               .replace("{date}", date))
        os.makedirs(out_dir, exist_ok=True)
        base = str(self.cfg.get("base_url") or DEFAULT_CONFIG["base_url"])
        skip_existing = bool(self.cfg.get("skip_existing"))
        done_editions = load_done(out_dir)          # 上次中断时已完成的部分
        resumed = 0
        split = self.effective_split(len(nodes))
        if split > 1:
            self.reporter.debug("版面数 %d，启用 %d 路分片下载" % (len(nodes), split))
        done_count = [0]
        lock = threading.Lock()

        def work(edition: str):
            path = os.path.join(out_dir, "rmrb_%s_%s.pdf" % (date, edition))
            try:
                exists = os.path.exists(path) and os.path.getsize(path) > 0
                if exists and (skip_existing or edition in done_editions):
                    self.reporter.debug("跳过已下载的第%s版" % edition)
                    return path
                html = self._node_html(date, edition)
                found = re.findall(r"attachement/\d{6}/\d{2}/[0-9a-f-]+\.pdf", html)
                if not found:
                    self.reporter.warn("第%s版: 未找到 PDF 链接" % edition)
                    return None
                label = "第%s版" % edition

                def on_bytes(done: int, total_bytes: int) -> None:
                    if total_bytes:
                        self.reporter.progress(None, "%s %5.1f%%  %.1f/%.1f MB" % (
                            label, done * 100.0 / total_bytes,
                            done / 1048576, total_bytes / 1048576))

                self.dl.download_file("%s/%s" % (base, found[0]), path, label, on_bytes,
                                      split=split)
                self.reporter.info("第%s版下载完成  %.1f MB" % (edition, os.path.getsize(path) / 1048576))
                mark_done(out_dir, edition)
                return path
            except Stopped:
                raise
            except Exception as exc:
                self.reporter.error("第%s版下载失败：%s" % (edition, describe_error(exc)))
                return None
            finally:
                with lock:
                    done_count[0] += 1
                    self.reporter.progress(done_count[0] / float(total), "PDF %d/%d" % (
                        done_count[0], total))

        concurrent = max(1, int(self.cfg.get("concurrent", 1)))
        if concurrent <= 1:
            outcomes = [work(n) for n in nodes]
        else:
            with ThreadPoolExecutor(max_workers=concurrent) as pool:
                outcomes = list(pool.map(work, nodes))
        files = [p for p in outcomes if p]
        failed = [n for n, p in zip(nodes, outcomes) if not p]
        if not failed:
            clear_done(out_dir)                     # 全部成功，标记文件没用了
        return files, failed, out_dir

    def run_single_day_pdf(self, date: str, nodes: Sequence[str], root: str) -> Optional[str]:
        files, failed, out_dir = self.download_pdfs(date, nodes, root)
        if failed:
            self.reporter.warn("%d 个版面未成功：%s" % (len(failed), ", ".join(failed)))
        if not files:
            self.reporter.error("没有任何版面下载成功")
            return None
        if not self.cfg.get("auto_merge", True):
            return None
        name = str(self.cfg.get("merged_filename", DEFAULT_CONFIG["merged_filename"])) \
            .replace("{date}", self._disp(date))
        merged = os.path.join(root, name + ".pdf")
        try:
            result = merge_pdfs(files, merged, str(self.cfg.get("pdf_engine", "auto")), self.reporter)
        except Exception as exc:
            self.reporter.error("合并失败：%s（单版 PDF 已保留）" % exc)
            return None
        self.reporter.info("%d 个版面已合并为 %d 页  %.1f MB"
                           % (len(files), result["pages"], os.path.getsize(merged) / 1048576))
        if not self.cfg.get("keep_singles", True):
            reason = safe_rmtree(out_dir, root)
            if reason:
                self.reporter.warn("%s，已跳过删除（单版 PDF 保留）" % reason)
            else:
                self.reporter.info("已按配置删除单版 PDF 目录")
        return merged

    # ---- 文字 ----
    def crawl_text(self, date: str, nodes: Sequence[str]):
        data = []
        known = set(nodes)
        # 头版可能已被 get_nodes 抓过，这里复用缓存
        for position, edition in enumerate(nodes, 1):
            try:
                html = self._node_html(date, edition)
            except Stopped:
                raise
            except Exception as exc:
                self.reporter.warn("第%s版抓取失败：%s" % (edition, describe_error(exc)))
                continue
            match = re.search(r"第%s版[：:]\s*([^<]+)" % edition, html)
            edition_name = match.group(1).strip() if match else "第%s版" % edition
            links = get_article_links(html)
            if not links:
                self.reporter.warn("第%s版(%s)：未发现文章" % (edition, edition_name))
                data.append((edition, edition_name, []))
                continue
            total = len(links)
            self.reporter.info("第%s版(%s)：%d 篇文章" % (edition, edition_name, total))
            articles = self._fetch_articles(date, links, edition, total)
            self.reporter.info("第%s版(%s)：抓取 %d 篇文章" % (edition, edition_name, len(articles)))
            data.append((edition, edition_name, articles))
            self.reporter.progress(position / float(len(nodes)), "正文 %d/%d 版" % (position, len(nodes)))
        if len(known) != len(data):
            self.reporter.debug("部分版面无内容")
        return data

    def _fetch_articles(self, date: str, links: Sequence[str], edition: str, total: int):
        base = str(self.cfg.get("base_url") or DEFAULT_CONFIG["base_url"])
        concurrent = max(1, int(self.cfg.get("text_concurrent", 1)))
        results: List[Optional[Tuple[str, List[str]]]] = [None] * len(links)
        done = [0]
        lock = threading.Lock()

        def one(index: int, cid: str) -> None:
            url = "%s/content/%s/%s/content_%s.html" % (base, date[:6], date[6:], cid)
            try:
                html = self.dl.fetch(url).decode("utf-8", "ignore")
                title, paras = parse_article(html)
                if title and paras:
                    results[index] = (title, paras)
            except Stopped:
                raise
            except Exception as exc:
                self.reporter.debug("文章 %s 抓取失败：%s" % (cid, describe_error(exc)))
            finally:
                with lock:
                    done[0] += 1
                    if done[0] % 5 == 0 or done[0] == total:
                        self.reporter.progress(None, "第%s版 正文 %d/%d" % (edition, done[0], total))

        if concurrent <= 1:
            for index, cid in enumerate(links):
                one(index, cid)
        else:
            with ThreadPoolExecutor(max_workers=concurrent) as pool:
                list(pool.map(lambda pair: one(*pair), list(enumerate(links))))
        return [item for item in results if item]

    def run_single_day_text(self, date: str, nodes: Sequence[str], root: str) -> Optional[str]:
        data = self.crawl_text(date, nodes)
        if not any(articles for _, _, articles in data):
            self.reporter.error("未抓到任何文章")
            return None
        lines = build_text_content(self._disp(date), data,
                                   bool(self.cfg.get("text_include_edition", True)))
        fmt = str(self.cfg.get("text_output_format", "TXT")).upper()
        writer, ext = WRITERS.get(fmt, WRITERS["TXT"])
        name = str(self.cfg.get("text_filename", DEFAULT_CONFIG["text_filename"])) \
            .replace("{date}", self._disp(date))
        path = os.path.join(root, "%s.%s" % (name, ext))
        try:
            size = write_text_file(lines, path, fmt)
        except Exception as exc:
            self.reporter.error("文字文件写入失败：%s" % describe_error(exc))
            return None
        self.reporter.info("%d 行已保存  %.1f KB  %s" % (len(lines), size / 1024, path))
        return path

    # ---- 单日 ----
    def run_single(self, date_arg: str = "", fmt_arg: str = "") -> int:
        date_arg = (date_arg or str(self.cfg.get("default_date") or "").strip()
                    or datetime.date.today().strftime("%Y%m%d"))
        if not re.fullmatch(r"\d{8}", date_arg):
            self.reporter.error("日期格式不正确，应为 8 位数字，例如 20260902")
            return 1
        try:
            datetime.datetime.strptime(date_arg, "%Y%m%d")
        except ValueError:
            self.reporter.error("日期不存在：%s（月份或日期越界）" % date_arg)
            return 1
        today = datetime.date.today().strftime("%Y%m%d")
        if date_arg > today:
            self.reporter.error("%s 是未来日期，人民日报尚未出版（今天 %s）"
                                % (self._disp(date_arg), self._disp(today)))
            return 1

        fmt = (fmt_arg or str(self.cfg.get("default_format", "pdf"))).lower()
        if fmt not in ("text", "pdf", "both"):
            self.reporter.error("格式参数应为 text / pdf / both")
            return 1

        disp = self._disp(date_arg)
        self.reporter.info("开始任务 日期=%s 格式=%s" % (disp, fmt.upper()))
        nodes, net_ok = get_nodes(self.dl, date_arg[:6], date_arg[6:], self._node_cache)
        if not nodes:
            if not net_ok:
                self.reporter.error("%s 版面列表读取失败，疑似网络/代理问题" % disp)
            else:
                self.reporter.error("%s 未找到任何版面（休刊，或 edition_filter 过滤为空）" % disp)
            if self.cfg.get("holiday_skip"):
                self.reporter.info("已按 holiday_skip 忽略该日期")
                return 0
            return 1

        root = out_root(self.cfg)
        os.makedirs(root, exist_ok=True)
        produced: List[str] = []
        if fmt in ("pdf", "both"):
            merged = self.run_single_day_pdf(date_arg, nodes, root)
            if merged:
                produced.append(merged)
        if fmt in ("text", "both"):
            text = self.run_single_day_text(date_arg, nodes, root)
            if text:
                produced.append(text)
        self.reporter.progress(1.0, "完成")
        if not produced:
            self.reporter.error("本次未生成任何文件，详见上方日志")
            return 1
        self.last_output = produced[-1]
        self.reporter.info("任务完成 产物=%s" % ", ".join(produced))
        return 0

    # ---- 批量 ----
    def run_batch(self, expr: str, fmt: str, merge_mode: str) -> int:
        try:
            dates = parse_batch_expr(expr)
        except ValueError as exc:
            self.reporter.error("日期表达式错误：%s" % exc)
            return 1
        if not dates:
            self.reporter.error("未解析到任何日期")
            return 1
        fmt = (fmt or str(self.cfg.get("default_format", "pdf"))).lower()
        if fmt not in ("text", "pdf", "both"):
            self.reporter.error("格式参数应为 text / pdf / both")
            return 1
        merge_mode = (merge_mode or str(self.cfg.get("batch_merge_mode", "each"))).lower()
        if merge_mode not in ("each", "all"):
            self.reporter.error("--merge-mode 应为 each / all")
            return 1

        root = out_root(self.cfg)
        os.makedirs(root, exist_ok=True)
        text_fmt = str(self.cfg.get("text_output_format", "TXT")).upper()
        _writer, text_ext = WRITERS.get(text_fmt, WRITERS["TXT"])
        ok_days, skip_days, fail_days = [], [], []
        all_pdfs: List[str] = []
        all_lines: List[str] = []
        total = len(dates)
        self.reporter.info("批量下载 %d 天  格式=%s  合并=%s" % (total, fmt.upper(), merge_mode))

        for index, date in enumerate(dates, 1):
            self.reporter.info("——— [%d/%d] %s ———" % (index, total, self._disp(date)))
            self.reporter.progress((index - 1) / float(total), "%s" % self._disp(date))
            try:
                nodes, net_ok = get_nodes(self.dl, date[:6], date[6:], self._node_cache)
            except Stopped:
                raise
            if not nodes:
                self.reporter.warn("%s 无版面，跳过（%s）" % (
                    self._disp(date), "网络异常" if not net_ok else "休刊/未出版"))
                skip_days.append(date)
                continue
            day_ok = True
            if fmt in ("pdf", "both"):
                if merge_mode == "all":
                    files, failed, _ = self.download_pdfs(date, nodes, root)
                    all_pdfs.extend(files)
                    if failed or not files:
                        day_ok = False
                else:
                    if self.run_single_day_pdf(date, nodes, root) is None:
                        day_ok = False
            if fmt in ("text", "both"):
                data = self.crawl_text(date, nodes)
                if not any(articles for _, _, articles in data):
                    day_ok = False
                else:
                    lines = build_text_content(self._disp(date), data,
                                               bool(self.cfg.get("text_include_edition", True)))
                    if merge_mode == "all":
                        all_lines.extend(lines)
                    else:
                        name = str(self.cfg.get("text_filename", DEFAULT_CONFIG["text_filename"])) \
                            .replace("{date}", self._disp(date))
                        path = os.path.join(root, "%s.%s" % (name, text_ext))
                        try:
                            write_text_file(lines, path, text_fmt)
                            self.reporter.info("文字已保存 %s" % path)
                        except Exception as exc:
                            self.reporter.error("%s 文字写入失败：%s" % (self._disp(date), exc))
                            day_ok = False
            (ok_days if day_ok else fail_days).append(date)

        span = "%s-%s" % (self._disp(dates[0]), self._disp(dates[-1]))
        final: Optional[str] = None
        pdf_all_ok = True
        if merge_mode == "all":
            if fmt in ("pdf", "both") and all_pdfs:
                target = os.path.join(root, "人民日报-%s-完整版.pdf" % span)
                try:
                    result = merge_pdfs(all_pdfs, target, str(self.cfg.get("pdf_engine", "auto")),
                                        self.reporter)
                    self.reporter.info("全部合并 %d 个版面 → %d 页  %s"
                                       % (len(all_pdfs), result["pages"], target))
                    final = target
                except Exception as exc:
                    pdf_all_ok = False
                    self.reporter.error("全部合并失败：%s（单版 PDF 已保留）" % exc)
            if fmt in ("text", "both") and all_lines:
                target = os.path.join(root, "人民日报-%s-文字版.%s" % (span, text_ext))
                try:
                    write_text_file(all_lines, target, text_fmt)
                    self.reporter.info("全部文字已保存 %s" % target)
                    final = final or target
                except Exception as exc:
                    self.reporter.error("全部文字写入失败：%s" % exc)
            if not self.cfg.get("keep_singles", True) and pdf_all_ok:
                removed = 0
                for date in dates:
                    sub = os.path.join(root, str(self.cfg.get("download_dir", "pdfs_{date}"))
                                       .replace("{date}", date))
                    if not safe_rmtree(sub, root):
                        removed += 1
                if removed:
                    self.reporter.info("已按配置删除 %d 个单版目录" % removed)
        else:
            for date in ok_days:
                for pattern, ext in (("merged_filename", "pdf"), ("text_filename", text_ext)):
                    if (pattern == "merged_filename" and fmt not in ("pdf", "both")) or \
                            (pattern == "text_filename" and fmt not in ("text", "both")):
                        continue
                    candidate = os.path.join(
                        root, str(self.cfg.get(pattern, DEFAULT_CONFIG[pattern]))
                        .replace("{date}", self._disp(date)) + "." + ext)
                    if os.path.exists(candidate):
                        final = candidate

        if final:
            self.last_output = final
        self.reporter.progress(1.0, "完成")
        self.last_failed = list(fail_days)
        self.reporter.info("批量汇总：成功 %d 天 / 跳过 %d 天 / 失败 %d 天"
                           % (len(ok_days), len(skip_days), len(fail_days)))
        if skip_days:
            self.reporter.info("跳过日期：%s" % ", ".join(skip_days))
        if fail_days:
            self.reporter.error("失败日期：%s" % ", ".join(fail_days))
            try:
                listing = os.path.join(root, "failed-%s.txt" % span.replace(" ", "_"))
                with open(listing, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(fail_days) + "\n")
                self.reporter.info("失败清单已保存：%s" % listing)
            except OSError:
                pass
        return 0 if ok_days else 1


# --------------------------------------------------------------------------
# 日期表达式
# --------------------------------------------------------------------------

def _normalize_date(token: str) -> str:
    raw = re.sub(r"[-/.]", "", token.strip())
    if not re.fullmatch(r"\d{8}", raw):
        raise ValueError("无效日期: %r" % token)
    try:
        datetime.datetime.strptime(raw, "%Y%m%d")
    except ValueError:
        raise ValueError("日期不存在（月份或日期越界）: %s" % token)
    return raw


def days_in_month(year: int, month: int) -> int:
    if month == 2:
        leap = (year % 4 == 0 and year % 100 != 0) or year % 400 == 0
        return 29 if leap else 28
    return 30 if month in (4, 6, 9, 11) else 31


def clamp_date(year: int, month: int, day: int) -> datetime.date:
    """把用户随手填的年月日收成一个合法日期（2 月 30 日会落成 2 月 28/29 日）。"""
    year = max(2000, min(2100, int(year)))
    month = max(1, min(12, int(month)))
    day = max(1, min(days_in_month(year, month), int(day)))
    return datetime.date(year, month, day)


def probe_edition_count(cfg: Dict[str, object], date: str) -> Tuple[int, bool]:
    """只花一个请求，问出这天有多少版（GUI 用来做预期管理）。"""
    local, _ = validate_config(dict(cfg))
    reporter = Reporter()
    downloader = Downloader(local, reporter)
    try:
        nodes, ok = get_nodes(downloader, date[:6], date[6:])
        return len(nodes), ok
    except Exception:
        return 0, False


def parse_batch_expr(expr: str) -> List[str]:
    """解析批量日期表达式。

    支持 `20260901-20260903`、`20260905`、`20260801-`（到今天）、
    `2026-09-01~2026-09-03`，逗号分隔多个片段，自动去重。
    """
    today = datetime.date.today().strftime("%Y%m%d")
    dates: List[str] = []
    for part in str(expr).split(","):
        part = part.strip()
        if not part:
            continue
        separator = None
        for sep in ("~", "..", "到"):
            if sep in part:
                separator = sep
                break
        if separator is None:
            hyphen = part.split("-")
            if len(hyphen) == 2 and (re.fullmatch(r"\d{8}", hyphen[0].strip())
                                     or re.fullmatch(r"\d{8}", hyphen[1].strip() or "0")):
                separator = "-"
        if separator is None:
            dates.append(_normalize_date(part))
            continue
        start_raw, _, end_raw = part.partition(separator)
        first = _normalize_date(start_raw)
        last = _normalize_date(end_raw) if end_raw.strip() else today
        if first > last:
            raise ValueError("起始日期 %s 晚于结束日期 %s" % (first, last))
        cursor = datetime.datetime.strptime(first, "%Y%m%d").date()
        end = datetime.datetime.strptime(last, "%Y%m%d").date()
        while cursor <= end:
            dates.append(cursor.strftime("%Y%m%d"))
            cursor += datetime.timedelta(days=1)
    seen, ordered = set(), []
    for date in dates:
        if date not in seen:
            seen.add(date)
            ordered.append(date)
    return ordered


# --------------------------------------------------------------------------
# 通知 / 调度 / 打开目录
# --------------------------------------------------------------------------

def notify(cfg: Dict[str, object], title: str, message: str) -> None:
    if cfg.get("beep_on_done"):
        try:
            import winsound
            winsound.MessageBeep()
        except Exception:
            pass
    if cfg.get("msg_on_done"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        except Exception:
            pass


def reveal(path: str) -> None:
    """在资源管理器里选中文件（失败则退化为打开所在目录）。"""
    if not path:
        return
    try:
        if sys.platform == "win32" and os.path.exists(path):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
            return
    except Exception:
        pass
    open_folder(os.path.dirname(path) or path)


def open_folder(path: str) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def task_command(cfg: Dict[str, object]) -> Tuple[List[str], str]:
    """构造 schtasks 参数。用列表传参，避免 cmd.exe 把引号吃掉。"""
    when = str(cfg.get("auto_run_time", "08:00")).strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", when)
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        when = "08:00"
    date_arg = str(cfg.get("default_date") or "").strip()
    fmt = str(cfg.get("default_format", "pdf")).lower()
    if fmt not in ("pdf", "text", "both"):
        fmt = "pdf"
    # --silent：不弹窗、不打印、不打开资源管理器，只按配置下载
    tail = " ".join(x for x in ("--silent", date_arg, fmt) if x)
    if getattr(sys, "frozen", False):
        target = '"%s" %s' % (os.path.abspath(sys.executable), tail)
    else:
        cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rmrb_downloader.py")
        target = '"%s" "%s" %s' % (sys.executable, cli, tail)
    target = re.sub(r"\s+", " ", target).strip()
    if len(target) > 260:
        raise ValueError("命令过长（%d 字符），schtasks 最多 261 字符，请把项目移到更短的路径"
                         % len(target))
    args = ["schtasks", "/create", "/tn", "RMRB_Download", "/tr", target,
            "/sc", "daily", "/st", when, "/f"]
    return args, when


def install_task(cfg: Dict[str, object], reporter: Reporter) -> int:
    try:
        args, when = task_command(cfg)
    except ValueError as exc:
        reporter.error(str(exc))
        return 1
    result = subprocess.run(args, capture_output=True, text=True, encoding="gbk",
                            errors="replace")
    if result.returncode != 0:
        reporter.error("注册计划任务失败：%s" % (result.stdout or result.stderr or "").strip())
        return 1
    reporter.info("已注册每日 %s 自动下载任务（任务名 RMRB_Download）" % when)
    return 0


def remove_task(reporter: Reporter) -> int:
    result = subprocess.run(["schtasks", "/delete", "/tn", "RMRB_Download", "/f"],
                            capture_output=True, text=True, encoding="gbk", errors="replace")
    if result.returncode != 0:
        reporter.warn("删除计划任务失败：%s" % (result.stdout or result.stderr or "").strip())
        return 1
    reporter.info("已删除自动下载计划任务")
    return 0
