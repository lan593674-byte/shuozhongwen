# AI 侧校准样本

- `claude-opus-5-5__*.txt`：Claude（claude-opus-5-5）按“未加写作规范约束的默认助手口吻”写的 17 篇，由 `samples.py` 生成。
- 其余由 `../gen_ai.py` 生成：火山方舟上的 deepseek-v4.1-flash、kimi-k3、glm-5.3、doubao-seed-2.0-pro、minimax-m3，Codex 上的 gpt-6-luna、gpt-5.5，每个模型 12 篇，覆盖散文、评论、演讲、小说、问答、工作文本、公众号、书评影评、新闻稿、作文、文案、社交长帖；其中三分之一题目要求“写得自然一点”。

结果见 `../RESULTS.md`。
