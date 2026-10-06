"""Calibrate the pass line of each judge model on texts of known quality.

Judges are noisy (one draft scored 3.5, 3.17 and 2.83 by three fresh judges)
and differ in strictness, so one fixed line (4.0 literary, 3.5 otherwise) is
too strict for one model and too lax for another. This script has every judge
model review the same reference texts several times with the current rubric
(agents/judge.md) and sets each model's line from how that model scores human
writing:

- literary line: from public-domain classics (calibration/human, 散文和小说片段)
- practical / argument line: from high-upvote Zhihu answers written before 2020
- line = the 25th percentile of that group's per-text mean score, rounded down
  to 0.25 and kept within [3.0, 4.0]: three in four published human texts of
  that kind pass on a single review by that model.
AI samples (calibration/ai) are reviewed too, to show how many of them would
pass under the new line.

Writes scripts/judge_thresholds.json (read by review_zh.py) and
calibration/JUDGE_CALIBRATION.md. Raw replies are cached in
calibration/raw/judge_calibration.json (not committed), so a rerun only makes
the calls that are missing.

Usage:
  python calibration/calibrate_judge.py --models deepseek-v4-pro,glm-5.3,kimi-k3 [--repeats 3]
The API base and key come from scripts/judge_config.py (~/.shuozhongwen/judge.json).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import judge_api  # noqa: E402
import judge_config  # noqa: E402
import review_zh  # noqa: E402

RAW = HERE / "raw" / "judge_calibration.json"
OUT_JSON = ROOT / "scripts" / "judge_thresholds.json"
OUT_MD = HERE / "JUDGE_CALIBRATION.md"
NOVELS = ("孔乙己", "故鄉", "祝福", "一件小事", "社戲", "呼蘭河傳")
AI_GENRE = {"essay": "散文", "fiction": "小说", "speech": "演讲稿", "comment": "评论", "polemic": "议论文",
            "answer": "知乎回答", "qa": "知乎回答", "review": "书评影评", "wechat": "公众号文章",
            "work": "工作周报或方案", "news": "新闻稿", "student": "学生作文", "copy": "广告文案", "social": "社交媒体帖子"}
GROUPS = ("经典名作", "知乎高赞", "AI 样本")
_lock = threading.Lock()


def excerpt(text: str, lo: int = 700, hi: int = 1400) -> str | None:
    """First run of whole paragraphs between lo and hi characters, skipping a short opening."""
    paras = [p.strip() for p in text.splitlines() if p.strip()]
    for start in range(min(len(paras), 6)):
        buf = ""
        for p in paras[start:]:
            if len(buf) + len(p) > hi and len(buf) >= lo:
                break
            buf += p + "\n\n"
            if len(buf) >= hi:
                break
        if lo <= len(buf) <= hi + 400:
            return buf.strip()
    return None


def samples(seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    out = []
    classics = sorted(f for f in (HERE / "human").glob("*.txt") if not f.name.startswith(("zhihu", "qidian", "tieba")))
    rng.shuffle(classics)
    for f in classics:
        t = excerpt(f.read_text(encoding="utf-8"))
        if t and sum(s["group"] == "经典名作" for s in out) < 10:
            genre = "小说片段" if any(n in f.stem for n in NOVELS) else "散文"
            out.append({"id": f.stem, "group": "经典名作", "genre": genre, "text": t})
    zhihu = sorted((HERE / "human").glob("zhihu_*.txt"))
    rng.shuffle(zhihu)
    for f in zhihu:
        t = excerpt(f.read_text(encoding="utf-8"))
        if t and sum(s["group"] == "知乎高赞" for s in out) < 12:
            out.append({"id": f.stem, "group": "知乎高赞", "genre": "知乎回答", "text": t})
    ai = sorted((HERE / "ai").glob("*__*.txt"))
    rng.shuffle(ai)
    seen_models: dict[str, int] = {}
    for f in ai:
        model, prompt = f.stem.split("__", 1)
        kind = prompt.split("_")[1] if prompt.startswith("p") else prompt.split("_")[0]
        if kind not in AI_GENRE or seen_models.get(model, 0) >= 2:
            continue
        t = f.read_text(encoding="utf-8").strip()
        if 400 <= len(t) <= 2200 and sum(s["group"] == "AI 样本" for s in out) < 12:
            seen_models[model] = seen_models.get(model, 0) + 1
            out.append({"id": f.stem, "group": "AI 样本", "genre": AI_GENRE[kind], "text": t})
    return out


def literary(genre: str) -> bool:
    return any(g in genre for g in review_zh.LITERARY)


def run_one(s: dict, model: str, rep: int, base: str, key: str | None, timeout: int, cache: dict) -> None:
    k = f"{model}|{s['id']}|{rep}"
    if k in cache and cache[k].get("average") is not None:
        return
    try:
        raw = judge_api.chat(judge_api.rubric("judge"), judge_api.prompt("judge", s["text"], s["genre"]),
                             model, base, key, timeout)
        r = review_zh.check_review(s["text"], review_zh.load_json(raw), s["genre"])
        res = {"average": r["average"], "valid": r["valid"], "dims": r["dims"], "flat": r["flat"],
               "templates": len(r["templates"]), "devices": len(r["devices"])}
    except Exception as error:  # keep going; the summary counts failures
        res = {"average": None, "error": f"{type(error).__name__}: {str(error)[:200]}"}
    with _lock:
        cache[k] = res
        RAW.parent.mkdir(parents=True, exist_ok=True)
        RAW.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def pctile(values: list[float], q: float) -> float:
    v = sorted(values)
    if not v:
        return float("nan")
    i = (len(v) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def line_from(values: list[float]) -> float:
    return min(4.0, max(3.0, int(pctile(values, 0.25) * 4) / 4))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", required=True, help="逗号分隔的评委模型")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--workers", type=int, default=12)
    a = p.parse_args()
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    r = judge_config.resolve("judge")
    cache = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else {}
    items = samples()
    jobs = [(s, m, k) for s in items for m in models for k in range(a.repeats)]
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(lambda j: run_one(*j, r["base"], r["key"], r["timeout"], cache), jobs))

    thresholds = {"calibrated": str(date.today()), "rubric": "agents/judge.md", "repeats": a.repeats,
                  "rule": "每个模型的分数线 = 该模型给同类人类文字（文学：经典名作；实用和议论：知乎高赞）每篇平均分的第 25 百分位，"
                          "向下取到 0.25，限制在 3.0 到 4.0 之间；每项最低分仍是 3",
                  "default": {"literary": {"average": 4.0, "each": 3}, "practical": {"average": 3.5, "each": 3}},
                  "models": {}}
    md = ["# 评委分数线校准", "",
          f"日期：{date.today()}。脚本：`python calibration/calibrate_judge.py --models {','.join(models)} --repeats {a.repeats}`。"
          f"评分标准是当前的 `agents/judge.md`。经典名作 {sum(s['group'] == '经典名作' for s in items)} 段、"
          f"知乎高赞 {sum(s['group'] == '知乎高赞' for s in items)} 段、AI 样本 {sum(s['group'] == 'AI 样本' for s in items)} 篇，"
          f"每个模型每篇各评 {a.repeats} 次。", "",
          "## 各组平均分（六项平均，每篇先取几次的均值）", "",
          "| 模型 | " + " | ".join(GROUPS) + " | 同一篇几次评分的标准差 | 失败调用 |", "|---|" + "---|" * (len(GROUPS) + 2)]
    detail = []
    for m in models:
        per_text: dict[str, list[float]] = {}
        sds, fails = [], 0
        mins: dict[str, list[int]] = {}
        for s in items:
            got = [cache.get(f"{m}|{s['id']}|{k}", {}) for k in range(a.repeats)]
            fails += sum(1 for g in got if g.get("average") is None)
            avgs = [g["average"] for g in got if g.get("average") is not None and g.get("valid")]
            if avgs:
                per_text[s["id"]] = avgs
                mins[s["id"]] = [min(g["dims"].values()) for g in got if g.get("dims")]
                if len(avgs) > 1:
                    sds.append(statistics.pstdev(avgs))
        by_group = {g: [statistics.mean(per_text[s["id"]]) for s in items if s["group"] == g and s["id"] in per_text]
                    for g in GROUPS}
        sd = statistics.mean(sds) if sds else 0.0
        md.append(f"| {m} | " + " | ".join(f"{statistics.mean(v):.2f}（{min(v):.2f}–{max(v):.2f}）" if v else "-"
                                          for v in by_group.values()) + f" | {sd:.2f} | {fails} |")
        lit = line_from(by_group["经典名作"]) if by_group["经典名作"] else 4.0
        prac = line_from(by_group["知乎高赞"]) if by_group["知乎高赞"] else 3.5
        thresholds["models"][m] = {"literary": {"average": lit, "each": 3}, "practical": {"average": prac, "each": 3},
                                   "noise_sd": round(sd, 2)}

        def single_pass(group: str) -> str:
            ok = n = 0
            for s in items:
                if s["group"] != group:
                    continue
                line = lit if literary(s["genre"]) else prac
                for k in range(a.repeats):
                    g = cache.get(f"{m}|{s['id']}|{k}", {})
                    if g.get("average") is None or not g.get("valid"):
                        continue
                    n += 1
                    ok += (g["average"] >= line and min(g["dims"].values()) >= 3 and not g["flat"]
                           and g["templates"] <= review_zh.MAX_TEMPLATES)
            return f"{ok / n:.0%}" if n else "-"

        def old_pass(group: str) -> str:
            ok = n = 0
            for s in items:
                if s["group"] != group:
                    continue
                line = 4.0 if literary(s["genre"]) else 3.5
                for k in range(a.repeats):
                    g = cache.get(f"{m}|{s['id']}|{k}", {})
                    if g.get("average") is None or not g.get("valid"):
                        continue
                    n += 1
                    ok += (g["average"] >= line and min(g["dims"].values()) >= 3 and not g["flat"]
                           and g["templates"] <= review_zh.MAX_TEMPLATES)
            return f"{ok / n:.0%}" if n else "-"

        detail.append(f"| {m} | {lit} | {prac} | " + " | ".join(f"{old_pass(g)} → {single_pass(g)}" for g in GROUPS) + " |")
    md += ["", "## 分数线和单次审读的通过率", "",
           "分数线按每个模型自己的打分习惯定：" + thresholds["rule"] + "。通过率按单次审读算（分数、每项 ≥ 3、不是白开水、模板腔 ≤ 1 处都要满足），"
           "箭头左边是旧的固定分数线（文学 4.0、其他 3.5），右边是校准后的分数线。", "",
           "| 模型 | 文学分数线 | 实用和议论分数线 | " + " | ".join(f"{g}通过率" for g in GROUPS) + " |",
           "|---|---|---|" + "---|" * len(GROUPS)] + detail
    md += ["", "没校准过的评委（比如 Claude Code 里的子代理）仍用固定分数线：文学 4.0、实用和议论 3.5。"
           "换评委模型或改了评分标准，重跑这个脚本；`scripts/judge_thresholds.json` 会跟着更新。", ""]
    OUT_JSON.write_text(json.dumps(thresholds, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
