"""How often each structural template rule fires on human text and on AI text.

A rule that fires as often on human writing as on model output is not an AI
signal; it is a ban on an ordinary writing device. Run this before adding a
rule to scripts/structure_scan.py or to the judge's 模板腔 list (agents/judge.md).

Every file in calibration/human/ and calibration/ai/ is cut into pieces of about
1500 characters (whole paragraphs, at most two per file; a shorter file counts
once if it has 500 characters), the length of a typical article written with
/shuozhongwen. For every piece it records which rules hit at least once, whether
the structure gate fails, and how many template instances there are in total
(the judge used to fail a draft at two). Also compares a few punctuation and
connector rates, because several rules in the skill's references push against
them. Writes calibration/TEMPLATE_AUDIT.md.
"""

from __future__ import annotations

import re
import statistics
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import score_zh  # noqa: E402
import structure_scan  # noqa: E402

PIECE = 1500
GROUPS = (
    ("经典名作", lambda n: not n.startswith(("qidian", "tieba")), "human"),
    ("网文和贴吧", lambda n: n.startswith(("qidian", "tieba")), "human"),
    ("AI 样本（8 个模型）", lambda n: True, "ai"),
)
RATES = (("dash_per_k", "破折号"), ("question_per_k", "问号"), ("ellipsis_per_k", "省略号"),
         ("exclaim_per_k", "感叹号"), ("connector_per_k", "连接词"), ("quote_per_k", "引号"), ("colon_per_k", "冒号"))


def pieces(text: str) -> list[str]:
    out, cur = [], ""
    for p in (p for p in re.split(r"\n\s*\n|\n", text) if p.strip()):
        cur += p + "\n\n"
        if len(cur) >= PIECE:
            out.append(cur)
            cur = ""
            if len(out) == 2:
                break
    if not out and len(cur) >= 500:
        out.append(cur)
    return out


def audit(files: list[Path]) -> dict:
    n, gate, two, q_sentence, q_word = 0, 0, 0, 0, 0
    per_rule: dict[str, int] = {k: 0 for k, _, _ in structure_scan.RULES}
    rates: dict[str, list[float]] = {k: [] for k, _ in RATES}
    for f in files:
        text = f.read_text(encoding="utf-8")
        feats, _ = score_zh.extract_features(text)
        for k, _ in RATES:
            if feats.get(k) is not None:
                rates[k].append(feats[k])
        whole = structure_scan.scan(text)
        q_sentence += whole["sentence_quotes"]
        q_word += len(whole["quotes"])
        for c in pieces(text):
            r = structure_scan.scan(c)
            n += 1
            gate += not r["passed"]
            instances = 0
            for rule in r["rules"]:
                if rule["count"]:
                    per_rule[rule["rule"]] += 1
                    if rule["rule"] != "source_mention":
                        instances += rule["count"]
            two += instances >= 2
    return {"n": n, "gate": gate, "two": two, "per_rule": per_rule, "q_sentence": q_sentence, "q_word": q_word,
            "rates": {k: statistics.mean(v) if v else 0.0 for k, v in rates.items()}}


def pct(a: int, b: int) -> str:
    return f"{a / b:.0%}" if b else "-"


def main() -> int:
    results = []
    for label, keep, folder in GROUPS:
        files = sorted(f for f in (HERE / folder).glob("*.txt") if keep(f.name))
        results.append((label, audit(files)))
    head = "| 规则 | 拦不拦 | " + " | ".join(label for label, _ in results) + " |"
    sep = "|---|---|" + "---|" * len(results)
    lines = ["# 结构套路规则体检：人类文字和 AI 文字各命中多少", "",
             f"日期：{date.today()}。脚本：`python calibration/template_audit.py`。"
             f"每篇切成约 {PIECE} 字的片段（整段切，每篇最多两段），这是用 /shuozhongwen 写一篇文章的常见长度。"
             "表里是至少命中一次的片段比例。", "",
             "| | " + " | ".join(label for label, _ in results) + " |", "|---|" + "---|" * len(results),
             "| 片段数 | " + " | ".join(str(r["n"]) for _, r in results) + " |",
             "| 结构扫描不通过（拦交付） | " + " | ".join(pct(r["gate"], r["n"]) for _, r in results) + " |",
             "| 套路总数 ≥ 2 处 | " + " | ".join(pct(r["two"], r["n"]) for _, r in results) + " |",
             "", head, sep]
    for key, label, _ in structure_scan.RULES:
        gate = "拦" if key in structure_scan.GATES else "提示"
        lines.append(f"| {label} | {gate} | " + " | ".join(pct(r["per_rule"][key], r["n"]) for _, r in results) + " |")
    lines += ["", "每千字的标点和连接词（整篇算，取平均）：", "",
              "| | " + " | ".join(label for label, _ in results) + " |", "|---|" + "---|" * len(results)]
    for key, label in RATES:
        lines.append(f"| {label} | " + " | ".join(f"{r['rates'][key]:.2f}" for _, r in results) + " |")
    lines += ["", "引号引的是什么（整篇算，说话动词后面的短引语不算）：", "",
              "| | " + " | ".join(label for label, _ in results) + " |", "|---|" + "---|" * len(results),
              "| 引整句的原话 | " + " | ".join(pct(r["q_sentence"], r["q_sentence"] + r["q_word"]) for _, r in results) + " |",
              "| 套在词和短语上 | " + " | ".join(pct(r["q_word"], r["q_sentence"] + r["q_word"]) for _, r in results) + " |",
              "", "引号的总数人和 AI 差不多，用法不一样：人多半引整句，AI 多半套在词上。按片段机械计数分不开"
              "（人也给人名、绰号、术语加引号），所以扫描只列出来让作者做去引号测试，由评委按语义判滥用引号。"]
    lines += ["", "怎么读：一条规则在人类文字里命中得和 AI 一样多、甚至更多，它就不是 AI 信号，只是一种常见写法；"
              "这样的规则只能当提示，不能拦交付，评委也不该把它算进模板腔。"
              "标点那张表同理：人类文字的破折号、问号、连接词都比 AI 多，规则里不能把它们当 AI 腔一律删。", "",
              "局限：AI 样本是各模型直接写的，没有用这个插件。模型照着一长串禁令写稿时会多出哪些套路"
              "（比如把长句全剁成短判断句），这里看不出来，要拿用插件写出来的稿子另测。", ""]
    (HERE / "TEMPLATE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
