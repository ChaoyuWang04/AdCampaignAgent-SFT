<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/ChaoyuWang04/AdCampaignAgent-SFT">
    <img src="images/logo.jpg" alt="Logo" width="100" height="100">
  </a>

<h3 align="center">AdCampaignAgent-SFT</h3>

<p align="center">
  An end-to-end SFT pipeline for mobile game UA tool-calling agents — rule-based synthetic data generation, Qwen3 LoRA fine-tuning, and an 11-metric benchmark suite across 15 ad-domain tools.
  <br /><br />
  | <a href="https://huggingface.co/datasets/SamWang0405/AdCampaignAgent-SFT">🤗 HuggingFace Dataset</a> |
  <a href="https://github.com/ChaoyuWang04/AdCampaignAgent-SFT/issues/new?labels=bug&template=bug-report---.md">Report Bug</a> |
  <a href="https://github.com/ChaoyuWang04/AdCampaignAgent-SFT/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a> |
</p>

</div>

## About

AdCampaignAgent-SFT is an open-source end-to-end pipeline for building, training, and evaluating **tool-calling agents** for mobile game advertising.

The repository covers six capabilities:

1. Generate structured Ad Agent seed records across 7 ad-operation workflows
2. Convert seeds into tool-call conversations in OpenAI Messages or ShareGPT format
3. Fine-tune local models (Qwen3) with LoRA across multiple training configurations
4. Provide 15 ad-domain tools for local runtime testing
5. Inspect or interact with local models for tool-calling behavior via REPL
6. Evaluate models with an 11-metric benchmark suite (format, routing, content, system-level)

The domain is mobile game UA (User Acquisition), with workflows grounded in:
- campaign performance analysis
- creative search
- creative upload
- anomaly diagnosis
- benchmark and policy lookup
- refusal handling for off-topic or unauthorized requests

## Current Scope

### Included in the main flow

- Rule-based seed generation
- Train/test seed splitting
- Conversation conversion to SFT-ready records (Message / ShareGPT / multiturn)
- Qwen3 LoRA fine-tuning with 4 experimental configurations under [src/train](src/train)
- 15 Ad Campaign Agent tools under [src/tools](src/tools)
- Local model tool-call REPL and inspector under [src/inference](src/inference)
- 11-metric benchmark suite under [tests/benchmark](tests/benchmark)

### Not in the current main flow

- [rag-system](rag-system) is a legacy travel-guide RAG subsystem kept in the repo as historical material. It is not part of the current Ad Agent training or inference pipeline.

## Dataset Snapshot

| Metric | Value |
|--------|-------|
| Total conversations | 1,000 |
| Format | OpenAI Messages / ShareGPT |
| Unique tools | 15 |
| Core workflows | 7 |
| Platforms covered | Google · Meta · TikTok · AppLovin · Unity |
| Game genres | Casual · Puzzle · Hyper-casual · RPG · Strategy |
| Tool-call heavy records | Majority of records |
| Refusal coverage | Off-topic · Unauthorized · Insufficient-data |

## Repository Layout

```text
AdCampaignAgent-SFT/
├── data/
│   ├── raw/                 # seed records, e.g. ad_agent_seeds_*.json
│   ├── processed/           # train/test split outputs
│   └── ready2train/         # final message/sharegpt datasets
├── docs/                    # repo documentation
├── images/                  # project images
├── models/                  # local checkpoints and LoRA adapters
├── prompts/                 # reusable prompt assets
├── src/
│   ├── common/              # shared path and utility helpers
│   ├── datapipeline/        # seed generation / split / conversion / multiturn expansion
│   ├── inference/           # local REPL and single-shot inspector
│   ├── tools/               # 15 ad-domain runtime tools + tool schema
│   └── train/               # LoRA fine-tuning, merging, and dataset inspection
├── tests/
│   ├── benchmark/           # 11-metric benchmark suite (format/routing/content/system)
│   └── inference/           # online tool-call smoke runner
├── scripts/                 # shell helpers for training, benchmarking, and REPL
└── rag-system/              # legacy travel RAG assets, not in main flow
```

## Requirements

- Python 3.13+
- `uv`

```sh
uv --version
```

## Setup

```sh
git clone https://github.com/ChaoyuWang04/AdCampaignAgent-SFT.git
cd AdCampaignAgent-SFT
uv venv
uv sync
```

## Main Workflow

### 1. Generate seed records

This creates raw Ad Agent seed data under `data/raw/`.

```sh
uv run python src/datapipeline/0_generate_base_dataset.py
```

Output example:

```text
data/raw/ad_agent_seeds_20260326_zh.json
data/raw/ad_agent_seeds_20260326_en.json
```

### 2. Split seeds into train / test

```sh
uv run python src/datapipeline/1_split_dataset.py
# Then enter the seed file name, for example:
# ad_agent_seeds_20260326_zh.json
```

The split script currently stratifies by:
- `workflow_name`
- `scene_tag`
- `needs_clarification`

Typical outputs:
- `data/processed/ad_agent_seeds_20260326_zh_train.json`
- `data/processed/ad_agent_seeds_20260326_zh_test.json`
- `data/processed/ad_agent_seeds_20260326_en_train.json`
- `data/processed/ad_agent_seeds_20260326_en_test.json`

### 3. Convert seeds into tool-call conversations

```sh
uv run python src/datapipeline/2_convert_dataset.py
```

Typical inputs:
- `data/processed/ad_agent_seeds_20260326_zh_train.json`
- `data/processed/ad_agent_seeds_20260326_zh_test.json`
- `data/processed/ad_agent_seeds_20260326_en_train.json`
- `data/processed/ad_agent_seeds_20260326_en_test.json`

Typical outputs:
- `data/ready2train/message/ad_agent_sft_*_message.json`
- `data/ready2train/sharegpt/ad_agent_sft_*_sharegpt.json`

### 4. Expand message-format data into multiturn samples

```sh
uv run python src/datapipeline/3_conversation_splitter.py
```

Typical output:
- `data/ready2train/message/ad_agent_sft_*_message_multiturn.json`

## Tools

The runtime tool schema lives in:
- [src/tools/all_tools.json](src/tools/all_tools.json)

The tool implementations live in:
- [src/tools](src/tools)

Current tool families:
- creative search
- creative upload
- campaign / creative analytics
- anomaly diagnosis
- benchmark / policy / knowledge retrieval

See:
- [src/tools/README.md](src/tools/README.md)

## Local Inference

### Local tool-call inspector

Single-shot local model inspection for tool-calling behavior.

```sh
uv run python src/inference/local_toolcall_inspector.py \
  --scenario campaign_metrics \
  --local_files_only
```

Useful for:
- checking chat template rendering
- checking whether a local model emits tool calls
- checking parsed tool-call arguments

### Local tool-call REPL

Interactive local REPL that can:
- send user turns to a local model
- parse tool calls
- execute local tools
- feed tool results back to the model

```sh
uv run python src/inference/local_toolcall_repl.py --local_files_only
```

You can also use the fixed-config shell wrapper:

```sh
bash scripts/local_repl.sh
```

The REPL defaults to:
- tool schema: [src/tools/all_tools.json](src/tools/all_tools.json)
- system prompt: [prompts/ad_agent_system_prompt.txt](prompts/ad_agent_system_prompt.txt)

You can override the system prompt with:

```sh
uv run python src/inference/local_toolcall_repl.py \
  --system-file prompts/ad_agent_system_prompt.txt
```

or:

```sh
uv run python src/inference/local_toolcall_repl.py \
  --system-text "You are a mobile game UA assistant..."
```

## External Model Runner

For OpenAI-compatible external model tool-call debugging, use:

```sh
uv run python tests/inference/online_toolcall_runner.py
```

This is intentionally kept under `tests/inference/` because it is an external-model smoke runner, not part of the local inference core.

## Prompt Assets

Prompt files are stored under:
- [prompts](prompts)

Current default runtime prompt:
- [prompts/ad_agent_system_prompt.txt](prompts/ad_agent_system_prompt.txt)

## Training

Training scripts live under [src/train](src/train) and shell helpers under [scripts](scripts).

Typical training flow:

1. Generate seeds
2. Split train/test
3. Convert to message/sharegpt data
4. Optionally expand multiturn message data
5. Inspect dataset formatting (`scripts/inspect_datasets.sh`)
6. Run LoRA fine-tuning:

```sh
bash scripts/train_model.sh
```

Or directly:

```sh
uv run python src/train/train_qwen_lora.py \
  --train_file data/ready2train/message/ad_agent_sft_*_train_message.json \
  --eval_file  data/ready2train/message/ad_agent_sft_*_test_message.json \
  --output_dir models/my_lora_output
```

7. Merge LoRA adapter into base model (`scripts/merge_lora_into_base.sh`)

For detailed paths and script descriptions, see:
- [docs/仓库使用指南.md](docs/仓库使用指南.md)

## Roadmap

- [x] Rule-based Ad Agent seed generation
- [x] 15-tool ad-domain runtime schema
- [x] OpenAI Messages / ShareGPT / multiturn conversion
- [x] Qwen3 LoRA fine-tuning (4 experimental configurations)
- [x] Local tool-call inspector
- [x] Local tool-call REPL
- [x] Online tool-call runner for external models
- [x] 11-metric benchmark suite (format / routing / content / system)
- [ ] Replace legacy travel RAG with ad-domain knowledge RAG
- [ ] Expand benchmark and policy retrieval quality
- [ ] Publish fine-tuned checkpoints to HuggingFace

## Contributing

Issues and pull requests are welcome. If you want to extend the repo, the highest-leverage areas are:
- better ad-domain RAG replacement
- stronger tool-call eval coverage
- cleaner training / reporting automation

## Links

- Project: [https://github.com/ChaoyuWang04/AdCampaignAgent-SFT](https://github.com/ChaoyuWang04/AdCampaignAgent-SFT)
- Dataset: [https://huggingface.co/datasets/SamWang0405/AdCampaignAgent-SFT](https://huggingface.co/datasets/SamWang0405/AdCampaignAgent-SFT)
- Author: [Chaoyu Wang](https://www.linkedin.com/in/samwang04/)

## License

Distributed under the MIT License. See `LICENSE` for more information.
