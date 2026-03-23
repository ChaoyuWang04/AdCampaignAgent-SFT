# 4model

This folder contains model-side utilities and smoke tests for AdCampaign prompts and generated conversations.

## Files

- `llm.py`: unified wrapper for calling several external LLM providers through OpenAI-compatible APIs
- `test_funcall.py`: smoke test for AdCampaign function-calling message generation in OpenAI Messages format
- `test_generate.py`: small-scale seed-generation smoke test built on the AdCampaign data generator
- `test_sequential.py`: validates sequential assistant-tool turns produced by the OpenAI Messages conversion pipeline

## Where to look

- If you need API-based model access, use `llm.py`
- If you want to sanity-check function-calling records, use `test_funcall.py`
- If you want to verify seed generation quickly, use `test_generate.py`
- If you want to check assistant/tool turn ordering, use `test_sequential.py`
