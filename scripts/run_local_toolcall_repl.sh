#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# =========================
# 可直接修改的默认配置
# =========================
# 直接修改这里，然后执行：
#   bash scripts/run_local_toolcall_repl.sh

MODEL_PATH="${REPO_ROOT}/models/Qwen3-1.7B-Base"
MAX_NEW_TOKENS="500"
TEMPERATURE="0.0"
TOP_P="1.0"
TOP_K="1"
REPETITION_PENALTY="1.1"
NO_REPEAT_NGRAM_SIZE="6"
DO_SAMPLE="false"

BF16="true"
FP16="false"
DEVICE_MAP_AUTO="true"
LOCAL_FILES_ONLY="true"

TOOLS_FILE="${REPO_ROOT}/src/tools/all_tools.json"
TOOLS_JSON=""
SYSTEM_FILE=""
SYSTEM_TEXT=""
MAX_TOOL_ROUNDS="4"

usage() {
  cat <<'EOF'
用法：
  直接在脚本顶部填写配置后运行
    bash scripts/run_local_toolcall_repl.sh

功能：
  调用 src/inference/local_toolcall_repl.py，启动本地工具调用 REPL。

说明：
  - 这个脚本不接受命令行参数
  - 默认按本地 GPU 路径加载模型
  - 如果你使用 merged 模型，只需要把 MODEL_PATH 改成 merged 目录
  - SYSTEM_FILE 和 SYSTEM_TEXT 二选一即可，两个都为空时走默认 prompt
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

if [[ -z "${MODEL_PATH}" ]]; then
  echo "错误：MODEL_PATH 不能为空。" >&2
  usage
  exit 1
fi

CMD=(
  uv run python "${REPO_ROOT}/src/inference/local_toolcall_repl.py"
  --model_path "${MODEL_PATH}"
  --max_new_tokens "${MAX_NEW_TOKENS}"
  --temperature "${TEMPERATURE}"
  --top_p "${TOP_P}"
  --top_k "${TOP_K}"
  --repetition_penalty "${REPETITION_PENALTY}"
  --no_repeat_ngram_size "${NO_REPEAT_NGRAM_SIZE}"
  --max_tool_rounds "${MAX_TOOL_ROUNDS}"
)

if [[ -n "${TOOLS_FILE}" ]]; then
  CMD+=(--tools_file "${TOOLS_FILE}")
fi
if [[ -n "${TOOLS_JSON}" ]]; then
  CMD+=(--tools_json "${TOOLS_JSON}")
fi
if [[ -n "${SYSTEM_FILE}" ]]; then
  CMD+=(--system-file "${SYSTEM_FILE}")
fi
if [[ -n "${SYSTEM_TEXT}" ]]; then
  CMD+=(--system-text "${SYSTEM_TEXT}")
fi
if [[ "${DO_SAMPLE}" == "true" ]]; then
  CMD+=(--do_sample)
fi
if [[ "${BF16}" == "true" ]]; then
  CMD+=(--bf16)
fi
if [[ "${FP16}" == "true" ]]; then
  CMD+=(--fp16)
fi
if [[ "${DEVICE_MAP_AUTO}" == "true" ]]; then
  CMD+=(--device_map_auto)
fi
if [[ "${LOCAL_FILES_ONLY}" == "true" ]]; then
  CMD+=(--local_files_only)
fi

echo "Run local toolcall REPL"
echo "Model              : ${MODEL_PATH}"
echo "Max new tokens     : ${MAX_NEW_TOKENS}"
echo "Temperature        : ${TEMPERATURE}"
echo "Top p              : ${TOP_P}"
echo "Top k              : ${TOP_K}"
echo "Repetition pen.    : ${REPETITION_PENALTY}"
echo "No repeat ngram    : ${NO_REPEAT_NGRAM_SIZE}"
echo "Do sample          : ${DO_SAMPLE}"
echo "BF16               : ${BF16}"
echo "FP16               : ${FP16}"
echo "Device map auto    : ${DEVICE_MAP_AUTO}"
echo "Local files only   : ${LOCAL_FILES_ONLY}"
echo "Tools file         : ${TOOLS_FILE}"
echo "System file        : ${SYSTEM_FILE}"
echo "Max tool rounds    : ${MAX_TOOL_ROUNDS}"
echo

"${CMD[@]}"
