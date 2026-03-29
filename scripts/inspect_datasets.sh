#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# =========================
# 可直接修改的默认配置
# =========================
# 直接修改这里，然后执行：
#   bash scripts/inspect_ready2train.sh

DATA_FILE="${REPO_ROOT}/data/ready2train/message/ad_agent_sft_20260326_181224_zh_test_message.json"
MODEL_NAME_OR_PATH="${REPO_ROOT}/models/"

NUM_SAMPLES="1"
START="0"
MAX_SEQ_LENGTH="20000"
MAX_PRINT_TOKENS="20000"

SHOW_SUMMARY="true"
SHOW_INPUT_IDS="false"
SHOW_LOSS_MASK="false"
SHOW_LOSS_SEGMENTS="true"
SHOW_TOKENS="false"
SHOW_FULL_DECODED="false"
SHOW_IGNORED_SEGMENTS="false"

ONLY_LAST_ASSISTANT="false"
LOCAL_FILES_ONLY="true"
COLOR="false"

TOOLS_FILE="${REPO_ROOT}/src/tools/all_tools.json"
EXPORT_DIR=""

usage() {
  cat <<'EOF'
用法：
  直接在脚本顶部填写配置后运行
    bash scripts/inspect_ready2train.sh

功能：
  调用 src/train/inspect_qwen_dataset.py，检查 ready2train 数据是否能被 tokenizer 正常模板化，
  并查看 token、decoded 文本、loss mask 等信息。

默认配置项：
  直接修改脚本顶部这些变量即可：
  - DATA_FILE
  - MODEL_NAME_OR_PATH
  - NUM_SAMPLES
  - START
  - MAX_SEQ_LENGTH
  - MAX_PRINT_TOKENS
  - SHOW_SUMMARY
  - SHOW_INPUT_IDS
  - SHOW_LOSS_MASK
  - SHOW_LOSS_SEGMENTS
  - SHOW_TOKENS
  - SHOW_FULL_DECODED
  - SHOW_IGNORED_SEGMENTS
  - ONLY_LAST_ASSISTANT
  - LOCAL_FILES_ONLY
  - COLOR
  - TOOLS_FILE
  - EXPORT_DIR

说明：
  - 这个脚本不接受命令行参数
  - 主要用于检查 data/ready2train 下的数据
  - SHOW_SUMMARY 控制是否显示样本概览
  - SHOW_INPUT_IDS 控制是否显示原始 input_ids
  - SHOW_LOSS_MASK 控制是否显示 1/. 形式的 loss mask
  - SHOW_LOSS_SEGMENTS 控制是否显示参与 loss 的 decoded 片段
  - SHOW_TOKENS=true 时会输出 token 级信息，内容会很多
  - SHOW_FULL_DECODED=true 时会打印完整 decode 后文本
  - SHOW_IGNORED_SEGMENTS=true 时会额外打印不参与 loss 的上下文片段
  - ONLY_LAST_ASSISTANT=true 时只查看最后一段 assistant 的 loss 区间
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

if [[ -z "${DATA_FILE}" || -z "${MODEL_NAME_OR_PATH}" ]]; then
  echo "错误：DATA_FILE 和 MODEL_NAME_OR_PATH 不能为空。" >&2
  usage
  exit 1
fi

CMD=(
  uv run python "${REPO_ROOT}/src/train/inspect_qwen_dataset.py"
  --data_file "${DATA_FILE}"
  --model_name_or_path "${MODEL_NAME_OR_PATH}"
  --num_samples "${NUM_SAMPLES}"
  --start "${START}"
  --max_seq_length "${MAX_SEQ_LENGTH}"
  --max_print_tokens "${MAX_PRINT_TOKENS}"
  --tools_file "${TOOLS_FILE}"
)

if [[ -n "${EXPORT_DIR}" ]]; then
  CMD+=(--export_dir "${EXPORT_DIR}")
fi
if [[ "${SHOW_SUMMARY}" == "true" ]]; then
  CMD+=(--show_summary)
fi
if [[ "${SHOW_INPUT_IDS}" == "true" ]]; then
  CMD+=(--show_input_ids)
fi
if [[ "${SHOW_LOSS_MASK}" == "true" ]]; then
  CMD+=(--show_loss_mask)
fi
if [[ "${SHOW_LOSS_SEGMENTS}" == "true" ]]; then
  CMD+=(--show_loss_segments)
fi
if [[ "${SHOW_TOKENS}" == "true" ]]; then
  CMD+=(--show_tokens)
fi
if [[ "${SHOW_FULL_DECODED}" == "true" ]]; then
  CMD+=(--show_full_decoded)
fi
if [[ "${SHOW_IGNORED_SEGMENTS}" == "true" ]]; then
  CMD+=(--show_ignored_segments)
fi
if [[ "${ONLY_LAST_ASSISTANT}" == "true" ]]; then
  CMD+=(--only_last_assistant)
fi
if [[ "${LOCAL_FILES_ONLY}" == "true" ]]; then
  CMD+=(--local_files_only)
fi
if [[ "${COLOR}" == "true" ]]; then
  CMD+=(--color)
fi

echo "Inspect ready2train dataset"
echo "Data file          : ${DATA_FILE}"
echo "Model              : ${MODEL_NAME_OR_PATH}"
echo "Num samples        : ${NUM_SAMPLES}"
echo "Start              : ${START}"
echo "Max seq length     : ${MAX_SEQ_LENGTH}"
echo "Max print tokens   : ${MAX_PRINT_TOKENS}"
echo "Show summary       : ${SHOW_SUMMARY}"
echo "Show input ids     : ${SHOW_INPUT_IDS}"
echo "Show loss mask     : ${SHOW_LOSS_MASK}"
echo "Show loss segments : ${SHOW_LOSS_SEGMENTS}"
echo "Show tokens        : ${SHOW_TOKENS}"
echo "Show full decoded  : ${SHOW_FULL_DECODED}"
echo "Show ignored segs  : ${SHOW_IGNORED_SEGMENTS}"
echo "Only last asst     : ${ONLY_LAST_ASSISTANT}"
echo "Local files only   : ${LOCAL_FILES_ONLY}"
echo "Color              : ${COLOR}"
echo "Tools file         : ${TOOLS_FILE}"
if [[ -n "${EXPORT_DIR}" ]]; then
  echo "Export dir         : ${EXPORT_DIR}"
fi

"${CMD[@]}"
