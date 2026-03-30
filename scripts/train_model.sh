#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

EXPERIMENT="${EXPERIMENT:-multi_last}"
ONLY_LAST_ASSISTANT="${ONLY_LAST_ASSISTANT:-true}"
TRAIN_FILE="${TRAIN_FILE:-${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260328_041007_zh_train_message_multiturn.json}"
EVAL_FILE="${EVAL_FILE:-${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260328_041007_zh_test_message_multiturn.json}"
LEARNING_RATE="${LEARNING_RATE:-2e-5}"
NUM_TRAIN_EPOCHS="${NUM_TRAIN_EPOCHS:-2}"
EVAL_STEPS="${EVAL_STEPS:-100}"
SAVE_STEPS="${SAVE_STEPS:-200}"
EARLY_STOPPING_PATIENCE="${EARLY_STOPPING_PATIENCE:-5}"
EARLY_STOPPING_THRESHOLD="${EARLY_STOPPING_THRESHOLD:-0.001}"

# =============================================================
# 核心开关（每次改实验只需要改这里）
# =============================================================

# 实验标签，自动生成 OUTPUT_DIR 和 WandB run name
# 建议命名规范：nonmulti_all / nonmulti_last / multi_all / multi_last
#EXPERIMENT="multi_last"

# --- Loss 策略 ---
# true  = 只对最后一条 assistant 回复计算 loss（last_assistant_only）
# false = 对所有 assistant 回复计算 loss（all_assistant）
#ONLY_LAST_ASSISTANT="true"

# --- 训练模式 ---
# true  = 全参数微调（不使用 LoRA）
# false = LoRA 微调（默认）
# 注意：FULL_FT=true 时 QLORA 必须为 false
FULL_FT="false"

# --- 数据选择（二选一，取消注释对应行）---

# 非 multiturn（779条）推荐：LR=5e-5  EPOCHS=5  EVAL_STEPS=50  SAVE_STEPS=100
# TRAIN_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260328_041007_zh_train_message.json"
# EVAL_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260328_041007_zh_test_message.json"

# multiturn（3807条）推荐：LR=2e-5  EPOCHS=2  EVAL_STEPS=100  SAVE_STEPS=200
#TRAIN_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260328_041007_zh_train_message_multiturn.json"
#EVAL_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260328_041007_zh_test_message_multiturn.json"

# =============================================================
# 训练超参（根据数据集大小调整，参考上方注释）
# =============================================================

#LEARNING_RATE="2e-5"
#NUM_TRAIN_EPOCHS="2"
#EVAL_STEPS="100"
#SAVE_STEPS="200"
#EARLY_STOPPING_PATIENCE="4"    # eval loss 连续4次不降就停
#EARLY_STOPPING_THRESHOLD="0.001"

# =============================================================
# 固定配置（一般不需要修改）
# =============================================================

MODEL_PATH="${MODEL_PATH:-${REPO_ROOT}/models/Qwen3-1.7B}"
OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B_lora_${EXPERIMENT}"
PYTHON_TRAIN_SCRIPT="${REPO_ROOT}/src/train/train_qwen_lora.py"

MAX_SEQ_LENGTH="4096"
PER_DEVICE_TRAIN_BATCH_SIZE="1"
PER_DEVICE_EVAL_BATCH_SIZE="1"
GRADIENT_ACCUMULATION_STEPS="8"
WARMUP_RATIO="0.03"
LR_SCHEDULER_TYPE="cosine"
WEIGHT_DECAY="0.0"
MAX_STEPS="-1"

LOGGING_STEPS="10"
SAVE_TOTAL_LIMIT="10"
EVAL_ACCUMULATION_STEPS="4"
LOG_FILE=""

DATALOADER_NUM_WORKERS="2"
SEED="42"

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

# =============================================================
# 参数校验
# =============================================================

usage() {
  cat <<'EOF'
用法：
  直接在脚本顶部修改配置后运行
    bash scripts/run_train_lora.sh

4组实验配置：
  实验A: 非multiturn + ONLY_LAST_ASSISTANT=false  EXPERIMENT=nonmulti_all
  实验B: 非multiturn + ONLY_LAST_ASSISTANT=true   EXPERIMENT=nonmulti_last
  实验C: multiturn   + ONLY_LAST_ASSISTANT=false  EXPERIMENT=multi_all
  实验D: multiturn   + ONLY_LAST_ASSISTANT=true   EXPERIMENT=multi_last

数据量 vs 超参建议：
  非multiturn（779条）：LR=5e-5  EPOCHS=5  EVAL_STEPS=50  SAVE_STEPS=100
  multiturn（3807条）：LR=2e-5  EPOCHS=2  EVAL_STEPS=100 SAVE_STEPS=200
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "错误：这个脚本不接受命令行参数，请直接编辑脚本顶部配置。" >&2
  exit 1
fi

if [[ "${FULL_FT}" == "true" && "${QLORA}" == "true" ]]; then
  echo "错误：FULL_FT 和 QLORA 不能同时为 true。" >&2
  exit 1
fi

if [[ "${BF16}" == "true" && "${FP16}" == "true" ]]; then
  echo "错误：BF16 和 FP16 不能同时为 true。" >&2
  exit 1
fi

# =============================================================
# 启动训练
# =============================================================

mkdir -p "${OUTPUT_DIR}"

export WANDB_PROJECT="AdCampaignAgent-SFT"
export WANDB_RUN_NAME="Qwen3-1.7B-${EXPERIMENT}-$(date +%Y%m%d-%H%M)"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

CMD=(
  python3 "${PYTHON_TRAIN_SCRIPT}"
  --train_file                   "${TRAIN_FILE}"
  --model_name_or_path           "${MODEL_PATH}"
  --output_dir                   "${OUTPUT_DIR}"
  --max_seq_length               "${MAX_SEQ_LENGTH}"
  --learning_rate                "${LEARNING_RATE}"
  --num_train_epochs             "${NUM_TRAIN_EPOCHS}"
  --warmup_ratio                 "${WARMUP_RATIO}"
  --weight_decay                 "${WEIGHT_DECAY}"
  --max_steps                    "${MAX_STEPS}"
  --lr_scheduler_type            "${LR_SCHEDULER_TYPE}"
  --per_device_train_batch_size  "${PER_DEVICE_TRAIN_BATCH_SIZE}"
  --per_device_eval_batch_size   "${PER_DEVICE_EVAL_BATCH_SIZE}"
  --gradient_accumulation_steps  "${GRADIENT_ACCUMULATION_STEPS}"
  --logging_steps                "${LOGGING_STEPS}"
  --save_steps                   "${SAVE_STEPS}"
  --save_total_limit             "${SAVE_TOTAL_LIMIT}"
  --eval_steps                   "${EVAL_STEPS}"
  --eval_accumulation_steps      "${EVAL_ACCUMULATION_STEPS}"
  --dataloader_num_workers       "${DATALOADER_NUM_WORKERS}"
  --seed                         "${SEED}"
  --lora_r                       "${LORA_R}"
  --lora_alpha                   "${LORA_ALPHA}"
  --lora_dropout                 "${LORA_DROPOUT}"
  --target_modules               "${TARGET_MODULES}"
)

if [[ -n "${EVAL_FILE}" ]];   then CMD+=(--eval_file "${EVAL_FILE}"); fi
if [[ -n "${LOG_FILE}" ]];    then CMD+=(--log_file "${LOG_FILE}"); fi
if [[ -n "${TOOLS_FILE}" ]];  then CMD+=(--tools_file "${TOOLS_FILE}"); fi
if [[ -n "${TOOLS_JSON}" ]];  then CMD+=(--tools_json "${TOOLS_JSON}"); fi
if [[ "${EARLY_STOPPING_PATIENCE}" -gt 0 ]]; then
  CMD+=(--early_stopping_patience "${EARLY_STOPPING_PATIENCE}")
  CMD+=(--early_stopping_threshold "${EARLY_STOPPING_THRESHOLD}")
fi
if [[ "${ONLY_LAST_ASSISTANT}" == "true" ]];    then CMD+=(--only_last_assistant); fi
if [[ "${FULL_FT}" == "true" ]];                then CMD+=(--full_ft); fi
if [[ "${BF16}" == "true" ]];                   then CMD+=(--bf16); fi
if [[ "${FP16}" == "true" ]];                   then CMD+=(--fp16); fi
if [[ "${GRADIENT_CHECKPOINTING}" == "true" ]]; then CMD+=(--gradient_checkpointing); fi
if [[ "${LOCAL_FILES_ONLY}" == "true" ]];       then CMD+=(--local_files_only); fi
if [[ "${QLORA}" == "true" ]];                  then CMD+=(--qlora); fi

echo "=============================="
echo " Run LoRA Training"
echo "=============================="
echo " Experiment         : ${EXPERIMENT}"
echo " Only last asst     : ${ONLY_LAST_ASSISTANT}"
echo " Full FT            : ${FULL_FT}"
echo " Train file         : $(basename ${TRAIN_FILE})"
echo " Eval file          : $(basename ${EVAL_FILE})"
echo " Model              : $(basename ${MODEL_PATH})"
echo " Output dir         : ${OUTPUT_DIR}"
echo " Learning rate      : ${LEARNING_RATE}"
echo " Num epochs         : ${NUM_TRAIN_EPOCHS}"
echo " Eval steps         : ${EVAL_STEPS}"
echo " Save steps         : ${SAVE_STEPS}"
echo " BF16               : ${BF16}"
echo " QLoRA              : ${QLORA}"
echo "=============================="
echo

"${CMD[@]}"