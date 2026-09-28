"""Fit scripts/zh_model.json from calibration/human and calibration/ai.

- Both classes are cut into 250–900 Han-character chunks at paragraph boundaries;
  each chunk keeps its source file as its group.
- Phrase markers (from the skill's symptom dictionary) that fire at least as often per 1000
  characters in human text as in AI text are excluded.
- Standardized features -> L2 logistic regression with class weights.
- Reported accuracy is grouped 10-fold (whole files held out) plus leave-one-model-out.
- Tiers: 'high' = 95th percentile of held-out human scores (≈5% human false
  positives), 'medium' = 80th percentile.
Writes scripts/zh_model.json and calibration/RESULTS.md.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import score_zh  # noqa: E402
from haohao_markers import load_markers  # noqa: E402

CAL = ROOT / "calibration"
FEATURES = score_zh.FEATURES
# Allowed weight direction per feature (+1: higher means more AI-like, -1: lower
# means more AI-like, 0: reported only). A feature gets a sign only when AI text
# differs from BOTH human groups (classics and pre-2020 Zhihu) in that direction;
# clauses_per_sent and connector_para_lead fail that test and never count.
SIGNS = {"sent_cv": -1, "para_cv": -1, "clauses_per_sent": 0, "connector_per_k": -1,
         "connector_para_lead": 0, "start_repeat": -1, "format_ratio": 1,
         "bigram_mattr": 1, "marker_per_k": 1, "we_per_k": 1, "de_per_k": -1,
         "colon_per_k": 1, "closer": 1, "i_per_k": -1, "quote_per_k": 1,
         "ellipsis_per_k": -1, "exclaim_per_k": -1, "question_per_k": -1, "dash_per_k": -1}


SIZES = (250, 400, 600, 850)  # rotating chunk sizes, same for both classes
PARA = chr(10) * 2
MAX_CHUNKS = 6  # per source file, so one very long text cannot dominate


def chunks(text: str, start: int = 0) -> list[str]:
    """Cut text at paragraph boundaries into chunks whose target length rotates
    through SIZES, so both classes cover the reply lengths the hook scores."""
    out, buf, n, k = [], [], 0, start
    for p in [p for p in text.splitlines() if p.strip()]:
        buf.append(p)
        n += score_zh.han_len(p)
        if n >= SIZES[k % len(SIZES)]:
            out.append(PARA.join(buf))
            buf, n, k = [], 0, k + 1
    if n >= SIZES[0]:
        out.append(PARA.join(buf))
    return out


def source_kind(stem: str, y: int) -> str:
    if y:
        return stem.split("__")[0]  # model name
    if stem.startswith("zhihu_"):
        return "知乎回答"
    if stem.startswith("qidian_"):
        return "起点网文"
    if stem.startswith("tieba_"):
        return "贴吧文章"
    return "经典名作"


def rejected() -> set[str]:
    """File stems dropped in manual review (calibration/rejected.txt)."""
    f = CAL / "rejected.txt"
    if not f.exists():
        return set()
    return {ln.split()[0] for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}


def load() -> list[tuple[str, int, str, str]]:
    rows = []
    skip = rejected()
    for y, d in ((0, "human"), (1, "ai")):
        for i, f in enumerate(f for f in sorted((CAL / d).glob("*.txt")) if f.stem not in skip):
            for c in chunks(f.read_text(encoding="utf-8"), start=i)[:MAX_CHUNKS]:
                rows.append((c, y, f.stem, source_kind(f.stem, y)))
    return rows


def marker_exclusions(rows) -> tuple[list[str], dict]:
    import re
    pats, _ = load_markers()
    han = [0, 0]
    counts = defaultdict(lambda: [0, 0])
    for text, y, _, _ in rows:
        body = score_zh.strip_code(text)
        han[y] += score_zh.han_len(body)
        for pat, label in pats:
            counts[label][y] += len(re.findall(pat, body))
    rates = {lab: (c[0] / han[0] * 1000, c[1] / han[1] * 1000) for lab, c in counts.items()}
    exclude = sorted(lab for lab, (h, a) in rates.items() if h > 0 and h >= a)
    return exclude, rates


def fit(X, y, w, l2=2.0, iters=1500, lr=0.3):
    d = len(X[0])
    beta, b = [0.0] * d, 0.0
    for _ in range(iters):
        gb, gw = 0.0, [0.0] * d
        for xi, yi, wi in zip(X, y, w):
            p = 1 / (1 + math.exp(-(b + sum(bj * xj for bj, xj in zip(beta, xi)))))
            e = (p - yi) * wi
            gb += e
            for j in range(d):
                gw[j] += e * xi[j]
        tot = sum(w)
        b -= lr * gb / tot
        beta = [bj - lr * (g / tot + l2 * bj / len(X)) for bj, g in zip(beta, gw)]
        # projected step: keep each weight on its allowed side (or at zero)
        beta = [0.0 if sg == 0 else (max(0.0, bj) if sg > 0 else min(0.0, bj))
                for bj, sg in zip(beta, (SIGNS[k] for k in FEATURES))]
    return beta, b


def standardize(feats, stats):
    out = []
    for f in feats:
        row = []
        for k in FEATURES:
            m, s = stats[k]
            v = f[k] if f[k] is not None else m
            row.append((v - m) / s if s else 0.0)
        out.append(row)
    return out


def train(feats, ys):
    stats = {}
    for k in FEATURES:
        vals = [f[k] for f in feats if f[k] is not None]
        stats[k] = (statistics.fmean(vals), statistics.pstdev(vals) or 1.0)
    n1 = sum(ys)
    n0 = len(ys) - n1
    w = [len(ys) / (2 * n1) if y else len(ys) / (2 * n0) for y in ys]
    beta, b = fit(standardize(feats, stats), ys, w)
    return stats, beta, b


def predict(f, stats, beta, b):
    x = standardize([f], stats)[0]
    return 1 / (1 + math.exp(-(b + sum(bj * xj for bj, xj in zip(beta, x)))))


def pct(vals, q):
    s = sorted(vals)
    i = min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))
    return s[i]


def folds_by_group(groups, k=10):
    uniq = sorted(set(groups))
    return [set(uniq[i::k]) for i in range(k)]


def cross_val(feats, ys, groups, held_sets):
    held = [None] * len(ys)
    for hs in held_sets:
        tr = [i for i, g in enumerate(groups) if g not in hs]
        st, be, bb = train([feats[i] for i in tr], [ys[i] for i in tr])
        for i, g in enumerate(groups):
            if g in hs:
                held[i] = predict(feats[i], st, be, bb)
    return held


def rate(vals, t):
    return sum(v >= t for v in vals) / len(vals) if vals else float("nan")


def main() -> int:
    rows = load()
    exclude, rates = marker_exclusions(rows)
    feats = [score_zh.extract_features(t, set(exclude))[0] for t, _, _, _ in rows]
    ys = [y for _, y, _, _ in rows]
    groups = [g for _, _, g, _ in rows]
    kinds = [k for _, _, _, k in rows]
    lens = [score_zh.han_len(score_zh.strip_code(t)) for t, _, _, _ in rows]

    # 1) grouped 10-fold: whole source files held out together
    held = cross_val(feats, ys, groups, folds_by_group(groups))
    human_held = [s for s, y in zip(held, ys) if y == 0]
    ai_held = [s for s, y in zip(held, ys) if y == 1]
    hi_t = pct(human_held, 0.95)
    med_t = pct(human_held, 0.80)
    acc05 = sum((s >= 0.5) == bool(y) for s, y in zip(held, ys)) / len(ys)

    # 2) leave-one-model-out: every AI model is unseen in turn (human folds as above)
    models = sorted({k for k, y in zip(kinds, ys) if y == 1})
    lomo = {}
    for m in models:
        hs = {g for g, k in zip(groups, kinds) if k == m}
        sc = cross_val(feats, ys, groups, [hs])
        lomo[m] = rate([s for s, k in zip(sc, kinds) if k == m], hi_t)

    stats, beta, b = train(feats, ys)
    hp = {k: [f[k] for f, y in zip(feats, ys) if y == 0 and f[k] is not None] for k in FEATURES}
    model = {
        "version": 2,
        "calibrated": str(date.today()),
        "features": list(FEATURES),
        "mean": {k: stats[k][0] for k in FEATURES},
        "sd": {k: stats[k][1] for k in FEATURES},
        "weights": dict(zip(FEATURES, beta)),
        "bias": b,
        "tiers": {"medium": round(med_t, 4), "high": round(hi_t, 4)},
        # 101 quantiles of held-out human chunk scores, for "more AI-like than X% of human text"
        "human_score_quantiles": [round(pct(human_held, q / 100), 4) if q else round(min(human_held), 4) for q in range(101)],
        "human_p10": {k: pct(v, 0.10) for k, v in hp.items() if v},
        "human_p90": {k: pct(v, 0.90) for k, v in hp.items() if v},
        "marker_exclude": exclude,
        "corpus": {"human_chunks": len(human_held), "ai_chunks": len(ai_held),
                   "human_sources": len({g for g, y in zip(groups, ys) if y == 0}),
                   "ai_sources": len({g for g, y in zip(groups, ys) if y == 1}),
                   "ai_models": models},
    }
    (ROOT / "scripts" / "zh_model.json").write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")

    means = {k: tuple(statistics.fmean([f[k] for f, y in zip(feats, ys) if y == c and f[k] is not None]) for c in (0, 1)) for k in FEATURES}
    c = model["corpus"]
    lines = [
        "# 校准结果", "",
        f"日期：{date.today()}。人类侧 {c['human_sources']} 篇（经典名作 + 2020 年前的知乎高赞回答和贴吧文章，均经人工审核）切成 {c['human_chunks']} 段；"
        f"AI 侧 {c['ai_sources']} 篇（{len(models)} 个模型）切成 {c['ai_chunks']} 段。每段 250–900 字，两边切法相同。",
        "", "## 分组交叉验证（整篇文章一起留出，不是训练集内成绩）", "",
        f"- 以 0.5 为界的准确率：{acc05:.1%}",
        f"- `high` 档阈值 {hi_t:.3f}（人类段落第 95 百分位）：AI 段落命中 {rate(ai_held, hi_t):.0%}，人类段落误判 {rate(human_held, hi_t):.0%}",
        f"- `medium` 档阈值 {med_t:.3f}（人类段落第 80 百分位）：AI 段落达到 medium 及以上 {rate(ai_held, med_t):.0%}",
        "", "### 人类段落按来源的误判率（达到 high）", "",
    ]
    for k in sorted({k for k, y in zip(kinds, ys) if y == 0}):
        v = [s for s, kk, y in zip(held, kinds, ys) if y == 0 and kk == k]
        lines.append(f"- {k}：{rate(v, hi_t):.0%}（{len(v)} 段）")
    lines += ["", "### 按长度分档", "", "| 长度 | 人类误判 | AI 命中 |", "|---|---|---|"]
    for lo, hi in ((250, 400), (400, 600), (600, 10**9)):
        hv = [s for s, y, n in zip(held, ys, lens) if y == 0 and lo <= n < hi]
        av = [s for s, y, n in zip(held, ys, lens) if y == 1 and lo <= n < hi]
        label = f"{lo}–{hi}" if hi < 10**9 else f"{lo}+"
        lines.append(f"| {label} 字 | {rate(hv, hi_t):.0%} | {rate(av, hi_t):.0%} |")
    lines += ["", "## 留一模型检验（该模型的样本完全不参与训练）", "",
              "这项最能说明对没见过的模型是否有效。", "", "| 模型 | 段落达到 high 的比例 |", "|---|---|"]
    for m in models:
        lines.append(f"| {m} | {lomo[m]:.0%} |")
    lines += ["", "## 各特征均值（人类 / AI）与权重", "", "| 特征 | 人类 | AI | 标准化权重 |", "|---|---|---|---|"]
    for k, wv in zip(FEATURES, beta):
        lines.append(f"| {k} | {means[k][0]:.3f} | {means[k][1]:.3f} | {wv:+.2f} |")
    lines += ["", f"## 按人类/AI 频率排除的 haohao 词条（{len(exclude)} 个）", "", "、".join(exclude) or "无",
              "", "## 局限", "",
              "- 分数只说明这些统计信号像不像校准集里的 AI 文本，不代表任何商业检测器的结论。",
              "- 被要求“写得自然一点”的 AI 文本明显更难认出，见留一模型检验和 AI 命中率。",
              "- 人类侧没有当代口语、网文、公文样本，这几类文体的误判率未知。",
              "- 扩充语料后重跑 `python calibration/calibrate.py` 即可更新模型。", ""]
    (CAL / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
