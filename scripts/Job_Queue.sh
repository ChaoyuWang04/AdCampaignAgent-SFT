#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 请不要修改 NTFY_TOPIC
NTFY_TOPIC="chaoyu_runpod_status"
NTFY_ALERT="chaoyu_runpod_alert"

if [[ -f "${REPO_ROOT}/secrets/wandb.env" ]]; then
  source "${REPO_ROOT}/secrets/wandb.env"
fi

# ─── ntfy helper ─────────────────────────────────────────────
notify() {
  local title="$1" body="$2" priority="${3:-default}" tags="${4:-}"
  curl -s \
    -H "Title: ${title}" \
    -H "Priority: ${priority}" \
    ${tags:+-H "Tags: ${tags}"} \
    -d "${body}" \
    "ntfy.sh/${NTFY_TOPIC}" || true
}

trap 'notify "❌ Pipeline 异常中断" "脚本在 $(date) 非正常退出，请检查日志" "urgent" "warning"' ERR

# ─── 数据路径 ─────────────────────────────────────────────────
SFT_TRAIN="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260403_222022_zh_train.json"
SFT_TEST="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260403_222022_zh_test.json"

MULTI_TRAIN="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260403_222022_zh_train_multiturn.json"
MULTI_TEST="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260403_222022_zh_test_multiturn.json"

# ─── 模型路径 ─────────────────────────────────────────────────
BASE_MODEL="${REPO_ROOT}/models/Qwen3-1.7B"

# ═════════════════════════════════════════════════════════════
# 步骤 1: 训练 nonmulti_all（完整对话 + all assistant loss）
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 1: 训练 nonmulti_all"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

EXPERIMENT="nonmulti_all" \
ONLY_LAST_ASSISTANT="false" \
TRAIN_FILE="${SFT_TRAIN}" \
EVAL_FILE="${SFT_TEST}" \
MODEL_PATH="${BASE_MODEL}" \
LEARNING_RATE="2e-4" \
NUM_TRAIN_EPOCHS="3" \
EVAL_STEPS="50" \
SAVE_STEPS="50" \
EARLY_STOPPING_PATIENCE="5" \
  bash "${SCRIPT_DIR}/train_model.sh"

echo "  ✅ nonmulti_all 训练完成"
notify "步骤1完成 ✅" "nonmulti_all 训练完成\n$(date '+%Y-%m-%d %H:%M:%S')" "default" "white_check_mark"

# ═════════════════════════════════════════════════════════════
# 步骤 2: 训练 multi_last（切分对话 + last assistant loss）
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 2: 训练 multi_last"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

EXPERIMENT="multi_last" \
ONLY_LAST_ASSISTANT="true" \
TRAIN_FILE="${MULTI_TRAIN}" \
EVAL_FILE="${MULTI_TEST}" \
MODEL_PATH="${BASE_MODEL}" \
LEARNING_RATE="2e-5" \
NUM_TRAIN_EPOCHS="2" \
EVAL_STEPS="50" \
SAVE_STEPS="50" \
EARLY_STOPPING_PATIENCE="5" \
  bash "${SCRIPT_DIR}/train_model.sh"

echo "  ✅ multi_last 训练完成"
notify "步骤2完成 ✅" "multi_last 训练完成\n$(date '+%Y-%m-%d %H:%M:%S')" "default" "white_check_mark"

# ═════════════════════════════════════════════════════════════
# 步骤 3: Merge nonmulti_all
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 3: Merge nonmulti_all LoRA"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

BASE_MODEL="${BASE_MODEL}" \
ADAPTER_PATH="${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_all" \
OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B_nonmulti_all_merged" \
  bash "${SCRIPT_DIR}/merge_lora_into_base.sh"

echo "  ✅ nonmulti_all merge 完成"
notify "步骤3完成 ✅" "nonmulti_all merge 完成\n$(date '+%Y-%m-%d %H:%M:%S')"

# ═════════════════════════════════════════════════════════════
# 步骤 4: Merge multi_last
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 4: Merge multi_last LoRA"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

BASE_MODEL="${BASE_MODEL}" \
ADAPTER_PATH="${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_last" \
OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B_multi_last_merged" \
  bash "${SCRIPT_DIR}/merge_lora_into_base.sh"

echo "  ✅ multi_last merge 完成"
notify "步骤4完成 ✅" "multi_last merge 完成\n$(date '+%Y-%m-%d %H:%M:%S')"

# ═════════════════════════════════════════════════════════════
# 步骤 5: Benchmark nonmulti_all
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 5: Benchmark nonmulti_all"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

MODEL="${REPO_ROOT}/models/Qwen3-1.7B_nonmulti_all_merged" \
RUN_NAME="nonmulti_all" \
  bash "${SCRIPT_DIR}/benchmark.sh"

echo "  ✅ nonmulti_all benchmark 完成"
notify "步骤5完成 ✅" "nonmulti_all benchmark 完成\n$(date '+%Y-%m-%d %H:%M:%S')"

# ═════════════════════════════════════════════════════════════
# 步骤 6: Benchmark multi_last
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 6: Benchmark multi_last"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

MODEL="${REPO_ROOT}/models/Qwen3-1.7B_multi_last_merged" \
RUN_NAME="multi_last" \
  bash "${SCRIPT_DIR}/benchmark.sh"

echo "  ✅ multi_last benchmark 完成"
notify "步骤6完成 ✅" "multi_last benchmark 完成\n$(date '+%Y-%m-%d %H:%M:%S')"

# ═════════════════════════════════════════════════════════════
# 完成
# ═════════════════════════════════════════════════════════════
FINISH_TIME="$(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "============================================"
echo "  全部任务完成 — ${FINISH_TIME}"
echo "============================================"

notify "全部完成 🎉" "Qwen3-1.7B Pipeline 完成！\n完成时间: ${FINISH_TIME}\n结果:\n  · nonmulti_all benchmark 完成\n  · multi_last benchmark 完成" "high" "white_check_mark,rocket"
