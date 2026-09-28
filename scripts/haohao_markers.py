"""Load AI-flavour markers from the shuozhongwen skill's own reference files so the
plugin keeps no second copy of that list. The skill text owns the rules; this module only
reads its reference files and turns them into countable patterns.

Sources (resolved from SHUOZHONGWEN_SKILL_DIR, default <plugin root>/skills/shuozhongwen):
- references/symptom-dictionary.md: quoted 「terms」 in the 句式/词汇/结构 sections
- references/quick-scan-regex.md: the B2 variant-family and meta-discourse regexes
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

HAN = re.compile(r"^[一-鿿]{2,8}$")
# Sections of symptom-dictionary.md whose quoted terms are phrase markers.
# 标点级 is excluded (punctuation is haohao's own hard gate), and so is 结构排比级
# (its structure is measured by score_zh features, not by phrase lookup).
SECTION_RE = re.compile(r"^## (二|三|四)、", re.M)
# quick-scan-regex.md: blocks 2 (B2) and 3 (meta-discourse). Block 1 is heading
# numbering (measured as format), block 4 is half-width punctuation (haohao's gate).
REGEX_BLOCKS = {2: "B2 不是X是Y 变体", 3: "元话语"}


def haohao_dir() -> Path:
    env = os.environ.get("SHUOZHONGWEN_SKILL_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "skills" / "shuozhongwen"


def _symptom_terms(text: str) -> list[str]:
    starts = [m.start() for m in SECTION_RE.finditer(text)]
    if not starts:
        return []
    ends = starts[1:] + [text.find("\n## 五、") if "\n## 五、" in text else len(text)]
    terms: set[str] = set()
    for s, e in zip(starts, ends):
        # skip the "fixed" examples (✅ lines, right-hand table cells): they are
        # the good version, not markers
        body = "\n".join(
            ln.split("|")[1] if ln.startswith("|") and ln.count("|") >= 3 else ln
            for ln in text[s:e].splitlines()
            if "✅" not in ln
        )
        for t in re.findall(r"「([^」]+)」", body):
            for part in re.split(r"\s*/\s*|…+|……", t):
                part = part.strip()
                if HAN.match(part) and "X" not in part:
                    terms.add(part)
    return sorted(terms)


def _scan_regexes(text: str) -> list[tuple[str, str]]:
    blocks = re.findall(r"```regex\n(.*?)\n```", text, re.S)
    out = []
    for idx, label in REGEX_BLOCKS.items():
        if len(blocks) >= idx:
            try:
                re.compile(blocks[idx - 1])
            except re.error:
                continue
            out.append((blocks[idx - 1], label))
    return out


@lru_cache(maxsize=1)
def load_markers() -> tuple[list[tuple[str, str]], str | None]:
    """Return ([(regex, label)], note). note is set when the skill references are missing."""
    try:
        base = haohao_dir() / "references"
    except RuntimeError:  # no home directory in this environment
        return [], "skill directory unavailable; phrase markers skipped"
    try:
        sym = (base / "symptom-dictionary.md").read_text(encoding="utf-8")
        qs = (base / "quick-scan-regex.md").read_text(encoding="utf-8")
    except OSError:
        return [], f"skill references not found under {base}; phrase markers skipped"
    patterns = [(re.escape(t), t) for t in _symptom_terms(sym)]
    patterns += _scan_regexes(qs)
    return patterns, None


if __name__ == "__main__":
    pats, note = load_markers()
    print(note or f"{len(pats)} markers")
    for p, label in pats:
        print(label)
