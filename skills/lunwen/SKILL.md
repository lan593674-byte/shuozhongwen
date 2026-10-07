---
name: lunwen
description: 说中文·论文：论文规划、文献与章节写作、学术改稿和翻译；采用 research-writing-skill 写作规范，保留独立评分、严谨审核、数据保真及 AI 相似度。只在用户输入 /shuozhongwen:lunwen 或 /shuozhongwen lunwen 时使用。
argument-hint: 论文题目、章节要求、文献材料或稿件路径
disable-model-invocation: true
---

# 说中文 · 论文

插件根目录 `R` = `${CLAUDE_SKILL_DIR}/../..`，脚本目录 `S` = `R/scripts`。Python 使用 `python3 -X utf8`，Windows 使用 `python -X utf8`，需要 3.10 以上。

与 `/shuozhongwen lunwen` 相同。读 `R/skills/shuozhongwen/references/lunwen.md`，根据用户范围执行；该参考中 `R`、`S` 沿用本页。按需读取 `research/`，不增加命令或加载绘图/环境安装。脚本不可用时保留稿件和人工核对，明确未执行检查。
