# AdCampaignAgent Benchmark

这个目录提供一套可执行的 benchmark，用来比较 base model、本地 SFT 模型、以及 OpenAI-compatible API 模型在 AdCampaignAgent 场景下的完整 trace 表现。

## 目标

- 评估对象不是首轮输出，而是完整的 `assistant -> tool -> assistant` trace
- 同一份样本和同一套 judge 逻辑，支持多种模型后端
- 输出聚合指标和逐样本结果，便于论文表格与错误分析同时使用

## 目录结构

```text
tests/benchmark/
├── README.md
├── run_benchmark.py
├── benchmark_runner.py
├── benchmark_schema.py
├── benchmark_utils.py
├── eval_format.py
├── eval_routing.py
├── eval_content.py
├── eval_system.py
├── data/
│   ├── test_standard.json
│   ├── test_sequential.json
│   ├── test_parallel.json
│   ├── test_oos.json
│   └── test_clarify.json
└── results/
    └── report.json
```

## 设计原则

### 1. 同一 case schema

所有样本统一使用一个 JSON schema，只是按 `case_type` 分文件组织。核心字段：

- `id`: 样本唯一 ID
- `case_type`: `standard` / `sequential` / `parallel` / `oos` / `clarify`
- `user_input`: 用户请求
- `context`: 附加上下文，会拼进 benchmark system prompt
- `expected_behavior`: `tool_call` / `reject` / `clarify` / `direct_answer`
- `expected_tools`: 期望工具列表
- `expected_tool_args`: 期望工具参数
- `expected_sequence`: 顺序调用样本的 gold 序列
- `expected_parallel_groups`: 并行调用样本的 gold 分组
- `required_missing_slots`: 信息不足样本需要追问的关键信息

### 2. 同一 runner 抽象

`benchmark_runner.py` 里统一抽象为 `run_case(case) -> trace`。

当前支持：

- `LocalHFCaseRunner`
- `OpenAICaseRunner`

两者都返回统一格式的 trace，便于后续 evaluator 复用。

### 3. 先做规则化自动判分

第一版优先保证自动可跑、自动可复现、自动可比较。

当前自动评估：

- `F1`: Parsability
- `F2`: Format compliance
- `R1`: Behavior decision accuracy
- `R2`: Tool selection accuracy
- `R3`: Tool-set F1
- `C1`: Parameter exact match
- `C2`: Parameter field accuracy
- `S1`: Sequential tool-call accuracy
- `S2`: Parallel tool-call accuracy
- `S3`: OOS rejection rate
- `S4`: Clarification rate
- `S5`: End-to-end task success rate

`C3` 暂未纳入第一版脚本主流程，因为当前 benchmark 的核心目标是 tool-calling trace，而不是开放文本生成质量。

## 运行方式

### 推荐：使用 shell 脚本

仓库根目录下提供了统一运行脚本：

[`scripts/run_benchmark.sh`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/scripts/run_benchmark.sh)

这个脚本支持两种常见模式：

- 跑整套 benchmark
- 单独跑某一个评测组：`format` / `routing` / `content` / `system`
- 通过脚本顶部 `CASE_FILES` 只跑指定题集

#### 跑整套 benchmark

```bash
bash scripts/run_benchmark.sh \
  # 先在脚本顶部填好 BACKEND / MODEL 等配置
```

#### 单独跑某一个评测组

```bash
bash scripts/run_benchmark.sh \
  # 先把脚本顶部的 EVAL_GROUP 改成 system
```

#### 只跑你手动指定的 case 文件

```bash
bash scripts/run_benchmark.sh \
  # 先把脚本顶部的 CASE_FILES 改成
  # CASE_FILES=("test_oos.json" "test_clarify.json")
```

说明：

- 如果不传 `--results-dir`，脚本会自动生成一个带时间戳的结果目录，避免覆盖旧结果
- 如果 `CASE_FILES` 为空，会按 `EVAL_GROUP` 自动选文件
- 如果 `CASE_FILES` 不为空，会优先使用你手动指定的文件
- 本地 `local_hf` 后端的生成参数也在脚本顶部配置，包括：
  - `MAX_NEW_TOKENS`
  - `TEMPERATURE`
  - `TOP_P`
  - `TOP_K`
  - `REPETITION_PENALTY`
  - `NO_REPEAT_NGRAM_SIZE`
  - `MAX_TOOL_ROUNDS`
  - `LOCAL_FILES_ONLY`
  - `BF16`
  - `FP16`
  - `DEVICE_MAP_AUTO`
- 如果你希望本地 benchmark 真正跑在 GPU 上，通常建议：
  - `BF16="true"`
  - `DEVICE_MAP_AUTO="true"`
- `openai` 后端需要环境变量 `OPENAI_API_KEY`
- 如果使用兼容 OpenAI 协议的其他服务，还需要设置 `OPENAI_BASE_URL`

### CPU dry run

如果你只想验证 benchmark 流程能否在 CPU 上跑通，而不追求完整评测，可以使用：

[`scripts/dry_run_benchmark_cpu.sh`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/scripts/dry_run_benchmark_cpu.sh)

```bash
bash scripts/dry_run_benchmark_cpu.sh
```

这个脚本会：

- 固定使用 `local_hf`
- 固定只跑 1 条 smoke case
- 把生成参数压到较小
- 把工具轮数压到 1

注意：

- 这只是 smoke test，不是正式 benchmark
- 即使如此，`1.7B` 模型在 CPU 上也可能仍然比较慢

### 本地 HF 模型

```bash
uv run python tests/benchmark/run_benchmark.py \
  --backend local_hf \
  --model models/qwen3-0_6b
```

### OpenAI-compatible API 模型

需要预先设置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`，如果不是官方默认地址

```bash
uv run python tests/benchmark/run_benchmark.py \
  --backend openai \
  --model qwen-plus
```

### 只跑部分数据文件

```bash
uv run python tests/benchmark/run_benchmark.py \
  --backend local_hf \
  --model models/qwen3-0_6b \
  --case-files test_standard.json test_oos.json
```

### 只跑某一个评测组

```bash
uv run python tests/benchmark/run_benchmark.py \
  --backend local_hf \
  --model models/qwen3-0_6b \
  --eval-group routing
```

## 输出

默认输出目录是 `tests/benchmark/results/`。

- `report.json`: 聚合指标，直接对齐论文表格
- `case_results.jsonl`: 逐样本 trace 和得分，便于排查失败模式

`report.json` 示例：

```json
{
  "model": "qwen3-1.7b-lora",
  "case_count": 10,
  "metrics": {
    "F1": 0.9,
    "R1": 0.8,
    "S5": 0.6
  }
}
```

## 评分口径

### `R1`

根据完整 trace 推断行为类别：

- 任何 assistant message 含 `tool_calls` -> `tool_call`
- 无工具调用且出现拒答信号 -> `reject`
- 无工具调用且出现追问信号 -> `clarify`
- 否则 -> `direct_answer`

### `S2`

第一版不判断真实异步执行，而判断“可并行工具是否在同一 assistant turn 中共同出现”。这是模型层能力，而不是 runtime 调度器能力。

### `S5`

端到端成功要求：

- 行为大类正确
- 必要工具调用正确
- 顺序/并行样本满足对应约束
- 存在收敛的最终 assistant 回复

## 扩展建议

- 先扩充 `test_oos.json` 和 `test_clarify.json`
- 再扩充高难 `sequential` 和 `parallel` 样本
- 等 runner 与 case schema 稳定后，再将 `C3` 作为可选指标接入
