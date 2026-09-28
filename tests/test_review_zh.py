"""review_zh: evidence rule, gate and fact summary (no model calls)."""

from __future__ import annotations

import review_zh

TEXT = ("罗马人拆自己的城，拆了两千年。斗兽场缺的那半圈，一部分是一三四九年的地震震塌的。"
        "外墙上那一排排碗口大的坑，是有人为了撬出石块之间的铁栓凿出来的。"
        "午后，猫趴在两千年前的石柱底座上晒太阳，没有一只在乎这里死过谁。")
QUOTES = ["罗马人拆自己的城，拆了两千年", "外墙上那一排排碗口大的坑", "斗兽场缺的那半圈",
          "是有人为了撬出石块之间的铁栓凿出来的", "一部分是一三四九年的地震震塌的", "没有一只在乎这里死过谁"]


def review(score=4, quotes=QUOTES, flat=False):
    return {"scores": {k: {"score": score, "evidence": q, "fix": "改法"} for (k, _), q in zip(review_zh.DIMENSIONS, quotes)},
            "flat": flat, "cliche": [], "summary": ""}


def test_passes_with_verbatim_evidence():
    r = review_zh.check_review(TEXT, review(4), "城市随笔散文")
    assert r["valid"] and r["passed"] and r["average"] == 4.0


def test_evidence_ignores_whitespace_and_quote_marks():
    q = list(QUOTES)
    q[0] = "“罗马人拆自己的城 拆了两千年”"
    assert review_zh.check_review(TEXT, review(5, q), "城市随笔散文")["valid"]


def test_invented_evidence_voids_the_dimension_and_the_review():
    q = list(QUOTES)
    q[2] = "罗马是一座充满魅力的永恒之城"
    r = review_zh.check_review(TEXT, review(5, q), "城市随笔散文")
    assert not r["valid"] and "语言与意象" in r["void"] and not r["passed"]


def test_too_short_evidence_is_void():
    q = list(QUOTES)
    q[1] = "罗马"
    assert not review_zh.check_review(TEXT, review(5, q), "城市随笔散文")["valid"]


def test_literary_and_practical_gates():
    assert not review_zh.check_review(TEXT, review(3), "城市随笔散文")["passed"]
    s = review(4)
    s["scores"]["voice"]["score"] = 3
    s["scores"]["rhythm"]["score"] = 3
    assert review_zh.check_review(TEXT, s, "周报")["passed"]      # 3.67 >= 3.5
    assert not review_zh.check_review(TEXT, s, "游记散文")["passed"]  # 3.67 < 4.0


def test_flat_always_fails():
    assert not review_zh.check_review(TEXT, review(5, flat=True), "周报")["passed"]


def test_facts_doubt_blocks_rhetoric_does_not():
    ok = {"claims": [{"text": "拆了两千年", "verdict": "rhetoric"}, {"text": "一三四九年的地震", "verdict": "ok"}]}
    bad = {"claims": [{"text": "一三四九年的地震", "verdict": "doubt", "note": "x"}]}
    assert review_zh.check_facts(TEXT, ok)["passed"]
    assert not review_zh.check_facts(TEXT, bad)["passed"]


def test_load_json_tolerates_wrapping():
    assert review_zh.load_json('好的：```json\n{"claims": []}\n```')["claims"] == []
