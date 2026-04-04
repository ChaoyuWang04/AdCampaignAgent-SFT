# AdCampaignAgent RLVR / GRPO Framework

## 1. Goal

本方案的目标是在现有 SFT agent 的基础上，引入一套面向 `tool-calling agent` 的 `RLVR / GRPO` 训练框架，用于提升以下能力：

- tool call 格式稳定性
- 工具选择准确率
- 参数填写准确率
- 多工具顺序与并行调用能力
- 信息不足时的澄清能力
- 越权或离题请求的拒答能力
- 端到端任务完成能力

本方案不重新定义一个新的 reward model，而是直接基于现有 benchmark 的规则化评测逻辑，构造可验证的程序化 reward。


## 2. Core Idea

当前仓库已经具备一条完整的 agent 主链：

- SFT policy 已经存在
- tools 已经可执行
- inference 已经可以完成本地 tool-calling rollout
- benchmark 已经可以对完整 trace 做规则化评分

因此，新的 RLVR 框架不需要从零搭建训练环境，而是应当把现有能力重新组织成以下结构：

- `policy`
  - 当前 SFT 后的 AdCampaignAgent 模型
- `task source`
  - 现有 benchmark case 数据
- `environment`
  - 现有工具执行链路
- `rollout runner`
  - 让 policy 在任务上生成 trace，并执行工具
- `reward function`
  - 复用 benchmark evaluator，将 trace 转成 reward

换句话说，这条路线不是“重新训练一个 judge”，而是继续训练当前 agent，使其在真实 tool-calling 任务上的行为更稳定、更高效、更接近 benchmark 所定义的成功标准。


## 3. Why RLVR / GRPO Fits This Project

这个项目适合做 RLVR / GRPO，原因在于：

- 任务是可执行的，不只是文本生成
- 成功与失败可以通过程序验证，而不是依赖人工主观打分
- 同一个任务往往不止一条合法 trace，不适合只靠单一 gold trace 做监督
- 当前 benchmark 已经覆盖格式、路由、参数、顺序、并行、拒答、澄清、端到端成功等关键能力

这意味着训练目标应当从“模仿某一条标准答案”扩展为“在 rollout 中拿到更高任务分数”。这正是 RLVR / GRPO 最适合发挥作用的场景。


## 4. What To Reuse

### 4.1 Reuse Existing Benchmark as Reward Backbone

直接复用以下评测模块作为 reward 的核心来源：

- `src/benchmark/eval_format.py`
- `src/benchmark/eval_routing.py`
- `src/benchmark/eval_content.py`
- `src/benchmark/eval_system.py`

它们已经分别覆盖：

- F1/F2：tool call 是否可解析、是否格式合规
- R1/R2/R3：行为决策、工具选择、工具集合质量
- C1/C2：参数整体与字段准确率
- S1/S2/S3/S4/S5：顺序、并行、拒答、澄清、端到端成功

对 RLVR 来说，最关键的复用原则是：

- benchmark 继续作为“唯一的规则定义源”
- reward 只是 benchmark 分数在训练阶段的折叠版本
- 不要额外维护一套与 benchmark 脱节的 reward 规则

### 4.2 Reuse Existing Tool Execution

直接复用：

- `src/tools/*`
- `src/tools/__init__.py`
- `src/inference/local_toolcall_repl.py`

这些模块已经提供：

- 工具 schema
- 工具实现
- tool call 解析
- tool dispatch
- 多轮 tool execution

RL rollout 时，不应重新写一套完全平行的工具执行逻辑，而应把现有 REPL 里的核心执行能力抽出来，用于无交互的批量 rollout。

### 4.3 Reuse Existing Benchmark Data

直接复用：

- `data/benchmark/test_standard.json`
- `data/benchmark/test_sequential.json`
- `data/benchmark/test_parallel.json`
- `data/benchmark/test_oos.json`
- `data/benchmark/test_clarify.json`

这些 case 已经覆盖了当前 RL 最需要优化的关键任务分布。

在当前实现中，RLVR 已经切换到独立数据目录：

- `data/rlvr/train_cases/`
- `data/rlvr/eval_cases/`

其中：

- `train_cases/` 用于 RLVR 训练，可独立于 benchmark 持续扩充
- `eval_cases/` 固定为 30 条 holdout case，用于 RLVR 验证
- `data/benchmark/` 继续作为 benchmark 的统一题库目录

当前 RLVR case 对 `expected_tool_args` 还有一个额外约束：

- 普通单工具或顺序工具仍使用 `tool_name -> {field: value}` 的字典形式
- 如果是并行场景中的“重复同名工具”，则使用 `tool_name -> [{...}, {...}]` 的列表形式

这样可以显式区分：

- “同一轮调用两个不同子任务”
- “把同一个 tool call 错误地重复两次”

否则并行评测只能看到工具名重复，无法判断子任务参数是否真的不同。


## 5. Training Object Definition

### 5.1 Policy

训练对象是当前 SFT 后的 AdCampaignAgent policy。

输入：

- system prompt
- benchmark case 中的 user input
- case context
- 历史 tool call / tool result

输出：

- assistant 文本
- tool call
- 最终答复

### 5.2 Environment

environment 由以下部分组成：

- benchmark case
- tool executor
- trace state
- rollout termination rule

environment 的职责是：

- 接收 policy 输出
- 如果输出 tool call，则执行工具
- 把 tool result 回填到 trace
- 继续下一轮 rollout
- 在终止后把完整 trace 交给 reward function

### 5.3 Task Source

任务源优先使用 benchmark case。

原因：

- 当前 benchmark 已经定义了清晰的预期行为
- 每条 case 都带有结构化 gold 信息
- 可以直接用于 reward 计算
- 训练与评估分布天然一致，便于快速验证 RL 是否有效


## 6. Rollout Design

一次 rollout 的标准流程应当定义为：

1. 从 benchmark 数据中采样一条 case
2. 构建 system + context + user input
3. 用 policy 生成 assistant 输出
4. 解析 tool call
5. 若有 tool call，则执行工具并追加 tool result
6. 继续下一轮，直到：
   - 模型停止调用工具
   - 达到最大工具轮数
   - 出现明确终态
7. 得到完整 trace
8. 调用 reward function，把 trace 映射为 reward

### 6.1 Rollout Constraints

建议沿用当前 benchmark / inference 的保守约束：

- 设置最大 tool round
- 设置最大生成长度
- 对非法 tool call 做显式惩罚
- 对重复、无效、空转调用做惩罚

这样可以避免 RL 早期探索阶段出现大量无效长 trace。

### 6.2 Determinism and Stability

训练期 rollout 应优先保证 reward 稳定，而不是追求完全开放探索。

建议：

- 工具执行尽量保持 deterministic
- benchmark case 的判分逻辑保持 deterministic
- 对随机 fallback 工具结果做控制或固定 seed

原因很简单：reward 一旦抖动过大，RL 信号会明显变差。


## 7. Reward Design

## 7.1 Design Principle

reward 必须直接来自现有 benchmark 指标，而不是单独发明另一套主观规则。

reward 设计应满足：

- 可验证
- 稳定
- 可分解
- 与最终 benchmark 指标一致

### 7.2 Dense Reward + Terminal Reward

建议采用“dense reward + terminal reward”组合，而不是只用最终成功率。

原因：

- 只看最终成功，训练初期奖励过 sparse
- benchmark 已经提供了大量中间能力信号
- dense reward 可以更快推动模型学会正确行为

### 7.3 Recommended Reward Components

建议将 reward 拆为以下部分：

- `format_reward`
  - 基于 F1/F2
  - 判断 tool call 是否可解析、是否合规

- `behavior_reward`
  - 基于 R1
  - 判断是否做出了正确的高层动作决策
  - 该调工具时调工具
  - 该澄清时澄清
  - 该拒答时拒答

- `tool_selection_reward`
  - 基于 R2/R3
  - 判断工具选择是否准确

- `argument_reward`
  - 基于 C1/C2
  - 判断参数整体与字段级正确性

- `workflow_reward`
  - 基于 S1/S2
  - 判断顺序依赖与并行分组是否正确

- `safety_reward`
  - 基于 S3/S4
  - 判断拒答与澄清是否正确

- `success_reward`
  - 基于 S5
  - 作为最重要的终局奖励

- `efficiency_penalty`
  - 基于 trace 统计新增
  - 包括：
    - 多余工具调用
    - 重复调用
    - 空参数或无效参数调用
    - 达到最大轮数仍未收敛

### 7.4 Recommended Reward Composition

第一版可以采用保守权重：

```text
total_reward =
(
    0.10 * format_reward
  + 0.15 * behavior_reward
  + 0.20 * tool_selection_reward
  + 0.20 * argument_reward
  + 0.10 * workflow_reward
  + 0.10 * safety_reward
  + 0.25 * success_reward
  - 0.10 * efficiency_penalty
) / 1.10
```

说明：

- `success_reward` 权重最高，因为训练目标最终仍是端到端成功
- `argument_reward` 和 `tool_selection_reward` 权重较高，因为它们最直接决定 tool-calling agent 的实用性
- `format_reward` 权重较低，因为它属于底层门槛，不应主导全部学习
- 正向权重会在聚合后统一除以 `1.10`，把“全对且无罚分”的理论上限归一到 `1.0`

### 7.5 Reward Gating

建议加入简单的 reward gating：

- 如果行为决策错误，则压低后续工具和参数奖励
- 如果 trace 完全不合规，则直接给予较低总分
- 如果拒答/澄清类 case 误调用业务工具，则直接重罚

这样可以减少“靠某些局部指标投机取巧”拿高分的情况。


## 8. Proposed Project Structure

建议在现有仓库中新增一条独立但轻量的 RLVR 路径。

推荐结构如下：

```text
data/rlvr/
├── train_cases/            # RLVR 训练任务
└── eval_cases/             # RLVR holdout 任务

src/rlvr/
├── rollout.py              # 多轮 rollout 主入口
├── reward.py               # benchmark-based reward 折叠逻辑
├── reward_components.py    # reward 各项分数拆分
├── dataset.py              # 训练任务采样封装
├── prompt_builder.py       # BenchmarkCase -> message list
└── trainer.py              # MultiTurn GRPO trainer

scripts/
├── train_rlvr.py           # RLVR / GRPO 训练入口
└── eval_rlvr_checkpoint.sh # 训练后 benchmark 验证脚本
```

这条路径的目标是：

- 最小侵入现有 SFT / benchmark 代码
- 最大化复用 benchmark evaluator
- 将 rollout、reward、训练控制组织成清晰模块

RLVR case 的 JSON 主结构沿用 `BenchmarkCase`，只额外增加 4 个可选字段：

- `rlvr_weight`
- `rlvr_split`
- `rlvr_tags`
- `rlvr_max_tool_rounds`

这样可以保持：

- benchmark evaluator 仍然理解主体字段
- RLVR 训练可以增加自己的采样权重、标签和 rollout 约束
- prompt 仍在运行时由 `prompt_builder.py` 构造，而不是写死进 JSON


## 9. Minimal Implementation Strategy

建议分三步做。

### Phase A: Reward Extraction MVP

目标：

- 不训练，只先把 benchmark evaluator 变成可被训练调用的 reward 接口

工作内容：

- 输入一条 case 和一条 trace
- 输出 reward breakdown + total reward

验收标准：

- 对已有 benchmark case 能稳定输出 reward
- reward 数值与 benchmark 直觉一致

### Phase B: Local Rollout MVP

目标：

- 不接大规模 RL 框架，先本地单样本 rollout 跑通

工作内容：

- 给一条 benchmark case
- 让现有 policy 完整执行 trace
- 执行工具
- 得到 reward

验收标准：

- 可以从 prompt 稳定走到 reward
- 全链路不依赖人工干预

### Phase C: RLVR / GRPO Training Integration

目标：

- 将 rollout + reward 接入 RL 训练循环

工作内容：

- 批量采样 benchmark case
- 生成 rollout
- 计算 reward
- 执行 policy update

验收标准：

- 能稳定训练多个 step
- benchmark 离线分数相对 SFT baseline 有提升

### Phase C Current Implementation Shape

当前实现采用 `TRL 0.29.1`，但不使用其默认的单轮 completion rollout。

具体方式：

- 在 `src/rlvr/trainer.py` 中定义 `MultiTurnGRPOTrainer`
- 子类化 `GRPOTrainer`
- 覆盖 `_generate_and_score_completions`
- 在内部调用自定义 `_generate_completions`
- 每个 prompt 通过 `run_rollout()` 执行完整 multi-turn trace
- 将 trace 中所有 assistant turn 的 token ids 与 logprobs 展平成一段 flat completion
- 不把 tool result token 纳入 GRPO loss
- 用 side-channel trace cache 将 `trace_id -> RolloutTrace` 保留给 reward function

这使得：

- reward 仍然在完整 trace 结束后统一计算
- advantage 可以覆盖整个 multi-turn assistant token 序列
- 训练保持与 benchmark evaluator 对完整 trace 的定义一致

当前最小训练入口是：

- `scripts/train_rlvr.py`

这一版只追求单机、本地、可重复地跑通全链路，不包含：

- vLLM 加速
- 分布式多卡 rollout
- reference model 独立部署


## 10. Validation Plan

训练后的效果验证应继续完全沿用现有 benchmark。

### 10.1 Primary Validation

使用：

- `src/benchmark/run_benchmark.py`

对比：

- SFT baseline
- RLVR checkpoint

重点关注：

- R2 Tool Selection Accuracy
- C2 Parameter Field Accuracy
- S1 Sequential Tool Call Accuracy
- S2 Parallel Tool Call Accuracy
- S4 Clarification Rate
- S5 End-to-End Task Success

### 10.2 Secondary Validation

除 benchmark 总分外，还应跟踪：

- 平均每个任务调用工具次数
- 无效工具调用占比
- 参数空值率
- 重复工具调用率
- 达到最大 tool round 的失败率

这些指标适合放在 rollout 日志中，用于定位 RL 是否在“刷分”而不是“真实变强”。


## 11. Risks

### 11.1 Reward Hacking

模型可能学会利用局部规则拿分，而不是提升真实能力。

应对：

- 让 `S5` 占较高权重
- 对无意义调用加 penalty
- 使用 gating，防止错误行为仍拿到高 reward

### 11.2 Overfitting to Benchmark

如果只在当前 benchmark 上训练过久，模型可能过拟合固定 case 分布。

应对：

- benchmark case 用作第一阶段 RLVR 数据
- 后续再扩展到更广的训练任务集
- 保留独立 holdout case 做最终验证

### 11.3 Reward Instability from Tool Randomness

如果工具返回内容波动大，reward 也会变得不稳定。

应对：

- 尽量让训练期工具执行 deterministic
- 固定随机种子
- 对 fallback 逻辑做受控简化


## 12. Recommended Next Steps

建议按以下顺序推进：

1. 抽出 benchmark-based reward 接口
2. 抽出无交互 rollout runner
3. 让 rollout runner 可以直接消费 benchmark case
4. 跑通单样本、本地、可重复的 rollout-to-reward 流程
5. 再接入正式的 GRPO / RLVR 训练框架

在整个过程中，benchmark 应始终作为：

- reward 设计来源
- 训练效果验证来源
- 回归测试来源

这样可以保证 RLVR 路线与现有仓库目标保持一致，而不是演化成一套脱离 benchmark 的平行系统。
