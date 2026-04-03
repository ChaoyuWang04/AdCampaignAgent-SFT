# 仓库使用指南

## 1. 仓库结构

当前仓库按职责分为以下区域：

- `data/raw/`
  - 原始生成样本。
- `data/intermediate/`
  - 中间转换产物。
- `data/processed/`
  - 训练和评测直接使用的数据集。
- `models/`
  - 本地模型权重和训练输出目录。
- `src/datapipeline/`
  - 数据生成、切分、转换、合并脚本。
  - `workflow/` 子目录存放按工作流拆分的 YAML 文本规则。
- `src/tools/`
  - Ad Campaign Agent 运行时工具实现。
- `src/inference/`
  - 本地模型推理检查脚本。
- `src/train/`
  - 训练、检查、LoRA 合并脚本。
- `src/common/`
  - 公共模块和路径工具。
- `tests/`
  - 手动运行的测试/验证脚本。
- `scripts/`
  - 训练启动 shell 脚本。
- `rag-system/`
  - 历史遗留的旧 RAG 子系统，当前已不在主流程内。

---

## 2. 关键数据与模型位置

### 数据目录

- 原始样本：
  - `data/raw/ad_agent_seeds_<timestamp>_zh.json`
- 切分后的训练/测试集：
  - `data/processed/ad_agent_seeds_train.json`
  - `data/processed/ad_agent_seeds_test.json`
- 转换后的训练数据：
  - `data/ready2train/ad_agent_sft_<timestamp>_zh_train.json`
  - `data/ready2train/ad_agent_sft_<timestamp>_zh_test.json`
- 多轮训练数据：
  - `data/ready2train/ad_agent_sft_<timestamp>_zh_train_multiturn.json`

### 模型目录

- 基础模型：
  - `models/qwen3-0_6b/`
- 训练输出默认目标：
  - `models/qwen3-0_6b_lora_last_assistant/`
  - `models/qwen3-0_6b_fullft_last_assistant/`
  - `models/qwen3-0_6b_merged/`

### 工具 Schema

- `src/tools/all_tools.json`

---

## 3. 运行前提

以下脚本依赖本地或外部资源，不满足条件时不会正常运行：

- 训练脚本：
  - 依赖 `torch`、`transformers`、`peft`、`trl`。
- 推理脚本：
  - 依赖本地模型文件。
- 工具脚本：
  - 非 RAG 工具可选依赖 `openai` 兼容接口；未配置 key 时会 fallback。
  - RAG 工具当前只通过兼容层调用旧 `/search` 接口；服务不可用时会 fallback。
- RAG 脚本：
  - 属于历史遗留资产，当前不在训练与推理主流程内。

---

## 4. 脚本清单

下面按目录说明每个 Python 脚本和 Shell 脚本的用途、输入、输出和默认位置。

## 4.1 `src/common/`

### `src/common/llm.py`

- 作用：统一管理 GPT、Claude、Gemini、Qwen、DeepSeek、GLM 等模型的调用接口。
- 典型输入：
  - `model_name`
  - `prompt` 或 `messages`
  - `system_prompt`
- 典型输出：
  - `str`，模型返回文本。
- 文件输入输出：
  - 无固定文件输入输出。
- 使用方式：
  - 供其他脚本 `import` 调用，不是主要 CLI 入口。

### `src/common/log_utils.py`

- 作用：初始化彩色日志和参数截断显示。
- 输入：
  - 环境变量 `LOG_LEVEL`
  - Python 字典参数
- 输出：
  - 日志对象或截断后的参数预览。
- 文件输入输出：
  - 无固定文件输入输出。

### `src/common/project_paths.py`

- 作用：统一提供仓库根目录、`data/`、`models/`、`src/` 等路径函数。
- 输入：
  - 无。
- 输出：
  - `Path` 对象。
- 文件输入输出：
  - 无固定文件输入输出。

---

## 4.2 `src/datapipeline/`

### `src/datapipeline/0_generate_base_dataset.py`

- 作用：规则生成 Ad Campaign Agent 原始 seed 样本。
- 运行方式：
  - `python src/datapipeline/0_generate_base_dataset.py`
- 输入：
  - 无命令行输入，脚本内置工作流配比、平台、品类、地区和场景模板。
- 输出：
  - 在 `data/raw/` 下生成 seed JSON 文件。
- 输出文件形式：
  - JSON 数组。
- 默认输出文件名：
  - `ad_agent_seeds_<timestamp>_zh.json`
- 建议输出位置：
  - `data/raw/`
- 规则来源：
  - 工作流文本模板、tool plan、追问模板等解耦在 `src/datapipeline/workflow/*.yaml`
  - Python 脚本仍负责随机上下文采样、baseline 注入、最终 seed record 组装

### `src/datapipeline/split_dataset.py`

- 作用：将原始样本切分为训练集和测试集。
- 运行方式：
  - `python src/datapipeline/split_dataset.py`
- 输入：
  - 运行时手动输入 seed JSON 文件名。
  - 脚本会在 `data/raw/` 下查找该文件。
- 输出：
  - 训练集 JSON
  - 测试集 JSON
- 输出文件形式：
  - JSON 数组。
- 备注：
  - 当前支持按 workflow + scene_tag + 是否追问 做分层切分。
  - 输出文件名会基于输入文件名自动生成，例如：
    - `ad_agent_seeds_20260326_zh_train.json`
    - `ad_agent_seeds_20260326_zh_test.json`

### `src/datapipeline/2_convert_dataset.py`

- 作用：将原始样本转换为带工具调用轨迹的对话训练数据。
- 运行方式：
  - `python src/datapipeline/2_convert_dataset.py`
- 输入：
  - 运行时手动输入 `data/processed/` 下的 seed 文件名。
- 输出：
  - 单个 `messages` 训练集 JSON 文件。
- 输出文件形式：
  - JSON 数组，每项含 `messages` 和 `_meta` 字段。
- 推荐输入位置：
  - `data/processed/ad_agent_seeds_<timestamp>_zh_train.json`
  - `data/processed/ad_agent_seeds_<timestamp>_zh_test.json`
- 推荐输出位置：
  - `data/ready2train/`

### `src/datapipeline/3_conversation_splitter.py`

- 作用：将 `message` 格式对话数据按 assistant 轮次拆分，扩展成多轮训练样本。
- 运行方式：
  - `python src/datapipeline/3_conversation_splitter.py`
- 运行时输入：
  - 手动输入要处理的 JSON 文件名。
- 默认查找目录：
  - `data/ready2train/`
- 默认输出：
  - 与输入文件同目录，文件名追加 `_multiturn`。
- 输入文件形式：
  - JSON 数组，每项含 `messages` 字段。
- 输出文件形式：
  - JSON 数组。

---

## 4.3 `src/tools/`

### `src/tools/*.py`

- 作用：Ad Campaign Agent 的运行时工具实现，每个工具单独一个 Python 文件。
- 工具数量：
  - 共 15 个，对应广告投放工作流中的搜索、上传、分析、诊断、知识检索能力。
- 工具分类：
  - 非 RAG 工具：优先调用 OpenAI 兼容接口并尝试解析 JSON，失败时 fallback。
  - RAG 工具：优先调用本地 `rag-system` 的 `/search` 接口，失败时 fallback。
- 公共辅助：
  - `src/tools/_shared.py`
- 统一导出：
  - `src/tools/__init__.py`
- 详细说明：
  - `src/tools/README.md`

### `src/tools/all_tools.json`

- 作用：定义 Ad Campaign Agent 的 Function Calling 工具 schema。
- 输入：
  - 无。
- 输出：
  - 无。
- 文件形式：
  - JSON 数组。
- 说明：
  - 仅保留最小必需参数，用于训练和推理时的工具注册。

---

## 4.4 `src/inference/`

### `src/inference/local_toolcall_inspector.py`

- 作用：检查本地模型对广告投放工具 schema 的 tool-calling 推理能力。
- 运行方式：
  - `python src/inference/local_toolcall_inspector.py [args]`
- 默认输入：
  - `models/qwen3-0_6b/`
  - `src/tools/all_tools.json`
- 输入形式：
  - 本地模型目录
  - 广告投放 system prompt
  - 单条用户消息或内置场景
  - 可选工具 schema JSON
- 输出：
  - 控制台中的 chat template、模型输出、解析后的 tool call。
- 文件输入输出：
  - 无固定文件输入输出。

### `src/inference/local_toolcall_repl.py`

- 作用：本地模型的广告投放助手 REPL，可执行多轮 tool-calling 与本地工具回灌。
- 运行方式：
  - `python src/inference/local_toolcall_repl.py [args]`
- 默认输入：
  - `models/qwen3-0_6b/`
  - `src/tools/all_tools.json`
- 输入形式：
  - 交互式终端输入
  - 本地模型目录
  - 广告投放工具 schema
  - 可选 `--system-file` 或 `--system-text` 覆盖默认 system prompt
- 默认 prompt：
  - `prompts/ad_agent_system_prompt.txt`
- 输出：
  - 控制台中的 assistant 输出、解析出的 tool call、tool result、最终回复。
- 文件输入输出：
  - 无固定文件输入输出。

### `scripts/run_local_toolcall_repl.sh`

- 作用：以固定配置启动本地 tool-calling REPL。
- 运行方式：
  - `bash scripts/run_local_toolcall_repl.sh`
- 特点：
  - 直接在脚本顶部改模型路径和生成参数即可。
  - 适合直接加载 merged 模型进行人工对话验证。

---

## 4.5 `src/train/`

### `src/train/inspect_qwen_dataset.py`

- 作用：可视化和检查训练数据模板、token span、loss mask。
- 运行方式：
  - `python src/train/inspect_qwen_dataset.py [args]`
- 默认输入：
  - `data/processed/merged_train_final.json`
  - `models/qwen3-0_6b`
  - `src/tools/all_tools.json`
- 输出：
  - 控制台可视化信息。
  - 可选导出张量 JSON。
- 输入文件形式：
  - JSON 或 JSONL。
- 输出文件形式：
  - 控制台输出，或导出 JSON。

### `src/train/train_qwen_lora_all_assistant_turns.py`

- 作用：LoRA 微调脚本，对所有 assistant 轮次计算 loss。
- 默认输入：
  - `data/processed/merged_train_final.json`
  - `models/qwen3-0_6b/`
- 默认输出：
  - `models/qwen_lora_output/`
- 输入文件形式：
  - JSON/JSONL 训练集。
- 输出文件形式：
  - 模型目录。

### `src/train/train_qwen_lora_last_assistant_turn_only.py`

- 作用：LoRA 训练，只对最后一个 assistant 轮次计算 loss。
- 默认输入：
  - `data/processed/merged_train_final_multiturn_v2.json`
  - `models/qwen3-0_6b/`
- 默认输出：
  - `models/qwen3-0_6b_lora_last_assistant/`
- 输出文件形式：
  - Adapter 模型目录。

### `src/train/train_qwen_full_finetune_last_assistant_turn_only.py`

- 作用：全参数训练，只对最后一个 assistant 轮次计算 loss。
- 默认输入：
  - `data/processed/merged_train_final_multiturn_v2.json`
  - `models/qwen3-0_6b/`
- 默认输出：
  - `models/qwen3-0_6b_fullft_last_assistant/`
- 输出文件形式：
  - 模型目录。

### `src/train/train_qwen_function_calling_all_assistant_turns.py`

- 作用：Function Calling SFT，对所有 assistant 轮次计算 loss，可选启用 QLoRA。
- 运行方式：
  - `python src/train/train_qwen_function_calling_all_assistant_turns.py --train_file <path> [args]`
- 输入：
  - `--train_file` 必填，JSON 或 JSONL。
- 特点：
  - 默认就是普通 LoRA，不是全参数训练。
  - 支持 `--local_files_only`。
  - 支持 `--tools_file` / `--tools_json` 为缺少 `tools` 字段的样本注入全局工具列表。
- 默认模型：
  - `models/qwen3-0_6b/`
- 默认输出：
  - `./qwen_tooluse_sft`
- 输出文件形式：
  - 模型目录。

### `scripts/run_train_function_calling_all_assistant.sh`

- 作用：以固定配置启动 Function Calling LoRA 训练。
- 运行方式：
  - `bash scripts/run_train_function_calling_all_assistant.sh`
- 特点：
  - 只需要修改脚本顶部变量。
  - 默认按“所有 assistant 轮次都参与 loss”的方式训练。

### `src/train/train_qwen_trl_lora_function_calling_completion_only.py`

- 作用：使用 TRL `SFTTrainer` 做 LoRA Function Calling 训练，并使用 completion-only loss mask。
- 默认输入：
  - `data/processed/merged_train_final.json`
  - `models/qwen3-0_6b/`
- 默认输出：
  - `models/qwen3-fc-sft/`
- 输入文件形式：
  - JSON 或 JSONL。
- 输出文件形式：
  - 模型目录。

### `src/train/merge_lora_into_base.py`

- 作用：将 LoRA Adapter 合并回基础模型。
- 运行方式：
  - `python src/train/merge_lora_into_base.py [args]`
- 默认输入：
  - `models/qwen3-0_6b/`
  - `models/qwen3-0_6b_lora_last_assistant/`
- 默认输出：
  - `models/qwen3-0_6b_merged/`
- 输出文件形式：
  - 合并后的模型目录。

---

## 4.6 `tests/`

这些脚本主要用于手动验证，不一定都是自动化单元测试。

### `tests/test_repo_structure.py`

- 作用：验证核心包结构和路径工具是否可导入。
- 运行方式：
  - `python -m unittest tests.test_repo_structure`
- 输入：
  - 无。
- 输出：
  - 单元测试结果。

### `tests/datapipeline/test_generate.py`

- 作用：验证数据生成脚本是否能生成少量样本。
- 运行方式：
  - `python tests/datapipeline/test_generate.py`
- 输入：
  - 无。
- 输出：
  - 控制台打印样本预览。

### `tests/inference/online_toolcall_runner.py`

- 作用：使用外部 OpenAI 兼容接口联调广告投放助手的 tool-calling，并执行本地工具实现。
- 运行方式：
  - `python tests/inference/online_toolcall_runner.py`
- 输入：
  - 环境变量 `OPENAI_API_KEY`
  - 可选环境变量 `OPENAI_BASE_URL`、`OPENAI_MODEL`
- 输出：
  - 控制台中的消息轨迹和工具执行结果。

### `tests/inference/test_online_toolcall_runner.py`

- 作用：对在线 tool-call runner 做手动 smoke test。
- 运行方式：
  - `python tests/inference/test_online_toolcall_runner.py`
- 输入：
  - 同 `online_toolcall_runner.py`
- 输出：
  - 控制台中的 trace 摘要。

### `tests/inference/test_sequential.py`

- 作用：验证数据转换时顺序工具调用链路。
- 输入：
  - 临时生成的测试 JSON 数据。
- 输出：
  - 控制台打印转换结构。
  - 临时生成测试文件和临时输出目录。
- 备注：
  - 该脚本更偏调试脚本。

### `tests/tools/test_llm_tool.py`

- 作用：验证 `src/common/llm.py` 中的模型调用封装。
- 输入：
  - 脚本内置模型名和提示词。
- 输出：
  - 控制台输出模型返回结果。
- 备注：
  - 依赖真实 API key 和网络。

---

## 4.7 `scripts/`

### `scripts/run_train_full_finetune.sh`

- 作用：启动全参数训练。
- 运行方式：
  - `bash scripts/run_train_full_finetune.sh`
- 默认输入：
  - `data/processed/merged_train_final_multiturn_v2.json`
  - `models/qwen3-0_6b/`
- 默认输出：
  - `models/qwen3-0_6b_fullft_last_assistant/`
- 输出形式：
  - 模型目录。

### `scripts/run_train_last_assistant.sh`

- 作用：启动 last-assistant LoRA 训练。
- 运行方式：
  - `bash scripts/run_train_last_assistant.sh`
- 默认输入：
  - `data/processed/merged_train_final_multiturn_v2.json`
  - `models/qwen3-0_6b/`
- 默认输出：
  - `models/qwen3-0_6b_lora_last_assistant/`
- 输出形式：
  - Adapter 模型目录。

---

## 4.8 `rag-system/`

### `rag-system/import_travel_guides.py`

- 作用：将 `original_data/travel_guides/` 中的攻略文本转 embedding 并导入 Milvus。
- 运行方式：
  - `python rag-system/import_travel_guides.py`
- 默认输入：
  - `rag-system/original_data/travel_guides/*_travel_guide.txt`
  - `rag-system/city_code_mapping.json`
- 默认输出：
  - `rag-system/milvus.db`
- 输入文件形式：
  - 文本文件。
- 输出文件形式：
  - Milvus 本地数据库文件。

### `rag-system/rag_api.py`

- 作用：提供 RAG 检索 API 服务。
- 运行方式：
  - `python rag-system/rag_api.py`
- 默认输入：
  - `rag-system/milvus.db`
- 输出：
  - HTTP 服务。
- 默认端口：
  - `8010`
- 主要接口：
  - `GET /health`
  - `POST /search`
  - `POST /search_by_location`
  - `GET /stats`

### `rag-system/test_api.py`

- 作用：测试 RAG API。
- 输入：
  - 正在运行的 `rag_api.py`
- 输出：
  - 控制台打印接口响应。

### `rag-system/test_import.py`

- 作用：只导入前 3 个攻略文本进行导入测试。
- 默认输入：
  - `rag-system/original_data/travel_guides/110000_北京_travel_guide.txt`
  - `rag-system/original_data/travel_guides/120000_天津_travel_guide.txt`
  - `rag-system/original_data/travel_guides/330100_杭州_travel_guide.txt`
- 默认输出：
  - `rag-system/test_milvus.db`

### `rag-system/*`

- 状态：历史遗留的旅行攻略 RAG 资产。
- 说明：
  - 当前不属于 Ad Campaign Agent 的主训练、主推理、主测试流程。
  - 后续如果要重建广告知识库 RAG，建议单独重构该目录。

### `rag-system/original_data/gen_data/llm.py`

- 作用：攻略生成脚本使用的本地 LLM 封装。
- 输入：
  - 模型名、prompt、system_prompt。
- 输出：
  - 文本字符串。
- 文件输入输出：
  - 无固定文件输入输出。

### `rag-system/original_data/gen_data/test_llm.py`

- 作用：验证 `rag-system/original_data/gen_data/llm.py`。
- 输入：
  - 脚本内固定模型名和提示词。
- 输出：
  - 控制台文本。

---

## 5. 推荐使用顺序

如果要从零复现数据和训练流程，推荐顺序如下：

1. 生成原始样本：
   - `python src/datapipeline/0_generate_base_dataset.py`
2. 切分训练/测试：
   - `python src/datapipeline/1_split_dataset.py`
3. 转换为带工具调用轨迹的对话：
   - `python src/datapipeline/2_convert_dataset.py`
4. 拆分成多轮训练数据：
   - `python src/datapipeline/3_conversation_splitter.py`
5. 检查训练数据：
   - `python src/train/inspect_qwen_dataset.py`
6. 启动训练：
   - `bash scripts/run_train_last_assistant.sh`
   - 或 `bash scripts/run_train_full_finetune.sh`
7. 合并 LoRA：
   - `python src/train/merge_lora_into_base.py`
8. 本地推理验证：
   - `python src/inference/local_toolcall_inspector.py --show_template`
   - `python src/inference/local_toolcall_inspector.py --scenario campaign_metrics`
   - `python src/inference/local_toolcall_repl.py`
9. 在线 tool-call 联调：
   - `python tests/inference/online_toolcall_runner.py`

---

## 6. 已验证的本地命令

本轮重构后，已经验证过以下命令可在当前仓库结构下运行：

- `python -m unittest tests.test_repo_structure`
- `python tests/datapipeline/test_generate.py`
- `python src/datapipeline/3_conversation_splitter.py`
- `bash -n scripts/run_train_full_finetune.sh`
- `bash -n scripts/run_train_last_assistant.sh`

这些验证覆盖了：

- 新包结构导入
- 新路径助手
- `data/` 新目录位置
- `scripts/` 中 shell 脚本的新路径引用

---

## 7. 当前仍需外部依赖才能完整验证的部分

以下脚本的“业务运行”本轮没有在本地完整执行，因为当前环境缺少外部依赖或在线服务：

- 训练脚本：
  - 缺少 `torch`、`transformers`、`peft`、`trl`
- 推理脚本：
  - 缺少 `openai`
- RAG 脚本：
  - 缺少 `pymilvus`、`flask`、`jieba`
- 工具脚本：
  - 需要外部 API key

但这些脚本已经通过：

- 路径重构修正
- 包导入结构修正
- 全量 `compileall` 语法检查

因此从仓库结构和路径组织角度，已经具备继续安装依赖后运行的条件。
