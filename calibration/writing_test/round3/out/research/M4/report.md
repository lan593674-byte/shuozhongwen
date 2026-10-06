# 报告（M4，research-writing-skill）

## 按技能走的步骤
1. 读入口 SKILL.md → using-research-writing：判定为写作任务、且影响多段落，属“中型任务”，转 paper-orchestration。
2. paper-orchestration：按硬门先建 plan/project-overview.md、outline.md、progress.md、task-packets/01-commentary.md。非整篇论文，不触发 chapter-architecture 与多代理章节门（测试也禁止子代理）。阶段记为 S0→S4→S5。
3. brainstorming-research：用户离线，7 轮问答全部用请求内容和默认值代替——类型“报纸评论”（不在 7 类论文中，按“其他”）、学科社会治理、语言中文、无 LaTeX 模板用 Markdown、结构为单篇 7 段评论；未得到用户确认，已在 notes.md 记录。
4. writing-chapters + writing-humanities + writing-core：按大纲写 chapters/01-commentary.md。立场：反对一刀切禁入，主张有条件放行，并划出“进楼/充电”红线。事实只用 WebSearch 摘要里能对上的内容（WebFetch 原文均被代理拦截），没有编造数据。
5. 初稿原样存 draft1.txt。
6. 两阶段 review + verification：运行 scripts/style_check.sh，并用 python 统计字数。
7. 更新 progress.md，写了能力使用审计。

## 改了什么
- 字数：初稿含标题 1043 字，超出上限，删到正文 965 字（含标点，不含 17 字的标题）。
- 去 AI 化：去掉“最后”“其实”和“这些做法说明……并非只能二选一”这类模板句，压缩了几处冗长的对比句。
- 事实：删去没有依据的判断“最后谁都没有占到便宜”；来源由“新华社”改为实际的“新华网”；长沙事件按报道补为“绕圈鸣笛，闹到深夜”。

## 与技能冲突的处理
- 技能要求用“本文/本研究”等学术表述，并在每章写完后等用户确认。报纸评论体裁以用户指令为准：不用“本文”，也不用“我认为”，直接用判断句表态。用户确认这一环因用户离线而跳过。

## 遗留风险
- 长沙小区事件的年份是推定的（正文写“去年年底”，即 2025 年 12 月）。“14 城 100+ 骑手友好社区”只经搜索摘要核对，没有读到原文。
