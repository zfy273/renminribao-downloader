# -*- coding: utf-8 -*-
"""纯标准库 PDF 合并器。

为什么要自己写：原项目合并 PDF 依赖 pypdf，源码运行时缺库会触发
`pip install`（无网络即失败，且要等 300 秒超时）。人民日报版面 PDF 结构
很规整（经典 xref 表、未加密、未 linearize），用标准库即可无损搬运对象、
重编号间接引用后拼装成一个新文档，零依赖、离线可用。

支持：
  * 经典 xref 表，含增量更新（/Prev 链）
  * 直接对象 + 流对象（按 /Length 精确定位，不误伤流里的 "endobj" 字节）
  * 每个源文档保留自身 Pages 子树（/Resources、/MediaBox 等继承属性不丢）

不支持（会抛 Unsupported，交给 pypdf 兜底）：
  * PDF 1.5+ 的交叉引用流（/Type /XRef）、对象流（/ObjStm）、混合 /XRefStm
  * 加密文档
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

XREF_ENTRY_RE = re.compile(rb"(\d{1,10})\s+(\d{1,5})\s+([nf])")
OBJ_HEADER_RE = re.compile(rb"\s*(\d{1,10})\s+(\d{1,5})\s+obj\b")
REF_RE = re.compile(rb"(?<![\d])(\d{1,10})(\s+)(\d{1,5})(\s+)R(?![A-Za-z])")
INT_RE = re.compile(rb"(\d+)")


class PdfError(Exception):
    """PDF 结构异常。"""


class Unsupported(PdfError):
    """当前实现不支持的 PDF 结构（可回退 pypdf）。"""


class SourceDoc:
    """一个待合并的源文档。"""

    __slots__ = ("path", "data", "entries", "trailer", "base")

    def __init__(self, path: str, data: bytes) -> None:
        self.path = path
        self.data = data
        self.entries: Dict[int, int] = {}      # objnum -> 文件内偏移（仅 n 条目）
        self.trailer: Dict[str, object] = {}
        self.base = 0                          # 重编号时的基数


# --------------------------------------------------------------------------
# 底层解析
# --------------------------------------------------------------------------

def _read_dict_at(data: bytes, pos: int) -> Tuple[bytes, int]:
    """从 pos 处的 `<<` 读取一个字典（支持嵌套），返回 (字典字节, 结束位置)。"""
    if data[pos:pos + 2] != b"<<":
        raise PdfError("期望字典起始位置 <<")
    depth = 0
    i = pos
    n = len(data)
    while i < n:
        two = data[i:i + 2]
        if two == b"<<":
            depth += 1
            i += 2
            continue
        if two == b">>":
            depth -= 1
            i += 2
            if depth == 0:
                return data[pos:i], i
            continue
        i += 1
    raise PdfError("字典未闭合")


def _int_of(value: bytes, default: int = 0) -> int:
    m = INT_RE.search(value)
    return int(m.group(1)) if m else default


def _parse_xref_at(data: bytes, offset: int, entries: Dict[int, int],
                   seen: set) -> Dict[str, object]:
    """解析 offset 处的经典 xref 段，返回该段 trailer 字典内容。"""
    if offset in seen:
        raise PdfError("xref /Prev 出现循环引用")
    seen.add(offset)
    if data[offset:offset + 4] != b"xref":
        raise Unsupported("找不到经典 xref 表（可能是压缩交叉引用流）")

    i = offset + 4
    n = len(data)
    while True:
        # 跳过行尾
        while i < n and data[i] in b"\r\n \t":
            i += 1
        m = re.match(rb"(\d+)\s+(\d+)", data[i:i + 40])
        if not m:
            break
        start, count = int(m.group(1)), int(m.group(2))
        i += m.end()
        for index in range(count):
            while i < n and data[i] in b"\r\n \t":
                i += 1
            em = XREF_ENTRY_RE.match(data, i)
            if not em:
                raise PdfError("xref 条目格式异常")
            offset_in_file, _gen, kind = int(em.group(1)), int(em.group(2)), em.group(3)
            i = em.end()
            if kind == b"n":
                # 先解析到的是最新的增量更新段，旧段不覆盖
                entries.setdefault(start + index, offset_in_file)
    while i < n and data[i] in b"\r\n \t":
        i += 1
    if data[i:i + 7] != b"trailer":
        raise PdfError("xref 后缺少 trailer")
    trailer_raw, _ = _read_dict_at(data, data.index(b"<<", i))

    trailer: Dict[str, object] = {"raw": trailer_raw}
    m = re.search(rb"/Prev\s+(\d+)", trailer_raw)
    if m:
        trailer["prev"] = int(m.group(1))
    m = re.search(rb"/Root\s+(\d+)\s+(\d+)\s+R", trailer_raw)
    if m:
        trailer["root"] = int(m.group(1))
    m = re.search(rb"/Info\s+(\d+)\s+(\d+)\s+R", trailer_raw)
    if m:
        trailer["info"] = int(m.group(1))
    if b"/XRefStm" in trailer_raw:
        raise Unsupported("混合型 PDF（/XRefStm）")
    if b"/Encrypt" in trailer_raw:
        raise PdfError("PDF 已加密，无法合并")
    return trailer


def _load_doc(path: str) -> SourceDoc:
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.startswith(b"%PDF-"):
        raise PdfError("不是 PDF 文件: %s" % os.path.basename(path))
    tail = data[-2048:]
    m = None
    for m in re.finditer(rb"startxref\s+(\d+)", tail):
        pass
    if m is None:
        raise PdfError("缺少 startxref")
    start = int(m.group(1))

    doc = SourceDoc(path, data)
    seen: set = set()
    offset = start
    first = True
    while True:
        trailer = _parse_xref_at(data, offset, doc.entries, seen)
        if first:
            doc.trailer = trailer
            first = False
        prev = trailer.get("prev")
        if prev is None:
            break
        offset = int(prev)
    if "root" not in doc.trailer:
        raise PdfError("trailer 缺少 /Root")
    return doc


def _object_at(doc: SourceDoc, num: int) -> Tuple[int, int, bytes]:
    """返回 (对象号, 代数, 从 obj 关键字到 endobj 之前的原始字节)。"""
    offset = doc.entries.get(num)
    if offset is None:
        raise PdfError("对象 %d 不在 xref 中" % num)
    data = doc.data
    m = OBJ_HEADER_RE.match(data, offset)
    if not m or int(m.group(1)) != num:
        raise PdfError("对象 %d 偏移与 xref 不一致" % num)
    body_start = m.end()
    if data[body_start:body_start + 2] == b"\r\n":
        body_start += 2
    elif data[body_start:body_start + 1] in (b"\n", b"\r"):
        body_start += 1

    # 找 stream 关键字（必须紧跟在字典之后）
    stream_at = -1
    probe = body_start
    while True:
        idx = data.find(b"stream", probe)
        if idx < 0:
            break
        before = data[max(body_start, idx - 32):idx]
        if before.rstrip().endswith(b">>"):
            stream_at = idx
            break
        probe = idx + 6
    endobj_at = data.find(b"endobj", body_start)

    if stream_at < 0 or (0 <= endobj_at < stream_at):
        if endobj_at < 0:
            raise PdfError("对象 %d 缺少 endobj" % num)
        return num, int(m.group(2)), data[body_start:endobj_at].rstrip(b"\r\n")

    dict_raw = data[body_start:stream_at].rstrip(b"\r\n")
    length = _stream_length(doc, dict_raw)
    pos = stream_at + 6
    if data[pos:pos + 2] == b"\r\n":
        pos += 2
    elif data[pos:pos + 1] in (b"\n", b"\r"):
        pos += 1
    end = pos + length
    if end > len(data):
        raise PdfError("对象 %d 的流长度越界" % num)
    tail_at = data.find(b"endstream", end)
    if tail_at < 0:
        raise PdfError("对象 %d 缺少 endstream" % num)
    tail_at += len(b"endstream")
    # 保留原始换行风格
    return num, int(m.group(2)), data[body_start:tail_at]


def _stream_length(doc: SourceDoc, dict_raw: bytes) -> int:
    m = re.search(rb"/Length\s+(\d+)\s+(\d+)\s+R", dict_raw)
    if m:
        ref = int(m.group(1))
        _, _, body = _object_at(doc, ref)
        return _int_of(body, 0)
    m = re.search(rb"/Length\s+(\d+)", dict_raw)
    if not m:
        raise PdfError("流对象缺少 /Length")
    return int(m.group(1))


# --------------------------------------------------------------------------
# 拼装
# --------------------------------------------------------------------------

def _rewrite_refs(chunk: bytes, base: int) -> bytes:
    if base == 0:
        return chunk

    def repl(m: "re.Match[bytes]") -> bytes:
        num = int(m.group(1))
        return b"%d%s%s%sR" % (num + base, m.group(2), m.group(3), m.group(4))

    return REF_RE.sub(repl, chunk)


def _dict_of(doc: SourceDoc, num: int) -> bytes:
    _, _, body = _object_at(doc, num)
    if b"stream" in body[:64]:
        raise PdfError("对象 %d 不是字典" % num)
    return body


def _catalog_pages(doc: SourceDoc) -> int:
    root_num = int(doc.trailer["root"])
    catalog = _dict_of(doc, root_num)
    m = re.search(rb"/Pages\s+(\d+)\s+(\d+)\s+R", catalog)
    if not m:
        raise PdfError("Catalog 缺少 /Pages")
    return int(m.group(1))


def _page_count(doc: SourceDoc, pages_num: int) -> int:
    body = _dict_of(doc, pages_num)
    m = re.search(rb"/Count\s+(\d+)", body)
    if m:
        return int(m.group(1))
    kids = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
    return len(re.findall(rb"\d+\s+\d+\s+R", kids.group(1))) if kids else 0


def _split_body(body: bytes) -> Tuple[bytes, bytes]:
    """把对象正文切成 (字典部分, 流部分)；非流对象返回 (body, b'')。

    只有 `stream` 关键字紧跟字典 `>>` 时才认为是流，避免误伤字典里的普通字符串。
    """
    probe = 0
    while True:
        idx = body.find(b"stream", probe)
        if idx < 0:
            return body, b""
        if body[:idx].rstrip().endswith(b">>"):
            return body[:idx], body[idx:]
        probe = idx + 6


def merge(paths: List[str], out_path: str) -> Dict[str, object]:
    """合并 PDF，返回 {"pages": n, "objects": n, "engine": "builtin"}。"""
    if not paths:
        raise PdfError("没有可合并的 PDF")
    docs = [_load_doc(p) for p in paths]

    # 先给每个对象分配新编号
    next_num = 1
    for doc in docs:
        doc.base = next_num - 1
        for num in sorted(doc.entries):
            if num + doc.base >= next_num:
                next_num = num + doc.base + 1
    pages_num = next_num
    catalog_num = pages_num + 1
    info_num = catalog_num + 1

    children: List[int] = []
    total_pages = 0
    info_src: Optional[Tuple[SourceDoc, int]] = None

    blob = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: Dict[int, int] = {}

    for doc in docs:
        pages_root = _catalog_pages(doc)
        children.append(pages_root + doc.base)
        total_pages += _page_count(doc, pages_root)
        if info_src is None and "info" in doc.trailer:
            info_src = (doc, int(doc.trailer["info"]))

        for num in sorted(doc.entries):
            new_num = num + doc.base
            _, _, body = _object_at(doc, num)
            head, stream_part = _split_body(body)
            head = _rewrite_refs(head, doc.base)
            if num == pages_root:
                head = _inject_parent(head, pages_num)
            offsets[new_num] = len(blob)
            blob += b"%d 0 obj\n" % new_num
            blob += head
            blob += stream_part
            blob += b"\nendobj\n"

    kids = b" ".join(b"%d 0 R" % n for n in children)
    offsets[pages_num] = len(blob)
    blob += b"%d 0 obj\n<< /Type /Pages /Kids [ %s ] /Count %d >>\nendobj\n" % (
        pages_num, kids, total_pages)
    offsets[catalog_num] = len(blob)
    blob += b"%d 0 obj\n<< /Type /Catalog /Pages %d 0 R >>\nendobj\n" % (
        catalog_num, pages_num)

    trailer_info = b""
    if info_src is not None:
        doc, num = info_src
        _, _, body = _object_at(doc, num)
        offsets[info_num] = len(blob)
        blob += b"%d 0 obj\n%s\nendobj\n" % (info_num, _rewrite_refs(body, doc.base))
        trailer_info = b" /Info %d 0 R" % info_num

    size = max(offsets) + 1
    xref_at = len(blob)
    blob += b"xref\n0 %d\n" % size
    blob += b"0000000000 65535 f\r\n"
    for num in range(1, size):
        off = offsets.get(num)
        if off is None:
            blob += b"0000000000 65535 f\r\n"
        else:
            blob += b"%010d 00000 n\r\n" % off
    blob += b"trailer\n<< /Size %d /Root %d 0 R%s >>\nstartxref\n%d\n%%%%EOF\n" % (
        size, catalog_num, trailer_info, xref_at)

    tmp = out_path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(blob)
    os.replace(tmp, out_path)
    return {"pages": total_pages, "objects": len(offsets), "engine": "builtin"}


def _inject_parent(dict_raw: bytes, parent_num: int) -> bytes:
    if b"/Parent" in dict_raw[:200]:
        return re.sub(rb"/Parent\s+\d+\s+\d+\s+R", b"/Parent %d 0 R" % parent_num, dict_raw, 1)
    idx = dict_raw.find(b"<<")
    if idx < 0:
        return dict_raw
    return dict_raw[:idx + 2] + b" /Parent %d 0 R" % parent_num + dict_raw[idx + 2:]


# --------------------------------------------------------------------------
# 自检（测试与故障排查用）
# --------------------------------------------------------------------------

def probe(path: str) -> Dict[str, object]:
    """重新解析一个 PDF，返回页数与对象数；解析失败抛异常。"""
    doc = _load_doc(path)
    pages_root = _catalog_pages(doc)
    bad = 0
    for num in doc.entries:
        try:
            _object_at(doc, num)
        except PdfError:
            bad += 1
    return {
        "pages": _page_count(doc, pages_root),
        "objects": len(doc.entries),
        "broken": bad,
    }
