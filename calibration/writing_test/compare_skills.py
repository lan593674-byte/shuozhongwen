"""Compare the final texts of several writing skills on the same topics.

For every topic in <dir>/topics.json, each skill wrote out/<skill>/<topic>/final.txt.
This script:

1. scores every final with every judge model several times (agents/judge.md,
   genre and task given) and applies each model's pass line;
2. compares every pair of skills blind, per topic and judge, in both orders;
3. runs polish_check.py and lists numbers not in the material.
Replies are cached in out/eval_cache.json (shared format with evaluate.py); writes RESULTS.md.

Usage: python calibration/writing_test/compare_skills.py --dir calibration/writing_test/round3 \
         --skills shuozhongwen,humanizer,research --names 说中文,Humanizer-zh,research-writing \
         --models deepseek-v4-pro,glm-5.3,kimi-k3 [--repeats 3] [--limit kimi-k3=2]
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import evaluate as ev  # same folder: judge calls, cache, per-model limits

judge_api, judge_config, polish_check, review_zh = ev.judge_api, ev.judge_config, ev.polish_check, ev.review_zh


def pair_job(cache, cfg, model, topic, order, a, b):
    """Blind comparison of skills a and b; order AB puts a first."""
    key = f"pair|{model}|{topic}|{a}~{b}|{order}"
    if key in cache and cache[key].get("winner"):
        return
    ta, tb = ev.text_of(a, topic, "final"), ev.text_of(b, topic, "final")
    if not ta or not tb:
        return
    first, second = (ta, tb) if order == "AB" else (tb, ta)
    user = f"任务：{ev.TOPICS[topic]['task']}\n\n稿子 A：\n<<<\n{first}\n>>>\n\n稿子 B：\n<<<\n{second}\n>>>"
    try:
        with ev.slot(model):
            raw = judge_api.chat(ev.PAIR_SYSTEM, user, model, cfg["base"], cfg["key"], cfg["timeout"])
        d = review_zh.load_json(raw)
        pick = str(d.get("better", "")).strip().upper()[:1]
        if pick not in ("A", "B"):
            raise ValueError(f"bad answer {d.get('better')!r}")
        winner = (a if pick == "A" else b) if order == "AB" else (b if pick == "A" else a)
        val = {"winner": winner, "margin": d.get("margin", ""), "reason": d.get("reason", "")}
    except Exception as error:
        val = {"winner": None, "error": f"{type(error).__name__}: {str(error)[:200]}"}
    ev.save(cache, key, val)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", required=True)
    p.add_argument("--skills", required=True, help="out/ 下的目录名，逗号分隔")
    p.add_argument("--names", help="报告里显示的名字，和 --skills 一一对应")
    p.add_argument("--models", required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit", action="append", default=[])
    a = p.parse_args()
    ev.BASE = Path(a.dir).resolve()
    ev.TOPICS = json.loads((ev.BASE / "topics.json").read_text(encoding="utf-8"))
    ev.OUT, ev.CACHE = ev.BASE / "out", ev.BASE / "out" / "eval_cache.json"
    for item in a.limit:
        name, _, n = item.partition("=")
        ev._slots[name] = threading.Semaphore(int(n))
    skills = [s.strip() for s in a.skills.split(",")]
    names = dict(zip(skills, [n.strip() for n in a.names.split(",")] if a.names else skills))
    models = [m.strip() for m in a.models.split(",")]
    topics = ev.TOPICS
    cfg = judge_config.resolve("judge")
    cache = ev.load_cache()
    pairs = list(itertools.combinations(skills, 2))
    jobs = [(ev.score_job, (cache, cfg, m, s, t, "final", k)) for m in models for s in skills for t in topics
            for k in range(a.repeats)]
    jobs += [(pair_job, (cache, cfg, m, t, o, x, y)) for m in models for t in topics for x, y in pairs
             for o in ("AB", "BA")]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(lambda j: j[0](*j[1]), jobs))

    def passed(v, model, topic):
        line, each, _ = review_zh.gate(topics[topic]["genre"], model)
        return (v["average"] >= line and all(x >= each for x in v["dims"].values()) and not v["flat"]
                and not v["off_task"] and len(v["templates"]) <= review_zh.MAX_TEMPLATES)

    def got(model, skill, topic):
        vals = [cache.get(f"score|{model}|{skill}|{topic}|final|{k}", {}) for k in range(a.repeats)]
        return [v for v in vals if v.get("average") is not None and v.get("valid")]

    lines = [f"# 写作技能对比：{'、'.join(names.values())}", "",
             f"五个题目，每个技能按自己的流程从头写（改稿题从同一份原稿改起），只比终稿。{len(models)} 个评委模型"
             f"（{'、'.join(models)}）按 `agents/judge.md` 各打 {a.repeats} 次分（给了文体和任务）；"
             "盲评对比把两个技能的终稿放在一起问哪篇更好，A、B 两种顺序各问一次。", "",
             "## 评委打分（六项平均，几次取均值；括号里是单次审读的过线比例）", "",
             "| 题目 | " + " | ".join(f"{names[s]}" for s in skills) + " |", "|---|" + "---|" * len(skills)]
    total = {s: [] for s in skills}
    for t, info in topics.items():
        cells = []
        for s in skills:
            vs = [v for m in models for v in got(m, s, t)]
            ok = [passed(v, m, t) for m in models for v in got(m, s, t)]
            total[s] += [v["average"] for v in vs]
            cells.append(f"{statistics.mean(v['average'] for v in vs):.2f}（{sum(ok) / len(ok):.0%}）" if vs else "-")
        lines.append(f"| {t} {info['short']} | " + " | ".join(cells) + " |")
    lines.append("| 全部平均 | " + " | ".join(f"{statistics.mean(total[s]):.2f}" if total[s] else "-" for s in skills) + " |")
    lines += ["", "分评委的全部平均：", "", "| 评委 | " + " | ".join(names[s] for s in skills) + " |",
              "|---|" + "---|" * len(skills)]
    for m in models:
        lines.append(f"| {m} | " + " | ".join(
            f"{statistics.mean(v['average'] for t in topics for v in got(m, s, t)):.2f}" if any(got(m, s, t) for t in topics) else "-"
            for s in skills) + " |")

    wins = {s: 0 for s in skills}
    firm = {s: 0 for s in skills}
    lines += ["", "## 盲评对比", "", f"每题每对 {len(models) * 2} 票。“稳胜”只算同一评委两种顺序都判它更好的。", "",
              "| 题目 | 对比 | 票数 | 稳胜 |", "|---|---|---|---|"]
    a_first = n_votes = 0
    for t, info in topics.items():
        for x, y in pairs:
            v = {x: 0, y: 0}
            f = {x: 0, y: 0}
            for m in models:
                ab = cache.get(f"pair|{m}|{t}|{x}~{y}|AB", {}).get("winner")
                ba = cache.get(f"pair|{m}|{t}|{x}~{y}|BA", {}).get("winner")
                for o, w in (("AB", ab), ("BA", ba)):
                    if w:
                        v[w] += 1
                        n_votes += 1
                        a_first += w == (x if o == "AB" else y)
                if ab and ab == ba:
                    f[ab] += 1
            for s in (x, y):
                wins[s] += v[s]
                firm[s] += f[s]
            lines.append(f"| {t} | {names[x]} 对 {names[y]} | {v[x]} : {v[y]} | {f[x]} : {f[y]} |")
    lines += ["", "合计（所有对比里赢下的票数 / 稳胜次数）：", "", "| 技能 | 票数 | 稳胜 |", "|---|---|---|"]
    lines += [f"| {names[s]} | {wins[s]} | {firm[s]} |" for s in skills]
    lines += ["", f"位置偏好：{n_votes} 票里有 {a_first} 票选了排在前面的那篇。", ""]

    lines += ["## 机器检查", "", "| 题目 | 技能 | 字数 | polish_check | AI 相似度 | 套在词上的引号 | 材料里没有的数字 |",
              "|---|---|---|---|---|---|---|"]
    for t in topics:
        for s in skills:
            txt = ev.text_of(s, t, "final")
            if not txt:
                continue
            r = polish_check.check(txt)
            sc = r["style"]["score"]
            lines.append(f"| {t} | {names[s]} | {len(txt)} | {'通过' if r['passed'] else '未通过'} | "
                         f"{'-' if sc is None else f'{sc:.2f}'} | {len(r['structure']['quotes'])} | "
                         f"{'、'.join(ev.stray_numbers(t, txt)) or '无'} |")
    lines += ["", "## 评委的盲评理由", ""]
    for t, info in topics.items():
        lines.append(f"**{t} {info['short']}**")
        for x, y in pairs:
            for m in models:
                for o in ("AB", "BA"):
                    r = cache.get(f"pair|{m}|{t}|{x}~{y}|{o}", {})
                    if r.get("winner"):
                        lines.append(f"- {names[x]} 对 {names[y]}，{m}（{o}）：{names[r['winner']]}{r.get('margin', '')}更好。{r.get('reason', '')}")
        lines.append("")
    lines += ["## 全文", ""]
    for t, info in topics.items():
        lines += [f"### {t} {info['short']}", "", f"任务：{info['task']}", ""]
        for s in skills:
            txt = ev.text_of(s, t, "final")
            if txt:
                lines += [f"#### {names[s]}", "", txt, ""]
    (ev.BASE / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    fails = [k for k, v in cache.items() if (k.startswith("score") and v.get("average") is None) or
             (k.startswith("pair") and not v.get("winner"))]
    print(f"wrote {ev.BASE / 'RESULTS.md'}; failed calls: {len(fails)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
