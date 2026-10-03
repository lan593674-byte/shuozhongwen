"""Check one file for invisible characters, garbled text and provenance marks.

Read-only. Shared by the PostToolUse hook (which only checks) and by
qingli.py (which repairs). Text files are decoded as UTF-8; Office and EPUB
documents (zip containers) are checked through the text of their XML parts.
"""

from __future__ import annotations

import html
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import garble  # noqa: E402

ZIP_DOCS = {".docx", ".docm", ".dotx", ".pptx", ".xlsx", ".odt", ".odp", ".ods", ".epub"}
ZIP_TEXT_PARTS = re.compile(r"\.(xml|xhtml|html?|rels)$", re.I)
XML_TEXT = re.compile(r">([^<]+)<")


def is_binary(raw: bytes) -> bool:
    return b"\x00" in raw[:8192]


def zip_text(path: Path) -> str:
    parts = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if ZIP_TEXT_PARTS.search(name):
                xml = z.read(name).decode("utf-8", errors="replace")
                parts.extend(html.unescape(m.group(1)) for m in XML_TEXT.finditer(xml))
    return "\n".join(parts)


def _provenance(path: Path) -> list[str]:
    try:
        from audit_lib import is_actionable, scan_file

        item = scan_file(path)
    except Exception:  # provenance is a bonus; never fail the check on it
        return []
    if item.get("kind") in ("unknown", "text") or not is_actionable(item):
        return []
    found = []
    if item.get("has_c2pa"):
        found.append("C2PA 来源清单")
    if item.get("has_ai_metadata"):
        found.append("AI 生成元数据")
    return found


def check_path(path: Path) -> dict:
    """{"path", "name", "kind", "counts", "items", "provenance", "skipped"}"""
    out = {"path": str(path), "name": path.name, "kind": "", "counts": {}, "items": [], "provenance": [],
           "skipped": ""}
    suffix = path.suffix.lower()
    try:
        if suffix in ZIP_DOCS and zipfile.is_zipfile(path):
            out["kind"] = "document"
            r = garble.inspect(zip_text(path))
        else:
            raw = path.read_bytes()
            if is_binary(raw):
                out["kind"] = "binary"
                out["provenance"] = _provenance(path)
                return out
            out["kind"] = "text"
            r = garble.inspect(raw.decode("utf-8", errors="surrogateescape"), raw)
    except (OSError, zipfile.BadZipFile) as error:
        out["skipped"] = f"读取失败：{error}"
        return out
    out["counts"], out["items"] = r["counts"], r["items"]
    if out["kind"] == "document":
        out["provenance"] = _provenance(path)
    return out


def describe(result: dict) -> str:
    """Short Chinese description of one file's problems, '' if clean."""
    parts = [garble.summary(result["counts"])] if result["counts"] else []
    parts += result["provenance"]
    return "、".join(p for p in parts if p)
