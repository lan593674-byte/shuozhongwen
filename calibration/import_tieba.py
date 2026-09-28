"""Import Tieba posts exported from the built-in browser (tieba_posts.json).

- excerpt (书摘/片段赏析) and essay (原创散文随笔) -> calibration/human/tieba_<cat>_<id>.txt
  (training data)
- test_spoken (口语长帖) and test_webnovel (网文连载) -> calibration/test/<cat>/<id>.txt
  (held out: only used by evaluate.py to measure false positives)
All posts were created before 2020-01-01 and hold only the original poster's text.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEWS = re.compile(r"记者|据报道|日电|新华社|中新网|通讯员|本报讯|（转载）|来源：")
# posts reviewed by hand and dropped: news or news commentary
DROP = {"1318699082", "1702351213", "1336845276", "1857195017", "2097688708", "1265475391",
        "10839418443", "6579880176", "6710353184", "6541631218",
        "7008151367"}  # + ads found in part3; duplicate repost in part4
TEST_BEFORE = "2024-01-01"  # held-out human test posts must predate widespread AI writing


def main(*paths: str) -> int:
    posts = {}
    for path in paths:
        posts.update(json.loads(Path(path).read_text(encoding="utf-8")))
    counts: dict[str, int] = {}
    rej = HERE / "rejected.txt"
    rejected = {ln.split()[0] for ln in rej.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")} if rej.exists() else set()
    for p in posts.values() if isinstance(posts, dict) else posts:
        cat, pid, text = p["category"], str(p["id"]), p["text"].strip()
        if pid in DROP or NEWS.search(text[:400]) or NEWS.search(p.get("title", "")):
            counts["dropped"] = counts.get("dropped", 0) + 1
            continue
        if f"tieba_{cat}_{pid}" in rejected:
            counts["rejected"] = counts.get("rejected", 0) + 1
            continue
        if cat in ("excerpt", "essay"):
            out = HERE / "human" / f"tieba_{cat}_{pid}.txt"
        elif cat in ("test_spoken", "test_webnovel"):
            if p.get("date", "") >= TEST_BEFORE:
                counts["test_after_2024"] = counts.get("test_after_2024", 0) + 1
                continue
            out = HERE / "test" / cat.removeprefix("test_") / f"{pid}.txt"
        else:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        counts[cat] = counts.get(cat, 0) + 1
    print(counts)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
