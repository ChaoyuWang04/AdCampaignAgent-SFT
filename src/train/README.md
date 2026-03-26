# `src/train/` 说明

这个目录的训练脚本主要看 3 件事：

- 训练方式：`LoRA` / `Full Fine-tuning` / `TRL LoRA`
- 监督范围：`所有 assistant 轮次` / `只最后一条 assistant` / `completion-only`
- 任务类型：普通对话 SFT / `Function Calling`

## 脚本总表

| 脚本 | 训练方式 | loss 范围 | 用途 |
|---|---|---|---|
| `train_qwen_lora_all_assistant_turns.py` | LoRA | 所有 assistant 轮次 | 常规多轮 SFT |
| `train_qwen_lora_last_assistant_turn_only.py` | LoRA | 只最后一条 assistant | 训练 agent 最终回复 |
| `train_qwen_full_finetune_last_assistant_turn_only.py` | Full Fine-tuning | 只最后一条 assistant | 和上一个目标相同，但全参数训练 |
| `train_qwen_function_calling_all_assistant_turns.py` | LoRA / 可选 QLoRA | 所有 assistant 轮次 | 训练 Function Calling |
| `train_qwen_trl_lora_function_calling_completion_only.py` | TRL LoRA | completion-only | 用 TRL 做 Function Calling SFT |

## 辅助脚本

| 脚本 | 用途 |
|---|---|
| `inspect_qwen_dataset.py` | 检查模板化结果、token span 和 loss mask |
| `merge_lora_into_base.py` | 把 LoRA adapter 合并回基础模型 |

另外，仓库根目录提供了对应的 shell 包装脚本：

- [merge_lora_into_base.sh](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/scripts/merge_lora_into_base.sh)

推荐直接编辑脚本顶部配置后执行，而不是手动在命令行里拼很长的 Python 参数。

## 快速选择

- 想做最常规的 LoRA 多轮训练：`train_qwen_lora_all_assistant_turns.py`
- 想重点训练最终回答：`train_qwen_lora_last_assistant_turn_only.py`
- 想做同目标的全参训练：`train_qwen_full_finetune_last_assistant_turn_only.py`
- 想强化工具调用能力：`train_qwen_function_calling_all_assistant_turns.py`
- 想使用 TRL 的 completion-only 监督：`train_qwen_trl_lora_function_calling_completion_only.py`
