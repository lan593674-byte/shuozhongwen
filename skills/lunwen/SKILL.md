---
name: lunwen
description: 说中文·论文特化：改学术论文、毕业论文、课程设计报告、实验报告、综述的语言，去掉 AI 腔，数据和研究内容一个字不动，附学术严谨性审查。只在用户输入 /shuozhongwen:lunwen 或 /shuozhongwen lunwen 时使用。
argument-hint: 论文稿件路径（.docx、.md 或 .txt，可附文体，如“课程设计报告”）
disable-model-invocation: true
---

# 说中文 · 论文特化

插件根目录 `R` = `${CLAUDE_SKILL_DIR}/../..`，脚本在 `R/scripts`（下称 `S`），Python 用 `python3 -X utf8`（Windows 上是 `python -X utf8`）。

这个命令和 `/shuozhongwen lunwen` 完全一样。现在读 `R/skills/shuozhongwen/references/lunwen.md`，按那里的流程处理用户给的稿件；那一页里的 `R`、`S` 就是上面这两个路径。没有 Python 时的处理办法见 `R/skills/shuozhongwen/SKILL.md`「先看参数」一节。
