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
2. Templates: observations count only with verbatim evidence and their quality
   impact is assessed in the six scores, not a separate count gate. Writing
   devices (devices: 设问自答, 单句成段, 前后回扣, 冒号清单, 段尾警句) are common
   in human prose too, so they are listed for the writer and never fail a review.
3. Gate: literary genres need average >= 4.0 and every dimension >= 3;
   practical and argument texts need average >= 3.5 and every dimension >= 3.
   Model identity and calibration records remain supported, but cannot override
   these research-writing quality lines. A "flat" verdict fails literary genres
   only, while "off_task" also fails (the judge was given
   the task and the text does not do what it asks). One exception: when the
   judge says only the length is off (off_task_kind 篇幅) and the writer has
   flagged that the material cannot fill the asked length (--short-material),
   the length is reported as a reminder and does not fail.
4. Compare (精修): check_compare() reads the two replies of the compare judge
   (agents/compare.md), asked in both orders; the new draft replaces the old
   one only when it wins both.
5. Facts: claims marked "doubt" block delivery only for the writer's own draft
   (--own). In someone else's draft the data is locked: doubts are listed for the
   author and the text is never changed because of them.
6. Paper mode (--paper, /shuozhongwen lunwen): the language judge's six academic
   dimensions, gate average >= 3.5 and every dimension >= 3; with --original and
   --rigor, any verbatim-quoted regression in academic rigor fails.

Usage:
  review_zh.py 稿件 --genre 城市随笔散文 --review 审读.json [--facts 核查.json] [--own] [--judge-model 模型名] [--short-material]
  review_zh.py 改稿 --genre 课程设计报告 --paper --review 审读.json --original 原稿 --rigor 严谨.json
Exit code 0 = passed.
"""

from __future__ import annotations

import argparse
import json
import os
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
_STRIP = re.compile(r"[\s“”‘’\"'「」『』《》…\.。，,、；;：:！!？?—\-]+")


THRESHOLDS = Path(__file__).resolve().parent / "judge_thresholds.json"


def thresholds() -> dict:
    path = Path(os.environ.get("SHUOZHONGWEN_THRESHOLDS") or THRESHOLDS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def gate(genre: str, model: str | None = None) -> tuple[float, int, str]:
    """Keep the model argument for compatibility; research-writing lines apply
    to every judge. Historical calibration data remain available via thresholds()."""
    kind = "literary" if any(g in genre for g in LITERARY) else "practical"
    return (4.0, 3, "固定分数线") if kind == "literary" else (3.5, 3, "固定分数线")


def _norm(s: str) -> str:
    return _STRIP.sub("", s or "")


def _escape_inner_quotes(s: str) -> str:
    """Escape ASCII double quotes inside JSON strings that the model forgot to
    escape (a quoted word inside an evidence quote). A quote closes a string only
    when the next non-space character is , : } or ]."""
    out, in_str, i = [], False, 0
    while i < len(s):
        c = s[i]
        if in_str and c == "\\":
            out.append(s[i:i + 2])
            i += 2
            continue
        if c == '"':
            if not in_str:
                in_str = True
            else:
                j = i + 1
                while j < len(s) and s[j] in " \t\r\n":
                    j += 1
                if j >= len(s) or s[j] in ",:}]":
                    in_str = False
                else:
                    out.append('\\"')
                    i += 1
                    continue
        out.append(c)
        i += 1
    return "".join(out)


def load_json(raw: str) -> dict:
    """Accept the subagent's reply as-is: pure JSON, or JSON wrapped in prose/fences.
    Unescaped quotes inside strings are repaired before giving up."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("no JSON object found")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return json.loads(_escape_inner_quotes(m.group(0)))


def quoted(text: str, evidence: str) -> bool:
    ev = _norm(evidence)
    return len(ev) >= MIN_EVIDENCE and ev in _norm(text)


def check_review(text: str, review: dict, genre: str, paper: bool = False, model: str | None = None,
                 short_material: bool = False) -> dict:
    avg_min, dim_min, source = (3.5, 3, "固定分数线") if paper else gate(genre, model)
    scores = review.get("scores", {})
    dims, void = {}, []
    for key, label in (PAPER_DIMENSIONS if paper else DIMENSIONS):
        item = scores.get(key)
        if not isinstance(item, dict) or not quoted(text, str(item.get("evidence", ""))):
            void.append(label)
            continue
        score = item.get("score")
        try:
            value = int(score)
            in_range = not isinstance(score, bool) and float(score) == value and 1 <= value <= 5
        except (TypeError, ValueError, OverflowError):
            in_range = False
        if not in_range:
            void.append(label)
            continue
        dims[key] = value
    valid = not void
    average = round(sum(dims.values()) / len(dims), 2) if dims else None
    flat = bool(review.get("flat"))
    flat_blocks = flat and not paper and any(g in genre for g in LITERARY)
    off_task = review.get("off_task") is True
    kind = str(review.get("off_task_kind", "") or "").strip()
    # only the length is off, and the writer said the material cannot fill it: a reminder, not a failure
    length_only = off_task and kind in ("篇幅", "length") and short_material
    templates = [t for t in review.get("templates", [])
                 if isinstance(t, dict) and quoted(text, str(t.get("evidence", "")))]
    devices = [t for t in review.get("devices", [])
               if isinstance(t, dict) and quoted(text, str(t.get("evidence", "")))]
    passed = (valid and average is not None and average >= avg_min and all(v >= dim_min for v in dims.values())
              and not flat_blocks and (not off_task or length_only))
    weakest = sorted(dims, key=lambda k: dims[k])[:2] if dims else []
    return {"valid": valid, "void": void, "dims": dims, "average": average, "flat": flat,
            "flat_blocks": flat_blocks, "paper": paper, "genre": genre,
            "gate": {"average": avg_min, "each": dim_min, "source": source}, "passed": passed, "weakest": weakest,
            "fixes": {k: scores[k].get("fix", "") for k in dims if k in scores},
            "cliche": [c for c in review.get("cliche", []) if quoted(text, c)],
            "templates": templates, "devices": devices,
            "off_task": off_task, "off_task_kind": kind, "length_only": length_only,
            "task_note": str(review.get("task_note", "") or ""),
            "summary": review.get("summary", "")}


def check_compare(base_in_a: dict, new_in_a: dict) -> dict:
    """Two replies of the compare judge: the first had the original draft as A and
    the polished one as B, the second the other way round. The polished draft
    replaces the original only when it wins both orders."""
    votes = []
    for data, new_pos, order in ((base_in_a, "B", "原稿在 A"), (new_in_a, "A", "新稿在 A")):
        pick = str(data.get("better", "")).strip().upper()[:1]
        winner = None if pick not in ("A", "B") else ("new" if pick == new_pos else "base")
        votes.append({"order": order, "winner": winner, "margin": str(data.get("margin", "") or ""),
                      "reason": str(data.get("reason", "") or "")})
    return {"votes": votes, "replace": all(v["winner"] == "new" for v in votes)}


def compare_report(c: dict) -> str:
    name = {"new": "新稿", "base": "原稿", None: "（没给出 A 或 B，作废）"}
    out = [f"对比评委（{v['order']}）：{name[v['winner']]}{v['margin']}更好。{v['reason']}" for v in c["votes"]]
    out.append("结论：换成新稿（两次都判新稿更好），新稿再做独立评分、保真核对与检查" if c["replace"] else "结论：交原稿（新稿没有两次都胜）")
    return "\n".join(out)


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
    problems, quoted from the original, for the author. An empty original means
    a new draft, so issues must quote the revised text. Any invalid evidence
    makes the review invalid and requires a fresh reviewer."""
    new_draft = not original.strip()
    regressions = [x for x in rigor.get("regressions", [])
                   if quoted(original, str(x.get("original", ""))) and quoted(revised, str(x.get("revised", "")))]
    issue_source = revised if new_draft else original
    issues = [x for x in rigor.get("issues", []) if quoted(issue_source, str(x.get("text", "")))]
    void = len(rigor.get("regressions", [])) - len(regressions) + len(rigor.get("issues", [])) - len(issues)
    valid = void == 0
    return {"regressions": regressions, "issues": issues, "void": void, "valid": valid,
            "new_draft": new_draft, "passed": valid and not regressions}


def report(r: dict, f: dict | None, g: dict | None = None) -> str:
    zh = dict(PAPER_DIMENSIONS if r.get("paper") else DIMENSIONS)
    out = []
    if not r["valid"]:
        out.append(f"审读无效：{('、'.join(r['void']))} 缺少有效原文证据或 1–5 整数评分，这几项作废。换一个全新的评委子代理重审。")
    dims = "、".join(f"{zh[k]} {v}" for k, v in r["dims"].items())
    source = r["gate"].get("source", "固定分数线")
    out.append(f"{'语言审读' if r.get('paper') else '编辑审读'}：平均 {r['average']}（要求 ≥{r['gate']['average']}，{source}），{dims}（要求都 ≥{r['gate']['each']}），"
               + (f"表达空泛：{'是' if r['flat'] else '否'}" if not r.get('paper') and any(x in r.get('genre', '') for x in LITERARY)
                  else "按所给文体评价，不以文采要求实用或学术文本"))
    if r.get("length_only"):
        out.append(f"  篇幅提醒（素材不足，不拦交付）：{r.get('task_note') or '篇幅和任务要求不符'}；修改报告第一条写明差多少、缺什么")
    elif r.get("off_task"):
        out.append(f"  偏题（未通过）：{r.get('task_note') or '正文没做任务要求的事'}")
        if r.get("off_task_kind") in ("篇幅", "length"):
            out.append("  只差篇幅：素材确实撑不起的，不凑字，按 SKILL.md 第 6 步加 --short-material 复审")
    if r["valid"] and not r["passed"]:
        for k in r["weakest"]:
            out.append(f"  先改 {zh[k]}：{r['fixes'].get(k, '')}")
    if r.get("templates"):
        out.append(f"  模板问题 {len(r['templates'])} 处（质量影响见六项评分，不按数量单独判退）：" + "；".join(
            f"{t.get('type', '')}「{str(t.get('evidence', ''))[:30]}」" for t in r["templates"]))
    if r.get("devices"):
        out.append(f"  手法重复 {len(r['devices'])} 处（仅提示，按语义和文体判断）：" + "；".join(
            f"{t.get('type', '')}「{str(t.get('evidence', ''))[:30]}」" for t in r["devices"]))
    if r["cliche"]:
        out.append("  套话：" + "；".join(r["cliche"]))
    if f is not None:
        out.append(f"事实核查：{f['claims']} 条，存疑 {len(f['doubts'])} 条"
                   + ("" if f["own"] or not f["doubts"] else "（改的是别人的稿子：存疑项只列进“待作者核对”，正文一字不改）"))
        for c in f["doubts"]:
            out.append(f"  存疑：{c.get('text')}  ——  {c.get('note')}")
    if g is not None:
        scope = "新稿问题" if g.get("new_draft") else "原稿或材料问题"
        comparison = "新稿无原稿比对" if g.get("new_draft") else f"退步 {len(g['regressions'])} 处"
        out.append(f"学术严谨性：{comparison}，{scope} {len(g['issues'])} 条"
                   + (f"；审查无效：{g['void']} 条证据不属于对应全文，需全新评委重审" if g["void"] else ""))
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
    p.add_argument("--genre", required=True, help="文体，如 城市随笔散文、周报、网络问答、课程设计报告")
    p.add_argument("--review", required=True, help="评委子代理返回的 JSON（文件路径）")
    p.add_argument("--facts", help="事实核查子代理返回的 JSON（文件路径）")
    p.add_argument("--own", action="store_true", help="只给题目、没有材料的稿子：事实存疑要改到 0 才算过；不加则存疑项只列给作者")
    p.add_argument("--paper", action="store_true", help="论文模式：按 lunwen-judge 的六项和 3.5 分线判")
    p.add_argument("--original", help="原稿或研究材料文件；论文模式省略时 --rigor 审查新稿")
    p.add_argument("--rigor", help="论文模式：严谨性审查子代理返回的 JSON（文件路径）")
    p.add_argument("--judge-model", help="兼容评委模型身份参数；使用统一写作分数线，不由旧模型校准门槛覆盖")
    p.add_argument("--short-material", action="store_true", help="素材撑不起任务要的篇幅、修改报告已写明：评委只因篇幅判偏题时只提示，不拦")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    if a.rigor and not a.original and not a.paper:
        p.error("--rigor needs --original")
    text = read_any(a.path)
    r = check_review(text, load_json(Path(a.review).read_text(encoding="utf-8")), a.genre, paper=a.paper,
                     model=a.judge_model, short_material=a.short_material)
    f = check_facts(text, load_json(Path(a.facts).read_text(encoding="utf-8")), own=a.own) if a.facts else None
    g = (check_rigor(read_any(a.original) if a.original else "", text, load_json(Path(a.rigor).read_text(encoding="utf-8")))
         if a.rigor else None)
    if a.json:
        print(json.dumps({"review": r, "facts": f, "rigor": g}, ensure_ascii=False, indent=1))
    else:
        print(report(r, f, g))
    return 0 if r["passed"] and (f is None or f["passed"]) and (g is None or g["passed"]) else 1

if __name__ == "__main__":
    sys.exit(main())
