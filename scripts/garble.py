#!/usr/bin/env python3
"""Detect and repair garbled text (乱码) and invisible characters (零宽字符等).

Used by the hooks (check only) and by /shuozhongwen qingli (repair).

What counts:
- invisible: zero-width and other invisible format characters, as text_unicode
  defines them (U+200B, U+200C, U+200D, U+2060, U+FEFF inside text, bidi
  controls, tag characters ...). Odd spaces such as U+00A0 are left alone.
- replacement: U+FFFD, the mark a decoder leaves where bytes were lost.
- control: C0 control characters other than tab, newline and carriage return.
- placeholder: 锟斤拷 and runs of 烫 / 屯, the classic markers of lost bytes.
- mojibake: UTF-8 text decoded with the wrong code page, e.g. "涓枃" for 中文
  (GBK) or "Ã©" for é (cp1252). A run counts when at least 80% of its bytes,
  re-encoded with that code page, form valid UTF-8; genuine text scores near 0.
  Repaired by re-decoding; bytes that were already lost are reported (lossy).
- invalid_utf8: bytes in a file that are not valid UTF-8 (files only).

Lost characters (replacement, placeholder) cannot be recovered: repair removes
them and the report says where they were, so the author can fill them in.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from text_unicode import clean_text, inspect_text  # noqa: E402

CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PLACEHOLDER = re.compile(r"(?:锟斤拷)+|烫{3,}|屯{3,}")
CJK_RUN = re.compile(r"[\u2e80-\u9fff\uac00-\ud7af\uf900-\ufaff\ufe30-\ufe4f\uff00-\ufffc]{2,}")  # U+FFFD splits runs
MIN_VALID = 0.8  # share of re-encoded bytes that must form valid UTF-8
LATIN_RUN = re.compile(r"[\u0080-ÿŒœŠšŸŽžƒˆ˜–—"
                       r"‘-„†-•…‰‹›€™]{2,}")
LATIN_LEAD = set("ÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ")

LABELS = {"invisible": "零宽/不可见字符", "replacement": "替换符 U+FFFD（字符已丢失）", "control": "控制字符",
          "placeholder": "乱码占位（锟斤拷/烫烫烫）", "mojibake": "编码错乱",
          "invalid_utf8": "非 UTF-8 字节"}


def visible(s: str) -> str:
    """Make invisible, control and replacement characters readable as ⟨U+XXXX⟩."""
    out = []
    for ch in s:
        cp = ord(ch)
        if ch in "\r\n\t":
            out.append(" ")
        elif cp == 0xFFFD or CONTROL.match(ch) or unicodedata.category(ch) == "Cf":
            out.append(f"⟨U+{cp:04X}⟩")
        else:
            out.append(ch)
    return "".join(out)


def _context(text: str, start: int, end: int, width: int = 12) -> str:
    return visible(text[max(0, start - width):end + width])


def _redecode(run: str, codec: str) -> tuple[float, str]:
    """Re-encode a run with the code page that misread it and decode as UTF-8.

    Returns (share of bytes that formed valid UTF-8, decoded text without the
    broken bytes). Genuine Chinese or European text scores near 0, because GBK
    and cp1252 bytes rarely line up as UTF-8 sequences; real mojibake scores
    near 1."""
    try:
        data = run.encode(codec)
    except UnicodeEncodeError:
        return 0.0, run
    # A run that starts right after lost bytes begins mid-character: skip the
    # orphan continuation bytes (0x80-0xBF) instead of counting them as noise.
    data = data.lstrip(bytes(range(0x80, 0xC0)))
    decoded = data.decode("utf-8", errors="replace")
    good = decoded.replace("\ufffd", "")
    if not data or not any(ord(c) > 0x7F for c in good):
        return 0.0, run
    return len(good.encode("utf-8")) / len(data), good


# CJK ideographs, CJK punctuation, full-width forms (code points, so no literal
# ideographic space can be mangled into an ASCII one by an editor).
HAN_RANGES = ((0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0x3000, 0x303F), (0xFF00, 0xFFEF))


def _plausible(fixed: str, cjk: bool) -> bool:
    """The repair must read as text: for Chinese mojibake, mostly CJK characters
    (GBK bytes of genuine Chinese often decode to stray Cyrillic or IPA letters);
    for European mojibake, Latin letters with accents."""
    letters = [c for c in fixed if not c.isspace()]
    if len(letters) < (2 if cjk else 1):
        return False
    if cjk:
        han = sum(1 for c in letters if any(lo <= ord(c) <= hi for lo, hi in HAN_RANGES))
        return han / len(letters) >= 0.9
    return all(c.isalpha() or c in "'-" or ord(c) < 0x80 for c in letters)


def _mojibake(text: str) -> list[dict]:
    found = []
    for pattern, codecs in ((CJK_RUN, ("gbk",)), (LATIN_RUN, ("cp1252", "latin-1"))):
        for m in pattern.finditer(text):
            run = m.group(0)
            if pattern is LATIN_RUN and not LATIN_LEAD & set(run):
                continue
            best = max((_redecode(run, c) + (c,) for c in codecs), key=lambda x: x[0])
            share, fixed, codec = best
            if share < MIN_VALID or not _plausible(fixed, pattern is CJK_RUN):
                continue
            lossy = share < 1.0
            found.append({"start": m.start(), "end": m.end(), "text": run, "codec": codec,
                          "fixed": fixed, "lossy": lossy})
    return found


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def inspect(text: str, raw: bytes | None = None) -> dict:
    """Counts and locations of every problem; never changes anything."""
    items: list[dict] = []
    report = inspect_text(text)
    for h in getattr(report, "hits", []):
        if h.kind in ("space",):
            continue
        for pos in list(getattr(h, "samples", []))[:5]:
            items.append({"type": "invisible", "char": f"U+{h.codepoint:04X}", "label": h.label,
                          "line": _line_of(text, pos), "context": _context(text, pos, pos + 1)})
        if h.count > len(getattr(h, "samples", [])[:5]):
            items.append({"type": "invisible", "char": f"U+{h.codepoint:04X}", "label": h.label,
                          "more": h.count - len(getattr(h, "samples", [])[:5])})
    counts: Counter = Counter()
    for h in getattr(report, "hits", []):
        if h.kind not in ("space",):
            counts["invisible"] += h.count
    for m in re.finditer("\ufffd+", text):
        counts["replacement"] += len(m.group(0))
        items.append({"type": "replacement", "line": _line_of(text, m.start()), "context": _context(text, m.start(), m.end())})
    for m in CONTROL.finditer(text):
        counts["control"] += 1
        items.append({"type": "control", "char": f"U+{ord(m.group(0)):04X}", "line": _line_of(text, m.start()),
                      "context": _context(text, m.start(), m.end())})
    for m in PLACEHOLDER.finditer(text):
        counts["placeholder"] += 1
        items.append({"type": "placeholder", "text": m.group(0), "line": _line_of(text, m.start()),
                      "context": _context(text, m.start(), m.end())})
    for f in _mojibake(text):
        counts["mojibake"] += 1
        items.append({"type": "mojibake", "text": f["text"], "fixed": f["fixed"], "lossy": f["lossy"],
                      "line": _line_of(text, f["start"]), "context": _context(text, f["start"], f["end"])})
    if raw is not None:
        bad = sum(1 for ch in raw.decode("utf-8", errors="surrogateescape") if 0xDC80 <= ord(ch) <= 0xDCFF)
        if bad:
            counts["invalid_utf8"] = bad
            items.append({"type": "invalid_utf8", "count": bad})
    return {"clean": not counts, "counts": dict(counts), "items": items}


def repair(text: str) -> tuple[str, dict]:
    """Remove invisible characters, control characters, U+FFFD and placeholder
    runs; fix mojibake whose round trip is exact. Returns (text, report) where
    report lists what was done, with line numbers in the original text."""
    before = inspect(text)
    out = text
    fixed = []
    for f in sorted(_mojibake(out), key=lambda x: -x["start"]):
        out = out[:f["start"]] + f["fixed"] + out[f["end"]:]
        fixed.append({"from": f["text"], "to": f["fixed"], "lossy": f["lossy"], "line": _line_of(text, f["start"])})
    out = PLACEHOLDER.sub("", out)
    out = out.replace("\ufffd", "")
    out = CONTROL.sub("", out)
    out, stats = clean_text(out, normalize_spaces=False)
    after = inspect(out)
    done = {k: v for k, v in before["counts"].items() if k != "invalid_utf8"}
    return out, {"removed": {k: v for k, v in done.items() if v}, "removed_by_char": stats.get("removed", {}),
                 "mojibake_fixed": fixed, "items": before["items"], "remaining": after["counts"],
                 "changed": out != text}


def summary(counts: dict) -> str:
    """One short Chinese line, e.g. 零宽/不可见字符 3、替换符 U+FFFD（字符已丢失） 1."""
    return "、".join(f"{LABELS.get(k, k)} {v}" for k, v in counts.items() if v)
