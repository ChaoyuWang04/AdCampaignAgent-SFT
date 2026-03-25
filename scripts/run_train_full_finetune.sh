#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TRAIN_FILE="${REPO_ROOT}/data/processed/merged_train_final_multiturn_v2.json"
MODEL_PATH="${REPO_ROOT}/models/qwen3-0_6b"
OUTPUT_DIR="${REPO_ROOT}/models/qwen3-0_6b_fullft_last_assistant"

mkdir -p "${OUTPUT_DIR}"

python3 "${REPO_ROOT}/src/train/train_qwen_full_finetune_last_assistant.py" \
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
