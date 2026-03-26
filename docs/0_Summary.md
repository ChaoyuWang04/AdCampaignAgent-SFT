1. Tool-Calling 多轮对话的关键陷阱

常见问题                    正确做法
─────────────────────────────────────────────────────
Tool call 格式不一致         严格统一 JSON schema，单一 tool namespace
assistant 直接输出结果       必须有 tool_call → tool_result → assistant 完整链路
单轮假多轮（padding）        每轮必须有信息增量，去掉冗余 turn
tool_result 内容太干净       注入真实噪声：API timeout、空结果、partial data

一个合格的多轮 tool-calling 样本结构：
user:     [自然语言意图]
assistant: [tool_call: get_campaign_metrics(campaign_id=xxx)]
tool:     [{"impressions": 12300, "ctr": 0.023, ...}]
assistant: [tool_call: get_creative_performance(ad_id=yyy)]  ← 多步推理
tool:     [{"ctr": 0.031, "spend": 450.2}]
assistant: [最终分析 + 建议]

关键：assistant 的中间步骤不能只是 tool call，要有 chain-of-thought（<think> 或内联推理），否则模型学不到决策逻辑。


2. 拒答（Refusal）数据的正确设计
拒答不是简单加几条"I cannot help with that"，需要分类型：

| 拒答类型 | 在你的 Ad Agent 场景下的例子 | 错误做法 |
|----------|------------------------------|----------|
| **越权操作** | "帮我删掉竞争对手的广告账户" | 生硬拒绝 |
| **数据不足** | 用户问 ROI 但没给 cost 数据 | 直接拒绝 |
| **歧义意图** | "优化我的广告" → 不知道优化什么 | 猜一个执行 |
| **能力边界** | 问实时竞价算法内部逻辑 | 编造答案 |

正确的拒答样本：不是拒绝，而是 clarify + 给出可行路径。这才是真实 agent 行为。
数据比例建议：拒答/边界样本占总量 10-15%，过少模型过度自信，过多模型过于保守。

3. 末轮数据平衡（Last-Turn Balance）
这是最容易被忽视、对模型影响最大的问题。
问题：如果你的数据集里末轮 assistant 输出 90% 是"分析+建议"文字，模型会退化成只会输出文字。
需要平衡的末轮类型：

末轮类型                    建议占比
─────────────────────────
纯文字分析/建议              ~35%
tool_call（还需继续）        ~20%  ← 容易缺失
确认 + 执行摘要              ~15%
主动澄清问题                 ~15%
拒答/边界说明                ~10%
简短确认（"已完成"类）        ~5%

你可以用脚本统计当前末轮分布，发现不平衡后 rule-based 补充。


二、什么让数据集在 HuggingFace 上被"喜欢"
技术社区真正在意的：

1. Dataset Card 要像论文 README

清楚写明：数据来源、生成 pipeline、质量过滤步骤
给出样本统计：turn 数分布、tool 调用频率、token 长度分布（直方图）
注明 intended use / out-of-scope use

2. 数据格式用社区标准
目前 SFT tool-calling 最通用的格式是 ShareGPT 格式（被 LLaMA Factory、Axolotl、OpenHermes 等主流框架直接支持）：

{
  "conversations": [
    {"from": "system", "value": "You are an Ad Campaign Agent..."},
    {"from": "human", "value": "..."},
    {"from": "gpt", "value": "...<tool_call>...</tool_call>"},
    {"from": "tool", "value": "..."},
    {"from": "gpt", "value": "..."}
  ]
}
```

或者 **OpenAI messages 格式**（更新，被 vLLM/SGLang 原生支持）。
**不要自创格式**，这是最快让人放弃使用你数据集的方式。

**3. 数据多样性可量化**
- 统计并展示：unique intent types、tool combination diversity、domain coverage
- 如果你的 ad agent 涵盖了 Google Ads / AppsFlyer / 出价策略 / 素材分析等多个子域，明确列出

**4. 质量过滤 pipeline 透明**

写清楚你做了哪些 rule-based 过滤：
```
✓ 过滤 tool_result 为空的样本
✓ 过滤 assistant 输出 < 20 tokens 的末轮
✓ 去重：ROUGE-L > 0.85 的相似样本
✓ 格式验证：JSON schema 检查
```

**5. 规模适中，质量优先**

1000-5000 条高质量 > 50000 条低质量。HuggingFace 上被引用最多的小数据集（如 OpenHermes-2.5 子集、Alpaca-GPT4）核心优势都是质量而非规模。

---

## 三、对你 PhD 申请/个人页面的加分策略

你的数据集应该能讲一个**完整的技术故事**：
```
问题定义 → 数据生成方法 → 质量保证 → 实验验证（fine-tune 后的指标）

具体建议：

写一篇 blog post（HuggingFace 支持直接在 dataset card 嵌入）说明你的 rule-based 生成方法
配套一个 fine-tuned model：用你的数据集 fine-tune Qwen3-0.6B，上传到 HuggingFace Model Hub，数据集和模型互相引用
给出 benchmark：哪怕是小规模的 eval，比如在 10 个 test cases 上 tool-call 准确率从 X% 提升到 Y%

下一步指引: 

今天：用脚本统计你现有 Guru Ad Agent 生成样本的末轮类型分布，找到最大的缺口
明天：确定用 ShareGPT 还是 OpenAI messages 格式，写好 JSON schema 验证脚本
本周：设计拒答/边界样本的 5 个 rule，生成 50-100 条
下周：写 Dataset Card 初稿，统计 token 分布，上传第一个版本


你的 Ad Agent 应该定义哪 7 个工作流: 

工作流1：素材搜寻          search_trending_creatives / search_competitor_ads
工作流2：素材上传           validate → upload（必须串联）
工作流3：单指标效果查询      get_campaign_metrics（单次tool call）
工作流4：多维深度分析        2-4个tool串联（核心多轮场景）
工作流5：异常诊断+优化建议   detect_anomalies → get_optimization_playbook
工作流6：知识问答            query_knowledge_base / get_benchmark_data
工作流7：拒答               3种子类型（离题/越权/数据不足）
