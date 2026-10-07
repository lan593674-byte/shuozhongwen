"""haohao_scan paper mode and reference-list exemption; doc_text reads .docx."""

from __future__ import annotations

import zipfile

import haohao_scan
from doc_text import read_any


def test_docx_text_includes_tables(tmp_path):
    doc = tmp_path / "a.docx"
    body = ('<w:document xmlns:w="w"><w:body><w:p><w:r><w:t>票房 600 亿元</w:t></w:r></w:p>'
            '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>R²</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>0.6372</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
            '</w:body></w:document>')
    with zipfile.ZipFile(doc, "w") as z:
        z.writestr("word/document.xml", body)
    text = read_any(doc)
    assert "600 亿元" in text and "R² | 0.6372" in text


def test_scan_exempts_reference_list_and_paper_headings():
    text = "## 1. 引言\n正文用全角标点。\n参考文献\n[1] 郝烨. 基于机器学习的电影票房预测研究[J]. 现代电影技术, 2023.\n"
    r = {x["rule"]: x for x in haohao_scan.scan(text)["rules"]}
    assert r["halfwidth_punct"]["count"] == 0
    assert r["heading_numbering"]["count"] == 1
    p = {x["rule"]: x for x in haohao_scan.scan(text, paper=True)["rules"]}
    assert p["heading_numbering"]["passed"] and p["heading_numbering"].get("skipped")
