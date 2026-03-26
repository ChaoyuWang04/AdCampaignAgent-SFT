#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TRAIN_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260324_211651_en_message_multiturn.json"
MODEL_PATH="${REPO_ROOT}/models/Qwen3-1.7B-Base"
OUTPUT_DIR="${REPO_ROOT}/models/dry_run_output"

mkdir -p "${OUTPUT_DIR}"

echo "🧪 Dry run on CPU — 2 steps only"

python3 "${REPO_ROOT}/src/train/train_qwen_lora_last_assistant_turn_only.py" \
  --train_file "${TRAIN_FILE}" \
  --model_name_or_path "${MODEL_PATH}" \
  --output_dir "${OUTPUT_DIR}" \
  --max_seq_length 512 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 1 \
  --learning_rate 2e-5 \
  --max_steps 2 \
  --logging_steps 1 \
  --save_steps 999999 \
  --save_total_limit 1 \
  --lr_scheduler_type cosine \
  --local_files_only

echo "✅ Dry run complete — pipeline is healthy"
