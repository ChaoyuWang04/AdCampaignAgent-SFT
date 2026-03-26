#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# =========================
# 可直接修改的默认配置
# =========================
# 直接改这里，然后执行：
#   bash scripts/merge_lora_into_base.sh

BASE_MODEL="${REPO_ROOT}/models/Qwen3-1.7B-Base"
ADAPTER_PATH="${REPO_ROOT}/models/你的_lora_adapter目录"
OUTPUT_DIR="${REPO_ROOT}/models/Qwen3-1.7B-merged"

LOCAL_FILES_ONLY="true"
BF16="true"
FP16="false"
DEVICE_MAP_AUTO="true"

usage() {
  cat <<'EOF'
用法：
  直接在脚本顶部填写配置后运行
    bash scripts/merge_lora_into_base.sh

功能：
  将 LoRA adapter 合并进 base model，并输出一个可直接用于 benchmark / inference 的 merged 模型目录。

默认配置项：
  直接修改脚本顶部这些变量即可：
  - BASE_MODEL
  - ADAPTER_PATH
  - OUTPUT_DIR
  - LOCAL_FILES_ONLY
  - BF16
  - FP16
  - DEVICE_MAP_AUTO

说明：
  - 这个脚本不接受命令行参数
  - 合并完成后，benchmark 的 MODEL 应指向 OUTPUT_DIR
  - BF16 和 FP16 不应同时为 true，通常 BF16 优先
  - 如果服务器没有 GPU，DEVICE_MAP_AUTO 可以改成 false
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

if [[ -z "${BASE_MODEL}" || -z "${ADAPTER_PATH}" || -z "${OUTPUT_DIR}" ]]; then
  echo "错误：BASE_MODEL、ADAPTER_PATH、OUTPUT_DIR 不能为空。" >&2
  usage
  exit 1
fi

if [[ "${BF16}" == "true" && "${FP16}" == "true" ]]; then
  echo "错误：BF16 和 FP16 不能同时为 true。" >&2
  exit 1
fi

CMD=(
  uv run python "${REPO_ROOT}/src/train/merge_lora_into_base.py"
  --base_model "${BASE_MODEL}"
  --adapter_path "${ADAPTER_PATH}"
  --output_dir "${OUTPUT_DIR}"
)

if [[ "${LOCAL_FILES_ONLY}" == "true" ]]; then
  CMD+=(--local_files_only)
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

echo "Merge LoRA into base"
echo "Base model        : ${BASE_MODEL}"
echo "Adapter path      : ${ADAPTER_PATH}"
echo "Output dir        : ${OUTPUT_DIR}"
echo "Local files only  : ${LOCAL_FILES_ONLY}"
echo "BF16              : ${BF16}"
echo "FP16              : ${FP16}"
echo "Device map auto   : ${DEVICE_MAP_AUTO}"

"${CMD[@]}"

echo
echo "Merge 完成。后续 benchmark / inference 请将模型目录指向："
echo "- ${OUTPUT_DIR}"
