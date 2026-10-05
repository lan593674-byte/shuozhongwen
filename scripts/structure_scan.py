#!/usr/bin/env python3
"""Scan a Chinese draft for structural AI templates (结构套路).

The four regex scans (haohao_scan.py) look at words and punctuation. A draft
can pass them and still read as AI because of how it is built. This scan
counts the moves Claude-style prose leans on:

- short_lead: paragraphs that open with a short verdict sentence and then
  unfold it ("代价一样具体。" "转折在 1971 年。" "先说传统。")
- one_line_para: a paragraph that is one short sentence, used as a pivot
  between longer paragraphs ("可是通用也有通用的代价。")
- self_qa: a set-up question in expository prose that the text then answers
  ("工程修了，打猎为什么没断？")
- summary_flip: wrap-up formulas ("不只是……也……" "说到底" "回头看" "其实不是一回事")
- scare_quotes: ordinary short words put in quotation marks (“威胁”“雁假”)
- attribution_repeat: the same source cited with a speech verb again and again
  ("讲座说" "据讲座说" "讲座里还说" ...)

Also: colon_list (冒号清单), aphorism (段尾对仗警句), callback (前后回扣) and
process_i (把写作过程写成“我”的经历：我没找到、我读得最久).

Blocking: short_lead, summary_flip, attribution_repeat, and stacking: four or
more rules of any kind over their limit in one text. The rest are hints. Limits were set on the calibration corpus (calibration/human
and calibration/test vs calibration/ai): the gates fail 2.8% of human texts.
Dialogue (text inside quotation marks) and headings are not scanned.

Usage: structure_scan.py 稿件 [--paper] [--json]   exit 0 = passed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_text import read_any  # noqa: E402

HAN = re.compile(r"[一-鿿]")
SENT = re.compile(r"[^。！？!?]+[。！？!?]+[”’」』）)]*")
QUOTED = re.compile(r"“[^”\n]*”|「[^」\n]*」|『[^』\n]*』")
SHORT_QUOTE = re.compile(r"“([^”\n，。！？：；、]{1,4})”")
SPEECH_BEFORE = re.compile(r"(说|道|问|叫|称|讲|喊|写|名为|叫做|叫作|意思是|所谓|号称|俗称|英语|英文)[：:，,]?\s*$")
QUESTION_CUE = re.compile(r"(为什么|为何|怎么|如何|何以|是什么|在哪|凭什么|难道)")
SUMMARY = re.compile(r"(不只是[^。]{1,30}[，,]?(也|还|更)|不仅仅是[^。]{1,30}(更|还|也)|说到底|归根结底|归根到底|回头看|回过头看|其实不是一回事|说白了|换句话说|一言以蔽之|与其说[^。]{1,30}不如说)")
ATTRIB = re.compile(r"(?:据|按|照)?([一-鿿]{2,4}?)(?:里|中)?(?:还|也|又)?(说过|说|提到|指出|承认|认为|写道|担心|强调|讲)")
ATTRIB_STOP = set("我们他们她们你们大家有人别人人们这里那里文章本文作者老师同学")
COLON_LIST = re.compile(r"：([^。！？\n]+)")
LIST_SEP = re.compile(r"[、，,；]")
CALLBACK = re.compile(r"就是[^。，！？\n]{0,24}?(那条|那个|那座|那位|那片|那家|那所|那年|那场|那次|那一)")
PROCESS_I = re.compile(r"我(没|没有|没能)(找到|看到|查到|读到|看懂|搜到)|我读得最|我(先|又|也)?(看了|查了|翻了|读了|搜了)|我想[^。！？\n]{0,6}(在这里|这里)")
PARALLEL_CUES = ("越", "只", "就", "都", "才", "也", "却", "反倒", "倒")

RULES = (
    # key, label, limit kind
    ("short_lead", "段首短判断句", "share"),
    ("one_line_para", "单句成段的转折", "count"),
    ("self_qa", "设问自答", "count"),
    ("summary_flip", "总结翻转套话", "count"),
    ("scare_quotes", "给普通词打引号", "per_k"),
    ("attribution_repeat", "同一出处反复引述", "count"),
    ("colon_list", "冒号清单", "count"),
    ("aphorism", "段尾对仗警句", "count"),
    ("callback", "前后回扣", "count"),
    ("process_i", "第一人称过程交代", "count"),
)
LIMITS = {"short_lead": 0.30, "one_line_para": 1, "self_qa": 1, "summary_flip": 2, "scare_quotes": 1.5,
          "attribution_repeat": 5, "colon_list": 2, "aphorism": 1, "callback": 0, "process_i": 0}
# Only these block delivery. On the calibration corpus they fail 2.8% of human
# texts (11 of 388) and 12% of the AI samples; the rest are common in human
# writing too (Zhihu answers ask and answer questions, quote words, use
# one-line paragraphs), so they are shown as hints for the writer to look at.
GATES = {"short_lead", "summary_flip", "attribution_repeat"}
# Templates rarely come alone. Four or more rules over their limit in one text
# (hints included) blocks delivery: 1.3% of the 388 human texts do that, the
# templated forum post that prompted this scan hit six.
STACK_LIMIT = 3
SHORT_LEAD_MIN = 3        # at least this many hits before the share counts
SHORT_LEAD_MAX_HAN = 10   # a "short verdict" opener has at most this many Han characters


def _han(s: str) -> int:
    return len(HAN.findall(s))


def paragraphs(text: str) -> list[str]:
    out = []
    for p in re.split(r"\n\s*\n|\n(?=\s*[#>*\-])", text):
        p = p.strip()
        if not p or p.startswith(("#", ">", "|", "```", "-", "*")) or re.match(r"^\d+[.、)]", p):
            continue
        out.append(p)
    return out


def scan(text: str, paper: bool = False) -> dict:
    paras = paragraphs(text)
    prose = [p for p in paras if _han(p) >= 8]
    hits: dict[str, list[str]] = {k: [] for k, _, _ in RULES}

    long_paras = [p for p in prose if _han(p) >= 40]
    for p in long_paras:
        body = QUOTED.sub("", p)
        first = SENT.match(body)
        if first and _han(first.group(0)) <= SHORT_LEAD_MAX_HAN and first.group(0).rstrip()[-1] in "。":
            hits["short_lead"].append(first.group(0).strip())

    for i, p in enumerate(prose):
        sents = SENT.findall(p)
        if (len(sents) == 1 and _han(p) <= 20 and 0 < i < len(prose) - 1
                and _han(prose[i - 1]) >= 40 and _han(prose[i + 1]) >= 40 and "“" not in p):
            hits["one_line_para"].append(p)

    for i, p in enumerate(prose):
        body = QUOTED.sub("", p)
        for s in SENT.findall(body):
            s = s.strip()
            if s.endswith(("？", "?")) and QUESTION_CUE.search(s):
                rest = body[body.find(s) + len(s):]
                if rest.strip() or i < len(prose) - 1:  # answered right after, here or in the next paragraph
                    hits["self_qa"].append(s)
        for m in SUMMARY.finditer(body):
            hits["summary_flip"].append(m.group(0))
        for m in SHORT_QUOTE.finditer(p):
            before = p[max(0, m.start() - 6):m.start()]
            if not SPEECH_BEFORE.search(before):
                hits["scare_quotes"].append(m.group(0))

    for p in prose:
        body = QUOTED.sub("", p)
        for m in COLON_LIST.finditer(body):
            items = [x for x in LIST_SEP.split(m.group(1)) if x.strip()]
            if len(items) >= 3 and all(_han(x) <= 10 for x in items[:3]):
                hits["colon_list"].append(m.group(0)[:40])
        sents = [x.strip() for x in SENT.findall(body)]
        if len(sents) >= 2:
            last = sents[-1]
            halves = [h for h in re.split(r"[，,；;]", last.rstrip("。！？!?”")) if h.strip()]
            if _han(last) <= 34 and len(halves) == 2:
                a, b = (_han(h) for h in halves)
                cue = sum(1 for c in PARALLEL_CUES if c in halves[0]) and sum(1 for c in PARALLEL_CUES if c in halves[1])
                if (last.count("越") >= 2 or (cue and min(a, b) >= 5 and abs(a - b) <= 3)):
                    hits["aphorism"].append(last)
        for m in CALLBACK.finditer(body):
            hits["callback"].append(body[m.start():m.end() + 8])
        for m in PROCESS_I.finditer(body):
            hits["process_i"].append(body[max(0, m.start() - 6):m.end() + 6])

    attrib = Counter()
    examples: dict[str, list[str]] = {}
    for p in prose:
        for m in ATTRIB.finditer(QUOTED.sub("", p)):
            src = m.group(1)
            if src in ATTRIB_STOP or any(c in "的了是在和与就也都还又" for c in src):
                continue
            attrib[src] += 1
            examples.setdefault(src, []).append(m.group(0))
    for src, n in attrib.items():
        if n > LIMITS["attribution_repeat"]:
            hits["attribution_repeat"].append(f"“{src}”作为出处出现 {n} 次：" + "、".join(examples[src][:5]))

    han_k = max(_han(text) / 1000, 0.3)
    rules, passed = [], True
    for key, label, kind in RULES:
        if paper and key == "scare_quotes":  # quoted terms are normal in academic prose
            rules.append({"rule": key, "label": label, "passed": True, "count": 0, "hits": [], "skipped": True})
            continue
        found = hits[key]
        if kind == "share":
            value = round(len(found) / len(long_paras), 2) if long_paras else 0.0
            ok = len(found) < SHORT_LEAD_MIN or value <= LIMITS[key]
            limit = f"占长段落 ≤{int(LIMITS[key] * 100)}%"
        elif kind == "per_k":
            value = round(len(found) / han_k, 2)
            ok = value <= LIMITS[key]
            limit = f"每千字 ≤{LIMITS[key]}"
        elif key == "attribution_repeat":
            value = len(found)
            ok = not found
            limit = f"同一出处 ≤{LIMITS[key]} 次"
        else:
            value = len(found)
            ok = value <= LIMITS[key]
            limit = f"≤{LIMITS[key]}"
        gate = key in GATES
        if gate:
            passed &= ok
        rules.append({"rule": key, "label": label, "count": len(found), "value": value, "limit": limit,
                      "passed": ok, "gate": gate, "hits": found[:12]})
    # 能不用引号就不用：every quotation outside dialogue and attributed speech is listed
    # for the writer to reconsider. Informational only: it neither blocks nor counts
    # toward stacking (revisions must keep the author's own quotes).
    quotes = []
    for p in prose:
        for m in re.finditer(r"“([^”\n]{1,40})”", p):
            before = p[max(0, m.start() - 6):m.start()]
            if not SPEECH_BEFORE.search(before) and not re.search(r"[。！？!?]$", m.group(1)):
                quotes.append(m.group(0))
    over = [r["label"] for r in rules if not r["passed"]]
    stacked = len(over) > STACK_LIMIT
    return {"passed": passed and not stacked, "paragraphs": len(prose), "long_paragraphs": len(long_paras),
            "rules": rules, "stacked": {"count": len(over), "limit": STACK_LIMIT, "passed": not stacked, "rules": over},
            "quotes": quotes}


def report(r: dict) -> str:
    out = []
    for rule in r["rules"]:
        if rule.get("skipped"):
            out.append(f"{rule['label']}：论文模式不扫")
            continue
        state = "" if rule["passed"] else ("  ← 未通过" if rule["gate"] else "  ← 提示：逐处看一遍，是套路就改")
        val = f"{rule['value']}" if rule["rule"] in ("short_lead", "scare_quotes") else f"{rule['count']} 处"
        out.append(f"{rule['label']}：{val}（{rule['limit']}）{state}")
        if not rule["passed"]:
            for h in rule["hits"]:
                out.append(f"    {h[:60]}")
    if r.get("quotes"):
        out.append(f"引号（能不用就不用）：{len(r['quotes'])} 处，逐处看能不能去掉：" + "、".join(r["quotes"][:12]))
    st = r.get("stacked")
    if st:
        state = "" if st["passed"] else "  ← 未通过：套路叠在一起，读者一眼就能看出来"
        out.append(f"套路叠加：{st['count']} 类超标（≤{st['limit']}）{state}")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    p.add_argument("--paper", action="store_true", help="论文模式：不扫引号")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    r = scan(read_any(a.path), paper=a.paper)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else report(r))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
