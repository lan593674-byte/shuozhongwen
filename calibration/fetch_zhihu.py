"""Sample modern human Chinese from high-upvote Zhihu answers written before ChatGPT.

Source: Hugging Face dataset wangrui6/Zhihu-KOL, read through the public
datasets-server rows API in pages of 100 at spread-out offsets (no bulk download).
Kept: answer_creation_time < CUTOFF (2022-11-30), upvotes >= MIN_UPVOTES, >= MIN_HAN Han
characters, one answer per question, little link/ad noise. The dataset joins
paragraphs with spaces; a space after sentence-final punctuation is restored as
a paragraph break.
Output: calibration/human/zhihu_<answer_id>.txt
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "human"
API = "https://datasets-server.huggingface.co/rows?dataset=wangrui6/Zhihu-KOL&config=default&split=train"
TOTAL_ROWS = 1_000_000  # approximate; out-of-range pages just come back empty
TARGET = 300  # total zhihu_* files wanted
MIN_UPVOTES = 1000
CUTOFF = "9999"  # no date limit (user decision 2026-09-27); the dataset itself ends early 2023
MIN_HAN = 600
HAN = re.compile(r"[一-鿿]")


def page(offset: int) -> list[dict]:
    url = f"{API}&offset={offset}&length=100"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "shuozhongwen-calibration/0.3"}), timeout=90) as r:
                return [x["row"] for x in json.load(r).get("rows", [])]
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10 * (attempt + 1))
    return []


def upvotes(meta: dict) -> int:
    m = re.search(r"([\d.]+)\s*(万)?", str(meta.get("upvotes", "")))
    if not m:
        return 0
    n = float(m.group(1))
    return int(n * 10000) if m.group(2) else int(n)


def restore_paragraphs(text: str) -> str:
    text = re.sub(r"(?<=[。！？!?…”」）)~])\s+(?=\S)", "\n\n", text.strip())
    return re.sub(r"[ \t]{2,}", " ", text)


def clean_enough(text: str) -> bool:
    han = len(HAN.findall(text))
    links = len(re.findall(r"https?://|www\.|淘宝|优惠券|加微信|公众号|私信我", text))
    return han >= MIN_HAN and links <= 1


def main() -> int:
    OUT.mkdir(exist_ok=True)
    have = len(list(OUT.glob("zhihu_*.txt")))
    rej = HERE / "rejected.txt"
    skip = {ln.split()[0] for ln in rej.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")} if rej.exists() else set()
    seen_q: set = set()
    rng = random.Random(20260928)
    tries = 0
    while have < TARGET and tries < 300:
        tries += 1
        for row in page(rng.randrange(0, TOTAL_ROWS - 100)):
            try:
                meta = json.loads(row["METADATA"])
            except (ValueError, TypeError):
                continue
            when = str(meta.get("answer_creation_time", ""))
            if not when or when >= CUTOFF or upvotes(meta) < MIN_UPVOTES:
                continue
            q = meta.get("question_id")
            if q in seen_q:
                continue
            text = restore_paragraphs(row.get("RESPONSE") or "")
            if not clean_enough(text):
                continue
            seen_q.add(q)
            aid = int(meta.get("answer_id") or 0)
            if f"zhihu_{aid}" in skip:
                continue
            (OUT / f"zhihu_{aid}.txt").write_text(text + "\n", encoding="utf-8")
            have += 1
            if have >= TARGET:
                break
        print(f"page {tries}: {have} kept", flush=True)
        time.sleep(1)
    print(f"zhihu kept {have}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
