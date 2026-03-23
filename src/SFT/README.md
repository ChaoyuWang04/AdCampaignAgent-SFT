# SFT

This folder contains supervised fine-tuning scripts for Qwen-based AdCampaign agents.

## Files

- `train_qwen_functioncall_sft.py`: generic function-calling SFT script with assistant-only loss masking and optional QLoRA
- `train_qwen_lora.py`: standard LoRA fine-tuning script over the full assistant response spans
- `train_qwen_last_assistant_lora.py`: LoRA training variant that only applies loss to the final assistant turn
- `train_qwen_full_finetune_last_assistant.py`: full-parameter fine-tuning variant that only supervises the last assistant turn
- `merge_lora_into_base.py`: merges a trained LoRA adapter into the base model and saves a standalone merged checkpoint

## Where to look

- If you are comparing training strategies, this folder is the place to start
- If you need last-turn-only supervision, use the `last_assistant` scripts
- If you need a merged deployment checkpoint after LoRA training, use `merge_lora_into_base.py`

## Notes

- These scripts depend on dataset helpers in `src/tools/4data/inspect_qwen_dataset.py`
- Default model and dataset paths are examples and should be replaced with local paths before training
