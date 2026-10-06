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
2. Templates: structural AI templates the judge lists (agents/judge.md 模板腔)
   count only with verbatim evidence; more than one fails the review. Writing
   devices (devices: 设问自答, 单句成段, 前后回扣, 冒号清单, 段尾警句) are common
   in human prose too, so they are listed for the writer and never fail a review.
3. Gate: literary genres need average >= 4.0 and every dimension >= 3;
   practical and argument texts need average >= 3.5 and every dimension >= 3;
   a "flat" verdict always fails, and so does "off_task" (the judge was given
   the task and the text does not do what it asks).
4. Facts: claims marked "doubt" block delivery only for the writer's own draft
   (--own). In someone else's draft the data is locked: doubts are listed for the
   author and the text is never changed because of them.
5. Paper mode (--paper, /shuozhongwen lunwen): the language judge's six academic
   dimensions, gate average >= 3.5 and every dimension >= 3; with --original and
   --rigor, any verbatim-quoted regression in academic rigor fails.

Usage:
  review_zh.py 稿件 --genre 城市随笔散文 --review 审读.json [--facts 核查.json] [--own]
  review_zh.py 改稿 --genre 课程设计报告 --paper --review 审读.json --original 原稿 --rigor 严谨.json
Exit code 0 = passed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_text import read_any  # noqa: E402

DIMENSIONS = [
    ("concrete", "具体可感"),
    ("insight", "自己的发现"),
    ("language", "语言与意象"),
    ("rhythm", "节奏"),
    ("structure", "结构与张力"),
    ("voice", "声音"),
]
# /shuozhongwen lunwen: the language judge (agents/lunwen-judge.md) scores these instead.
PAPER_DIMENSIONS = [
    ("accuracy", "表述准确"),
    ("concision", "简洁"),
    ("register", "学术语体"),
    ("coherence", "衔接与逻辑"),
    ("consistency", "一致"),
    ("naturalness", "去模板腔"),
]
LITERARY = ("散文", "游记", "随笔", "小说", "演讲", "书评", "影评", "诗", "故事", "回忆", "文学")
MIN_EVIDENCE = 8
MAX_TEMPLATES = 1  # structural AI templates the judge quoted (agents/judge.md 模板腔); more fails
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


def check_review(text: str, review: dict, genre: str, paper: bool = False) -> dict:
    avg_min, dim_min = (3.5, 3) if paper else gate(genre)
    scores = review.get("scores", {})
    dims, void = {}, []
    for key, label in (PAPER_DIMENSIONS if paper else DIMENSIONS):
        item = scores.get(key)
        if not isinstance(item, dict) or not quoted(text, str(item.get("evidence", ""))):
            void.append(label)
            continue
        dims[key] = int(item.get("score", 0))
    valid = not void
    average = round(sum(dims.values()) / len(dims), 2) if dims else None
    flat = bool(review.get("flat"))
    off_task = review.get("off_task") is True
    templates = [t for t in review.get("templates", [])
                 if isinstance(t, dict) and quoted(text, str(t.get("evidence", "")))]
    devices = [t for t in review.get("devices", [])
               if isinstance(t, dict) and quoted(text, str(t.get("evidence", "")))]
    passed = (valid and average is not None and average >= avg_min and all(v >= dim_min for v in dims.values())
              and not flat and not off_task and len(templates) <= MAX_TEMPLATES)
    weakest = sorted(dims, key=lambda k: dims[k])[:2] if dims else []
    return {"valid": valid, "void": void, "dims": dims, "average": average, "flat": flat, "paper": paper,
            "gate": {"average": avg_min, "each": dim_min}, "passed": passed, "weakest": weakest,
            "fixes": {k: scores[k].get("fix", "") for k in dims if k in scores},
            "cliche": [c for c in review.get("cliche", []) if quoted(text, c)],
            "templates": templates, "devices": devices,
            "off_task": off_task, "task_note": str(review.get("task_note", "") or ""),
            "summary": review.get("summary", "")}


def check_facts(text: str, facts: dict, own: bool = False) -> dict:
    """Doubts block delivery only for the writer's own draft (own=True), where they
    must be verified and fixed. In someone else's draft the data is locked: doubts
    are listed for the author to check and never block or trigger an edit."""
    claims = facts.get("claims", [])
    doubts = [c for c in claims if c.get("verdict") == "doubt"]
    return {"claims": len(claims), "doubts": doubts, "own": own, "passed": not doubts or not own}


def check_rigor(original: str, revised: str, rigor: dict) -> dict:
    """Academic rigor review (agents/rigor.md). A regression counts only when both
    quotes are verbatim: the original sentence from the original, the revised one
    from the revision. Any counted regression fails. Issues are the original's own
    problems, quoted from the original, for the author."""
    regressions = [x for x in rigor.get("regressions", [])
                   if quoted(original, str(x.get("original", ""))) and quoted(revised, str(x.get("revised", "")))]
    issues = [x for x in rigor.get("issues", []) if quoted(original, str(x.get("text", "")))]
    void = len(rigor.get("regressions", [])) - len(regressions) + len(rigor.get("issues", [])) - len(issues)
    return {"regressions": regressions, "issues": issues, "void": void, "passed": not regressions}


def report(r: dict, f: dict | None, g: dict | None = None) -> str:
    zh = dict(PAPER_DIMENSIONS if r.get("paper") else DIMENSIONS)
    out = []
    if not r["valid"]:
        out.append(f"审读无效：{('、'.join(r['void']))} 的证据在原文里找不到，这几项分数作废。换一个全新的评委子代理重审。")
    dims = "、".join(f"{zh[k]} {v}" for k, v in r["dims"].items())
    out.append(f"{'语言审读' if r.get('paper') else '编辑审读'}：平均 {r['average']}（要求 ≥{r['gate']['average']}），{dims}（要求都 ≥{r['gate']['each']}），"
               f"白开水：{'是' if r['flat'] else '否'}")
    if r.get("off_task"):
        out.append(f"  偏题（未通过）：{r.get('task_note') or '正文没做任务要求的事'}")
    if r["valid"] and not r["passed"]:
        for k in r["weakest"]:
            out.append(f"  先改 {zh[k]}：{r['fixes'].get(k, '')}")
    if r.get("templates"):
        state = "" if len(r["templates"]) <= MAX_TEMPLATES else f"（超过 {MAX_TEMPLATES} 处，未通过）"
        out.append(f"  模板腔 {len(r['templates'])} 处{state}：" + "；".join(
            f"{t.get('type', '')}「{str(t.get('evidence', ''))[:30]}」" for t in r["templates"]))
    if r.get("devices"):
        out.append(f"  手法重复 {len(r['devices'])} 处（只提醒，不算未通过；同一种手法别拿来搭架子）：" + "；".join(
            f"{t.get('type', '')}「{str(t.get('evidence', ''))[:30]}」" for t in r["devices"]))
    if r["cliche"]:
        out.append("  套话：" + "；".join(r["cliche"]))
    if f is not None:
        out.append(f"事实核查：{f['claims']} 条，存疑 {len(f['doubts'])} 条"
                   + ("" if f["own"] or not f["doubts"] else "（改的是别人的稿子：存疑项只列进“待作者核对”，正文一字不改）"))
        for c in f["doubts"]:
            out.append(f"  存疑：{c.get('text')}  ——  {c.get('note')}")
    if g is not None:
        out.append(f"学术严谨性：退步 {len(g['regressions'])} 处，原稿问题 {len(g['issues'])} 条"
                   + (f"，{g['void']} 条引不出原文已作废" if g["void"] else ""))
        for x in g["regressions"]:
            out.append(f"  退步（{x.get('type')}）：原稿「{x.get('original')}」→ 改稿「{x.get('revised')}」 {x.get('note', '')}")
        for x in g["issues"]:
            out.append(f"  待作者处理（{x.get('type')}）：「{x.get('text')}」 {x.get('note', '')}")
    ok = r["passed"] and (f is None or f["passed"]) and (g is None or g["passed"])
    out.append("结论：通过" if ok else "结论：未通过")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="稿件文件（论文模式下是改稿）")
    p.add_argument("--genre", required=True, help="文体，如 城市随笔散文、周报、知乎回答、课程设计报告")
    p.add_argument("--review", required=True, help="评委子代理返回的 JSON（文件路径）")
    p.add_argument("--facts", help="事实核查子代理返回的 JSON（文件路径）")
    p.add_argument("--own", action="store_true", help="只给题目、没有材料的稿子：事实存疑要改到 0 才算过；不加则存疑项只列给作者")
    p.add_argument("--paper", action="store_true", help="论文模式：按 lunwen-judge 的六项和 3.5 分线判")
    p.add_argument("--original", help="论文模式：原稿文件，配合 --rigor")
    p.add_argument("--rigor", help="论文模式：严谨性审查子代理返回的 JSON（文件路径）")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    if a.rigor and not a.original:
        p.error("--rigor needs --original")
    text = read_any(a.path)
    r = check_review(text, load_json(Path(a.review).read_text(encoding="utf-8")), a.genre, paper=a.paper)
    f = check_facts(text, load_json(Path(a.facts).read_text(encoding="utf-8")), own=a.own) if a.facts else None
    g = (check_rigor(read_any(a.original), text, load_json(Path(a.rigor).read_text(encoding="utf-8")))
         if a.rigor else None)
    if a.json:
        print(json.dumps({"review": r, "facts": f, "rigor": g}, ensure_ascii=False, indent=1))
    else:
        print(report(r, f, g))
    return 0 if r["passed"] and (f is None or f["passed"]) and (g is None or g["passed"]) else 1

if __name__ == "__main__":
    sys.exit(main())
