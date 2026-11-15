# -*- coding: utf-8 -*-
"""离线单元测试：不联网、不依赖第三方库。

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rmrb_core as core      # noqa: E402
import rmrb_pdf               # noqa: E402


# --------------------------------------------------------------------------
# 最小 PDF 构造器（用于合并测试）
# --------------------------------------------------------------------------

def build_pdf(objects, root=1):
    """objects: [(num, body_bytes)]，返回完整的经典 xref PDF 字节。"""
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number, body in objects:
        offsets[number] = len(out)
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    size = max(offsets) + 1
    out += b"xref\n0 %d\n0000000000 65535 f\r\n" % size
    for number in range(1, size):
        offset = offsets.get(number, 0)
        out += b"%010d 00000 %s\r\n" % (offset, b"n" if offset else b"f")
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        size, root, xref_at)
    return bytes(out)


def one_page_pdf(text: bytes) -> bytes:
    content = b"BT /F1 12 Tf 20 100 Td (" + text + b") Tj ET"
    objects = [
        (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        (2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
        (3, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"),
        (4, b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)),
        (5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    return build_pdf(objects)


class PdfMergeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rmrb_pdf_")

    def _write(self, name, data):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_merge_two_single_page_pdfs(self):
        first = self._write("a.pdf", one_page_pdf(b"AAA"))
        second = self._write("b.pdf", one_page_pdf(b"BBB"))
        self.assertEqual(rmrb_pdf.probe(first)["pages"], 1)

        target = os.path.join(self.dir, "merged.pdf")
        result = rmrb_pdf.merge([first, second], target)

        self.assertEqual(result["pages"], 2)
        self.assertEqual(result["engine"], "builtin")
        info = rmrb_pdf.probe(target)
        self.assertEqual(info["pages"], 2)
        self.assertEqual(info["broken"], 0)
        with open(target, "rb") as fh:
            data = fh.read()
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        self.assertEqual(data.count(b"/Type /Page "), 2)
        self.assertIn(b"AAA", data)
        self.assertIn(b"BBB", data)
        # 每个源文档的 Pages 子树都挂到了新的根节点下
        self.assertEqual(data.count(b"/Kids"), 3)

    def test_merge_reports_object_count(self):
        first = self._write("a.pdf", one_page_pdf(b"AAA"))
        target = os.path.join(self.dir, "one.pdf")
        result = rmrb_pdf.merge([first], target)
        self.assertEqual(result["pages"], 1)
        self.assertGreaterEqual(result["objects"], 5)

    def test_merge_empty_list_fails(self):
        with self.assertRaises(rmrb_pdf.PdfError):
            rmrb_pdf.merge([], os.path.join(self.dir, "x.pdf"))

    def test_xref_stream_is_unsupported(self):
        broken = self._write("broken.pdf",
                             b"%PDF-1.5\n1 0 obj << /Type /XRef /Size 2 >>\nendobj\n"
                             b"startxref\n9\n%%EOF\n")
        with self.assertRaises(rmrb_pdf.Unsupported):
            rmrb_pdf.merge([broken], os.path.join(self.dir, "out.pdf"))

    def test_non_pdf_is_rejected(self):
        bogus = self._write("bogus.pdf", b"<html>not a pdf</html>")
        with self.assertRaises(rmrb_pdf.PdfError):
            rmrb_pdf.merge([bogus], os.path.join(self.dir, "out.pdf"))

    def test_merge_pdfs_api_autofalls_back(self):
        first = self._write("a.pdf", one_page_pdf(b"AAA"))
        second = self._write("b.pdf", one_page_pdf(b"BBB"))
        target = os.path.join(self.dir, "api.pdf")
        result = core.merge_pdfs([first, second], target, "builtin")
        self.assertEqual(result["pages"], 2)
        self.assertEqual(rmrb_pdf.probe(target)["pages"], 2)


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------

class ParseTest(unittest.TestCase):
    def test_article_title_is_unescaped(self):
        html = ("<html><head><title>备用</title></head><body>"
                "<h1><p>政策 &amp; 数据 &lt;解读&gt;</p></h1>"
                "<!--enpcontent--><p>第一段</p><p>&nbsp;</p><p>第二段</p><!--/enpcontent-->"
                "</body></html>")
        title, paras = core.parse_article(html)
        self.assertEqual(title, "政策 & 数据 <解读>")
        self.assertEqual(paras, ["第一段", "第二段"])

    def test_article_title_falls_back_to_title_tag(self):
        html = "<html><head><title>备用标题</title></head><body></body></html>"
        title, paras = core.parse_article(html)
        self.assertEqual(title, "备用标题")
        self.assertEqual(paras, [])

    def test_paragraphs_outside_markers_are_ignored(self):
        html = ("<h1><p>T</p></h1><p>包裹外</p>"
                "<!--enpcontent--><p>包裹内</p><!--/enpcontent-->")
        _, paras = core.parse_article(html)
        self.assertEqual(paras, ["包裹内"])

    def test_article_links_are_sorted_and_unique(self):
        html = ("content/202609/03/content_30.html "
                "content/202609/03/content_9.html "
                "content/202609/03/content_30.html")
        self.assertEqual(core.get_article_links(html), ["9", "30"])


class BatchExprTest(unittest.TestCase):
    def test_range_and_dedup(self):
        dates = core.parse_batch_expr("20260901-20260903,20260902,20260905")
        self.assertEqual(dates, ["20260901", "20260902", "20260903", "20260905"])

    def test_open_ended_range_ends_today(self):
        today = datetime.date.today().strftime("%Y%m%d")
        dates = core.parse_batch_expr("20260801-")
        self.assertEqual(dates[0], "20260801")
        self.assertEqual(dates[-1], today)

    def test_dashed_date_is_normalised(self):
        self.assertEqual(core.parse_batch_expr("2026-09-03"), ["20260903"])

    def test_tilde_range(self):
        self.assertEqual(core.parse_batch_expr("2026-09-01~2026-09-02"),
                         ["20260901", "20260902"])

    def test_reversed_range_raises(self):
        with self.assertRaises(ValueError):
            core.parse_batch_expr("20260905-20260901")

    def test_invalid_date_raises(self):
        for expr in ("20260231", "2026093", "2026-13-01", "abc"):
            with self.assertRaises(ValueError):
                core.parse_batch_expr(expr)


# --------------------------------------------------------------------------
# 配置
# --------------------------------------------------------------------------

class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rmrb_cfg_")
        self.path = os.path.join(self.dir, "config.json")

    def test_roundtrip_is_atomic_and_keeps_content(self):
        cfg = dict(core.DEFAULT_CONFIG)
        cfg["timeout"] = 45
        cfg["download_path"] = "out"
        core.save_config(cfg, self.path)
        self.assertTrue(os.path.exists(self.path))
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        loaded = core.load_config(self.path)
        self.assertEqual(loaded["timeout"], 45)
        self.assertEqual(loaded["download_path"], "out")

    def test_corrupt_config_backs_up_and_uses_defaults(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{ this is not json")
        loaded = core.load_config(self.path)
        self.assertEqual(loaded["timeout"], core.DEFAULT_CONFIG["timeout"])
        self.assertIn("_load_error", loaded)
        self.assertTrue(os.path.exists(self.path + ".bad"))

    def test_numbers_are_clamped(self):
        cfg, warns = core.validate_config({"timeout": 0, "retry": 99, "concurrent": 0,
                                           "request_interval": -1})
        self.assertEqual(cfg["timeout"], 30)
        self.assertEqual(cfg["retry"], 3)
        self.assertEqual(cfg["concurrent"], 1)
        self.assertEqual(cfg["request_interval"], 0.2)
        self.assertTrue(warns)

    def test_download_dir_is_sanitised(self):
        for danger in ("", "  ", "../evil", "C:/Windows/Temp", "/tmp/x"):
            cfg, _ = core.validate_config({"download_dir": danger})
            self.assertEqual(cfg["download_dir"], "pdfs_{date}", danger)

    def test_output_names_are_sanitised(self):
        cfg, _ = core.validate_config({"merged_filename": "../../x",
                                       "text_filename": ""})
        self.assertEqual(cfg["merged_filename"], core.DEFAULT_CONFIG["merged_filename"])
        self.assertEqual(cfg["text_filename"], core.DEFAULT_CONFIG["text_filename"])

    def test_edition_filter_is_cleaned(self):
        cfg, _ = core.validate_config({"edition_filter": ["2", 3, "x", -1]})
        self.assertEqual(cfg["edition_filter"], [2, 3])

    def test_enums_fall_back(self):
        cfg, warns = core.validate_config({"text_output_format": "RTF",
                                           "pdf_engine": "magic",
                                           "log_level": "loud",
                                           "batch_merge_mode": "nope"})
        self.assertEqual(cfg["text_output_format"], "TXT")
        self.assertEqual(cfg["pdf_engine"], "auto")
        self.assertEqual(cfg["log_level"], "normal")
        self.assertEqual(cfg["batch_merge_mode"], "each")
        self.assertEqual(len(warns), 4)

    def test_out_root_relative_to_program_dir(self):
        self.assertEqual(core.out_root({"download_path": ""}), core.HERE)
        self.assertEqual(core.out_root({"download_path": "out"}),
                         os.path.join(core.HERE, "out"))
        absolute = os.path.join(self.dir, "abs")
        self.assertEqual(core.out_root({"download_path": absolute}), absolute)


class SafeDeleteTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rmrb_root_")
        self.sub = os.path.join(self.root, "pdfs_20260903")
        os.makedirs(self.sub)
        with open(os.path.join(self.sub, "a.pdf"), "w") as fh:
            fh.write("x")

    def test_refuses_root_itself(self):
        self.assertTrue(core.safe_rmtree(self.root, self.root))
        self.assertTrue(os.path.isdir(self.root))

    def test_refuses_outside_target(self):
        outside = tempfile.mkdtemp(prefix="rmrb_out_")
        self.assertTrue(core.safe_rmtree(outside, self.root))
        self.assertTrue(os.path.isdir(outside))

    def test_deletes_real_subdir(self):
        self.assertEqual(core.safe_rmtree(self.sub, self.root), "")
        self.assertFalse(os.path.exists(self.sub))


# --------------------------------------------------------------------------
# 文字输出
# --------------------------------------------------------------------------

SAMPLE_LINES = [
    "人民日报  2026-09-03",
    "=" * 46,
    "",
    "【要闻】",
    "-" * 46,
    "",
    "文章 A & B",
    "",
    "第一段 <正文>",
    "第二段",
]


class TextOutputTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rmrb_txt_")

    def test_txt(self):
        path = os.path.join(self.dir, "a.txt")
        core.write_txt(SAMPLE_LINES, path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("【要闻】", text)
        self.assertIn("文章 A & B", text)

    def test_markdown_structure(self):
        path = os.path.join(self.dir, "a.md")
        core.write_md(SAMPLE_LINES, path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("# 人民日报  2026-09-03", text)
        self.assertIn("## 要闻", text)
        self.assertNotIn("====", text)
        self.assertNotIn("----", text)

    def test_docx_is_valid_ooxml(self):
        path = os.path.join(self.dir, "a.docx")
        core.write_docx(SAMPLE_LINES, path)
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            self.assertEqual(names, {"[Content_Types].xml", "_rels/.rels",
                                     "word/document.xml"})
            document = zf.read("word/document.xml").decode("utf-8")
        root = ET.fromstring(document)
        self.assertTrue(root.tag.endswith("document"))
        # 特殊字符必须转义，否则 Word 打不开
        self.assertIn("&amp;", document)
        self.assertIn("&lt;正文&gt;", document)

    def test_doc_html_escaped(self):
        path = os.path.join(self.dir, "a.doc")
        core.write_doc(SAMPLE_LINES, path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("&amp;", text)
        self.assertIn("<hr>", text)


# --------------------------------------------------------------------------
# 其它
# --------------------------------------------------------------------------

class TaskCommandTest(unittest.TestCase):
    def test_command_is_a_list_and_quotes_path(self):
        args, when = core.task_command({"auto_run_time": "07:30", "default_date": ""})
        self.assertIsInstance(args, list)
        self.assertEqual(args[0], "schtasks")
        self.assertIn("/st", args)
        self.assertEqual(when, "07:30")
        target = args[args.index("/tr") + 1]
        self.assertTrue(target.startswith('"'))
        self.assertNotIn("\\\"", target)

    def test_bad_time_falls_back(self):
        _, when = core.task_command({"auto_run_time": "99:99", "default_date": ""})
        self.assertEqual(when, "08:00")


class DescribeErrorTest(unittest.TestCase):
    def test_http_error_mapping(self):
        import urllib.error
        err = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        self.assertIn("访问过于频繁", core.describe_error(err))

    def test_timeout_mapping(self):
        self.assertIn("超时", core.describe_error(TimeoutError("timed out")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
