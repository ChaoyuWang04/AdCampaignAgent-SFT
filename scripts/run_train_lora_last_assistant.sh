#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TRAIN_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260326_181224_zh_train_message_multiturn.json"
EVAL_PATH="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260326_181224_zh_test_message_multiturn.json"

MODEL_PATH="${REPO_ROOT}/models/Qwen3-1.7B-Base"

# DEBUG 模式：输出到独立目录，避免覆盖正式 checkpoint
DEBUG=${DEBUG:-0}
if [ "${DEBUG}" = "1" ]; then
  OUTPUT_DIR="${REPO_ROOT}/models/debug_output"
  EXTRA_ARGS="--max_steps 2 --max_seq_length 512 --logging_steps 1 --save_steps 999999"
  echo "🧪 DEBUG mode — 2 steps only"
else
  OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B-Base_lora_last_assistant"
  EXTRA_ARGS=""
  echo "🚀 Full training"
fi

mkdir -p "${OUTPUT_DIR}"

# WandB 配置
export WANDB_PROJECT="AdCampaignAgent-SFT"
export WANDB_RUN_NAME="Qwen3-1.7B-lora-$(date +%Y%m%d-%H%M)"

python3 "${REPO_ROOT}/src/train/train_qwen_lora_last_assistant_turn_only.py" \
  --train_file "${TRAIN_FILE}" \
  --model_name_or_path "${MODEL_PATH}" \
  --output_dir "${OUTPUT_DIR}" \
  --max_seq_length 20000 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 8 \
  --learning_rate 2e-5 \
  --num_train_epochs 1 \
  --warmup_ratio 0.03 \
  --logging_steps 10 \
  --save_steps 1000 \
  --save_total_limit 3 \
  --lr_scheduler_type cosine \
  --bf16 \
  --gradient_checkpointing \
  --local_files_only \
  --eval_file "${EVAL_PATH}" \
  --eval_steps 100 \
  ${EXTRA_ARGS}
