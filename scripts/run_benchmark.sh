#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# =========================
# 可直接修改的默认配置
# =========================
# 你可以只改这里，然后直接执行：
#   bash scripts/run_benchmark.sh

BACKEND="local_hf"
MODEL="${REPO_ROOT}/models/Qwen3-1.7B-merged"
EVAL_GROUP="all"
DATA_DIR="${REPO_ROOT}/tests/benchmark/data"
RESULTS_DIR=""
RUN_NAME="qwen3_1.7b_benchmark"
MAX_NEW_TOKENS="500"
TEMPERATURE="0.0"
TOP_P="1.0"
TOP_K="1"
REPETITION_PENALTY="1.0"
NO_REPEAT_NGRAM_SIZE="0"
MAX_TOOL_ROUNDS="4"
LOCAL_FILES_ONLY="true"
BF16="true"
FP16="false"
DEVICE_MAP_AUTO="true"
CASE_FILES=()

# 如果你只想跑某几个文件，可以直接在这里填写，例如：
# CASE_FILES=("test_oos.json" "test_clarify.json")

usage() {
  cat <<'EOF'
用法：
  直接在脚本顶部填写配置后运行
    bash scripts/run_benchmark.sh

功能：
  1. 跑整套 benchmark
  2. 单独跑某一个评测组：format / routing / content / system

默认配置项：
  直接修改脚本顶部这些变量即可：
  - BACKEND
  - MODEL
  - EVAL_GROUP
  - DATA_DIR
  - RESULTS_DIR
  - RUN_NAME
  - MAX_NEW_TOKENS
  - TEMPERATURE
  - TOP_P
  - TOP_K
  - REPETITION_PENALTY
  - NO_REPEAT_NGRAM_SIZE
  - MAX_TOOL_ROUNDS
  - LOCAL_FILES_ONLY
  - BF16
  - FP16
  - DEVICE_MAP_AUTO
  - CASE_FILES

示例：
  1. 在脚本顶部填好配置后直接运行
     bash scripts/run_benchmark.sh

  2. 如果只想跑系统层，把脚本中的 EVAL_GROUP 改成 system 后再运行

  3. 如果只想跑自定义 case 文件，把脚本中的 CASE_FILES 改成：
     CASE_FILES=("test_oos.json" "test_clarify.json")

说明：
  - 如果 CASE_FILES 为空，就按 EVAL_GROUP 自动选择数据文件
  - 如果 CASE_FILES 不为空，就优先使用你手动指定的文件
  - 本地 `local_hf` 后端如果要真正走 GPU，通常需要 BF16=true 且 DEVICE_MAP_AUTO=true
  - openai 后端需要提前设置 OPENAI_API_KEY
  - 如果不是官方默认接口，还需要设置 OPENAI_BASE_URL
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

if [[ -z "${BACKEND}" || -z "${MODEL}" ]]; then
  echo "错误：BACKEND 和 MODEL 不能为空。" >&2
  echo "请直接编辑 scripts/run_benchmark.sh 顶部配置。" >&2
  usage
  exit 1
fi

case "${BACKEND}" in
  local_hf|openai)
    ;;
  *)
    echo "错误：--backend 只能是 local_hf 或 openai。" >&2
    exit 1
    ;;
esac

case "${EVAL_GROUP}" in
  all|format|routing|content|system)
    ;;
  *)
    echo "错误：--eval-group 只能是 all / format / routing / content / system。" >&2
    exit 1
    ;;
esac

if [[ -z "${RESULTS_DIR}" ]]; then
  TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
  SAFE_MODEL="$(basename "${MODEL}" | tr ' /:' '___')"
  SUFFIX="${RUN_NAME:-${SAFE_MODEL}}"
  RESULTS_DIR="${REPO_ROOT}/tests/benchmark/results/${TIMESTAMP}_${BACKEND}_${EVAL_GROUP}_${SUFFIX}"
fi

mkdir -p "${RESULTS_DIR}"

CMD=(
  uv run python "${REPO_ROOT}/tests/benchmark/run_benchmark.py"
  --backend "${BACKEND}"
  --model "${MODEL}"
  --eval-group "${EVAL_GROUP}"
  --data-dir "${DATA_DIR}"
  --results-dir "${RESULTS_DIR}"
)

if [[ ${#CASE_FILES[@]} -gt 0 ]]; then
  CMD+=(--case-files)
  for case_file in "${CASE_FILES[@]}"; do
    CMD+=("${case_file}")
  done
fi

echo "Benchmark backend : ${BACKEND}"
echo "Benchmark model   : ${MODEL}"
echo "Eval group        : ${EVAL_GROUP}"
echo "Data dir          : ${DATA_DIR}"
echo "Results dir       : ${RESULTS_DIR}"
echo "Max new tokens    : ${MAX_NEW_TOKENS}"
echo "Temperature       : ${TEMPERATURE}"
echo "Top p             : ${TOP_P}"
echo "Top k             : ${TOP_K}"
echo "Repetition pen.   : ${REPETITION_PENALTY}"
echo "No repeat ngram   : ${NO_REPEAT_NGRAM_SIZE}"
echo "Max tool rounds   : ${MAX_TOOL_ROUNDS}"
echo "Local files only  : ${LOCAL_FILES_ONLY}"
echo "BF16              : ${BF16}"
echo "FP16              : ${FP16}"
echo "Device map auto   : ${DEVICE_MAP_AUTO}"
if [[ ${#CASE_FILES[@]} -gt 0 ]]; then
  echo "Case files        : ${CASE_FILES[*]}"
fi

CMD+=(
  --max-new-tokens "${MAX_NEW_TOKENS}"
  --temperature "${TEMPERATURE}"
  --top-p "${TOP_P}"
  --top-k "${TOP_K}"
  --repetition-penalty "${REPETITION_PENALTY}"
  --no-repeat-ngram-size "${NO_REPEAT_NGRAM_SIZE}"
  --max-tool-rounds "${MAX_TOOL_ROUNDS}"
)

if [[ "${LOCAL_FILES_ONLY}" == "true" ]]; then
  CMD+=(--local-files-only)
fi
if [[ "${BF16}" == "true" ]]; then
  CMD+=(--bf16)
fi
if [[ "${FP16}" == "true" ]]; then
  CMD+=(--fp16)
fi
if [[ "${DEVICE_MAP_AUTO}" == "true" ]]; then
  CMD+=(--device-map-auto)
fi

"${CMD[@]}"

echo
echo "Benchmark 完成。结果文件："
echo "- ${RESULTS_DIR}/report.json"
echo "- ${RESULTS_DIR}/case_results.jsonl"
