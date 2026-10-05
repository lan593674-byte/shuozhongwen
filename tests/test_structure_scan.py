"""structure_scan: structural AI templates; gates vs hints; calibration false-positive rate."""

from __future__ import annotations

import glob
from pathlib import Path

import structure_scan as ss

ROOT = Path(__file__).resolve().parents[1]

TEMPLATED = """这一单元的讲座把亚北极生活讲成一年的循环，人跟着资源走，春天打鸭子和雁，夏天打鱼，秋天拦截南下的驯鹿，冬天穿上雪鞋去追驼鹿。

这套描述的长处是清楚。资源只在特定的地方、特定的季节出现，所以人只好跟着走，这个约束是真的，讲座说它从阿拉斯加到纽芬兰都适用。

可是通用也有通用的代价。

最明显的是时态。春夏秋冬四讲几乎全用过去时，讲的是接触以前的样子，读完看不出这套循环在二十世纪有没有变过，讲座里还说当代只是“威胁”。

范围也一样。讲座承认材料主要取自加拿大亚北极，再往整个北方森林带推，可同一讲里就有例外，据讲座说萨米人从中世纪晚期就在种地。

先说传统。克里人按家族分猎区，每块猎区有一位管事的长辈，由他决定今年哪里能打、哪里要歇，讲座提到老猎人会决定哪只猎物留着繁殖。

代价一样具体。水库淹了大片猎区和鱼场，鱼的汞含量升高，政府发了食用警告，讲座担心的污染在这里有了实例，最靠鱼过日子的人家反倒要少吃鱼。

回头看，季节循环这个骨架没错。两边说的其实不是一回事，当代不只是外来的威胁，也包括克里人自己一条条谈下来的东西。
"""

PLAIN = """我外婆家的厨房在院子东头，屋顶压着几块青瓦，下雨天漏水，她就在灶台边摆一只搪瓷盆接着，叮叮咚咚响一晚上。

灶是土砌的，两口锅，一口煮猪食，一口做饭。外婆烧火用松毛，引火快，烟大，熏得她眼睛常年红着，她也不在乎，一边添柴一边跟我讲村里谁家的媳妇跑了。

那年冬天她摔了一跤，腿就不大好了。舅舅要接她去城里，她不肯，说城里的煤气灶打不着火，她看着心慌，宁可守着这口土灶慢慢烧。

后来厨房塌了半边，没人修。我去年回去，看见灶台还在，锅早被人拿走了，灶膛里长出一棵小构树，叶子比巴掌还大。
"""


def rules(text: str, **kw) -> dict:
    return {r["rule"]: r for r in ss.scan(text, **kw)["rules"]}


def test_templated_text_fails_on_the_gates():
    r = ss.scan(TEMPLATED)
    by = {x["rule"]: x for x in r["rules"]}
    assert not r["passed"]
    assert not by["short_lead"]["passed"] and "代价一样具体。" in by["short_lead"]["hits"]
    assert not by["summary_flip"]["passed"]
    assert not by["attribution_repeat"]["passed"] and "讲座" in by["attribution_repeat"]["hits"][0]
    assert "可是通用也有通用的代价。" in by["one_line_para"]["hits"]


def test_plain_human_prose_passes():
    assert ss.scan(PLAIN)["passed"]


def test_hints_never_block():
    text = PLAIN + "\n\n为什么她不肯走？这件事我想了很久。\n\n“灶”“锅”“柴”“火”都是她的“命”。\n"
    r = ss.scan(text)
    by = {x["rule"]: x for x in r["rules"]}
    assert r["passed"]
    assert by["self_qa"]["count"] >= 1 and not by["self_qa"]["gate"]
    assert not by["scare_quotes"]["gate"]


def test_paper_mode_skips_quote_rule():
    assert rules(TEMPLATED, paper=True)["scare_quotes"]["skipped"]


def test_gates_rarely_fire_on_human_calibration_texts():
    files = glob.glob(str(ROOT / "calibration" / "human" / "*.txt")) + glob.glob(str(ROOT / "calibration" / "test" / "*" / "*.txt"))
    texts = [t for t in (Path(f).read_text(encoding="utf-8") for f in files) if len(t) >= 300]
    if len(texts) < 100:
        return  # corpus not present (e.g. a minimal checkout)
    failed = sum(1 for t in texts if not ss.scan(t)["passed"])
    assert failed / len(texts) <= 0.04, (failed, len(texts))


def test_new_rules_and_stacking_on_the_templated_post():
    text = TEMPLATED + "\n\n当代只以威胁的身份出现：水坝、采矿、伐木、污染。性别分工那一讲我读得最久，短片我没找到字幕，只能看介绍。\n\n2009 年鲁珀特河的水开始改流，就是 1930 年代设河狸保护区的那条河。打猎越靠制度撑着，猎人跟水电公司就越难分开算账。\n"
    r = ss.scan(text)
    by = {x["rule"]: x for x in r["rules"]}
    assert by["colon_list"]["count"] >= 1
    assert by["process_i"]["count"] >= 2 and not by["process_i"]["gate"]
    assert by["callback"]["count"] == 1
    assert by["aphorism"]["count"] == 1
    assert not r["stacked"]["passed"] and r["stacked"]["count"] >= 4


def test_quotes_are_listed_but_never_block():
    text = PLAIN + "\n\n她把这口灶叫作“老伙计”，说城里那种“方便”她用不惯，邻居都说她“犟”。\n"
    r = ss.scan(text)
    assert r["passed"]
    assert "“方便”" in r["quotes"] and "“犟”" in r["quotes"]
    assert "“老伙计”" not in r["quotes"]  # named with 叫作: a word used as a word
