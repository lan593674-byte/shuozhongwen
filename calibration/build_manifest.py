#!/usr/bin/env python3
"""Publish what can be published of the human calibration corpus.

- Public-domain classics (authors died more than 50 years ago; texts from
  zh.wikisource) are copied in full to calibration/corpus/public-domain/.
- Everything else (Zhihu answers, Tieba posts, Qidian free chapters) is still
  under copyright, so only its source is listed in calibration/corpus/MANIFEST.csv:
  id, source, URL, character count and whether it was used for training or
  held-out testing. Use the fetch/import scripts to rebuild the texts yourself.
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "corpus"
PD = OUT / "public-domain"


def source(name: str) -> tuple[str, str] | None:
    if m := re.fullmatch(r"zhihu_(\d+)", name):
        return "zhihu", f"https://www.zhihu.com/answer/{m[1]}"
    if m := re.fullmatch(r"tieba_\w+?_(\d+)|(\d+)", name):
        return "tieba", f"https://tieba.baidu.com/p/{m[1] or m[2]}"
    if m := re.fullmatch(r"qidian_(\d+)_(\d+)", name):
        return "qidian", f"https://www.qidian.com/chapter/{m[1]}/{m[2]}/"
    return None


def main() -> None:
    PD.mkdir(parents=True, exist_ok=True)
    rows = []
    for split, folder in (("train", HERE / "human"), ("test", HERE / "test")):
        for f in sorted(folder.rglob("*.txt")):
            chars = len(f.read_text(encoding="utf-8"))
            src = source(f.stem)
            if src is None:  # a public-domain classic
                shutil.copy2(f, PD / f.name)
                rows.append([f.stem, "wikisource (public domain)", f"public-domain/{f.name}", chars, split])
                continue
            kind, url = src
            rows.append([f"{f.parent.name}/{f.stem}" if split == "test" else f.stem, kind, url, chars, split])
    with (OUT / "MANIFEST.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "source", "url_or_file", "chars", "split"])
        w.writerows(rows)
    print(f"{len(rows)} rows, {len(list(PD.glob('*.txt')))} public-domain texts")


if __name__ == "__main__":
    main()
