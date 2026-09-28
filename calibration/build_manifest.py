#!/usr/bin/env python3
"""Write calibration/corpus/MANIFEST.csv: one row per human calibration text.

Columns: file (relative to calibration/), source, original URL, character
count, and whether the text was used for training (human/) or held-out
testing (test/). Texts in rejected/ (ads, reposts) are not listed.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "corpus"


def source(name: str) -> tuple[str, str]:
    if m := re.fullmatch(r"zhihu_(\d+)", name):
        return "zhihu", f"https://www.zhihu.com/answer/{m[1]}"
    if m := re.fullmatch(r"qidian_(\d+)_(\d+)", name):
        return "qidian", f"https://www.qidian.com/chapter/{m[1]}/{m[2]}/"
    if m := re.fullmatch(r"tieba_\w+?_(\d+)|(\d+)", name):
        return "tieba", f"https://tieba.baidu.com/p/{m[1] or m[2]}"
    return "wikisource (public domain)", "https://zh.wikisource.org/wiki/" + name.split("_", 1)[-1].replace("_", "/")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for split, folder in (("train", HERE / "human"), ("test", HERE / "test")):
        for f in sorted(folder.rglob("*.txt")):
            kind, url = source(f.stem)
            rows.append([f.relative_to(HERE).as_posix(), kind, url, len(f.read_text(encoding="utf-8")), split])
    with (OUT / "MANIFEST.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "source", "url", "chars", "split"])
        w.writerows(rows)
    print(f"{len(rows)} rows")


if __name__ == "__main__":
    main()
