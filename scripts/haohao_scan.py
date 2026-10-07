#!/usr/bin/env python3
"""Run the skill's four zero-tolerance scans on a draft.

The regexes are read from the skill's references/quick-scan-regex.md
(the four ```regex blocks, in order), so this module never keeps a second copy.
Python's re handles CJK ranges on every platform, unlike `grep -P` in a
non-UTF-8 Git Bash.

Rules and gate (skills/shuozhongwen/SKILL.md「改前逐字扫」「交付硬闸」):
- heading_numbering: zero tolerance (A1 exemptions are judged by a person)
- b2_variants: at most 2 in the whole text
- meta_discourse: zero tolerance
- halfwidth_punct: zero tolerance, part of the delivery gate
Code spans, URLs and numbers are exempt, as the reference page says, and so
is the reference list (GB/T 7714 entries use half-width punctuation).
--paper skips the heading-numbering rule: numbered sections are the academic norm.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_text import read_any  # noqa: E402
from haohao_markers import haohao_dir  # noqa: E402

RULES = (
    ("heading_numbering", "章节序号+量词标题", 0),
    ("b2_variants", "“不是 X 是 Y”变体族", 2),
    ("meta_discourse", "元话语", 0),
    ("halfwidth_punct", "中文正文半角标点", 0),
)
CODE = re.compile(r"```.*?```|`[^`\n]*`|https?://\S+", re.S)


def load_patterns() -> list[re.Pattern]:
    ref = haohao_dir() / "references" / "quick-scan-regex.md"
    blocks = re.findall(r"```regex\n(.*?)\n```", ref.read_text(encoding="utf-8"), re.S)
    if len(blocks) < 4:
        raise RuntimeError(f"expected 4 regex blocks in {ref}, found {len(blocks)}")
    return [re.compile(b, re.M) for b in blocks[:4]]


REF_HEAD = re.compile(r"^\s*#*\s*(参考文献|references|bibliography)\s*$", re.I)
REF_LINE = re.compile(r"^\s*[\[［]\s*\d+\s*[\]］]")


def reference_lines(lines: list[str]) -> set[int]:
    """Line numbers (1-based) of the reference list: GB/T 7714 entries use
    half-width punctuation by rule, so the half-width scan skips them."""
    out, in_refs = set(), False
    for i, line in enumerate(lines, 1):
        if REF_HEAD.match(line):
            in_refs = True
            continue
        if in_refs or REF_LINE.match(line):
            out.add(i)
    return out


def scan(text: str, paper: bool = False) -> dict:
    """paper=True (the /shuozhongwen lunwen mode): numbered headings are the
    academic convention and are not scanned."""
    body = CODE.sub(lambda m: " " * len(m.group(0)), text)
    lines = body.splitlines()
    refs = reference_lines(lines)
    out = {"passed": True, "rules": []}
    for (key, label, limit), pat in zip(RULES, load_patterns()):
        if paper and key == "heading_numbering":
            out["rules"].append({"rule": key, "label": label, "limit": limit, "count": 0,
                                 "passed": True, "hits": [], "skipped": "论文的章节编号是规范，不扫"})
            continue
        hits = []
        for i, line in enumerate(lines, 1):
            if key == "halfwidth_punct" and i in refs:
                continue
            for m in pat.finditer(line):
                hits.append({"line": i, "match": m.group(0), "text": line.strip()[:80]})
        ok = len(hits) <= limit
        out["passed"] &= ok
        out["rules"].append({"rule": key, "label": label, "limit": limit, "count": len(hits),
                             "passed": ok, "hits": hits[:20]})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    p.add_argument("--paper", action="store_true", help="论文模式：不扫章节编号")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    r = scan(read_any(a.path), paper=a.paper)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        for rule in r["rules"]:
            state = "通过" if rule["passed"] else "未通过"
            print(f"=== {rule['label']}：{rule['count']} 处（上限 {rule['limit']}，{state}）")
            for h in rule["hits"]:
                print(f"  {h['line']}: {h['text']}")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
