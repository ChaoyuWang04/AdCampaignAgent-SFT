# 4data

This folder contains data-preparation helper scripts used around training and debugging.

## Files

- `inspect_qwen_dataset.py`: visualizes tokenized training samples, assistant-only loss masks, decoded spans, and optional tool injection for Qwen datasets
- `conversation_splitter.py`: expands multi-turn conversations into assistant-prefix samples for training experiments that want intermediate stopping points
- `split_dataset.py`: creates train/test splits for AdCampaign datasets while stratifying by workflow and scene

## Where to look

- If you want to inspect masking and tokenization, start with `inspect_qwen_dataset.py`
- If you want to create more prefix-style training samples, use `conversation_splitter.py`
- If you want a train/test split for experiments or evaluation, use `split_dataset.py`
