#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# =========================
# 可直接修改的默认配置
# =========================
# 直接修改这里，然后执行：
#   bash scripts/run_train_function_calling_all_assistant.sh

TRAIN_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260326_181224_zh_train_message.json"
EVAL_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260326_181224_zh_test_message.json"
MODEL_PATH="${REPO_ROOT}/models/Qwen3-1.7B-Base"
OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B-Base_lora_function_calling_all_assistant"

MAX_SEQ_LENGTH="20000"
PER_DEVICE_TRAIN_BATCH_SIZE="1"
GRADIENT_ACCUMULATION_STEPS="8"
LEARNING_RATE="2e-5"
NUM_TRAIN_EPOCHS="1"
WARMUP_RATIO="0.03"
LOGGING_STEPS="10"
SAVE_STEPS="1000"
SAVE_TOTAL_LIMIT="3"
LR_SCHEDULER_TYPE="cosine"
EVAL_STEPS="100"
DATALOADER_NUM_WORKERS="2"
SEED="42"
LOG_FILE=""

BF16="true"
FP16="false"
GRADIENT_CHECKPOINTING="true"
LOCAL_FILES_ONLY="true"
QLORA="false"

LORA_R="32"
LORA_ALPHA="64"
LORA_DROPOUT="0.05"
TARGET_MODULES="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj"

TOOLS_FILE="${REPO_ROOT}/src/tools/all_tools.json"
TOOLS_JSON=""

usage() {
  cat <<'EOF'
用法：
  直接在脚本顶部填写配置后运行
    bash scripts/run_train_function_calling_all_assistant.sh

功能：
  调用 src/train/train_qwen_function_calling_all_assistant_turns.py，
  以所有 assistant 轮次参与 loss 的方式进行 Function Calling LoRA 训练。

说明：
  - 这个脚本不接受命令行参数
  - 默认是普通 LoRA，不是全参数训练
  - QLORA=true 时会启用 4-bit 量化训练，需要 bitsandbytes
  - TOOLS_FILE 可为没有 tools 字段的样本补齐全局工具列表
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "错误：这个脚本不接受命令行参数，请直接编辑脚本顶部配置。" >&2
  usage
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

CMD=(
  python3 "${REPO_ROOT}/src/train/train_qwen_function_calling_all_assistant_turns.py"
  --train_file "${TRAIN_FILE}"
  --model_name_or_path "${MODEL_PATH}"
  --output_dir "${OUTPUT_DIR}"
  --max_seq_length "${MAX_SEQ_LENGTH}"
  --per_device_train_batch_size "${PER_DEVICE_TRAIN_BATCH_SIZE}"
  --gradient_accumulation_steps "${GRADIENT_ACCUMULATION_STEPS}"
  --learning_rate "${LEARNING_RATE}"
  --num_train_epochs "${NUM_TRAIN_EPOCHS}"
  --warmup_ratio "${WARMUP_RATIO}"
  --logging_steps "${LOGGING_STEPS}"
  --save_steps "${SAVE_STEPS}"
  --save_total_limit "${SAVE_TOTAL_LIMIT}"
  --lr_scheduler_type "${LR_SCHEDULER_TYPE}"
  --eval_steps "${EVAL_STEPS}"
  --dataloader_num_workers "${DATALOADER_NUM_WORKERS}"
  --seed "${SEED}"
  --lora_r "${LORA_R}"
  --lora_alpha "${LORA_ALPHA}"
  --lora_dropout "${LORA_DROPOUT}"
  --target_modules "${TARGET_MODULES}"
)

if [[ -n "${EVAL_FILE}" ]]; then
  CMD+=(--eval_file "${EVAL_FILE}")
fi
if [[ -n "${LOG_FILE}" ]]; then
  CMD+=(--log_file "${LOG_FILE}")
fi
if [[ -n "${TOOLS_FILE}" ]]; then
  CMD+=(--tools_file "${TOOLS_FILE}")
fi
if [[ -n "${TOOLS_JSON}" ]]; then
  CMD+=(--tools_json "${TOOLS_JSON}")
fi
if [[ "${BF16}" == "true" ]]; then
  CMD+=(--bf16)
fi
if [[ "${FP16}" == "true" ]]; then
  CMD+=(--fp16)
fi
if [[ "${GRADIENT_CHECKPOINTING}" == "true" ]]; then
  CMD+=(--gradient_checkpointing)
fi
if [[ "${LOCAL_FILES_ONLY}" == "true" ]]; then
  CMD+=(--local_files_only)
fi
if [[ "${QLORA}" == "true" ]]; then
  CMD+=(--qlora)
fi

echo "Run function-calling all-assistant LoRA training"
echo "Train file         : ${TRAIN_FILE}"
echo "Eval file          : ${EVAL_FILE}"
echo "Model              : ${MODEL_PATH}"
echo "Output dir         : ${OUTPUT_DIR}"
echo "Max seq length     : ${MAX_SEQ_LENGTH}"
echo "Batch size         : ${PER_DEVICE_TRAIN_BATCH_SIZE}"
echo "Grad accum         : ${GRADIENT_ACCUMULATION_STEPS}"
echo "Learning rate      : ${LEARNING_RATE}"
echo "Num train epochs   : ${NUM_TRAIN_EPOCHS}"
echo "Warmup ratio       : ${WARMUP_RATIO}"
echo "Logging steps      : ${LOGGING_STEPS}"
echo "Save steps         : ${SAVE_STEPS}"
echo "Eval steps         : ${EVAL_STEPS}"
echo "BF16               : ${BF16}"
echo "FP16               : ${FP16}"
echo "Gradient ckpt      : ${GRADIENT_CHECKPOINTING}"
echo "Local files only   : ${LOCAL_FILES_ONLY}"
echo "QLoRA              : ${QLORA}"
echo "Tools file         : ${TOOLS_FILE}"

"${CMD[@]}"
