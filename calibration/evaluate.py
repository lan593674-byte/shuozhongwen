"""Score held-out human text with the current model and report false positives.

Reads calibration/test/<kind>/*.txt (never used for training), cuts each file
into the same 250–900 character chunks as calibration, scores every chunk with
scripts/zh_model.json, and reports how many reach medium and high.
Writes calibration/TEST_RESULTS.md.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))

import score_zh  # noqa: E402
from calibrate import MAX_CHUNKS, chunks  # noqa: E402

LABELS = {"spoken": "口语长帖（贴吧，未参与训练）", "webnovel": "网络小说（起点免费章节，2024 年前开始连载，11 部，未参与训练）"}


def main() -> int:
    lines = ["# 留出测试：人类文本误判率", "",
             f"日期：{date.today()}。这些文本没有参与训练，用来检验评分对当代口语和网文会不会误判。", "",
             "| 文本类型 | 篇数 | 段数 | 达到 medium | 达到 high（误判） |", "|---|---|---|---|---|"]
    for kind in sorted(p.name for p in (HERE / "test").iterdir() if p.is_dir()):
        files = sorted((HERE / "test" / kind).glob("*.txt"))
        scores = []
        for i, f in enumerate(files):
            for c in chunks(f.read_text(encoding="utf-8"), start=i)[:MAX_CHUNKS]:
                r = score_zh.score_text_stylometry(c)
                if r.score is not None:
                    scores.append(r.density_tier)
        if not scores:
            continue
        med = sum(t in ("medium", "high") for t in scores) / len(scores)
        high = sum(t == "high" for t in scores) / len(scores)
        lines.append(f"| {LABELS.get(kind, kind)} | {len(files)} | {len(scores)} | {med:.0%} | {high:.0%} |")
    lines += ["", "训练集里人类段落的 high 误判率按设计是 5%，medium 是 20%，可以拿来对照。", ""]
    (HERE / "TEST_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
