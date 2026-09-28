#!/usr/bin/env python3
"""Check the verdicts of the shuozhongwen judge and fact-check subagents.

The reviewing itself is done by fresh subagents of the current session model
(agents/judge.md, agents/factcheck.md): each call sees only the genre, the text
and the rubric, never the conversation that produced the draft. This script
does not call any model. It takes the JSON they returned and:

1. Evidence rule: every dimension's evidence must be a verbatim quote from the
   draft (whitespace and quote marks ignored, at least 8 characters). A score
   whose evidence cannot be found is void. Any void dimension makes the whole
   review invalid: run a fresh judge again.
2. Gate: literary genres need average >= 4.0 and every dimension >= 3;
   practical and argument texts need average >= 3.5 and every dimension >= 3;
   a "flat" verdict always fails.
3. Facts: claims marked "doubt" block delivery; "rhetoric" does not.

Usage:
  review_zh.py 稿件 --genre 城市随笔散文 --review 审读.json [--facts 核查.json]
Exit code 0 = passed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DIMENSIONS = [
    ("concrete", "具体可感"),
    ("insight", "自己的发现"),
    ("language", "语言与意象"),
    ("rhythm", "节奏"),
    ("structure", "结构与张力"),
    ("voice", "声音"),
]
LITERARY = ("散文", "游记", "随笔", "小说", "演讲", "书评", "影评", "诗", "故事", "回忆", "文学")
MIN_EVIDENCE = 8
_STRIP = re.compile(r"[\s“”‘’\"'「」『』《》…\.。，,、；;：:！!？?—\-]+")


def gate(genre: str) -> tuple[float, int]:
    return (4.0, 3) if any(g in genre for g in LITERARY) else (3.5, 3)


def _norm(s: str) -> str:
    return _STRIP.sub("", s or "")


def load_json(raw: str) -> dict:
    """Accept the subagent's reply as-is: pure JSON, or JSON wrapped in prose/fences."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("no JSON object found")
    return json.loads(m.group(0))


def quoted(text: str, evidence: str) -> bool:
    ev = _norm(evidence)
    return len(ev) >= MIN_EVIDENCE and ev in _norm(text)


def check_review(text: str, review: dict, genre: str) -> dict:
    avg_min, dim_min = gate(genre)
    scores = review.get("scores", {})
    dims, void = {}, []
    for key, label in DIMENSIONS:
        item = scores.get(key)
        if not isinstance(item, dict) or not quoted(text, str(item.get("evidence", ""))):
            void.append(label)
            continue
        dims[key] = int(item.get("score", 0))
    valid = not void
    average = round(sum(dims.values()) / len(dims), 2) if dims else None
    flat = bool(review.get("flat"))
    passed = valid and average is not None and average >= avg_min and all(v >= dim_min for v in dims.values()) and not flat
    weakest = sorted(dims, key=lambda k: dims[k])[:2] if dims else []
    return {"valid": valid, "void": void, "dims": dims, "average": average, "flat": flat,
            "gate": {"average": avg_min, "each": dim_min}, "passed": passed, "weakest": weakest,
            "fixes": {k: scores[k].get("fix", "") for k in dims if k in scores},
            "cliche": [c for c in review.get("cliche", []) if quoted(text, c)],
            "summary": review.get("summary", "")}


def check_facts(text: str, facts: dict) -> dict:
    claims = facts.get("claims", [])
    doubts = [c for c in claims if c.get("verdict") == "doubt"]
    return {"claims": len(claims), "doubts": doubts, "passed": not doubts}


def report(r: dict, f: dict | None) -> str:
    zh = dict(DIMENSIONS)
    out = []
    if not r["valid"]:
        out.append(f"审读无效：{('、'.join(r['void']))} 的证据在原文里找不到，这几项分数作废。换一个全新的评委子代理重审。")
    dims = "、".join(f"{zh[k]} {v}" for k, v in r["dims"].items())
    out.append(f"编辑审读：平均 {r['average']}（要求 ≥{r['gate']['average']}），{dims}（要求都 ≥{r['gate']['each']}），"
               f"白开水：{'是' if r['flat'] else '否'}")
    if r["valid"] and not r["passed"]:
        for k in r["weakest"]:
            out.append(f"  先改 {zh[k]}：{r['fixes'].get(k, '')}")
    if r["cliche"]:
        out.append("  套话：" + "；".join(r["cliche"]))
    if f is not None:
        out.append(f"事实核查：{f['claims']} 条，存疑 {len(f['doubts'])} 条")
        for c in f["doubts"]:
            out.append(f"  存疑：{c.get('text')}  ——  {c.get('note')}")
    ok = r["passed"] and (f is None or f["passed"])
    out.append("结论：通过" if ok else "结论：未通过")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="稿件文件")
    p.add_argument("--genre", required=True, help="文体，如 城市随笔散文、周报、知乎回答")
    p.add_argument("--review", required=True, help="评委子代理返回的 JSON（文件路径）")
    p.add_argument("--facts", help="事实核查子代理返回的 JSON（文件路径）")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    text = Path(a.path).read_text(encoding="utf-8")
    r = check_review(text, load_json(Path(a.review).read_text(encoding="utf-8")), a.genre)
    f = check_facts(text, load_json(Path(a.facts).read_text(encoding="utf-8"))) if a.facts else None
    if a.json:
        print(json.dumps({"review": r, "facts": f}, ensure_ascii=False, indent=1))
    else:
        print(report(r, f))
    return 0 if r["passed"] and (f is None or f["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
