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


def test_flat_is_a_literary_quality_check_not_a_demand_for_practical_prose():
    assert review_zh.check_review(TEXT, review(5, flat=True), "周报")["passed"]
    assert not review_zh.check_review(TEXT, review(5, flat=True), "游记散文")["passed"]


def test_templates_and_devices_are_contextual_observations():
    s = review(5)
    s["templates"] = [{"type": "总结翻转", "evidence": "罗马人拆自己的城，拆了两千年"}]
    assert review_zh.check_review(TEXT, s, "城市随笔散文")["passed"]
    s["templates"].append({"type": "滥用引号", "evidence": "外墙上那一排排碗口大的坑"})
    assert review_zh.check_review(TEXT, s, "城市随笔散文")["passed"]
    s["scores"]["language"]["score"] = 2
    assert not review_zh.check_review(TEXT, s, "城市随笔散文")["passed"]
    # devices (设问自答, 单句成段 ...) are common in human prose: listed, never failing
    d = review(5)
    d["devices"] = [{"type": "设问自答", "evidence": "斗兽场缺的那半圈"},
                    {"type": "前后回扣", "evidence": "没有一只在乎这里死过谁"},
                    {"type": "单句转折段", "evidence": "编出来的句子不在原文里"}]
    r = review_zh.check_review(TEXT, d, "城市随笔散文")
    assert r["passed"] and len(r["devices"]) == 2
    assert "手法重复 2 处" in review_zh.report(r, None)


def test_off_task_fails_with_the_judges_note():
    s = review(5)
    s["off_task"], s["task_note"] = True, "任务要对比两地，正文只写了罗马"
    r = review_zh.check_review(TEXT, s, "游记散文")
    assert not r["passed"] and "只写了罗马" in review_zh.report(r, None)
    s["off_task"] = "false"  # anything but a real true is not a verdict
    assert review_zh.check_review(TEXT, s, "游记散文")["passed"]


def test_length_only_off_task_is_a_reminder_when_the_material_is_short():
    s = review(5)
    s["off_task"], s["off_task_kind"], s["task_note"] = True, "篇幅", "要一千字，正文三百多字"
    r = review_zh.check_review(TEXT, s, "散文")
    assert not r["passed"] and "--short-material" in review_zh.report(r, None)
    r = review_zh.check_review(TEXT, s, "散文", short_material=True)
    assert r["passed"] and r["length_only"] and "篇幅提醒" in review_zh.report(r, None)
    s["off_task_kind"] = "内容"  # really off task: the flag does not help
    assert not review_zh.check_review(TEXT, s, "散文", short_material=True)["passed"]


def test_compare_needs_the_new_draft_to_win_both_orders():
    a, b = {"better": "A", "margin": "明显"}, {"better": "B", "margin": "略微"}
    # first reply has the original as A, second has the new draft as A
    assert review_zh.check_compare(b, a)["replace"]
    c = review_zh.check_compare(a, a)  # A both times: position, not quality
    assert not c["replace"] and [v["winner"] for v in c["votes"]] == ["base", "new"]
    assert not review_zh.check_compare(b, {"better": "都好"})["replace"]
    assert "交原稿" in review_zh.compare_report(c)


def test_facts_doubt_blocks_own_draft_rhetoric_does_not():
    ok = {"claims": [{"text": "拆了两千年", "verdict": "rhetoric"}, {"text": "一三四九年的地震", "verdict": "ok"}]}
    bad = {"claims": [{"text": "一三四九年的地震", "verdict": "doubt", "note": "x"}]}
    assert review_zh.check_facts(TEXT, ok, own=True)["passed"]
    assert not review_zh.check_facts(TEXT, bad, own=True)["passed"]


def test_facts_doubt_in_someone_elses_draft_is_listed_not_blocking():
    bad = {"claims": [{"text": "一三四九年的地震", "verdict": "doubt", "note": "x"}]}
    r = review_zh.check_facts(TEXT, bad)
    assert r["passed"] and len(r["doubts"]) == 1
    assert "待作者核对" in review_zh.report(review_zh.check_review(TEXT, review(4), "城市随笔散文"), r)


PAPER_ORIG = "实验结果表明，随机森林模型表现最优，这可能与数据的规模和特征的尺度有关。线性模型无法有效捕捉票房数据中的非线性关系。"
PAPER_REV = "随机森林表现最好，原因在于数据的规模和特征的尺度。线性模型无法有效捕捉票房数据中的非线性关系。"


def test_paper_dimensions_and_gate():
    quotes = ["随机森林表现最好，原因在于数据的规模", "线性模型无法有效捕捉票房数据中的非线性关系"] * 3
    rv = {"scores": {k: {"score": 4, "evidence": q, "fix": ""} for (k, _), q in zip(review_zh.PAPER_DIMENSIONS, quotes)}}
    r = review_zh.check_review(PAPER_REV, rv, "课程设计报告", paper=True)
    assert r["valid"] and r["passed"] and set(r["dims"]) == {k for k, _ in review_zh.PAPER_DIMENSIONS}
    # a literary-rubric review is void in paper mode
    assert not review_zh.check_review(PAPER_REV, review(5), "课程设计报告", paper=True)["valid"]


def test_rigor_regression_needs_both_quotes_and_fails():
    rig = {"regressions": [{"original": "这可能与数据的规模和特征的尺度有关", "revised": "原因在于数据的规模和特征的尺度",
                            "type": "模态", "note": "推测改成了结论"},
                           {"original": "编造的一句原稿里没有的话", "revised": "随机森林表现最好", "type": "论断"}],
           "issues": [{"text": "线性模型无法有效捕捉票房数据中的非线性关系", "type": "表述", "note": "x"}]}
    g = review_zh.check_rigor(PAPER_ORIG, PAPER_REV, rig)
    assert not g["passed"] and len(g["regressions"]) == 1 and g["void"] == 1 and len(g["issues"]) == 1
    assert review_zh.check_rigor(PAPER_ORIG, PAPER_ORIG, {"regressions": [], "issues": []})["passed"]


def test_load_json_tolerates_wrapping():
    assert review_zh.load_json('好的：```json\n{"claims": []}\n```')["claims"] == []


def test_model_identity_and_calibration_cannot_override_research_writing_gates(tmp_path, monkeypatch):
    t = tmp_path / "th.json"
    t.write_text('{"models": {"strict-model": {"literary": {"average": 3.5, "each": 3}, '
                 '"practical": {"average": 3.0, "each": 3}}}}', encoding="utf-8")
    monkeypatch.setenv("SHUOZHONGWEN_THRESHOLDS", str(t))
    s = review(4)
    s["scores"]["voice"]["score"] = 3
    s["scores"]["rhythm"]["score"] = 3
    s["scores"]["insight"]["score"] = 3   # average 3.5
    assert not review_zh.check_review(TEXT, s, "游记散文")["passed"]
    r = review_zh.check_review(TEXT, s, "游记散文", model="Strict-Model")
    assert not r["passed"] and r["gate"] == {"average": 4.0, "each": 3, "source": "固定分数线"}
    assert review_zh.check_review(TEXT, review(3), "周报", model="Strict-Model")["passed"] is False
    assert review_zh.check_review(TEXT, s, "周报", model="other-model")["gate"]["average"] == 3.5
    assert review_zh.thresholds()["models"]["strict-model"]["literary"]["average"] == 3.5
    assert "固定分数线" in review_zh.report(r, None)
    t.write_text('{"models": {"strict-model": {"literary": {"average": 5.0, "each": 5}, '
                 '"practical": {"average": 5.0, "each": 5}}}}', encoding="utf-8")
    assert review_zh.check_review(TEXT, review(4), "游记散文", model="strict-model")["passed"]
    assert review_zh.check_review(TEXT, review(4), "周报", model="strict-model")["passed"]


def test_load_json_repairs_unescaped_quotes_inside_strings():
    raw = '{"scores": {"concrete": {"score": 4, "evidence": "他说"好"就走了，没有回头", "fix": "x"}}, "flat": false}'
    d = review_zh.load_json(raw)
    assert d["scores"]["concrete"]["evidence"] == '他说"好"就走了，没有回头' and d["flat"] is False


def test_template_count_does_not_override_evidence_based_scores():
    rv = review(4)
    rv["templates"] = [{"type": "需结合文体判断", "evidence": q} for q in QUOTES]
    r = review_zh.check_review(TEXT, rv, "周报")
    assert r["passed"] and len(r["templates"]) == len(QUOTES)
    rv["scores"]["language"]["score"] = 2
    assert not review_zh.check_review(TEXT, rv, "周报")["passed"]


def test_invalid_scores_cannot_bypass_the_one_to_five_rubric():
    for score in (0, 6, 4.5, True, None, "not a score"):
        r = review_zh.check_review(TEXT, review(score), "周报")
        assert not r["valid"] and not r["passed"]


def test_new_paper_issues_need_evidence_from_the_new_draft():
    rig = {"regressions": [], "issues": [
        {"text": "原因在于数据的规模和特征的尺度", "type": "结论与证据", "note": "需作者核对支持依据"},
        {"text": "这句话并没有出现在新的稿件中", "type": "方法"},
    ]}
    g = review_zh.check_rigor("", PAPER_REV, rig)
    assert g["new_draft"] and not g["valid"] and not g["passed"] and len(g["issues"]) == 1 and g["void"] == 1
    r = review_zh.check_review(TEXT, review(4), "周报")
    report = review_zh.report(r, None, g)
    assert "新稿问题 1 条" in report and "原稿问题" not in report
    assert "审查无效" in report and "需全新评委重审" in report and report.endswith("结论：未通过")


def test_existing_paper_issues_cannot_quote_only_the_revised_version():
    g = review_zh.check_rigor(PAPER_ORIG, PAPER_REV, {
        "regressions": [], "issues": [{"text": "原因在于数据的规模和特征的尺度", "type": "结论与证据"}],
    })
    assert not g["new_draft"] and g["issues"] == [] and g["void"] == 1 and not g["passed"]


def test_invalid_regression_alone_cannot_produce_a_successful_rigor_review():
    rig = {"regressions": [{"original": "这句话从未出现在原稿中", "revised": "这句话也没有出现在新稿中", "type": "论断"}], "issues": []}
    g = review_zh.check_rigor(PAPER_ORIG, PAPER_REV, rig)
    assert g["regressions"] == [] and g["void"] == 1 and not g["valid"] and not g["passed"]


def test_empty_rigor_findings_and_valid_new_draft_issues_pass():
    for original in (PAPER_ORIG, ""):
        g = review_zh.check_rigor(original, PAPER_REV, {"regressions": [], "issues": []})
        assert g["valid"] and g["passed"] and g["void"] == 0
    g = review_zh.check_rigor("", PAPER_REV, {
        "regressions": [], "issues": [{"text": "原因在于数据的规模和特征的尺度", "type": "结论与证据"}],
    })
    assert g["valid"] and g["passed"] and len(g["issues"]) == 1
