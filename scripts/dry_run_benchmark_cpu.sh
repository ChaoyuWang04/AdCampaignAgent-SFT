#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# =========================
# CPU dry run 固定配置
# =========================
# 目标不是得到有意义的 benchmark 分数，而是用最小成本验证：
# 1. benchmark 入口能否启动
# 2. 本地模型能否在 CPU 上完成一次最小 trace
# 3. 工具执行、打分、结果写盘流程是否正常

BACKEND="local_hf"
MODEL="${REPO_ROOT}/models/qwen3-0_6b"
EVAL_GROUP="format"
DATA_DIR="${REPO_ROOT}/tests/benchmark/data"
RESULTS_DIR=""
RUN_NAME="cpu_dry_run"

# 只跑 1 条 smoke case，避免把 CPU 时间浪费在整套 benchmark 上。
CASE_FILES=("test_smoke.json")

# 把所有生成相关参数压到尽量小，只求流程跑通。
MAX_NEW_TOKENS="64"
TEMPERATURE="0.0"
TOP_P="1.0"
TOP_K="1"
REPETITION_PENALTY="1.0"
NO_REPEAT_NGRAM_SIZE="0"
MAX_TOOL_ROUNDS="1"
LOCAL_FILES_ONLY="true"

usage() {
  cat <<'EOF'
用法：
  bash scripts/dry_run_benchmark_cpu.sh

说明：
  这是一个 CPU smoke test 脚本，不是正式 benchmark 脚本。
  它会用最小配置跑 1 条样本，只验证流程能否跑通。

特点：
  - 固定 local_hf 后端
  - 固定只跑 test_smoke.json
  - 固定最小生成参数
  - 固定最多 1 轮工具调用

适用场景：
  - 先确认 benchmark 入口没问题
  - 先确认本地模型在 CPU 上至少能完成一次最小推理
  - 先确认结果文件会正常输出

注意：
  - 即使是 dry run，1.7B 模型在 CPU 上也可能比较慢
  - 这个脚本的目标只是“流程通过”，不是“分数有意义”
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "错误：这个脚本不接受命令行参数。" >&2
  usage
  exit 1
fi

TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
if [[ -z "${RESULTS_DIR}" ]]; then
  RESULTS_DIR="${REPO_ROOT}/tests/benchmark/results/${TIMESTAMP}_${RUN_NAME}"
fi

mkdir -p "${RESULTS_DIR}"

echo "CPU dry run benchmark"
echo "Model             : ${MODEL}"
echo "Eval group        : ${EVAL_GROUP}"
echo "Case files        : ${CASE_FILES[*]}"
echo "Max new tokens    : ${MAX_NEW_TOKENS}"
echo "Top k             : ${TOP_K}"
echo "Max tool rounds   : ${MAX_TOOL_ROUNDS}"
echo "Results dir       : ${RESULTS_DIR}"

uv run python "${REPO_ROOT}/tests/benchmark/run_benchmark.py" \
  --backend "${BACKEND}" \
  --model "${MODEL}" \
  --eval-group "${EVAL_GROUP}" \
  --data-dir "${DATA_DIR}" \
  --results-dir "${RESULTS_DIR}" \
  --case-files "${CASE_FILES[@]}" \
  --max-new-tokens "${MAX_NEW_TOKENS}" \
  --temperature "${TEMPERATURE}" \
  --top-p "${TOP_P}" \
  --top-k "${TOP_K}" \
  --repetition-penalty "${REPETITION_PENALTY}" \
  --no-repeat-ngram-size "${NO_REPEAT_NGRAM_SIZE}" \
  --max-tool-rounds "${MAX_TOOL_ROUNDS}" \
  --local-files-only

echo
echo "CPU dry run 完成。请检查："
echo "- ${RESULTS_DIR}/report.json"
echo "- ${RESULTS_DIR}/case_results.jsonl"
