#!/usr/bin/env python3
"""Report contextual structure signals in a Chinese draft (结构信号).

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

And meta_source: words that are not about the subject, an opener announcing
what follows or where it comes from (下面关于……的内容都出自……) and remarks on the
writer's own sources (材料里只有两条 / 课程都没有讲). Naming a source when it is part
of the argument is fine.

All observations are hints. Counts and co-occurrence do not decide writing
quality or block delivery. A fresh judge assesses whether the structure serves
the content. Normal academic subjects, headings, citations and topic sentences
are permitted. Code, math, quoted dialogue and reference lists are not scanned.

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
# Words that are not about the subject: an opener announcing what follows or
# where it comes from, and remarks on the writer's own sources (what they cover,
# what they leave out). Naming a source as part of the argument is fine.
META_OPEN = re.compile(r"^(下面|以下|这篇文章|这篇|接下来)[^。！？\n]{0,20}(内容|介绍|讨论|谈谈|说说|讲讲|分析|关于|将|要)")
META_SOURCE = re.compile(r"(材料|资料|课程|课件|讲座|字幕|视频|阅读材料|本单元|这一单元|这一讲|那几讲|这几讲)"
                         r"(里|中|上)?(都|还|也|并|又)?(只有|没有讲|没讲|都没有讲|都没讲|没有交代|没交代|没有提|没提|没有说|没说)"
                         r"|(都|均)?(出自|来自|取自)(本|这|以上|上述|所给的?|提供的)?(单元|课程|材料|资料|讲座|课件|字幕)")
# 课上讲过 / 老师说过 / 讲座里提到过: where a fact was heard. Not banned; a hint,
# because the source is often unnecessary: state the fact directly unless the
# source matters to the point.
SOURCE_MENTION = re.compile(r"(课上|课堂上|上课时|老师|讲座里|讲座上|材料里|资料里|书上|课本上)(也|还|都)?(讲过|说过|提到过|提过|讲到过|学过|讲了|说了)")

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
    ("meta_source", "开场白和无关交代", "count"),
    ("source_mention", "交代信息出处（非必要不写）", "count"),
)
# Preserve the 3.8 attribution signal while removing acceptance thresholds.
ATTRIBUTION_REPEAT_MIN = 6
SHORT_LEAD_MAX_HAN = 10   # a "short verdict" opener has at most this many Han characters
OPENER_MAX_HAN = 20       # listed for review (not counted): what the judges call 段首短判断
PROTECTED = re.compile(
    r"```.*?```|~~~.*?~~~|`[^`\n]*`|https?://\S+"
    r"|\$\$.*?\$\$|(?<!\\)\$[^\n$]+\$|\\\(.*?\\\)|\\\[.*?\\\]"
    r"|\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?|math|displaymath)\}.*?\\end\{\1\}"
    r"|\\(?:[A-Za-z]*cite[A-Za-z]*|[A-Za-z]*ref[A-Za-z]*|label|bibitem|bibliography|bibliographystyle)"
    r"\*?(?:\[[^\]\n]*\])*(?:\{[^{}\n]*\})+", re.S)
REFERENCE_HEAD = re.compile(r"^\s*(?:#*\s*(参考文献|references|bibliography)\s*|\\begin\{thebibliography\}(?:\{[^}]*\})?)$", re.I)
REFERENCE_ENTRY = re.compile(r"^\s*[\[［]\s*\d+\s*[\]］]")


def _han(s: str) -> int:
    return len(HAN.findall(s))


def _protected_prose(text: str) -> str:
    body = PROTECTED.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    lines, in_refs = [], False
    for line in body.splitlines():
        if REFERENCE_HEAD.match(line):
            in_refs = True
        lines.append("" if in_refs or REFERENCE_ENTRY.match(line) else line)
    return "\n".join(lines)


def paragraphs(text: str) -> list[str]:
    out = []
    for p in re.split(r"\n\s*\n|\n(?=\s*[#>*\-])", text):
        p = p.strip()
        if not p or p.startswith(("#", ">", "|", "```", "-", "*")) or re.match(r"^\d+[.、)]", p):
            continue
        out.append(p)
    return out


def scan(text: str, paper: bool = False) -> dict:
    paras = paragraphs(_protected_prose(text))
    prose = [p for p in paras if _han(p) >= 8]
    hits: dict[str, list[str]] = {k: [] for k, _, _ in RULES}

    if prose and META_OPEN.match(prose[0]):
        first = SENT.match(prose[0])
        hits["meta_source"].append((first.group(0) if first else prose[0])[:40])
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
            head = re.split(r"[，,；;]", m.group(1))[0]  # the list is what follows the colon up to the first comma
            items = [x for x in head.split("、") if x.strip()]
            if len(items) >= 3 and all(_han(x) <= 8 for x in items[:3]):
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
        for m in META_SOURCE.finditer(body):
            hits["meta_source"].append(body[max(0, m.start() - 6):m.end() + 8])
        for m in SOURCE_MENTION.finditer(body):
            hits["source_mention"].append(body[max(0, m.start() - 6):m.end() + 8])
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
        if n >= ATTRIBUTION_REPEAT_MIN:
            hits["attribution_repeat"].append(f"“{src}”作为出处出现 {n} 次：" + "、".join(examples[src][:5]))

    han_k = max(_han(text) / 1000, 0.3)
    rules = []
    for key, label, kind in RULES:
        if paper and key == "scare_quotes":  # quoted terms are normal in academic prose
            rules.append({"rule": key, "label": label, "passed": True, "gate": False, "flagged": False,
                          "count": 0, "hits": [], "skipped": True})
            continue
        found = hits[key]
        if kind == "share":
            value = round(len(found) / len(long_paras), 2) if long_paras else 0.0
        elif kind == "per_k":
            value = round(len(found) / han_k, 2)
        elif key == "attribution_repeat":
            value = len(found)
        else:
            value = len(found)
        rules.append({"rule": key, "label": label, "count": len(found), "value": value, "limit": None,
                      "passed": True, "gate": False, "flagged": bool(found), "hits": found[:12]})
    # 能不用引号就不用. In human prose most quotation marks hold a whole sentence
    # someone said (classics 51%, web novels and Tieba 82%); in model output most sit
    # on a single word or label (59%; Claude 64%): “上瘾模型” “参考地图” “一点点”.
    # Counted per piece the two overlap (people quote names and terms too), so this
    # never blocks: the word and phrase quotes are listed for the remove-the-quotes
    # test, and revisions keep the author's own quotes.
    quotes, sentence_quotes = [], 0
    for p in prose:
        for m in re.finditer(r"“([^”\n]{1,80})”", p):
            inner, before = m.group(1), p[max(0, m.start() - 6):m.start()]
            if re.search(r"[。！？!?…，,；;：:]", inner) or _han(inner) > 12:
                sentence_quotes += 1
            elif not SPEECH_BEFORE.search(before):
                quotes.append(m.group(0))
    # Paragraphs that open with one short sentence (20 Han characters or fewer).
    # The judges' 段首短判断 is wider than the short_lead signal above (they flag
    # "从这个冬至到下一个冬至是一年。" and "可太阳走得并不匀。"), but a short
    # opener is just as often plain narration (classics: 58% of pieces have three),
    # so this only lists them for the writer to check, and never blocks.
    openers = []
    for p in long_paras:
        first = SENT.match(QUOTED.sub("", p))
        if first and _han(first.group(0)) <= OPENER_MAX_HAN and first.group(0).rstrip()[-1] in "。":
            openers.append(first.group(0).strip())
    observed = [r["label"] for r in rules if r.get("flagged")]
    return {"passed": True, "paragraphs": len(prose), "long_paragraphs": len(long_paras),
            "rules": rules, "stacked": {"count": len(observed), "limit": None, "passed": True, "rules": observed},
            "quotes": quotes, "sentence_quotes": sentence_quotes, "openers": openers}


def report(r: dict) -> str:
    out = []
    for rule in r["rules"]:
        if rule.get("skipped"):
            out.append(f"{rule['label']}：论文模式不扫")
            continue
        out.append(f"{rule['label']}：{rule['count']} 处（仅提示，按语义和文体判断）")
        if rule.get("flagged"):
            for h in rule["hits"]:
                out.append(f"    {h[:60]}")
    if r.get("quotes"):
        out.append(f"引号套在词和短语上 {len(r['quotes'])} 处（引整句的 {r.get('sentence_quotes', 0)} 处不算）："
                   "核对引用、专名或讨论用语，保留有用表达："
                   + "、".join(r["quotes"][:12]))
    if len(r.get("openers", [])) >= 2:
        out.append(f"段首第一句很短的段落 {len(r['openers'])} 个（仅提示，按语义和文体判断）："
                   "正常主题句、结论句和事实可以保留，核对其与后文的关系："
                   + "｜".join(r["openers"][:8]))
    st = r.get("stacked")
    if st:
        out.append(f"结构信号：{st['count']} 类有命中，数量不决定通过，质量由独立内容评审判断")
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
