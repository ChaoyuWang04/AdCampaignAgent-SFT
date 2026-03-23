# src

This folder contains the main code for the AdCampaignAgent-SFT project. The code is organized by stage of work instead of keeping every script flat in one place.

## What lives here

- `datapipeline/`: seed generation, dataset conversion, and dataset quality checking
- `SFT/`: Qwen fine-tuning, LoRA training, and adapter merge scripts
- `Infer/`: local inference smoke test for a trained or merged Qwen checkpoint
- `tools/`: helper utilities for dataset inspection, splitting, and model-side smoke tests
- `run_train_full_finetune.sh`: example launcher for full fine-tuning
- `run_train_last_assistant.sh`: example launcher for last-assistant LoRA training

## Where to look

- If you need to generate or convert data, start in `datapipeline/`
- If you need to train or merge checkpoints, go to `SFT/`
- If you need to quickly test a model response, use `Infer/`
- If you need to inspect, split, or sanity-check data and prompts, use `tools/`

## Notes

- The shell scripts in this folder are examples. Update model, dataset, and output paths for your local machine before running them.
- Each subfolder has its own `README.md` with file-level details.
