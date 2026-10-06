"""Compare two versions of the skill on the same writing tasks.

For every topic in topics/ the writer produced, with each version, a first draft
(draft1.txt, saved before any check or review) and a final text (final.txt) in
out/<version>/<topic>/. This script:

1. scores every text with every judge model several times (agents/judge.md of
   the current version, genre and task given), and applies each model's
   calibrated pass line (scripts/judge_thresholds.json);
2. asks every judge model which of the two versions is better, blind, for the
   first drafts and for the finals, in both orders (A/B and B/A);
3. runs polish_check.py and counts word quotes;
4. lists numbers in the text that are not in the material (fidelity).
Raw replies are cached in out/eval_cache.json; writes RESULTS.md.

Usage: python calibration/writing_test/evaluate.py --models m1,m2,m3 [--repeats 3] [--versions old,new]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import judge_api  # noqa: E402
import judge_config  # noqa: E402
import polish_check  # noqa: E402
import review_zh  # noqa: E402

TOPICS = json.loads((HERE / "topics.json").read_text(encoding="utf-8"))
OUT = HERE / "out"
CACHE = OUT / "eval_cache.json"
_lock = threading.Lock()
PAIR_SYSTEM = """你是一位资深中文编辑。你会收到一个写作任务和同一任务的两篇稿子 A、B。按发给真实读者的成稿标准比较两篇：
是否完成了任务要求；内容是否具体、准确、取舍得当；语言是否自然，有没有 AI 腔、套话、模板句、给普通词乱加引号；结构和节奏好不好。
不要因为篇幅长就偏向哪一篇。只输出一个 JSON，不要任何别的文字：
{"better": "A 或 B", "margin": "明显 或 略微", "reason": "一两句理由"}"""


def load_cache() -> dict:
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def save(cache: dict, key: str, value) -> None:
    with _lock:
        cache[key] = value
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def text_of(version: str, topic: str, stage: str) -> str | None:
    p = OUT / version / topic / f"{stage}.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def score_job(cache, cfg, model, version, topic, stage, rep):
    key = f"score|{model}|{version}|{topic}|{stage}|{rep}"
    if key in cache and cache[key].get("average") is not None:
        return
    t = text_of(version, topic, stage)
    if not t:
        return
    info = TOPICS[topic]
    raw = ""
    try:
        raw = judge_api.chat(judge_api.rubric("judge"), judge_api.prompt("judge", t, info["genre"], task=info["task"]),
                             model, cfg["base"], cfg["key"], cfg["timeout"])
        r = review_zh.check_review(t, review_zh.load_json(raw), info["genre"], model=model)
        val = {"average": r["average"], "valid": r["valid"], "passed": r["passed"], "dims": r["dims"],
               "flat": r["flat"], "off_task": r["off_task"], "templates": [x.get("type") for x in r["templates"]],
               "devices": [x.get("type") for x in r["devices"]], "summary": r["summary"]}
    except Exception as error:
        val = {"average": None, "error": f"{type(error).__name__}: {str(error)[:200]}", "raw": raw[:4000]}
    save(cache, key, val)


def pair_job(cache, cfg, model, topic, stage, order, a_ver, b_ver):
    key = f"pair|{model}|{topic}|{stage}|{order}"
    if key in cache and cache[key].get("winner"):
        return
    ta, tb = text_of(a_ver, topic, stage), text_of(b_ver, topic, stage)
    if not ta or not tb:
        return
    first, second = (ta, tb) if order == "AB" else (tb, ta)
    user = f"任务：{TOPICS[topic]['task']}\n\n稿子 A：\n<<<\n{first}\n>>>\n\n稿子 B：\n<<<\n{second}\n>>>"
    try:
        d = review_zh.load_json(judge_api.chat(PAIR_SYSTEM, user, model, cfg["base"], cfg["key"], cfg["timeout"]))
        pick = str(d.get("better", "")).strip().upper()[:1]
        if pick not in ("A", "B"):
            raise ValueError(f"bad answer {d.get('better')!r}")
        winner = (a_ver if pick == "A" else b_ver) if order == "AB" else (b_ver if pick == "A" else a_ver)
        val = {"winner": winner, "margin": d.get("margin", ""), "reason": d.get("reason", "")}
    except Exception as error:
        val = {"winner": None, "error": f"{type(error).__name__}: {str(error)[:200]}"}
    save(cache, key, val)


NUM = re.compile(r"\d+(?:\.\d+)?")


def stray_numbers(topic: str, text: str) -> list[str]:
    mat = HERE / "topics" / topic / "material.md"
    if not mat.exists():
        return []
    have = set(NUM.findall(mat.read_text(encoding="utf-8")))
    return sorted({n for n in NUM.findall(text) if n not in have})


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--versions", default="old,new")
    p.add_argument("--workers", type=int, default=12)
    a = p.parse_args()
    models = [m.strip() for m in a.models.split(",")]
    v_old, v_new = [v.strip() for v in a.versions.split(",")]
    cfg = judge_config.resolve("judge")
    cache = load_cache()
    stages = ("draft1", "final")
    jobs = [(score_job, (cache, cfg, m, v, t, s, k)) for m in models for v in (v_old, v_new)
            for t in TOPICS for s in stages for k in range(a.repeats)]
    jobs += [(pair_job, (cache, cfg, m, t, s, o, v_old, v_new)) for m in models for t in TOPICS
             for s in stages for o in ("AB", "BA")]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(lambda j: j[0](*j[1]), jobs))

    lines = ["# 写作对照测试：旧版（3.6.4）和新版", ""]
    lines += ["五个题目，新旧两版各自按自己的 SKILL.md 从头写：初稿（写完、任何检查和审读之前存下）和终稿（走完整个流程）。"
              f"打分用新版评分标准（`agents/judge.md`，给了文体和任务），{len(models)} 个评委模型各评 {a.repeats} 次；"
              "盲评对比把两版放在一起问哪篇更好，A、B 两种顺序各问一次。", ""]

    def passed(v, model, topic):
        # recomputed with the current pass lines, so a recalibration needs no new calls
        line, each, _ = review_zh.gate(TOPICS[topic]["genre"], model)
        return (v["average"] >= line and all(x >= each for x in v["dims"].values()) and not v["flat"]
                and not v["off_task"] and len(v["templates"]) <= review_zh.MAX_TEMPLATES)

    def avg(model, ver, topic, stage):
        vals = [cache.get(f"score|{model}|{ver}|{topic}|{stage}|{k}", {}) for k in range(a.repeats)]
        got = [v["average"] for v in vals if v.get("average") is not None and v.get("valid")]
        passes = [passed(v, model, topic) for v in vals if v.get("average") is not None and v.get("valid")]
        return (statistics.mean(got) if got else None), (sum(passes) / len(passes) if passes else None)

    for stage, title in (("draft1", "初稿"), ("final", "终稿")):
        lines += [f"## {title}：评委打分（六项平均，几次取均值；括号里是单次审读的过线比例）", "",
                  "| 题目 | " + " | ".join(f"{m} 旧 → 新" for m in models) + " |", "|---|" + "---|" * len(models)]
        tot = {v: [] for v in (v_old, v_new)}
        for t, info in TOPICS.items():
            cells = []
            for m in models:
                (ao, po), (an, pn) = avg(m, v_old, t, stage), avg(m, v_new, t, stage)
                if ao is not None:
                    tot[v_old].append(ao)
                if an is not None:
                    tot[v_new].append(an)
                fmt = lambda x, q: "-" if x is None else f"{x:.2f}（{q:.0%}）"  # noqa: E731
                cells.append(f"{fmt(ao, po)} → {fmt(an, pn)}")
            lines.append(f"| {t} {info['short']} | " + " | ".join(cells) + " |")
        if tot[v_old] and tot[v_new]:
            lines += ["", f"全部平均：旧版 {statistics.mean(tot[v_old]):.2f}，新版 {statistics.mean(tot[v_new]):.2f}。", ""]
        wins = {v_old: 0, v_new: 0}
        rows = []
        for t, info in TOPICS.items():
            w = {v_old: 0, v_new: 0}
            for m in models:
                for o in ("AB", "BA"):
                    r = cache.get(f"pair|{m}|{t}|{stage}|{o}", {})
                    if r.get("winner"):
                        w[r["winner"]] += 1
                        wins[r["winner"]] += 1
            rows.append(f"| {t} {info['short']} | {w[v_old]} | {w[v_new]} |")
        lines += [f"## {title}：盲评对比（每题 {len(models) * 2} 票）", "", "| 题目 | 旧版胜 | 新版胜 |", "|---|---|---|"] + rows
        lines += [f"| 合计 | {wins[v_old]} | {wins[v_new]} |", ""]

    lines += ["## 机器检查", "", "| 题目 | 版本 | 稿 | 字数 | polish_check | AI 相似度 | 套在词上的引号 | 材料里没有的数字 |",
              "|---|---|---|---|---|---|---|---|"]
    for t, info in TOPICS.items():
        for v in (v_old, v_new):
            for s in stages:
                txt = text_of(v, t, s)
                if not txt:
                    continue
                r = polish_check.check(txt)
                sc = r["style"]["score"]
                lines.append(f"| {t} | {v} | {'初稿' if s == 'draft1' else '终稿'} | {len(txt)} | "
                             f"{'通过' if r['passed'] else '未通过'} | {'-' if sc is None else f'{sc:.2f}'} | "
                             f"{len(r['structure']['quotes'])} | {'、'.join(stray_numbers(t, txt)) or '无'} |")
    lines += ["", "## 评委的盲评理由（终稿）", ""]
    for t, info in TOPICS.items():
        lines.append(f"**{t} {info['short']}**")
        for m in models:
            for o in ("AB", "BA"):
                r = cache.get(f"pair|{m}|{t}|final|{o}", {})
                if r.get("winner"):
                    lines.append(f"- {m}（{o}）：{'新版' if r['winner'] == v_new else '旧版'}{r.get('margin', '')}更好。{r.get('reason', '')}")
        lines.append("")
    lines += ["## 全文", ""]
    for t, info in TOPICS.items():
        lines += [f"### {t} {info['short']}", "", f"任务：{info['task']}", ""]
        for v in (v_old, v_new):
            for s in stages:
                txt = text_of(v, t, s)
                if txt:
                    lines += [f"#### {'旧版' if v == v_old else '新版'}{'初稿' if s == 'draft1' else '终稿'}", "", txt, ""]
    (HERE / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    fails = [k for k, v in cache.items() if (v.get("average") is None and k.startswith("score")) or
             (k.startswith("pair") and not v.get("winner"))]
    print(f"wrote {HERE / 'RESULTS.md'}; failed calls: {len(fails)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
