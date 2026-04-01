set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

NTFY_TOPIC="chaoyu_runpod_status"
NTFY_ALERT="chaoyu_runpod_alert"

if [[ -f "${REPO_ROOT}/secrets/wandb.env" ]]; then
  source "${REPO_ROOT}/secrets/wandb.env"
fi

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

SFT_TRAIN="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_train.json"
SFT_TEST="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_test.json"
MULTI_TRAIN="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_train_multiturn.json"
MULTI_TEST="${REPO_ROOT}/data/ready2train/ad_agent_sft_20260330_205257_zh_test_multiturn.json"

# ═════════════════════════════════════════════════════════════
# 步骤 4: Benchmark 两组 Qwen3-0.6B
# ═════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 4: Benchmark Qwen3-0.6B"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"


merged_model="${REPO_ROOT}/models/Qwen3-0.6B"

MODEL="${merged_model}" \
RUN_NAME="${exp}" \
  bash "${SCRIPT_DIR}/benchmark.sh"

echo "  ✅ Benchmark 完成: ${exp}"
notify "Benchmark完成 ✅" "${exp} benchmark 完成\n$(date '+%Y-%m-%d %H:%M:%S')"


FINISH_TIME="$(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "============================================"
echo "# 全部任务完成 — ${FINISH_TIME}"
echo "============================================"

notify "全部完成 🎉" "Qwen3-0.6B Pipeline 完成！\n完成时间: ${FINISH_TIME}\n结果:\n  · 0.6B_nonmulti_all benchmark 完成\n  · 0.6B_multi_last benchmark 完成" "high" "white_check_mark,rocket"