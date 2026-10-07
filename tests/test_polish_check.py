"""haohao_scan and polish_check: the combined pre-delivery check."""

from __future__ import annotations

import haohao_scan
import polish_check
from haohao_markers import haohao_dir

BAD = "## 一、开头\n\n这不是问题，而是机会。值得深思。有逗号,在这。\n"
CLEAN = "价格是 1,000 元，版本 3.14，代码 `a,b` 和网址 https://x.y/a,b 都不算。\n"


def _haohao_installed() -> bool:
    return (haohao_dir() / "references" / "quick-scan-regex.md").exists()


def test_scan_flags_all_four_rules():
    if not _haohao_installed():
        return
    r = haohao_scan.scan(BAD)
    counts = {x["rule"]: x["count"] for x in r["rules"]}
    assert counts["heading_numbering"] == 1
    assert counts["meta_discourse"] == 1
    assert counts["halfwidth_punct"] >= 1
    assert counts["b2_variants"] == 1
    assert r["passed"] is False  # Chinese half-width punctuation remains a formatting check
    assert counts["heading_numbering"] == counts["meta_discourse"] == 1
    assert all(x["passed"] for x in r["rules"] if not x["gate"])


def test_scan_exempts_numbers_code_and_urls():
    if not _haohao_installed():
        return
    r = haohao_scan.scan(CLEAN)
    assert all(x["count"] == 0 for x in r["rules"])
    assert r["passed"] is True


def test_polish_check_reports_invisible_chars():
    if not _haohao_installed():
        return
    r = polish_check.check("正文里藏了一个​零宽字符。")
    assert r["invisible_chars"] >= 1
    assert r["passed"] is False


def test_polish_check_accepts_academic_subjects_and_numbered_structure():
    r = polish_check.check("## 1. 方法\n\n本文分析样本范围，实验结果表明结论仍受数据边界约束。", paper=True)
    assert r["passed"] and r["structure"]["passed"]
    assert r["style"]["status"] == "insufficient_length" and r["style"]["score"] is None
