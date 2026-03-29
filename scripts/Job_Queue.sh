#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BENCHMARK_SCRIPT="${SCRIPT_DIR}/benchmark.sh"

run_benchmark() {
  local name=$1
  local model_path=$2
  echo ""
  echo "############################################"
  echo "# 开始 Benchmark：${name}"
  echo "# $(date '+%Y-%m-%d %H:%M:%S')"
  echo "############################################"
  echo ""
  MODEL="${model_path}" RUN_NAME="${name}" bash "${BENCHMARK_SCRIPT}"
  echo ""
  echo "✅ Benchmark ${name} 完成 — $(date '+%Y-%m-%d %H:%M:%S')"
  echo ""
}

# ── Benchmark A: multi_all ────────────────────────
run_benchmark "multi_all"     "${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_all"

# ── Benchmark B: multi_last ───────────────────────
run_benchmark "multi_last"    "${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_last"

# ── Benchmark C: nonmulti_all ─────────────────────
run_benchmark "nonmulti_all"  "${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_all"

# ── Benchmark D: nonmulti_last ────────────────────
run_benchmark "nonmulti_last" "${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_last"

echo "############################################"
echo "# 全部 Benchmark 完成 — $(date '+%Y-%m-%d %H:%M:%S')"
echo "############################################"
