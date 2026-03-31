set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

#请不要修改NTFY_TOPIC
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
SFT_TRAIN="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_train.json"
SFT_TEST="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_test.json"

MULTI_TRAIN="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_train_multiturn.json"
MULTI_TEST="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_test_multiturn.json"

# ═════════════════════════════════════════════════════════════
# 步骤 3: 训练 nonmulti_all（完整对话 + all_assistant）
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 3: 训练 nonmulti_all"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

EXPERIMENT="nonmulti_all" \
ONLY_LAST_ASSISTANT="false" \
TRAIN_FILE="${SFT_TRAIN}" \
EVAL_FILE="${SFT_TEST}" \
LEARNING_RATE="2e-4" \
NUM_TRAIN_EPOCHS="3" \
EVAL_STEPS="50" \
SAVE_STEPS="50" \
EARLY_STOPPING_PATIENCE="3" \
  bash "${SCRIPT_DIR}/train_model.sh"

echo "✅ 步骤3完成 — $(date '+%Y-%m-%d %H:%M:%S')"
notify "步骤3完成 ✅" "nonmulti_all 训练完成\n$(date '+%Y-%m-%d %H:%M:%S')"

# ═════════════════════════════════════════════════════════════
# 步骤 4: 训练 multi_last（multiturn拆解 + last_assistant_only）
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 4: 训练 multi_last"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

EXPERIMENT="multi_last" \
ONLY_LAST_ASSISTANT="true" \
TRAIN_FILE="${MULTI_TRAIN}" \
EVAL_FILE="${MULTI_TEST}" \
LEARNING_RATE="2e-5" \
NUM_TRAIN_EPOCHS="2" \
EVAL_STEPS="100" \
SAVE_STEPS="100" \
EARLY_STOPPING_PATIENCE="3" \
  bash "${SCRIPT_DIR}/train_model.sh"

echo "✅ 步骤4完成 — $(date '+%Y-%m-%d %H:%M:%S')"
notify "步骤4完成 ✅" "multi_last 训练完成\n$(date '+%Y-%m-%d %H:%M:%S')"

# ═════════════════════════════════════════════════════════════
# 步骤 5: 合并 LoRA Adapter
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 5: 合并 LoRA Adapter"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

for exp in "nonmulti_all" "multi_last"; do
  merged_dir="${REPO_ROOT}/models/Qwen3-1.7B_lora_${exp}_merged"
  if [[ -d "${merged_dir}" ]]; then
    echo "  已存在，跳过: $(basename ${merged_dir})"
    continue
  fi

  BASE_MODEL="${REPO_ROOT}/models/Qwen3-1.7B" \
  ADAPTER_PATH="${REPO_ROOT}/models/Qwen3-1.7B_lora_${exp}" \
  OUTPUT_DIR="${merged_dir}" \
    bash "${SCRIPT_DIR}/merge_lora_into_base.sh"

  echo "  ✅ 合并完成: ${exp}"
done

echo "✅ 步骤5完成 — $(date '+%Y-%m-%d %H:%M:%S')"
notify "步骤5完成 ✅" "LoRA 合并完成\n$(date '+%Y-%m-%d %H:%M:%S')"

# ═════════════════════════════════════════════════════════════
# 步骤 6: Benchmark
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 6: 运行 Benchmark"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

for exp in "nonmulti_all" "multi_last"; do
  merged_model="${REPO_ROOT}/models/Qwen3-1.7B_lora_${exp}_merged"
  echo ""
  echo "  开始 Benchmark: ${exp}"
  echo "  模型路径: ${merged_model}"

  MODEL="${merged_model}" \
  RUN_NAME="${exp}" \
    bash "${SCRIPT_DIR}/benchmark.sh"

  echo "  ✅ Benchmark 完成: ${exp}"
  notify "Benchmark完成 ✅" "${exp} benchmark 完成\n$(date '+%Y-%m-%d %H:%M:%S')"
done

FINISH_TIME="$(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "============================================"
echo "# 全部任务完成 — ${FINISH_TIME}"
echo "============================================"

notify "全部完成 🎉" "Pipeline 完成！\n完成时间: ${FINISH_TIME}\n实验结果:\n  · nonmulti_all_merged benchmark 完成\n  · multi_last_merged benchmark 完成" "high" "white_check_mark,rocket"
