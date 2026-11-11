# -*- coding: utf-8 -*-
"""
人民日报电子版下载器（全配置版 v2）
====================================
功能：
  - PDF 模式：下载当日全部版面 PDF 并自动合并为完整版
  - 文字模式：抓取当日全部版面文章正文，合并为 TXT / DOC / DOCX
  - both 模式：两种同时
  - 批量模式：--batch 支持多日期/日期范围下载，每日期单独合并或全部合并
  - 所有行为可通过 config.json 调节（含 download_path 下载根目录）
用法：
  python rmrb_downloader.py [日期] [格式]
    日期: YYYYMMDD，缺省按配置 default_date 或今日
    格式: text / pdf / both，缺省按配置 default_format
  批量:
  python rmrb_downloader.py --batch "20260901-20260903,20260905" [格式] [--merge-mode each|all]
    日期范围: 逗号分隔；支持 "起始-结束" 与 "日期-"(到今日)
  python rmrb_downloader.py --init
"""
import contextlib
import datetime
import html as html_mod
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

APP_NAME = "人民日报电子版下载器"

# Windows 控制台编码适配：PyInstaller 打包后 stdout 默认 UTF-8，
# 而 cmd 默认 GBK(CP936)，导致中文乱码。通过文件描述符重开为 GBK。
if sys.platform == "win32":
    try:
        sys.stdout = open(sys.stdout.fileno(), "w", encoding="gbk", closefd=False)
        sys.stderr = open(sys.stderr.fileno(), "w", encoding="gbk", closefd=False)
    except Exception:
        pass
DEFAULT_CONFIG = {
    # 抓取与网络
    "base_url": "http://paper.people.com.cn/rmrb/pc",
    "rate_limit_kbps": 0,
    "timeout": 30,
    "retry": 3,
    "retry_interval": 2,
    "request_interval": 0.2,
    "concurrent": 1,
    "proxy": "",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    # 界面
    "color_foreground": "A",
    "color_background": "0",
    "window_title": "人民日报电子版下载器",
    "show_progress": True,
    # 日期与内容
    "default_date": "",
    "default_format": "pdf",
    "edition_filter": [],
    "holiday_skip": False,
    # 批量下载
    "batch_enable": False,           # True 时 BAT 显示批量下载界面
    "batch_merge_mode": "each",      # each=每日期单独合并  all=全部合并成一个
    "download_path": "",             # 下载根目录（留空=脚本所在文件夹）
    # 输出与合并
    "download_dir": "pdfs_{date}",
    "merged_filename": "人民日报-{date}-完整版",
    "auto_merge": True,
    "keep_singles": True,
    "open_folder_after": True,
    # 文字输出
    "text_output_format": "TXT",     # TXT / DOC / DOCX / MD
    "text_filename": "人民日报-{date}-文字版",
    "text_include_edition": True,
    # 日志与通知
    "log_file": "rmrb_download.log",
    "log_level": "normal",           # quiet / normal / debug
    "beep_on_done": False,
    "msg_on_done": False,
}

def _app_dir():
    """应用所在目录：打包后(PyInstaller frozen)=exe 所在目录，开发时=脚本所在目录。
    确保 config.json / 下载目录 / 日志都在 exe 同级，而非临时解压目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

HERE = _app_dir()
CONFIG_PATH = os.path.join(HERE, "config.json")

_log_enabled = True
_log_level = "normal"


# ------------------------- 配置 -------------------------

def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
            cfg.update(user)
        except Exception as e:
            print("[警告] config.json 读取失败(%s)，使用默认配置" % e)
    else:
        save_config(cfg)
        print("[提示] 已生成默认配置文件 config.json，可编辑后使用")
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def out_root(cfg):
    """下载根目录：download_path 留空=脚本目录，相对路径相对脚本目录"""
    p = str(cfg.get("download_path", "")).strip()
    if not p:
        return HERE
    if os.path.isabs(p):
        return p
    return os.path.join(HERE, p)


# ------------------------- 日志 -------------------------

def log(msg, level="info"):
    if not _log_enabled:
        return
    lvl_map = {"debug": 0, "info": 1, "warn": 2, "error": 3}
    cur = lvl_map.get(_log_level, 1)
    lv = lvl_map.get(level, 1)
    if lv < cur:
        return
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(os.path.join(HERE, "rmrb_download.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def describe_error(e):
    """把底层网络异常翻译成中文可操作提示。"""
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 404:
            return "页面不存在(HTTP 404)：该日期可能未出版，或官网版面结构已变化"
        if e.code in (403, 429):
            return "服务器拒绝(HTTP %s)：访问过于频繁，可增大 request_interval 后重试" % e.code
        if 500 <= e.code < 600:
            return "人民日报服务器异常(HTTP %s)，请稍后重试" % e.code
        return "服务器返回 HTTP %s" % e.code
    if isinstance(e, urllib.error.URLError):
        reason = getattr(e, "reason", e)
        txt = str(reason).lower()
        if "name or service not known" in txt or "getaddrinfo" in txt or "name resolution" in txt:
            return "域名解析失败：网络未连接或 DNS 异常，请检查网络后重试"
        if "refused" in txt:
            return "连接被拒绝：目标服务器不可达，请检查网络/代理(config.proxy)"
        return "网络连接失败(%s)：请检查网络连接或代理设置" % reason
    if isinstance(e, (TimeoutError, socket.timeout)) or "timed out" in str(e).lower():
        return "连接/读取超时：可在 config.json 增大 timeout，或稍后重试"
    if isinstance(e, ConnectionError):
        return "连接中断(%s)：网络不稳定，请重试" % e
    return str(e)


def validate_config(cfg):
    """校验并修正配置中的非法值，返回(修正后的cfg, 警告列表)。"""
    warns = []

    def _num(key, cast, default, lo=None, hi=None):
        try:
            v = cast(cfg.get(key, default))
            if lo is not None and v < lo:
                warns.append("%s=%s 小于最小值 %s，已回退为 %s" % (key, cfg.get(key), lo, default))
                v = default
            if hi is not None and v > hi:
                warns.append("%s=%s 大于最大值 %s，已回退为 %s" % (key, cfg.get(key), hi, default))
                v = default
            cfg[key] = v
        except (TypeError, ValueError):
            warns.append("%s=%r 不是合法数值，已回退为 %s" % (key, cfg.get(key), default))
            cfg[key] = default

    _num("rate_limit_kbps", float, 0, 0)
    _num("timeout", int, 30, 1)
    _num("retry", int, 3, 0, 20)
    _num("retry_interval", float, 2, 0)
    _num("request_interval", float, 0.2, 0)
    _num("concurrent", int, 1, 1, 16)

    if str(cfg.get("default_format", "pdf")).lower() not in ("text", "pdf", "both"):
        warns.append("default_format=%r 非法，已回退为 pdf" % cfg.get("default_format"))
        cfg["default_format"] = "pdf"
    if str(cfg.get("text_output_format", "TXT")).upper() not in ("TXT", "DOC", "DOCX", "MD"):
        warns.append("text_output_format=%r 非法，已回退为 TXT" % cfg.get("text_output_format"))
        cfg["text_output_format"] = "TXT"
    if str(cfg.get("batch_merge_mode", "each")).lower() not in ("each", "all"):
        warns.append("batch_merge_mode=%r 非法，已回退为 each" % cfg.get("batch_merge_mode"))
        cfg["batch_merge_mode"] = "each"
    # cmd color 两位十六进制
    cc = str(cfg.get("color_background", "0")) + str(cfg.get("color_foreground", "A"))
    if not re.fullmatch(r"[0-9A-Fa-f]{2}", cc):
        warns.append("颜色配置非法(应为两位十六进制如 0A)，已回退为 0A")
        cfg["color_background"], cfg["color_foreground"] = "0", "A"
    # edition_filter 必须是整数列表
    ef = cfg.get("edition_filter", [])
    if not isinstance(ef, list):
        warns.append("edition_filter 应为列表，已清空(=全部版面)")
        cfg["edition_filter"] = []
    else:
        good = []
        for x in ef:
            try:
                good.append(int(x))
            except (TypeError, ValueError):
                warns.append("edition_filter 含非法值 %r，已忽略" % x)
        cfg["edition_filter"] = good
    return cfg, warns


# ------------------------- 网络 -------------------------

class Downloader:
    def __init__(self, cfg):
        self.cfg = cfg
        self.ua = cfg["user_agent"]
        self.timeout = int(cfg.get("timeout", 30))
        self.retry = int(cfg.get("retry", 3))
        self.retry_interval = float(cfg.get("retry_interval", 2))
        self.rate_kbps = float(cfg.get("rate_limit_kbps", 0))
        self.proxy = cfg.get("proxy", "")

    def _opener(self):
        handlers = []
        if self.proxy:
            handlers.append(urllib.request.ProxyHandler({
                "http": self.proxy, "https": self.proxy}))
        return urllib.request.build_opener(*handlers)

    def fetch(self, url, timeout=None):
        last_err = None
        for attempt in range(self.retry + 1):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": self.ua, "Referer": self.cfg["base_url"]})
                with self._opener().open(req, timeout=timeout or self.timeout) as resp:
                    return resp.read()
            except Exception as e:
                last_err = e
                if attempt < self.retry:
                    time.sleep(self.retry_interval)
        raise last_err

    def download_stream(self, url, path, label, total_editions):
        show_prog = bool(self.cfg.get("show_progress", True))
        last_err = None
        for attempt in range(self.retry + 1):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": self.ua, "Referer": self.cfg["base_url"]})
                with self._opener().open(req, timeout=max(self.timeout, 120)) as resp:
                    total = int(resp.headers.get("Content-Length") or 0)
                    done = 0
                    t0 = time.time()
                    with open(path, "wb") as f:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            done += len(chunk)
                            if self.rate_kbps > 0:
                                target = done / (self.rate_kbps * 1024)
                                remain = target - (time.time() - t0)
                                if remain > 0:
                                    time.sleep(remain)
                            if show_prog:
                                elapsed = time.time() - t0
                                speed = done / elapsed / 1024 if elapsed > 0 else 0
                                if total > 0:
                                    pct = done / total * 100
                                    bar = "#" * int(pct / 2) + "-" * (50 - int(pct / 2))
                                    sys.stdout.write(
                                        "\r  [%s/%s版] |%s| %5.1f%%  %6.1f/%6.1f MB  %6.0f KB/s"
                                        % (label, total_editions, bar, pct,
                                           done / 1048576, total / 1048576, speed))
                                else:
                                    sys.stdout.write("\r  [%s] 已下载 %6.1f MB" % (label, done / 1048576))
                                sys.stdout.flush()
                if show_prog:
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    sys.stdout.flush()
                print("  [%s/%s版] 下载完成  %6.1f MB"
                      % (label, total_editions, done / 1048576))
                return done
            except Exception as e:
                last_err = e
                # 清理可能写了一半的残文件
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except OSError:
                    pass
                if attempt < self.retry:
                    print("  [%s] 第 %d 次下载失败(%s)，%.0f 秒后重试..."
                          % (label, attempt + 1, describe_error(e), self.retry_interval))
                    time.sleep(self.retry_interval)
        raise last_err


# ------------------------- 版面解析 -------------------------

def get_nodes(dl, ym, dd):
    """获取某日全部版面号。
    返回 (版面号字符串列表, 头版页面是否成功访问)。
    edition_filter 为白名单：非空时只保留列出的版面号；为空=全部版面。"""
    nodes = []
    net_ok = False
    try:
        node1 = dl.fetch("%s/layout/%s/%s/node_01.html" % (dl.cfg["base_url"], ym, dd)) \
            .decode("utf-8", "ignore")
        net_ok = True
        nodes = sorted(set(re.findall(r'href="node_(\d+)\.html"', node1)),
                       key=lambda x: int(x))
    except Exception as e:
        log("读取头版页面失败: %s" % e, "warn")
        print("  [网络] 读取版面列表失败：%s" % describe_error(e))
    if not nodes:
        try:
            idx = dl.fetch("%s/layout/index.html" % dl.cfg["base_url"]) \
                .decode("utf-8", "ignore")
            nodes = sorted(set(re.findall(rf"{ym}/{dd}/node_(\d+)\.html", idx)),
                           key=lambda x: int(x))
        except Exception:
            pass
    flt = [int(x) for x in dl.cfg.get("edition_filter", [])]
    if flt:
        before = len(nodes)
        nodes = [n for n in nodes if int(n) in flt]
        log("edition_filter 白名单 %s：%d -> %d 版" % (flt, before, len(nodes)), "debug")
    return nodes, net_ok


# ------------------------- PDF -------------------------

def ensure_pypdf(interactive=False):
    """确保 pypdf 可用。exe 模式已内置直接返回 True；
    源码模式缺少时，interactive=True 则提示 Y/N，否则自动安装。"""
    try:
        import pypdf  # noqa
        return True
    except ImportError:
        pass
    if getattr(sys, "frozen", False):
        print("[错误] exe 内置 pypdf 加载失败，请重新下载发布包。")
        return False
    if interactive:
        try:
            ans = input("[提示] 未检测到 pypdf 库（PDF 合并需要），是否自动安装？(Y/N): ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            ans = "N"
        if ans != "Y":
            print("[信息] 已跳过 pypdf 安装，PDF 合并不可用（文字版仍可使用）。")
            return False
    print("[提示] 正在安装 pypdf（需联网，优先国内镜像）...")
    cmds = [
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "pypdf"],
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q",
         "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "pypdf"],
    ]
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                import pypdf  # noqa
                print("[提示] pypdf 安装成功。")
                return True
        except Exception:
            continue
    print("[错误] pypdf 安装失败，请检查网络后手动执行: pip install pypdf")
    return False


def merge_pdfs(pdf_files, out_path):
    """合并 PDF。先清理旧文件；目标被占用时自动重试，仍失败抛错。"""
    from pypdf import PdfReader, PdfWriter
    # 清理可能存在的旧文件（防止被占用导致无法覆盖）
    if os.path.exists(out_path):
        try:
            os.remove(out_path)
        except OSError:
            pass

    def _build_and_write(target):
        writer = PdfWriter()
        total_pages = 0
        for f in pdf_files:
            r = PdfReader(f)
            total_pages += len(r.pages)
            for p in r.pages:
                writer.add_page(p)
        with open(target, "wb") as fh:
            with open(os.devnull, "w") as devnull, contextlib.redirect_stderr(devnull):
                writer.write(fh)
        return total_pages

    last_err = None
    pages = 0
    for attempt in range(4):
        try:
            pages = _build_and_write(out_path)
            return pages
        except PermissionError as e:
            last_err = e
            time.sleep(2)
    raise last_err


def download_pdfs(dl, date_arg, nodes, out_root):
    """下载单日全部版面 PDF，返回 (单版文件列表, 失败版号列表)"""
    cfg = dl.cfg
    total = len(nodes)
    print("  共 %d 个版面，开始下载 PDF...\n" % total)
    singles = []
    failed = []
    concurrent = max(1, int(cfg.get("concurrent", 1)))
    ym, dd = date_arg[:6], date_arg[6:]
    dir_tpl = str(cfg.get("download_dir", "pdfs_{date}"))
    out_dir = os.path.join(out_root, dir_tpl.replace("{date}", date_arg))
    os.makedirs(out_dir, exist_ok=True)

    def work(n):
        node_url = "%s/layout/%s/%s/node_%s.html" % (cfg["base_url"], ym, dd, n)
        try:
            html = dl.fetch(node_url).decode("utf-8", "ignore")
            pdfs = re.findall(r"attachement/\d{6}/\d{2}/[0-9a-f-]+\.pdf", html)
            if not pdfs:
                print("  第%s版: 未找到 PDF 链接，跳过" % n)
                return n, None
            rel = pdfs[0]
            fpath = os.path.join(out_dir, "rmrb_%s_%s.pdf" % (date_arg, n))
            dl.download_stream("%s/%s" % (cfg["base_url"], rel), fpath,
                               "第%s版" % n, total)
            return n, fpath
        except Exception as e:
            log("第%s版失败: %s" % (n, e), "error")
            print("  第%s版: 下载失败 - %s" % (n, describe_error(e)))
            return n, None

    if concurrent <= 1:
        for n in nodes:
            n, fpath = work(n)
            if fpath:
                singles.append(fpath)
            else:
                failed.append(n)
            time.sleep(float(cfg.get("request_interval", 0.2)))
    else:
        with ThreadPoolExecutor(max_workers=concurrent) as ex:
            for n, fpath in ex.map(work, nodes):
                if fpath:
                    singles.append(fpath)
                else:
                    failed.append(n)
    print()
    return singles, failed, out_dir


def run_single_day_pdf(dl, date_arg, date_disp, nodes, out_root, merge_mode="auto"):
    """单日 PDF 流程。merge_mode: auto(按config)/force/each(合并)/all/None(不合并)
    返回 (合并文件路径或None, 单版文件列表)"""
    cfg = dl.cfg
    singles, failed, out_dir = download_pdfs(dl, date_arg, nodes, out_root)
    merged = None
    if not singles:
        print("[错误] %s 没有任何版面下载成功" % date_disp)
        return None, singles
    do_merge = False
    if merge_mode == "force" or merge_mode == "each":
        do_merge = True
    elif merge_mode == "auto":
        do_merge = bool(cfg.get("auto_merge", True))
    if do_merge:
        if not ensure_pypdf():
            print("[错误] 无法安装合并库 pypdf，跳过合并")
        else:
            merged_name = str(cfg.get("merged_filename", "人民日报-{date}-完整版")) \
                .replace("{date}", date_disp)
            merged = os.path.join(out_root, merged_name + ".pdf")
            try:
                pages = merge_pdfs(sorted(singles), merged)
                print("[合并] %d 个版面已合并为 %d 页  %.1f MB"
                      % (len(singles), pages, os.path.getsize(merged) / 1048576))
                print("[文件] %s" % merged)
            except Exception as e:
                if isinstance(e, PermissionError):
                    print("[错误] 合并失败：目标文件正被占用（可能已在 PDF 阅读器中打开）。")
                    print("       请关闭同名文件后重试，或修改 config.json 的 merged_filename / download_path。")
                else:
                    print("[错误] 合并失败: %s" % e)
                merged = None
    if not cfg.get("keep_singles", True) and merged:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
        print("[信息] 已按配置删除单版 PDF（keep_singles=false）")
    if failed:
        print("[提示] %d 个版面未成功: %s" % (len(failed), ", ".join(failed)))
    return merged, singles


# ------------------------- 文字模式 -------------------------

def parse_article(html):
    title = ""
    m = re.search(r"<h1[^>]*>\s*<p[^>]*>(.*?)</p>\s*</h1>", html, re.S)
    if m:
        title = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    if not title:
        m = re.search(r"<title>\s*(.*?)\s*</title>", html, re.S)
        if m:
            title = html_mod.unescape(m.group(1)).strip()
    body = ""
    m = re.search(r"<!--enpcontent-->(.*?)<!--/enpcontent-->", html, re.S)
    if m:
        body = m.group(1)
    paras = []
    for pm in re.finditer(r"<p[^>]*>(.*?)</p>", body, re.S):
        inner = pm.group(1)
        is_heading = bool(re.search(r"<strong\b", inner, re.I))
        text = re.sub(r"<[^>]+>", "", inner)
        text = html_mod.unescape(text).replace("\u3000", "　").strip()
        if text:
            paras.append({"text": text, "heading": is_heading})
    return title, paras


def get_article_links(node_html):
    ids = re.findall(r"content/(\d{6})/(\d{2})/content_(\d+)\.html", node_html)
    return sorted(set(ids), key=lambda x: int(x[2]))


def crawl_text(dl, date_arg, nodes):
    cfg = dl.cfg
    result = []
    for n in nodes:
        node_url = "%s/layout/%s/%s/node_%s.html" % (cfg["base_url"], date_arg[:6], date_arg[6:], n)
        try:
            html = dl.fetch(node_url).decode("utf-8", "ignore")
        except Exception as e:
            print("  第%s版: 抓取失败 - %s" % (n, e))
            continue
        m = re.search(r"第%s版[：:]\s*([^<]+)" % n, html)
        ed_name = m.group(1).strip() if m else "第%s版" % n
        links = get_article_links(html)
        if not links:
            print("  第%s版(%s): 未发现文章" % (n, ed_name))
            continue
        arts = []
        for _, _, cid in links:
            art_url = "%s/content/%s/%s/content_%s.html" % (
                cfg["base_url"], date_arg[:6], date_arg[6:], cid)
            try:
                art_html = dl.fetch(art_url).decode("utf-8", "ignore")
                title, paras = parse_article(art_html)
                if title and paras:
                    arts.append((title, paras))
                time.sleep(float(cfg.get("request_interval", 0.2)))
            except Exception:
                continue
        print("  第%s版(%s): 抓取 %d 篇文章" % (n, ed_name, len(arts)))
        result.append((n, ed_name, arts))
    return result


def build_text_content(date_disp, data, show_edition=True, markdown=False):
    lines = []
    if markdown:
        lines.extend(["# 人民日报 %s" % date_disp, ""])
    else:
        lines.extend(["人民日报  %s" % date_disp, "=" * 46])
    for n, ed_name, arts in data:
        if not arts:
            continue
        if show_edition:
            lines.append("")
            lines.append("## %s" % ed_name if markdown else "【%s】" % ed_name)
            if not markdown:
                lines.append("-" * 46)
        for title, paras in arts:
            lines.extend(["", "# %s" % title if markdown else title, ""])
            for para in paras:
                text = para["text"] if isinstance(para, dict) else para
                is_heading = para.get("heading", False) if isinstance(para, dict) else False
                lines.append(("## " if is_heading else "") + text if markdown else text)
    return lines


def write_txt(lines, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return len(lines)


def write_markdown(lines, path):
    return write_txt(lines, path)


def write_doc(lines, path):
    body = ["<html><head><meta http-equiv=\"Content-Type\" "
            "content=\"text/html; charset=utf-8\"></head><body>"]
    for line in lines:
        text = html_mod.escape(line)
        if line.startswith("=") or line.startswith("-"):
            body.append("<hr>")
        elif line.startswith("【"):
            body.append("<h2 style=\"margin:18px 0 6px;\">%s</h2>" % text)
        elif line == "":
            body.append("<p>&nbsp;</p>")
        else:
            body.append("<p style=\"font-family:宋体;font-size:12pt;line-height:1.8;\">%s</p>" % text)
    body.append("</body></html>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(body))
    return len(lines)


def _xml(s):
    return html_mod.escape(s)


def write_docx(lines, path):
    paras = []
    for line in lines:
        if line.startswith("=") or line.startswith("-") or line == "":
            continue
        if line.startswith("【"):
            run = ("<w:r><w:rPr><w:rFonts w:ascii=\"微软雅黑\" w:eastAsia=\"微软雅黑\"/>"
                   "<w:b/><w:sz w:val=\"32\"/></w:rPr><w:t xml:space=\"preserve\">%s</w:t></w:r>"
                   % _xml(line))
        else:
            run = ("<w:r><w:rPr><w:rFonts w:ascii=\"宋体\" w:eastAsia=\"宋体\"/>"
                   "<w:sz w:val=\"24\"/></w:rPr><w:t xml:space=\"preserve\">%s</w:t></w:r>"
                   % _xml(line))
        paras.append("<w:p>%s</w:p>" % run)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>%s<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>'
    ) % "".join(paras)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
    return len(lines)


def write_text_file(lines, path, fmt):
    fmt = fmt.upper()
    if fmt == "DOC":
        write_doc(lines, path)
    elif fmt == "DOCX":
        write_docx(lines, path)
    elif fmt == "MD":
        write_markdown(lines, path)
    else:
        write_txt(lines, path)
    return os.path.getsize(path)


def run_single_day_text(dl, date_arg, date_disp, nodes, out_root):
    cfg = dl.cfg
    print("  共 %d 个版面，开始抓取文章正文...\n" % len(nodes))
    data = crawl_text(dl, date_arg, nodes)
    if not data:
        print("[错误] 未抓到任何文章")
        return None
    fmt = str(cfg.get("text_output_format", "TXT")).upper()
    lines = build_text_content(date_disp, data, bool(cfg.get("text_include_edition", True)),
                              markdown=(fmt == "MD"))
    fname_tpl = str(cfg.get("text_filename", "人民日报-{date}-文字版"))
    out_path = os.path.join(out_root, fname_tpl.replace("{date}", date_disp) + "." + fmt.lower())
    try:
        size = write_text_file(lines, out_path, fmt)
    except Exception as e:
        print("[错误] 文字文件写入失败：%s" % describe_error(e))
        print("       请检查 download_path 是否存在/可写，或文件是否被占用。")
        return None
    print("[文字] %d 行已保存: %s  (%.1f KB)" % (len(lines), out_path, size / 1024))
    return out_path


# ------------------------- 批量下载 -------------------------

def parse_batch_expr(expr):
    """解析批量日期表达式，返回日期列表(YYYYMMDD)。
    支持: "20260901-20260903,20260905,20260801-"(到今日)"""
    today = datetime.date.today().strftime("%Y%m%d")
    dates = []
    for part in str(expr).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            a, b = a.strip(), b.strip()
            if not re.fullmatch(r"\d{8}", a):
                raise ValueError("无效起始日期: %r" % a)
            if not b:
                b = today
            if not re.fullmatch(r"\d{8}", b):
                raise ValueError("无效结束日期: %r" % b)
            if a > b:
                raise ValueError("起始日期 %s 晚于结束日期 %s" % (a, b))
            try:
                da = datetime.datetime.strptime(a, "%Y%m%d").date()
                db = datetime.datetime.strptime(b, "%Y%m%d").date()
            except ValueError:
                raise ValueError("无效日期（月份或日期不存在）: %s~%s" % (a, b))
            cur = da
            while cur <= db:
                dates.append(cur.strftime("%Y%m%d"))
                cur += datetime.timedelta(days=1)
        else:
            if not re.fullmatch(r"\d{8}", part):
                raise ValueError("无效日期: %r" % part)
            try:
                datetime.datetime.strptime(part, "%Y%m%d")
            except ValueError:
                raise ValueError("无效日期（月份或日期不存在）: %s" % part)
            dates.append(part)
    seen, out = set(), []
    for d in dates:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def batch_main(cfg, expr, fmt, merge_mode):
    dl = Downloader(cfg)
    root = out_root(cfg)
    os.makedirs(root, exist_ok=True)
    try:
        dates = parse_batch_expr(expr)
    except ValueError as e:
        print("[错误] 日期表达式错误: %s" % e)
        return 1
    if not dates:
        print("[错误] 未解析到任何日期")
        return 1
    total_days = len(dates)
    print("=" * 60)
    print("  批量下载  %d 天  %s  合并模式: %s" % (total_days, fmt.upper(), merge_mode))
    print("  下载目录: %s" % root)
    print("=" * 60)

    ok_days, skip_days, fail_days = [], [], []
    all_singles, all_text_lines = [], []
    text_ext = str(cfg.get("text_output_format", "TXT")).lower()
    for idx, d in enumerate(dates, 1):
        date_disp = "%s-%s-%s" % (d[:4], d[4:6], d[6:])
        print("\n----------- [%d/%d] %s -----------" % (idx, total_days, date_disp))
        nodes, _ = get_nodes(dl, d[:6], d[6:])
        if not nodes:
            print("[跳过] %s 无版面（休刊/未出版/被 edition_filter 过滤为空）" % date_disp)
            skip_days.append(d)
            continue
        day_ok = True
        if fmt in ("pdf", "both"):
            if merge_mode == "all":
                singles, failed, _ = download_pdfs(dl, d, nodes, root)
                all_singles.extend(singles)
                if failed:
                    day_ok = False
                if not singles:
                    print("[警告] %s PDF 无成功版面" % date_disp)
            else:
                merged, singles = run_single_day_pdf(dl, d, date_disp, nodes, root,
                                                     merge_mode="force")
                if merged is None:
                    day_ok = False
        if fmt in ("text", "both"):
            data = crawl_text(dl, d, nodes)
            if data:
                lines = build_text_content(date_disp, data,
                                           bool(cfg.get("text_include_edition", True)),
                                           markdown=(text_ext == "md"))
                if merge_mode == "all":
                    all_text_lines.extend(lines)
                else:
                    fname = str(cfg.get("text_filename", "人民日报-{date}-文字版")) \
                        .replace("{date}", date_disp) + "." + text_ext
                    fpath = os.path.join(root, fname)
                    try:
                        write_text_file(lines, fpath, text_ext)
                        print("[文字] %d 行已保存: %s" % (len(lines), fpath))
                    except Exception as e:
                        print("[错误] %s 文字文件写入失败: %s" % (date_disp, describe_error(e)))
                        day_ok = False
            else:
                day_ok = False
        if day_ok:
            ok_days.append(d)
        else:
            fail_days.append(d)

    # all 模式最终合并
    final_result = None
    pdf_all_ok = True
    if merge_mode == "all":
        start, end = dates[0], dates[-1]
        span = "%s-%s" % (start[:4] + "-" + start[4:6] + "-" + start[6:],
                          end[:4] + "-" + end[4:6] + "-" + end[6:])
        if fmt in ("pdf", "both") and all_singles:
            pdf_all_ok = False
            if not ensure_pypdf():
                print("[错误] 无法安装合并库 pypdf，已保留全部单版 PDF")
            else:
                merged = os.path.join(root, "人民日报-%s-完整版.pdf" % span)
                try:
                    pages = merge_pdfs(sorted(all_singles), merged)
                    print("\n[全部合并] %d 个版面 -> %s  (%d 页, %.1f MB)"
                          % (len(all_singles), merged, pages, os.path.getsize(merged) / 1048576))
                    final_result = merged
                    pdf_all_ok = True
                except Exception as e:
                    if isinstance(e, PermissionError):
                        print("[错误] 全部合并失败：目标文件正被占用（可能已在 PDF 阅读器中打开）。")
                        print("       请关闭同名文件后重试，或修改 merged_filename / download_path。")
                    else:
                        print("[错误] 全部合并失败: %s" % e)
                    print("       已保留全部单版 PDF，可手动合并或重跑。")
        if fmt in ("text", "both") and all_text_lines:
            fname = "人民日报-%s-文字版.%s" % (span, text_ext)
            fpath = os.path.join(root, fname)
            try:
                write_text_file(all_text_lines, fpath, text_ext)
                print("[全部文字] %d 行 -> %s" % (len(all_text_lines), fpath))
                final_result = final_result or fpath
            except Exception as e:
                print("[错误] 全部文字文件写入失败: %s" % describe_error(e))
        # keep_singles：仅在 PDF 合并成功后才删除单版，避免合并失败又丢源文件
        if not cfg.get("keep_singles", True):
            if pdf_all_ok:
                import shutil
                dir_tpl = str(cfg.get("download_dir", "pdfs_{date}"))
                for d in dates:
                    ddir = os.path.join(root, dir_tpl.replace("{date}", d))
                    shutil.rmtree(ddir, ignore_errors=True)
                print("[信息] 已按配置删除全部单版 PDF（keep_singles=false）")
            else:
                print("[信息] 因 PDF 合并未成功，暂保留单版 PDF 目录")
    else:
        # each 模式：定位最后一个产物作为打开目标
        candidates = []
        for d in ok_days:
            date_disp = "%s-%s-%s" % (d[:4], d[4:6], d[6:])
            if fmt in ("pdf", "both"):
                candidates.append(os.path.join(
                    root, str(cfg.get("merged_filename", "人民日报-{date}-完整版"))
                    .replace("{date}", date_disp) + ".pdf"))
            if fmt in ("text", "both"):
                candidates.append(os.path.join(
                    root, str(cfg.get("text_filename", "人民日报-{date}-文字版"))
                    .replace("{date}", date_disp) + "." + text_ext))
        for c in candidates:
            if os.path.exists(c):
                final_result = c

    print("\n========== 批量汇总 ==========")
    print("  成功 %d 天 | 无报跳过 %d 天 | 失败 %d 天"
          % (len(ok_days), len(skip_days), len(fail_days)))
    if skip_days:
        print("  跳过日期: %s" % ", ".join(skip_days))
    if fail_days:
        print("  失败日期: %s" % ", ".join(fail_days))
    if final_result and cfg.get("open_folder_after", True):
        try:
            subprocess.Popen('explorer /select,"%s"' % final_result)
        except Exception:
            pass
    log("批量完成 成功=%d 跳过=%d 失败=%d 格式=%s 合并=%s"
        % (len(ok_days), len(skip_days), len(fail_days), fmt, merge_mode))
    if not ok_days:
        print("[错误] 批量下载没有任何日期成功，请检查网络、日期范围或上方报错。")
        return 1
    print("[完成] 批量下载完成！")
    notify(cfg, APP_NAME, "人民日报批量下载完成：成功 %d 天" % len(ok_days))
    return 0


# ------------------------- 通知 / 调度 -------------------------

def notify(cfg, title, msg):
    if cfg.get("beep_on_done"):
        try:
            import winsound
            winsound.MessageBeep()
        except Exception:
            print("\a", end="", flush=True)
    if cfg.get("msg_on_done"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x40)
        except Exception:
            pass


# ------------------------- 单日下载（独立函数） -------------------------

def single_day_main(cfg, date_arg="", fmt_arg=""):
    """单日下载主逻辑（从 main 中提取，供命令行和交互菜单共用）。
    date_arg: 8 位日期字符串，空 = 默认/今日
    fmt_arg: text/pdf/both，空 = 默认格式
    返回 0 成功，1 失败
    """
    if not date_arg:
        date_arg = str(cfg.get("default_date", "")).strip() or \
            datetime.date.today().strftime("%Y%m%d")
    if not re.fullmatch(r"\d{8}", date_arg):
        print("[错误] 日期格式不正确，应为 8 位数字，例如 20260902")
        return 1
    try:
        datetime.datetime.strptime(date_arg, "%Y%m%d")
    except ValueError:
        print("[错误] 日期不存在：%s（月份或日期越界，请检查）" % date_arg)
        return 1

    fmt = (fmt_arg or str(cfg.get("default_format", "pdf"))).lower()
    if fmt not in ("text", "pdf", "both"):
        print("[错误] 格式参数应为 text / pdf / both")
        return 1

    date_disp = "%s-%s-%s" % (date_arg[:4], date_arg[4:6], date_arg[6:])
    log("开始任务 日期=%s 格式=%s" % (date_disp, fmt))
    print("=" * 60)
    print("  %s   日期: %s   格式: %s" % (APP_NAME, date_disp, fmt.upper()))
    print("=" * 60)

    dl = Downloader(cfg)
    today_str = datetime.date.today().strftime("%Y%m%d")
    if date_arg > today_str:
        td = "%s-%s-%s" % (today_str[:4], today_str[4:6], today_str[6:])
        print("[错误] %s 是未来日期，人民日报尚未出版（今天 %s）。" % (date_disp, td))
        print("       请检查输入日期，或修改 config.json 的 default_date。")
        return 1
    nodes, net_ok = get_nodes(dl, date_arg[:6], date_arg[6:])
    if not nodes:
        if not net_ok:
            msg = "%s 版面列表读取失败，疑似网络/代理问题（详见上方 [网络] 提示）" % date_disp
        else:
            msg = ("%s 未找到任何版面（该日期可能未出版/休刊，或 edition_filter 把版面过滤为空）"
                   % date_disp)
        print("[错误] " + msg)
        log(msg, "error")
        if cfg.get("holiday_skip"):
            print("[信息] 已按配置 holiday_skip 忽略该日期")
            return 0
        return 1

    root = out_root(cfg)
    os.makedirs(root, exist_ok=True)
    result = None
    if fmt in ("pdf", "both"):
        merged, _ = run_single_day_pdf(dl, date_arg, date_disp, nodes, root,
                                       merge_mode="auto")
        result = merged or result
    if fmt in ("text", "both"):
        result = run_single_day_text(dl, date_arg, date_disp, nodes, root) or result

    if result and os.path.exists(result):
        if cfg.get("open_folder_after", True):
            try:
                subprocess.Popen('explorer /select,"%s"' % result)
            except Exception:
                pass
        log("任务完成 日期=%s 格式=%s 产物=%s" % (date_disp, fmt, result))
        print("\n[完成] 全部完成！文件位置已自动打开。")
        notify(cfg, APP_NAME, "人民日报 %s %s 下载完成" % (date_disp, fmt.upper()))
        return 0
    print("\n[错误] 本次未生成任何文件：下载或合并失败，请查看上方具体报错。")
    log("任务失败 日期=%s 格式=%s" % (date_disp, fmt), "error")
    return 1


# ------------------------- 交互式菜单 -------------------------

def _input(prompt=""):
    """安全的 input，处理 EOF/中断"""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def interactive_single_day(cfg):
    """交互式单日下载"""
    print("\n" + "-" * 50)
    print("  单日下载")
    print("-" * 50)
    date_input = _input("请输入日期（YYYYMMDD，回车=今日）: ")
    if date_input is None:
        return 0
    date_input = date_input.strip()
    if not date_input:
        date_input = datetime.date.today().strftime("%Y%m%d")

    fmt_input = _input("请选择格式 [T]文字 / [P]PDF / [B]两者（回车=PDF）: ")
    if fmt_input is None:
        return 0
    fmt_map = {"T": "text", "P": "pdf", "B": "both"}
    fmt = fmt_map.get(fmt_input.strip().upper(), "pdf")

    print()
    return single_day_main(cfg, date_input, fmt)


def interactive_batch(cfg):
    """交互式批量下载"""
    print("\n" + "-" * 50)
    print("  批量下载")
    print("-" * 50)
    print("日期范围格式：20260901-20260903,20260905")
    print("  20260801-  表示从该日期到今日")
    print("  单个日期如 20260903 也可")
    expr = _input("请输入批量日期范围（回车=今日）: ")
    if expr is None:
        return 0
    expr = expr.strip()
    if not expr:
        expr = datetime.date.today().strftime("%Y%m%d")

    mm = _input("合并模式 [E]每天单独合并 / [A]全部合并为一个（回车=E）: ")
    if mm is None:
        return 0
    merge_mode = "all" if mm.strip().upper() == "A" else "each"

    fmt_input = _input("请选择格式 [T]文字 / [P]PDF / [B]两者（回车=PDF）: ")
    if fmt_input is None:
        return 0
    fmt_map = {"T": "text", "P": "pdf", "B": "both"}
    fmt = fmt_map.get(fmt_input.strip().upper(), "pdf")

    print()
    return batch_main(cfg, expr, fmt, merge_mode)


def interactive_config(cfg):
    """交互式配置管理"""
    while True:
        print("\n" + "-" * 50)
        print("  配置管理")
        print("-" * 50)
        print("  当前配置：")
        print("    默认日期: %s" % (cfg.get("default_date") or "(今日)"))
        print("    默认格式: %s" % cfg.get("default_format", "pdf"))
        print("    下载路径: %s" % (cfg.get("download_path") or "(当前目录)"))
        print("    批量开关: %s" % ("开启" if cfg.get("batch_enable") else "关闭"))
        print("    批量合并: %s" % cfg.get("batch_merge_mode", "each"))
        print("    保留单版: %s" % ("是" if cfg.get("keep_singles", True) else "否"))
        print("    自动打开文件夹: %s" % ("是" if cfg.get("open_folder_after", True) else "否"))
        print("    文字输出格式: %s" % cfg.get("text_output_format", "TXT"))
        print("    下载限速(kbps): %s" % (cfg.get("rate_limit_kbps", 0) or "不限"))
        print()
        print("  1. 修改默认格式")
        print("  2. 修改下载路径")
        print("  3. 切换批量开关")
        print("  4. 修改批量合并模式")
        print("  5. 切换保留单版")
        print("  6. 切换自动打开文件夹")
        print("  7. 修改文字输出格式")
        print("  8. 修改下载限速")
        print("  9. 恢复默认配置")
        print("  0. 返回主菜单")
        print("-" * 50)
        choice = _input("请选择: ")
        if choice is None:
            return
        choice = choice.strip()

        if choice == "1":
            v = _input("默认格式 [text/pdf/both]（当前 %s）: " % cfg.get("default_format"))
            if v and v.strip().lower() in ("text", "pdf", "both"):
                cfg["default_format"] = v.strip().lower()
                save_config(cfg)
                print("[配置] 已更新默认格式为 %s" % cfg["default_format"])
        elif choice == "2":
            v = _input("下载路径（空=当前目录，当前 %s）: " % (cfg.get("download_path") or "空"))
            if v is not None:
                cfg["download_path"] = v.strip()
                save_config(cfg)
                print("[配置] 已更新下载路径为 %s" % (cfg["download_path"] or "(当前目录)"))
        elif choice == "3":
            cfg["batch_enable"] = not cfg.get("batch_enable", False)
            save_config(cfg)
            print("[配置] 批量开关已切换为 %s" % ("开启" if cfg["batch_enable"] else "关闭"))
        elif choice == "4":
            v = _input("批量合并模式 [each/all]（当前 %s）: " % cfg.get("batch_merge_mode", "each"))
            if v and v.strip().lower() in ("each", "all"):
                cfg["batch_merge_mode"] = v.strip().lower()
                save_config(cfg)
                print("[配置] 已更新批量合并模式为 %s" % cfg["batch_merge_mode"])
        elif choice == "5":
            cfg["keep_singles"] = not cfg.get("keep_singles", True)
            save_config(cfg)
            print("[配置] 保留单版已切换为 %s" % ("是" if cfg["keep_singles"] else "否"))
        elif choice == "6":
            cfg["open_folder_after"] = not cfg.get("open_folder_after", True)
            save_config(cfg)
            print("[配置] 自动打开文件夹已切换为 %s" % ("是" if cfg["open_folder_after"] else "否"))
        elif choice == "7":
            v = _input("文字输出格式 [TXT/DOC/DOCX/MD]（当前 %s）: " % cfg.get("text_output_format", "TXT"))
            if v and v.strip().upper() in ("TXT", "DOC", "DOCX", "MD"):
                cfg["text_output_format"] = v.strip().upper()
                save_config(cfg)
                print("[配置] 已更新文字输出格式为 %s" % cfg["text_output_format"])
        elif choice == "8":
            v = _input("下载限速 kbps（0=不限，当前 %s）: " % cfg.get("rate_limit_kbps", 0))
            if v and v.strip().isdigit():
                cfg["rate_limit_kbps"] = int(v.strip())
                save_config(cfg)
                print("[配置] 已更新下载限速为 %s kbps" % cfg["rate_limit_kbps"])
        elif choice == "9":
            cfg = {}
            cfg, _ = validate_config(cfg)
            save_config(cfg)
            print("[配置] 已恢复默认配置")
        elif choice == "0":
            return
        else:
            print("[错误] 无效选择")


def interactive_menu(cfg):
    """主交互菜单：无参数运行时进入（exe 双击 / 命令行无参数）"""
    # 确保 pypdf 可用（源码运行时自动安装；exe 已内置）
    try:
        ensure_pypdf(interactive=True)
    except Exception as e:
        print("[警告] pypdf 检查失败: %s（PDF 合并可能不可用）" % e)

    while True:
        print("\n" + "=" * 60)
        print("         %s" % APP_NAME)
        print("=" * 60)
        print("  1. 单日下载")
        print("  2. 批量下载")
        print("  3. 配置管理")
        print("  4. 退出")
        print("=" * 60)
        choice = _input("请选择 [1-4]: ")
        if choice is None:
            print("\n再见！")
            return 0
        choice = choice.strip()

        if choice == "1":
            rc = interactive_single_day(cfg)
            _input("\n按回车键返回主菜单...")
        elif choice == "2":
            rc = interactive_batch(cfg)
            _input("\n按回车键返回主菜单...")
        elif choice == "3":
            interactive_config(cfg)
        elif choice == "4":
            print("再见！")
            return 0
        else:
            print("[错误] 无效选择，请输入 1-4")


# ------------------------- 主流程 -------------------------

def main():
    global _log_enabled, _log_level
    cfg = load_config()
    cfg, cfg_warns = validate_config(cfg)
    for w in cfg_warns:
        print("[配置警告] %s" % w)
    if cfg_warns:
        save_config(cfg)
    _log_level = str(cfg.get("log_level", "normal"))
    _log_enabled = bool(cfg.get("log_file"))

    args = sys.argv[1:]

    if "--init" in args:
        save_config(cfg)
        print("已生成/更新 config.json")
        return 0
    # 批量模式
    if "--batch" in args:
        i = args.index("--batch")
        expr = args[i + 1] if i + 1 < len(args) else ""
        fmt = ""
        merge_mode = str(cfg.get("batch_merge_mode", "each"))
        j = 0
        while j < len(args):
            if args[j] == "--merge-mode" and j + 1 < len(args):
                merge_mode = args[j + 1].lower()
            elif re.fullmatch(r"(text|pdf|both)", args[j].lower()):
                fmt = args[j].lower()
            j += 1
        fmt = fmt or str(cfg.get("default_format", "pdf"))
        if fmt not in ("text", "pdf", "both"):
            print("[错误] 格式参数应为 text / pdf / both")
            return 1
        if merge_mode not in ("each", "all"):
            print("[错误] --merge-mode 应为 each / all")
            return 1
        return batch_main(cfg, expr, fmt, merge_mode)

    # 无参数：进入交互菜单（exe 双击 / 命令行无参数）
    if not args:
        return interactive_menu(cfg)

    # 单日模式（有参数）
    if args and re.fullmatch(r"\d+", args[0]):
        if not re.fullmatch(r"\d{8}", args[0]):
            print("[错误] 日期应为 8 位数字 YYYYMMDD（例如 20260902），当前输入: %s" % args[0])
            return 1
        date_arg = args[0]
        fmt_arg = args[1] if len(args) > 1 else ""
    elif args and args[0].lower() in ("text", "pdf", "both"):
        date_arg = ""
        fmt_arg = args[0]
    else:
        date_arg = ""
        fmt_arg = args[0] if args else ""

    return single_day_main(cfg, date_arg, fmt_arg)


if __name__ == "__main__":
    sys.exit(main())
