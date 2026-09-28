#!/usr/bin/env python3
# Dev-only: the Ark-API reviewer used for calibration experiments (validate_review.py).
# The plugin itself reviews with fresh Claude subagents (agents/judge.md), see scripts/review_zh.py.
"""Craft review of a Chinese draft by an independent model (literary quality).

The stylometry score (score_zh) can only say whether text looks statistically
like AI output; it cannot say whether the writing is good. This script asks a
different model than the writer to review the draft against a fixed craft
rubric and return, per dimension, a 1-5 score, quoted evidence and a concrete
revision suggestion.

Model: Volcengine Ark (OpenAI-compatible chat API). Key from env ARK_API_KEY.
By default two reviewers (kimi-k3 and deepseek-v4.1-flash) review in parallel
and the stricter result counts; deepseek-v4.1-flash also checks facts. GLM is
not used (it can reason past the 65536-token ceiling without answering). Override with
--models / --factcheck-model. The key is only read at runtime and never stored.

Pass rule (validated in calibration/REVIEW_VALIDATION.md: classic literature
averages 4.5-4.9, a flat guidebook rewrite 2.7 once the genre is given):
- literary genres: average >= 4.0, every dimension >= 3, not flat
- practical / argument: average >= 3.5, every dimension >= 3
The numbers are a gate, not a target: use the evidence and fixes, and stop
once the gate is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ARK_BASE = os.environ.get("SHUOZHONGWEN_REVIEW_BASE", "https://ark.cn-beijing.volces.com/api/plan/v3")
DEFAULT_MODEL = os.environ.get("SHUOZHONGWEN_REVIEW_MODEL", "kimi-k3")
DEFAULT_MODELS = ["kimi-k3", "deepseek-v4.1-flash"]
FACTCHECK_MODEL = "deepseek-v4.1-flash"
LITERARY = ("散文", "游记", "随笔", "小说", "演讲", "书评", "影评", "诗", "故事", "回忆", "文学")

DIMENSIONS = [
    ("concrete", "具体可感", "有没有只属于这篇的细节：看得见的动作、东西、数字、声音、气味，而不是换个题目也能照搬的概括"),
    ("insight", "自己的发现", "有没有作者自己看出来、想明白的东西（一个判断、一处意外、一种态度），而不是百科常识或人人都会说的话"),
    ("language", "语言与意象", "用词是否准确有质感；比喻和意象是新鲜贴切，还是陈词滥调（如“时光隧道”“陈年佳酿”“历史的见证”）；有没有空洞的形容词"),
    ("rhythm", "节奏", "句子长短、语气是否有起伏，读出声是否顺；是否单调得像记流水账，或整齐得像排比文件"),
    ("structure", "结构与张力", "有没有一条主线和推进，详略是否得当，有没有转折、悬念或层次；结尾是留有余味，还是总结、拔高、喊口号"),
    ("voice", "声音", "读得出一个具体的人在说话吗（语气、态度、分寸），还是面目模糊的通用腔"),
]

PROMPT = """你是一位严格的中文文学编辑，审读下面这篇{genre}。只按下列六个维度打分，每项 1–5 分：
5 = 出色，放进优秀的作家文集也不逊色；4 = 好，有明显亮点；3 = 合格但平庸；2 = 明显的毛病；1 = 很差。
打分要严：流畅但空洞、面面俱到但没有自己东西的文字，最多 3 分；辞藻华丽但全是套话的，语言一项给 2 分以下；平铺直叙、像记流水账的，节奏和结构给 2 分以下。

维度：
{dims}

另外判断两件事：
- "flat"：是否写成了白开水（信息都对，但没有细节、没有态度、没有文采）？true/false
- "cliche"：列出文中的陈词滥调或套话原句，最多 8 条

每个维度都要给：score（整数）、evidence（从原文摘一句作证据，没有就写“无”）、fix（一条具体的修改建议，指明改哪里、往什么方向改，不要泛泛而谈）。

只输出 JSON，格式：
{{"scores": {{"concrete": {{"score": 3, "evidence": "...", "fix": "..."}}, ...六项...}}, "flat": false, "cliche": ["..."], "summary": "一句话总评"}}

原文：
<<<
{text}
>>>"""


def ark_key() -> str:
    key = os.environ.get("ARK_API_KEY")
    if key:
        return key
    raise SystemExit("No Ark API key: set ARK_API_KEY")


def _post(body: dict, key: str) -> dict:
    req = urllib.request.Request(ARK_BASE + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(15 * (attempt + 1))
    return {}


def call(model: str, prompt: str, key: str) -> str:
    """Full reasoning, no client-side token limit; retried up to 3 times if no answer came back."""
    base = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
    # No client-side token limit (max_tokens is not sent). Ark still stops a reply at
    # its own ceiling (65536 tokens); if a model reasons all the way there without
    # answering, retry the identical request, never with reduced reasoning.
    for _ in range(3):
        d = _post(base, key)
        content = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if content.strip():
            return content
    return ""


def parse(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("reviewer returned no JSON")
    return json.loads(m.group(0))


def review(text: str, genre: str = "文章", model: str = DEFAULT_MODEL, key: str | None = None) -> dict:
    dims = "\n".join(f"- {k}（{zh}）：{desc}" for k, zh, desc in DIMENSIONS)
    raw = call(model, PROMPT.format(genre=genre, dims=dims, text=text.strip()), key or ark_key())
    data = parse(raw)
    scores = data.get("scores", {})
    vals = [int(scores[k]["score"]) for k, _, _ in DIMENSIONS if k in scores]
    data["average"] = round(sum(vals) / len(vals), 2) if vals else None
    data["weakest"] = [k for k, _, _ in DIMENSIONS if k in scores and int(scores[k]["score"]) <= 2]
    data["model"] = model
    return data


FACT_PROMPT = """你是一名严谨的事实核查编辑。列出下面文字里所有可以核实的事实陈述（人名、地名、年代、数字、因果、归属、传说与史实的区分），逐条判断：
- "ok"：公认属实
- "doubt"：事实错误、常见误传、或说法不准确（说明正确说法）
- "rhetoric"：修辞、夸张、文学化概括（如“拆了两千年”“人人都”），或文中已明确标为传说、据说的内容。这类不算错误
- "unknown"：无法判断
只有真正的事实问题才标 doubt；文学性文字允许修辞，别把修辞当错误。
只输出 JSON：{{"claims": [{{"text": "原文里的说法", "verdict": "ok|doubt|rhetoric|unknown", "note": "简短说明"}}]}}

原文：
<<<
{text}
>>>"""


def factcheck(text: str, model: str = FACTCHECK_MODEL, key: str | None = None) -> dict:
    data = parse(call(model, FACT_PROMPT.format(text=text.strip()), key or ark_key()))
    data["model"] = model
    return data


def gate(genre: str) -> tuple[float, int]:
    return (4.0, 3) if any(g in genre for g in LITERARY) else (3.5, 3)


def review_panel(text: str, genre: str, models: list[str] | None = None, key: str | None = None,
                 with_facts: bool = True) -> dict:
    """Run several reviewers (and a fact check) in parallel; the strictest counts."""
    from concurrent.futures import ThreadPoolExecutor

    models = models or DEFAULT_MODELS
    key = key or ark_key()
    with ThreadPoolExecutor(max_workers=len(models) + 1) as ex:
        futs = {m: ex.submit(review, text, genre, m, key) for m in models}
        ff = ex.submit(factcheck, text, FACTCHECK_MODEL, key) if with_facts else None
        reviews = {}
        for m, f in futs.items():
            try:
                reviews[m] = f.result()
            except Exception as e:  # one reviewer failing must not sink the panel
                reviews[m] = {"error": f"{type(e).__name__}: {e}"}
        facts = None
        if ff:
            try:
                facts = ff.result()
            except Exception as e:
                facts = {"error": f"{type(e).__name__}: {e}"}
    ok = [r for r in reviews.values() if "error" not in r]
    avg_min, dim_min = gate(genre)
    dims = {k: min(int(r["scores"][k]["score"]) for r in ok if k in r["scores"]) for k, _, _ in DIMENSIONS
            if all(k in r["scores"] for r in ok)} if ok else {}
    strict_avg = min(r["average"] for r in ok) if ok else None
    flat = any(r.get("flat") for r in ok)
    doubts = [c for c in (facts or {}).get("claims", []) if c.get("verdict") == "doubt"]
    complete = len(ok) == len(models) and facts is not None and "error" not in (facts or {"error": 1}) if with_facts else len(ok) == len(models)
    passed = complete and strict_avg >= avg_min and all(v >= dim_min for v in dims.values()) and not flat and not doubts
    return {"genre": genre, "gate": {"average": avg_min, "each": dim_min}, "passed": passed, "complete": complete,
            "strict_average": strict_avg, "strict_dims": dims, "flat": flat,
            "reviews": reviews, "facts": facts, "fact_doubts": doubts}


def print_panel(p: dict) -> None:
    zh = {k: z for k, z, _ in DIMENSIONS}
    for m, r in p["reviews"].items():
        if "error" in r:
            print(f"=== {m}：调用失败 {r['error']}")
            continue
        print_human(r)
        print()
    if p.get("facts") and "error" in p["facts"]:
        print(f"=== 事实核查：调用失败 {p['facts']['error']}")
    if p.get("facts") and "error" not in p["facts"]:
        print(f"=== 事实核查（{p['facts']['model']}）：{len(p['facts'].get('claims', []))} 条，存疑 {len(p['fact_doubts'])} 条")
        for c in p["fact_doubts"]:
            print(f"    存疑：{c.get('text')}  ——  {c.get('note')}")
    g = p["gate"]
    dims = "、".join(f"{zh[k]} {v}" for k, v in p["strict_dims"].items())
    print()
    print(f"结论（按最严的评审）：平均 {p['strict_average']}（要求 ≥{g['average']}），各项 {dims}（要求都 ≥{g['each']}），"
          f"白开水：{'是' if p['flat'] else '否'}，事实存疑：{len(p['fact_doubts'])} 条")
    if not p["complete"]:
        print("未通过：有评审或事实核查没跑成，结论无效，重跑一次")
        return
    print("通过" if p["passed"] else "未通过：照上面的证据和改法改最弱的几项，事实存疑的先核实或删掉")


def print_human(r: dict) -> None:
    zh = {k: z for k, z, _ in DIMENSIONS}
    print(f"=== 写作质量评审（{r['model']}）：平均 {r['average']} / 5 ===")
    for k, _, _ in DIMENSIONS:
        s = r["scores"].get(k)
        if not s:
            continue
        print(f"{zh[k]}：{s['score']}  证据：{s.get('evidence', '')}")
        print(f"    改法：{s.get('fix', '')}")
    if r.get("flat"):
        print("白开水：是（信息都在，但没有细节、态度和文采）")
    if r.get("cliche"):
        print("套话：" + "；".join(r["cliche"]))
    print("总评：" + r.get("summary", ""))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    p.add_argument("--genre", default="文章", help="文体，如 游记散文、周报、小说片段、评论（一定要给，决定审读标准）")
    p.add_argument("--models", default=",".join(DEFAULT_MODELS), help="评审模型，逗号分隔")
    p.add_argument("--no-factcheck", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    panel = review_panel(Path(a.path).read_text(encoding="utf-8"), a.genre,
                         [m.strip() for m in a.models.split(",") if m.strip()], with_facts=not a.no_factcheck)
    if a.json:
        print(json.dumps(panel, ensure_ascii=False, indent=1))
    else:
        print_panel(panel)
    return 0 if panel["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
