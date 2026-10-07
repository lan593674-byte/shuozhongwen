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
    assert r["heading_numbering"]["passed"] and not r["heading_numbering"]["gate"]
    p = {x["rule"]: x for x in haohao_scan.scan(text, paper=True)["rules"]}
    assert p["heading_numbering"]["passed"] and p["heading_numbering"].get("skipped")


def test_scan_preserves_quotes_formula_code_tables_and_reference_punctuation():
    text = ("## 1. 方法\n本文分析样本范围。\n\n逐字引语：“原文,不得改写”。\n\n"
            "公式 $\\text{原文,数值}$ 和代码 `中文,变量`。\n\n"
            "| 样本,编号 | 数据 |\n| --- | --- |\n| 原文,术语 | 0.6372 |\n\n"
            "> 保留的引用,不应改写。\n\n参考文献\n[1] 作者. 文献, 2020.\n")
    r = haohao_scan.scan(text, paper=True)
    rules = {x["rule"]: x for x in r["rules"]}
    assert r["passed"] and rules["halfwidth_punct"]["count"] == 0
    assert haohao_scan.scan("可编辑正文,标点仍须检查。")["passed"] is False


def test_latex_citation_and_reference_parameters_are_not_chinese_prose():
    text = r"""本文采用已有材料支持的论述\citet[见中文,原文]{中文键,EnglishKey}。
交叉引用为\crefrange{中文标签,起点}{中文标签,终点}，标签为\label{中文标签,编号}。
链接可用\hyperref[中文标签,编号]{中文,链接文字}。
\bibliography{中文文献,EnglishReferences}
\begin{thebibliography}{99}
\bibitem[作者,2020]{中文键} 作者. 中文标题,出版物,2020.
\end{thebibliography}
"""
    r = haohao_scan.scan(text, paper=True)
    rules = {x["rule"]: x for x in r["rules"]}
    assert r["passed"] and rules["halfwidth_punct"]["count"] == 0


def test_protected_multiline_spans_preserve_reported_line_numbers():
    text = "```python\nprint('中文,代码')\n```\n\n正文,这一处需要检查。"
    rule = {x["rule"]: x for x in haohao_scan.scan(text)["rules"]}["halfwidth_punct"]
    assert rule["count"] == 1 and rule["hits"][0]["line"] == 5
