# Infer

This folder contains lightweight inference-side smoke tests for trained AdCampaign checkpoints.

## Files

- `test_qwen_infer.py`: loads a local Qwen checkpoint, builds a sample AdCampaign chat prompt, optionally injects tool schemas, prints the rendered template, and runs generation

## Where to look

- Use this folder when you want a quick manual sanity check after training or after merging a LoRA adapter
- If you need to inspect how the chat template expands before generation, `test_qwen_infer.py` is the right entry point

## Notes

- The default model path is only an example
- Pass your own local model path and optional tool schema file when running it
