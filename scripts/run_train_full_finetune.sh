#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TRAIN_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260324_211651_en_message_multiturn.json"
MODEL_PATH="${REPO_ROOT}/models/Qwen3-1.7B-Base"
OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B-Base_fullft_last_assistant"

mkdir -p "${OUTPUT_DIR}"

python3 "${REPO_ROOT}/src/train/train_qwen_full_finetune_last_assistant_turn_only.py" \
  --train_file "${TRAIN_FILE}" \
  --model_name_or_path "${MODEL_PATH}" \
  --output_dir "${OUTPUT_DIR}" \
  --max_seq_length 14096 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 16 \
  --learning_rate 2e-5 \
  --num_train_epochs 3 \
  --warmup_ratio 0.03 \
  --logging_steps 10 \
  --save_steps 300 \
  --save_total_limit 3 \
  --lr_scheduler_type cosine \
  --bf16 \
  --gradient_checkpointing \
  --local_files_only
