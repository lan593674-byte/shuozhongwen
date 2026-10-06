# 执行报告（research-writing-skill，M1）

## 按技能走的步骤
1. 读 SKILL.md → 入口 skills/using-research-writing：单一章节属“中型任务”，路由到 paper-orchestration。
2. paper-orchestration：建 plan/project-overview.md、outline.md、progress.md、notes.md、stage-gates.md 和任务包 plan/task-packets/results-discussion.md；阶段判为 S3/S4（结果 + 起草）。多子代理门禁只针对整篇论文，不适用于本次单节任务（测试环境也不允许子代理）。
3. brainstorming-research：用户离线，没法逐题问答。按用户输入和材料定下：课程调查报告、社科问卷、中文、Markdown，并用课程论文的默认结构；这些都在 notes.md 里记为“默认确认”。
4. experiment-results-planning：按问卷数据做了一套数据门文件，包括 experiment-protocol.md（数据说明）、可追踪表、table-schema、data-manifest。核对材料内部是否一致：分组“睡眠不足 7 小时”的人数合计 182，和 64+118 相等。
5. statistical-analysis：私下算了 2×4 卡方（χ²≈28.5），只用来确认“逐级上升”的说法不夸大。用户要求只用材料数据，所以这个数不写进正文。
6. writing-chapters + writing-humanities：写成连续段落，没有列表和加粗，也不用因果措辞，写完存为 draft1.txt。
7. 两阶段 review、verification 和 peer-review：用 grep 做了 style_check.sh 的等价检查，因为环境里没有 rg；另外跑了字数统计和逐个数字对照材料的脚本。自审记录在 plan/review/results-peer-review.md。
8. 修改后定稿为 final.txt，并在 progress.md 写了能力使用审计。

## 初稿 → 终稿 改了什么
- 字数从约 905 压到约 785（汉字 659），回到 800±10% 的范围内。
- 删掉禁用过渡词“此外”。
- 删掉超出数据的推论：“困难主要在能否坚持”“提醒式干预效果有限”“可能存在回忆偏差”。
- 删掉依赖 18 人小组的“相差约 48 个百分点”，改为强调后三组本身的上升趋势。
- 删掉多数自己算出的百分比，只保留计数和少量从计数直接得到的比例（68.0%、60.7%），尽量少出现材料里没写的数字。
- 年级构成改为直接给出 82/79/74/65。

## 默认处理和需要用户确认的地方
- 章节标题没有编号，正文前加了一行标题“结果与讨论”。
- 没写“测试用虚构数据”这一点，由用户决定要不要注明。
- 按技能规定，写完后应等用户确认；用户不在线，这一步标为待确认。
