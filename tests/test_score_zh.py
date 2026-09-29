"""Tests for the Chinese stylometry gauge."""

from __future__ import annotations

import score_zh
from haohao_markers import load_markers

AI = (
    "在当今快速发展的时代，人工智能正在深刻地改变我们的生活方式。值得注意的是，这一变革不仅带来了机遇，也带来了挑战。"
    "首先，我们需要进行全面的分析；其次，我们需要作出合理的规划；最后，我们需要实现有效的落地。\n\n"
    "综上所述，只有不断创新，才能在激烈的竞争中立于不败之地。企业应当积极拥抱变化，持续提升核心竞争力，从而在新的时代浪潮中把握先机。"
    "与此同时，个人也需要不断学习，提升自身的综合素质，以适应社会发展的需要。\n\n"
    "总而言之，人工智能的发展是一个系统工程，需要政府、企业和个人的共同努力。让我们携手并进，共同迎接更加美好的未来。\n"
)

HUMAN = (
    "我与父亲不相见已二年余了，我最不能忘记的是他的背影。那年冬天，祖母死了，父亲的差使也交卸了，正是祸不单行的日子，"
    "我从北京到徐州，打算跟着父亲奔丧回家。到徐州见着父亲，看见满院狼藉的东西，又想起祖母，不禁簌簌地流下眼泪。"
    "父亲说：“事已如此，不必难过，好在天无绝人之路！”\n\n"
    "回家变卖典质，父亲还了亏空；又借钱办了丧事。这些日子，家中光景很是惨淡，一半为了丧事，一半为了父亲赋闲。"
    "丧事完毕，父亲要到南京谋事，我也要回北京念书，我们便同行。\n\n"
    "到南京时，有朋友约去游逛，勾留了一日；第二日上午便须渡江到浦口，下午上车北去。父亲因为事忙，本已说定不送我，"
    "叫旅馆里一个熟识的茶房陪我同去。他再三嘱咐茶房，甚是仔细。\n"
)


def test_short_text_is_not_scored():
    r = score_zh.score_text_stylometry("这是一句很短的话。", path="s")
    assert r.status == "insufficient_length"
    assert r.score is None and r.density_tier == "uncalibrated"


def test_ai_text_scores_above_human_text():
    ai = score_zh.score_text_stylometry(AI, path="ai")
    human = score_zh.score_text_stylometry(HUMAN, path="human")
    assert ai.status == human.status == "ok"
    assert ai.score > human.score
    assert ai.density_tier == "high"
    assert human.density_tier != "high"


def test_chinese_sentences_are_split():
    r = score_zh.score_text_stylometry(HUMAN, path="h")
    assert r.sentence_count >= 8
    assert r.burstiness_cv is not None


def test_code_fence_is_ignored():
    fenced = "```\n" + AI + "\n```\n"
    r = score_zh.score_text_stylometry(fenced, path="f")
    assert r.word_count == 0 and r.status == "insufficient_length"


def test_compute_burstiness_unmeasurable():
    assert score_zh.compute_burstiness([])[2] is None
    assert score_zh.compute_burstiness(["只有一句。"])[2] is None


def test_markers_come_from_haohao_when_present():
    pats, note = load_markers()
    if note:  # skill references missing
        return
    labels = {label for _, label in pats}
    assert "至关重要" in labels


def test_missing_haohao_degrades_gracefully(monkeypatch, tmp_path):
    import haohao_markers

    monkeypatch.setenv("SHUOZHONGWEN_SKILL_DIR", str(tmp_path))
    haohao_markers.load_markers.cache_clear()
    try:
        r = score_zh.score_text_stylometry(AI, path="ai")
        assert r.matched_markers == []
        assert any("phrase markers skipped" in n for n in r.notes)
    finally:
        haohao_markers.load_markers.cache_clear()


def test_chinese_prose_mentioning_c2pa_is_not_provenance():
    from container_meta import named_value_is_ai

    assert not named_value_is_ai("description", "中文环境的去 AI 检测：清理图片里的 C2PA、EXIF 和 AI 来源元数据。")
    assert named_value_is_ai("description", "这篇文章 generated with ChatGPT，内容仅供参考和学习使用。")
    assert named_value_is_ai("description", "c2pa manifest")


def test_claude_code_agent_config_keys_are_not_provenance():
    from container_meta import inspect_markdown

    fm = "---\nname: judge\ndescription: x\ntools: Read\nmodel: inherit\nomitClaudeMd: true\nmaxTurns: 1\n---\n\nbody\n"
    has_ai = inspect_markdown(fm)[0]
    assert has_ai is False
