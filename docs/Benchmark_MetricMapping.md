# Benchmark 指标映射表

这个文档单独说明当前 benchmark 中每一个指标：

- 在哪个 Python 脚本中完成评分
- 主要使用哪个 JSON 文件记录题目与正确答案
- 正确答案主要写在哪些字段中

这里的基本概念是：

- `data/benchmark/*.json` 负责存放题目和 gold
- `src/benchmark/eval_*.py` 负责对模型跑出来的 trace 进行判分

## 总表

| 指标 ID | 指标名称 | 评分脚本 | 主要样本文件 | 主要 gold 字段 | 说明 |
|---------|----------|----------|--------------|----------------|------|
| `F1` | Parsability Rate | [eval_format.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_format.py) | [test_standard.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_standard.json), [test_sequential.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_sequential.json), [test_parallel.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_parallel.json) | 无单独字段，主要依赖“该题本身应为工具调用类任务” | 检查 trace 中是否存在可解析的 tool call |
| `F2` | Format Compliance Rate | [eval_format.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_format.py) | [test_standard.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_standard.json), [test_sequential.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_sequential.json), [test_parallel.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_parallel.json) | 无单独字段，依赖工具调用结构本身 | 检查工具名是否存在、参数是否可解析为字典 |
| `R1` | Tool Invocation Decision Accuracy | [eval_routing.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_routing.py) | [test_standard.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_standard.json), [test_sequential.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_sequential.json), [test_parallel.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_parallel.json), [test_oos.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_oos.json), [test_clarify.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_clarify.json) | `expected_behavior` | 判断模型是该调工具、该拒答、该追问，还是直接回答 |
| `R2` | Tool Selection Accuracy | [eval_routing.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_routing.py) | [test_standard.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_standard.json), [test_sequential.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_sequential.json) | `expected_tools` | 判断调用的工具名是否与 gold 完全一致 |
| `R3` | Tool Set F1 | [eval_routing.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_routing.py) | [test_parallel.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_parallel.json), [test_sequential.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_sequential.json) | `expected_tools` | 主要用于多工具场景，按工具集合计算 F1 |
| `C1` | Parameter Exact Match | [eval_content.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_content.py) | [test_standard.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_standard.json) | `expected_tool_args` | 判断整组工具参数是否与 gold 完全一致 |
| `C2` | Parameter Field Accuracy | [eval_content.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_content.py) | [test_standard.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_standard.json) | `expected_tool_args` | 按字段逐一比较参数正确率 |
| `C3` | Semantic Similarity | 未实现 | 无 | 无 | 当前 benchmark 第一版没有实现这个指标 |
| `S1` | Sequential Tool Call Accuracy | [eval_system.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_system.py) | [test_sequential.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_sequential.json) | `expected_sequence` | 判断顺序调用是否严格符合 gold 序列 |
| `S2` | Parallel Tool Call Accuracy | [eval_system.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_system.py) | [test_parallel.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_parallel.json) | `expected_parallel_groups` | 判断可并行工具是否出现在同一 assistant turn 中 |
| `S3` | Rejection Rate (OOS) | [eval_system.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_system.py) | [test_oos.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_oos.json) | `expected_behavior`, `rejection_category` | 判断越界请求是否被正确拒绝 |
| `S4` | Clarification Rate | [eval_system.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_system.py) | [test_clarify.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_clarify.json) | `expected_behavior`, `required_missing_slots` | 判断信息不足时是否正确追问缺失信息 |
| `S5` | End-to-End Task Success Rate | [eval_system.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/eval_system.py) | 全部样本文件 | 综合使用 `expected_behavior`、`expected_tools`、`expected_tool_args`、`expected_sequence`、`expected_parallel_groups`、`required_missing_slots` | 规则化综合判断任务是否完成 |

## 题目和正确答案分别存在哪里

当前 benchmark 的设计里，每条 JSON 样本本身就同时包含：

- 题目
- 正确答案

### 题目字段

题目主要由以下字段组成：

- `user_input`
- `context`

其中：

- `user_input` 是直接给模型的用户请求
- `context` 是补充到 benchmark system prompt 中的上下文信息

### 正确答案字段

正确答案主要由以下字段组成：

- `expected_behavior`
- `expected_tools`
- `expected_tool_args`
- `expected_sequence`
- `expected_parallel_groups`
- `required_missing_slots`
- `rejection_category`

不是每条样本都会用到所有字段，不同题型使用的 gold 字段不同。

## 不同 JSON 文件主要承载什么题型

| JSON 文件 | 主要题型 | 主要用于哪些指标 |
|-----------|----------|------------------|
| [test_standard.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_standard.json) | 标准单工具/常规工具调用 | `F1`, `F2`, `R1`, `R2`, `C1`, `C2`, `S5` |
| [test_sequential.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_sequential.json) | 链式顺序调用 | `F1`, `F2`, `R1`, `R2`, `R3`, `S1`, `S5` |
| [test_parallel.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_parallel.json) | 并行多工具调用 | `F1`, `F2`, `R1`, `R3`, `S2`, `S5` |
| [test_oos.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_oos.json) | 越界拒答 | `R1`, `S3`, `S5` |
| [test_clarify.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/benchmark/test_clarify.json) | 信息不足需追问 | `R1`, `S4`, `S5` |

## 实际判分流程

整体运行时，判分流程如下：

1. [run_benchmark.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/run_benchmark.py) 读取 `data/benchmark/*.json`
2. [benchmark_schema.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/benchmark_schema.py) 把样本加载成 `BenchmarkCase`
3. [benchmark_runner.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/benchmark/benchmark_runner.py) 调模型得到完整 trace
4. `eval_*.py` 读取样本里的 gold 字段，与模型输出对比打分
5. 结果输出到：
   - `outputs/benchmark/<run>/report.json`
   - `case_results.jsonl`

## 当前尚未覆盖的点

当前唯一还没有脚本和数据落地的是：

- `C3 Semantic Similarity`

也就是说，目前这张映射表里，除了 `C3` 之外，其余指标都已经有对应的：

- 评分脚本
- 样本 JSON
- gold 字段定义
