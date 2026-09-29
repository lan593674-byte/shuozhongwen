#!/usr/bin/env python3
"""One entry point for checking a Chinese draft before it is delivered.

Runs, in this order, and reports all of them:
1. invisible Unicode carriers (text_unicode, report only)
2. the skill's four zero-tolerance scans (haohao_scan)
3. the Chinese stylometry gauge (score_zh): tier, where the score sits among
   human text, and (only when the tier is high) what to fix

The draft passes when: no invisible carriers, every scan passes, and the
stylometry tier is not "high". Scoring lower than typical human text is not a
goal; writing quality is checked separately by review_zh.py. Exit code 0 = pass.
The rewriting itself is done by a person or by Claude following
the shuozhongwen skill; this script only checks and never edits the file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import haohao_scan  # noqa: E402
from doc_text import read_any  # noqa: E402
import score_zh  # noqa: E402
from text_unicode import inspect_text  # noqa: E402

FEATURE_ZH = {
    "sent_cv": "句长起伏小", "para_cv": "段长起伏小", "connector_per_k": "连接词少",
    "start_repeat": "相邻句开头从不重复", "format_ratio": "标题列表多", "bigram_mattr": "辞藻堆砌",
    "marker_per_k": "AI 味词句", "we_per_k": "“我们”多", "de_per_k": "“的”少", "colon_per_k": "冒号多",
    "closer": "结尾总结号召", "i_per_k": "“我”少", "quote_per_k": "引号多",
    "ellipsis_per_k": "省略号少", "exclaim_per_k": "感叹号少", "question_per_k": "问号少", "dash_per_k": "破折号少",
}


def check(text: str, paper: bool = False) -> dict:
    uni = inspect_text(text)
    invisible = getattr(uni, "suspicious_total", None)
    if invisible is None:
        invisible = uni.get("suspicious_total", 0) if isinstance(uni, dict) else 0
    scan = haohao_scan.scan(text, paper=paper)
    rep = score_zh.score_text_stylometry(text, path="<draft>")
    push = sorted(((k, v) for k, v in rep.contributions.items() if v > 0.3), key=lambda kv: -kv[1])
    style_ok = rep.status != "ok" or rep.density_tier != "high"
    return {
        "passed": invisible == 0 and scan["passed"] and style_ok,
        "invisible_chars": invisible,
        "haohao_scan": scan,
        "style": {"status": rep.status, "score": rep.score, "tier": rep.density_tier,
                  "human_percentile": rep.human_percentile,
                  "findings": rep.findings if rep.density_tier == "high" else [],
                  "pushing_up": [{"feature": k, "label": FEATURE_ZH.get(k, k), "weight": round(v, 2)} for k, v in push]},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    p.add_argument("--paper", action="store_true", help="论文模式：章节编号不扫")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    r = check(read_any(a.path), paper=a.paper)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["passed"] else 1
    print(f"不可见字符：{r['invisible_chars']} 个")
    for rule in r["haohao_scan"]["rules"]:
        if rule.get("skipped"):
            print(f"{rule['label']}：不扫（{rule['skipped']}）")
            continue
        print(f"{rule['label']}：{rule['count']} 处（上限 {rule['limit']}）{'' if rule['passed'] else '  ← 未通过'}")
        for h in rule["hits"][:5]:
            print(f"    第 {h['line']} 行：{h['text']}")
    s = r["style"]
    if s["score"] is None:
        print(f"文体评分：未评（{s['status']}）")
    else:
        pct = s.get("human_percentile")
        where = f"比 {pct}% 的人类段落更像 AI" if pct is not None else ""
        print(f"AI 相似度：{s['score']:.2f}（{s['tier']}，{where}）")
        if s["tier"] == "high":
            for f in s["findings"]:
                print(f"    待改：{f}")
            if s["pushing_up"]:
                print("    推高分数的特征：" + "、".join(f"{x['label']} +{x['weight']}" for x in s["pushing_up"]))
        else:
            print("    在人类文字的常见区间内，不用再往下压；写得好不好看 review_zh.py")
    print("结论：" + ("通过" if r["passed"] else "未通过，按上面逐项改完再跑"))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
