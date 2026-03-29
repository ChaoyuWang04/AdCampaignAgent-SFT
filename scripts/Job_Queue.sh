#!/usr/bin/env bash
# 这是一个不会被服用的任务队列脚本,请依据我给出要跑的任务完全的依据需求改写这个脚本, 同时更新训练完成的通知内容.

# ntfy通知我,如果脚本执行有错误(请依据实际任务进行通知内容的修改)
trap 'curl -s -H "Title: ❌ Benchmark 异常中断" \
  -H "Priority: urgent" -H "Tags: warning" \
  -d "脚本在 $(date) 非正常退出，请检查日志" \
  ntfy.sh/chaoyu-runpod-alert' ERR

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



#ntfy训练通知(请依据实际任务进行通知内容的修改):
FINISH_TIME="$(date '+%Y-%m-%d %H:%M:%S')"
curl -s \
  -H "Title: Benchmark 全部完成 🎉" \
  -H "Priority: high" \
  -H "Tags: white_check_mark,rocket" \
  -d "RunPod 任务结束：${FINISH_TIME}
跑完了 4 个实验：
  · multi_all
  · multi_last
  · nonmulti_all
  · nonmulti_last
去看结果吧 👀" \
  ntfy.sh/chaoyu-runpod-alert
