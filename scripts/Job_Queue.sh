#!/usr/bin/env bash
# Round 2 SFT Pipeline — Job Queue
# 步骤1: 生成数据 → 步骤2: 训练R2 → 步骤3: 合并R2 → 步骤4: Benchmark
# （Round 1 模型已 merge，无需重复合并）
# 用法: bash scripts/Job_Queue.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

NTFY_TOPIC="chaoyu-runpod-abc123"
NTFY_ALERT="chaoyu-runpod-alert"

#load_wandb_api
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

# ─── Error trap ──────────────────────────────────────────────
trap 'echo ""; echo "❌ 脚本在 $(date) 异常退出"; \
  curl -s \
    -H "Title: ❌ Round-2 Pipeline 异常中断" \
    -H "Priority: urgent" \
    -H "Tags: warning" \
    -d "脚本在 $(date) 非正常退出，请检查日志" \
    "ntfy.sh/${NTFY_ALERT}" || true' ERR

R2_EXPERIMENTS=("nonmulti_all" "nonmulti_last" "multi_all" "multi_last")

# ─────────────────────────────────────────────────────────────
# 步骤 1: 生成 Round 2 训练数据
# ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 1: 生成 Round 2 训练数据"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"
echo ""

python3 "${REPO_ROOT}/src/datapipeline/round2_data_generator.py"

echo ""
echo "✅ 步骤1完成 — $(date '+%Y-%m-%d %H:%M:%S')"
notify "步骤1完成 ✅" "Round-2 数据生成完成
已写入 data/continue/ 目录
$(date '+%Y-%m-%d %H:%M:%S')"

# ─────────────────────────────────────────────────────────────
# 步骤 3: 依次训练 4 组 Round 2 模型（串行）
# ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 3: 训练 Round 2 模型（串行）"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"

for exp in "${R2_EXPERIMENTS[@]}"; do
  echo ""
  echo "############################################"
  echo "# 开始 Round 2 训练：${exp}"
  echo "# $(date '+%Y-%m-%d %H:%M:%S')"
  echo "############################################"
  echo ""

  EXPERIMENT="${exp}" bash "${SCRIPT_DIR}/run_train_r2.sh"

  echo ""
  echo "✅ Round 2 训练完成：${exp} — $(date '+%Y-%m-%d %H:%M:%S')"
  notify "训练完成: ${exp} ✅" "Round-2 模型 ${exp} 训练完成
输出: models/Qwen3-1.7B_r2_${exp}
$(date '+%Y-%m-%d %H:%M:%S')"
done

echo ""
echo "✅ 步骤3完成 — $(date '+%Y-%m-%d %H:%M:%S')"
notify "步骤3完成 ✅" "4个 Round-2 模型全部训练完成
$(date '+%Y-%m-%d %H:%M:%S')"

# ─────────────────────────────────────────────────────────────
# 步骤 4: 合并 Round 2 LoRA Adapter（如已存在则跳过）
# ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 4: 合并 Round 2 LoRA Adapter"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"
echo ""

for exp in "${R2_EXPERIMENTS[@]}"; do
  r2_merged="${REPO_ROOT}/models/Qwen3-1.7B_r2_${exp}-merged"
  if [[ -d "${r2_merged}" ]]; then
    echo "  已存在，跳过: $(basename ${r2_merged})"
    continue
  fi

  # Round 2 base = Round 1 merged model (实际存放路径，无 -merged 后缀)
  case "${exp}" in
    nonmulti_all)  r1_merged="${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_all"  ;;
    nonmulti_last) r1_merged="${REPO_ROOT}/models/Qwen3-1.7B_lora_nonmulti_last" ;;
    multi_all)     r1_merged="${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_all"     ;;
    multi_last)    r1_merged="${REPO_ROOT}/models/Qwen3-1.7B_lora_multi_last"    ;;
  esac

  r2_adapter="${REPO_ROOT}/models/Qwen3-1.7B_r2_${exp}"

  echo "  正在合并 R2 Adapter: ${exp}"
  BASE_MODEL="${r1_merged}" \
  ADAPTER_PATH="${r2_adapter}" \
  OUTPUT_DIR="${r2_merged}" \
    bash "${SCRIPT_DIR}/merge_lora_into_base.sh"
  echo "  ✅ 合并完成: ${exp}"
done

echo ""
echo "✅ 步骤4完成 — $(date '+%Y-%m-%d %H:%M:%S')"
notify "步骤4完成 ✅" "Round-2 Adapter 合并完成
$(date '+%Y-%m-%d %H:%M:%S')"

# ─────────────────────────────────────────────────────────────
# 步骤 5: 跑全部 Round 2 Benchmark
# ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  步骤 5: 运行 Round 2 Benchmark"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════"
echo ""

MODEL_PATTERN="Qwen3-1.7B_r2_*-merged" \
  bash "${SCRIPT_DIR}/run_benchmark_r2.sh"

FINISH_TIME="$(date '+%Y-%m-%d %H:%M:%S')"

echo ""
echo "============================================"
echo "# Round 2 全部任务完成 — ${FINISH_TIME}"
echo "============================================"

notify "步骤5完成 🎉" "Round-2 全部任务完成！
完成时间: ${FINISH_TIME}
4个模型已训练、合并并完成 Benchmark:
  · r2_nonmulti_all-merged
  · r2_nonmulti_last-merged
  · r2_multi_all-merged
  · r2_multi_last-merged
结果在 tests/benchmark/results/r2_*/" "high" "white_check_mark,rocket"
