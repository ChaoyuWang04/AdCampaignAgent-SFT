#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MERGE_SCRIPT="${SCRIPT_DIR}/merge_lora_into_base.sh"

run_merge() {
  local name=$1
  echo ""
  echo "############################################"
  echo "# 开始 Merge：${name}"
  echo "# $(date '+%Y-%m-%d %H:%M:%S')"
  echo "############################################"
  echo ""
  bash "${MERGE_SCRIPT}"
  echo ""
  echo "✅ Merge ${name} 完成 — $(date '+%Y-%m-%d %H:%M:%S')"
  echo ""
}

# ── Merge A：multi_all ────────────────────────────
export BASE_MODEL="${REPO_ROOT}/models/Qwen3-1.7B"
export ADAPTER_PATH="${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_all_adapter"
export OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_all"
run_merge "A: multi_all"

# ── Merge B：multi_last ───────────────────────────
export BASE_MODEL="${REPO_ROOT}/models/Qwen3-1.7B"
export ADAPTER_PATH="${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_last_adapter"
export OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_last"
run_merge "B: multi_last"

# ── Merge C：nonmulti_all ─────────────────────────
export BASE_MODEL="${REPO_ROOT}/models/Qwen3-1.7B"
export ADAPTER_PATH="${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_all_adapter"
export OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_all"
run_merge "C: nonmulti_all"

# ── Merge D：nonmulti_last ────────────────────────
export BASE_MODEL="${REPO_ROOT}/models/Qwen3-1.7B"
export ADAPTER_PATH="${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_last_adapter"
export OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_last"
run_merge "D: nonmulti_last"

echo "############################################"
echo "# 全部 Merge 完成 — $(date '+%Y-%m-%d %H:%M:%S')"
echo "############################################"
