#!/usr/bin/env python3
"""Read the text of a draft: .txt/.md as UTF-8, .docx as paragraphs (stdlib only).

Word tables come out one row per line with cells joined by " | ", so table
contents are read along with the prose.

Usage: doc_text.py 稿件.docx [-o 输出.txt]
"""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

_BLOCK = re.compile(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>|<w:p/>", re.S)
_ROW = re.compile(r"<w:tr[ >].*?</w:tr>", re.S)
_CELL = re.compile(r"<w:tc>.*?</w:tc>", re.S)
_PARA = re.compile(r"<w:p[ >].*?</w:p>", re.S)
_TEXT = re.compile(r"<w:t(?: [^>]*)?>([^<]*)</w:t>|<w:tab/>|<w:br/>")


def _para_text(xml: str) -> str:
    out = []
    for m in _TEXT.finditer(xml):
        if m.group(1) is not None:
            out.append(html.unescape(m.group(1)))
        else:
            out.append("\t" if m.group(0) == "<w:tab/>" else "\n")
    return "".join(out)


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    lines = []
    for block in _BLOCK.finditer(xml):
        b = block.group(0)
        if b.startswith("<w:tbl>"):
            for row in _ROW.finditer(b):
                cells = [" ".join(_para_text(p.group(0)) for p in _PARA.finditer(c.group(0)))
                         for c in _CELL.finditer(row.group(0))]
                lines.append(" | ".join(cells))
        else:
            lines.append(_para_text(b))
    return "\n".join(lines)


def read_any(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    return path.read_text(encoding="utf-8-sig")


def main() -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="把 .docx/.md/.txt 的正文（含表格）抽成纯文本")
    p.add_argument("path")
    p.add_argument("-o", "--output", help="输出文件，默认打印到屏幕")
    a = p.parse_args()
    text = read_any(a.path)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
