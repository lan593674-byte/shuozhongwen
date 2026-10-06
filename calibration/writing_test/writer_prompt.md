你在做一次写作测试：模拟用户在 Claude Code 里输入了下面这条命令，你按 shuozhongwen 技能把它做完。

用户输入：
{request}

技能：插件根目录 R = {R}，脚本目录 S = {R}/scripts。先完整读 {R}/skills/shuozhongwen/SKILL.md，然后严格照它执行。技能要你加载 baozhen 时，读 {R}/skills/baozhen/SKILL.md。技能让你读哪个参考文件就读哪个；除了 R 和下面的工作目录，不要读别的目录。

工作目录：{OUT}，所有文件都写在这里。用户提到的 material.md 就是 {OUT}/material.md（没有这个文件就是没给材料）。

这次测试的环境限制：
1. 你不能再开子代理，MCP 评委也不可用。技能里需要编辑审读和事实核查时，一律用命令行 `python3 {R}/scripts/judge_api.py 稿件 --genre 文体`，其他参数按技能的写法加。judge_api 已经配置好外部评委模型，会同时做审读和事实核查，把 JSON 存在稿件旁边，并直接给出 review_zh 的核对结果。
2. 用户不在线，不能回答问题。技能要你问用户时，用户能给的东西都已经在上面的输入和材料里；没有的，就按技能里用户不答、材料没有时的办法处理。
3. 可以用 WebSearch、WebFetch 查资料。
4. 初稿：写完第一版完整正文以后，在跑任何脚本、做任何审读之前，立刻把它原样存成 {OUT}/draft1.txt，之后不许再改这个文件。
5. 终稿：流程走完以后，最终正文（只有正文，不含修改报告）存成 {OUT}/final.txt；修改报告存成 {OUT}/report.md。
6. 最后回复一段简短总结：审读了几轮，每轮的分数和是否过线，最后 polish_check 的结果。
