#!/usr/bin/env python3
"""Read the text of a draft: .txt/.md as UTF-8, .docx as paragraphs (stdlib only).

Word tables come out one row per line with cells joined by " | ", so table
contents are read along with the prose.

Usage: doc_text.py 稿件.docx [-o 输出.txt]
"""

from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr(node: ET.Element, name: str) -> str:
    return next((value for key, value in node.attrib.items() if _local(key) == name), "")


def _node_text(node: ET.Element) -> str:
    tag = _local(node.tag)
    if tag in {"oMath", "oMathPara"}:
        # Joining m:t would turn a fraction or superscript into a new number.
        return "\n```xml\n" + ET.tostring(node, encoding="unicode") + "\n```\n"
    if tag == "t":
        return node.text or ""
    if tag == "tab":
        return "\t"
    if tag in {"br", "cr"}:
        return "\n"
    if tag in {"footnoteReference", "endnoteReference"}:
        kind = "脚注" if tag == "footnoteReference" else "尾注"
        return f"[{kind} {_attr(node, 'id')}]"
    if tag in {"del", "moveFrom"}:
        return ""
    return "".join(_node_text(child) for child in node)


def _para_text(xml: str) -> str:
    return _node_text(ET.fromstring(xml))


def _contained(node: ET.Element, tag: str):
    """Unwrap Word content controls without crossing into nested table cells."""
    for child in node:
        name = _local(child.tag)
        if name == tag:
            yield child
        elif name in {"sdt", "sdtContent", "customXml", "ins", "moveTo"}:
            yield from _contained(child, tag)


def _block_lines(node: ET.Element) -> list[str]:
    lines = []
    for child in node:
        tag = _local(child.tag)
        if tag == "p":
            lines.append(_node_text(child))
        elif tag == "tbl":
            for row in _contained(child, "tr"):
                cells = [" ".join(_block_lines(cell)) for cell in _contained(row, "tc")]
                lines.append(" | ".join(cells))
        elif tag in {"oMath", "oMathPara"}:
            lines.append(_node_text(child))
        elif tag not in {"del", "moveFrom"}:
            lines.extend(_block_lines(child))
    return lines


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        lines = _block_lines(ET.fromstring(z.read("word/document.xml")))
        for part, kind in (("word/footnotes.xml", "脚注"), ("word/endnotes.xml", "尾注")):
            if part not in z.namelist():
                continue
            for note in ET.fromstring(z.read(part)):
                if _attr(note, "type") in {"separator", "continuationSeparator", "continuationNotice"}:
                    continue
                contents = _block_lines(note)
                if contents:
                    lines.append(f"\n[{kind} {_attr(note, 'id')}]")
                    lines.extend(contents)
    return "\n".join(lines)


def read_any(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    return path.read_text(encoding="utf-8-sig")


def main() -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="读取 .docx/.md/.txt，含表格、脚注、尾注和受保护的 Word 公式")
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
