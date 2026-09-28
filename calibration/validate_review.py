"""Check that review_zh can tell good writing from bad before trusting it.

Reviews a fixed sample with two models: classic literature passages, high-upvote
Zhihu answers, AI samples from several models, and the three Rome versions
(DeepSeek original, first rewrite, flat v2). Writes calibration/REVIEW_VALIDATION.md.
"""

from __future__ import annotations

import json
import os
import random
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

import ark_review as review_zh  # noqa: E402  (dev-only: Ark API reviewers)
from calibrate import chunks  # noqa: E402

MODELS = ["kimi-k3", "deepseek-v4.1-flash"]
SAMPLES = Path(os.environ.get("SHUOZHONGWEN_SAMPLES", Path(__file__).resolve().parent / "samples"))


def pick(pattern: str, n: int, seed: int) -> list[tuple[str, str]]:
    files = sorted((HERE / pattern.split("/")[0]).glob(pattern.split("/")[1]))
    rng = random.Random(seed)
    rng.shuffle(files)
    out = []
    for f in files:
        cs = [c for c in chunks(f.read_text(encoding="utf-8")) if 500 <= len(c) <= 1400]
        if cs:
            out.append((f.stem, cs[0]))
        if len(out) >= n:
            break
    return out


def main() -> int:
    items = []
    for stem, t in pick("human/鲁迅_*.txt", 3, 1) + pick("human/朱自清_*.txt", 3, 2) + pick("human/萧红_*.txt", 2, 3):
        items.append(("经典名作", stem, t, "散文或小说片段"))
    for stem, t in pick("human/zhihu_*.txt", 8, 4):
        items.append(("知乎高赞", stem, t, "知乎回答"))
    ai = []
    for m in ["deepseek-v4.1-flash", "kimi-k3", "glm-5.3", "doubao-seed-2.0-pro", "minimax-m3", "gpt-6-luna", "gpt-5.5", "claude-opus-5-5"]:
        ai += pick(f"ai/{m}__*.txt", 1, 5)
    for stem, t in ai:
        items.append(("AI 样本", stem, t, "散文、评论或小说片段"))
    for name in ["罗马_DeepSeek原稿", "罗马_改写终稿_v2", "罗马_文学版_v3"]:
        items.append(("罗马三版", name, (SAMPLES / f"{name}.txt").read_text(encoding="utf-8"), "城市随笔散文"))

    key = review_zh.ark_key()
    jobs = [(g, s, t, genre, m) for g, s, t, genre in items for m in MODELS]

    def run(job):
        g, s, t, genre, m = job
        try:
            r = review_zh.review(t, genre, m, key)
            return (g, s, m, r["average"], bool(r.get("flat")))
        except Exception as e:
            return (g, s, m, None, f"ERR {type(e).__name__}")

    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(run, jobs))
    (HERE / "raw").mkdir(exist_ok=True)
    (HERE / "raw" / "review_validation.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# 写作质量评审的有效性检验", "", "同一批已知优劣的文字，标明文体后交给两个模型分别评审（六项平均分，满分 5）。", "",
             "| 组别 | " + " | ".join(MODELS) + " | 判为白开水的比例 |", "|---|" + "---|" * (len(MODELS) + 1)]
    for g in ["经典名作", "知乎高赞", "AI 样本"]:
        row = [g]
        flats = []
        for m in MODELS:
            v = [a for gg, s, mm, a, f in res if gg == g and mm == m and a is not None]
            flats += [f for gg, s, mm, a, f in res if gg == g and mm == m and isinstance(f, bool)]
            row.append(f"{statistics.fmean(v):.2f}（{len(v)} 篇）" if v else "n/a")
        row.append(f"{sum(flats) / len(flats):.0%}" if flats else "n/a")
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "| 罗马三版 | " + " | ".join(MODELS) + " | 白开水 |", "|---|" + "---|" * (len(MODELS) + 1)]
    for name in ["罗马_DeepSeek原稿", "罗马_改写终稿_v2", "罗马_文学版_v3"]:
        row = [name]
        fl = []
        for m in MODELS:
            v = [a for gg, s, mm, a, f in res if s == name and mm == m]
            fl += [f for gg, s, mm, a, f in res if s == name and mm == m]
            row.append(f"{v[0]}" if v and v[0] is not None else "n/a")
        row.append("、".join("是" if f is True else "否" if f is False else str(f) for f in fl))
        lines.append("| " + " | ".join(row) + " |")
    errs = [r for r in res if r[3] is None]
    lines += ["", f"失败调用：{len(errs)} 次。", ""]
    (HERE / "REVIEW_VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
