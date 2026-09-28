"""Feature experiments (calibration-time only; needs numpy + scikit-learn).

Compares candidate features against the current score_zh set with grouped
10-fold CV (whole files held out) and leave-one-model-out, reporting
AUC, AI recall at 5% human false positives, and Wikipedia false positives.
"""

from __future__ import annotations

import re
import statistics
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

import score_zh  # noqa: E402
from calibrate import load, marker_exclusions  # noqa: E402

HAN = re.compile(r"[一-鿿]")
CLAUSE_SPLIT = re.compile(r"[，,；;：:、。！？!?…]+")
CLOSERS = ("总之", "总而言之", "综上", "让我们", "希望", "愿", "最后", "未来")


def extra(text: str) -> dict[str, float]:
    body = score_zh.strip_code(text).replace("「", "“").replace("」", "”").replace("『", "‘").replace("』", "’")
    n = max(1, len(HAN.findall(body))) / 1000
    paras = score_zh.split_paragraphs(body)
    sents = score_zh.split_sentences(paras)
    clauses = [len(HAN.findall(c)) for c in CLAUSE_SPLIT.split(body) if HAN.search(c)]
    pairs = list(zip(clauses, clauses[1:]))
    last = re.sub(r"^[\W_]+", "", paras[-1]) if paras else ""
    return {
        "mean_sent_len": statistics.fmean([score_zh.han_len(s) for s in sents]) if sents else 0.0,
        "parallel_ratio": sum(1 for a, b in pairs if a == b and a >= 3) / len(pairs) if pairs else 0.0,
        "four_char_ratio": sum(1 for c in clauses if c == 4) / len(clauses) if clauses else 0.0,
        "we_per_k": body.count("我们") / n,
        "i_per_k": (body.count("我") - body.count("我们")) / n,
        "you_per_k": body.count("你") / n,
        "de_per_k": body.count("的") / n,
        "colon_per_k": (body.count("：") + body.count(":")) / n,
        "dash_per_k": body.count("——") / n,
        "ellipsis_per_k": (body.count("……") + body.count("...")) / n,
        "exclaim_per_k": (body.count("！") + body.count("!")) / n,
        "question_per_k": (body.count("？") + body.count("?")) / n,
        "quote_per_k": body.count("“") / n,
        "digit_per_k": len(re.findall(r"\d+", body)) / n,
        "closer": float(any(last.startswith(c) for c in CLOSERS)),
    }


def evaluate(X, y, groups, kinds, cols, label):
    Xs = X[:, cols]
    held = np.zeros(len(y))
    for tr, te in GroupKFold(10).split(Xs, y, groups):
        sc = StandardScaler().fit(Xs[tr])
        m = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000).fit(sc.transform(Xs[tr]), y[tr])
        held[te] = m.predict_proba(sc.transform(Xs[te]))[:, 1]
    t = np.quantile(held[y == 0], 0.95)
    rec = (held[y == 1] >= t).mean()
    wiki = (held[(y == 0) & (kinds == "知乎回答")] >= t).mean() if ((y == 0) & (kinds == "知乎回答")).any() else float("nan")
    lomo = []
    for m_ in sorted(set(kinds[y == 1])):
        te = kinds == m_
        tr = ~te
        sc = StandardScaler().fit(Xs[tr])
        mdl = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000).fit(sc.transform(Xs[tr]), y[tr])
        lomo.append((mdl.predict_proba(sc.transform(Xs[te]))[:, 1] >= t).mean())
    print(f"{label:<28} AUC {roc_auc_score(y, held):.3f}  recall@5% {rec:.0%}  zhihuFP {wiki:.0%}  LOMO-min {min(lomo):.0%} mean {np.mean(lomo):.0%}")


def main():
    rows = load()
    exclude, _ = marker_exclusions(rows)
    base = [score_zh.extract_features(t, set(exclude))[0] for t, _, _, _ in rows]
    ext = [extra(t) for t, _, _, _ in rows]
    base_names = [k for k in score_zh.FEATURES if k != "clauses_per_sent"]
    ext_names = list(ext[0])
    names = base_names + ext_names
    X = np.array([[b[k] if b[k] is not None else np.nan for k in base_names] + [e[k] for k in ext_names]
                  for b, e in zip(base, ext)], dtype=float)
    col_means = np.nanmean(X, axis=0)
    X = np.where(np.isnan(X), col_means, X)
    y = np.array([r[1] for r in rows])
    groups = np.array([r[2] for r in rows])
    kinds = np.array([r[3] for r in rows])
    print(f"rows {len(y)}  human {int((y == 0).sum())}  ai {int(y.sum())}")
    idx = {n: i for i, n in enumerate(names)}
    base_cols = [idx[n] for n in base_names]
    evaluate(X, y, groups, kinds, base_cols, "base")
    for n in ext_names:
        evaluate(X, y, groups, kinds, base_cols + [idx[n]], f"base + {n}")
    evaluate(X, y, groups, kinds, list(range(len(names))), "all")
    # univariate direction, for sign constraints
    print("\nmeans human / ai:")
    for n in names:
        c = X[:, idx[n]]
        print(f"  {n:<20} {c[y == 0].mean():8.3f} {c[y == 1].mean():8.3f}")


if __name__ == "__main__":
    main()
