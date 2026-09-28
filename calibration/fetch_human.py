"""Fetch public-domain modern Chinese prose from zh.wikisource as the human side
of the calibration corpus. Output: calibration/human/<slug>.txt (simplified)."""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "human"
UA = {"User-Agent": "shuozhongwen-calibration/0.1 (personal research)"}

TITLES = [  # classic works only; archaic or dated pieces were dropped on purpose
    ("故鄉", "鲁迅"), ("孔乙己", "鲁迅"), ("祝福", "鲁迅"), ("社戲", "鲁迅"),
    ("藤野先生", "鲁迅"), ("從百草園到三味書屋", "鲁迅"), ("阿長與山海經", "鲁迅"),
    ("風箏", "鲁迅"), ("一件小事", "鲁迅"), ("記念劉和珍君", "鲁迅"), ("拿来主义", "鲁迅"),
    ("背影", "朱自清"), ("荷塘月色", "朱自清"), ("匆匆", "朱自清"), ("春 (朱自清)", "朱自清"),
    ("槳聲燈影裏的秦淮河", "朱自清"), ("給亡婦", "朱自清"),
    ("呼蘭河傳/第一章", "萧红"), ("呼蘭河傳/第二章", "萧红"), ("呼蘭河傳/第三章", "萧红"),
    ("呼蘭河傳/第四章", "萧红"), ("落花生", "许地山"), ("差不多先生傳", "胡适"),
    ("我的母親", "胡适"), ("我所知道的康橋", "徐志摩"),
]


def to_simplified(text: str) -> str:
    """Traditional -> simplified (opencc, calibration-only dependency) and strip invisibles."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from text_unicode import clean_text

    text, _ = clean_text(text, normalize_spaces=False)
    try:
        from opencc import OpenCC
    except ImportError:
        return text
    return OpenCC("t2s").convert(text)


def fetch(title: str) -> str | None:
    params = {"action": "parse", "page": title, "prop": "text", "format": "json",
              "variant": "zh-cn", "redirects": 1, "disableeditsection": 1}
    url = "https://zh.wikisource.org/w/api.php?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        data = json.load(r)
    if "error" in data:
        return None
    raw = data["parse"]["text"]["*"]
    # drop headers/navboxes/notes/tables/references, keep paragraph text
    raw = re.sub(r"(?is)<(table|style|script|sup|div class=\"(?:mw-references|reflist|navbox)[^\"]*\")[^>]*>.*?</\1>", "", raw)
    raw = re.sub(r"(?is)<table.*?</table>", "", raw)
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", raw)
    out = []
    for p in paras:
        t = html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
        t = re.sub(r"\[\d+\]", "", t)
        if len(re.findall(r"[一-鿿]", t)) >= 15:
            out.append(t)
    return "\n\n".join(out) if out else None


def fetch_retry(title: str) -> str | None:
    for attempt in range(5):
        try:
            return fetch(title)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(15 * (attempt + 1))
    return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for title, author in TITLES:
        slug = re.sub(r"[\\/:*?\"<>| ()]+", "_", title).strip("_")
        if (OUT / f"{author}_{slug}.txt").exists():
            ok += 1
            continue
        try:
            text = fetch_retry(title)
        except Exception as e:  # network or parse failure: report and continue
            print(f"FAIL {title}: {type(e).__name__} {getattr(e, 'code', '')}", file=sys.stderr)
            continue
        if not text:
            print(f"MISS {title}", file=sys.stderr)
            continue
        (OUT / f"{author}_{slug}.txt").write_text(text + "\n", encoding="utf-8")
        ok += 1
        print(f"OK   {author} {title}: {len(text)} chars")
        time.sleep(4)
    print(f"{ok}/{len(TITLES)} fetched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
