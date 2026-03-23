# datapipeline

This folder contains the end-to-end data pipeline for AdCampaignAgent-SFT: seed generation, conversation conversion, and dataset quality reporting.

## Files

- `1_ad_gen_data.py`: generates bilingual seed records for seven AdCampaign workflows, including context, baselines, scene tags, tool chains, clarification cases, and refusals
- `2_convert_data_message.py`: converts seed records into OpenAI Messages format with tool calls and tool results
- `2_convert_dataset_sharegpt.py`: converts the same seed records into ShareGPT format for training frameworks that expect `conversations`
- `3_dataquality_check.py`: auto-detects dataset format, normalizes it, computes statistics, renders figures, and writes `dataset_card.md` into `checker/`

## Where to look

- If you want the raw synthetic business scenarios, start with `1_ad_gen_data.py`
- If you want OpenAI-style training data, use `2_convert_data_message.py`
- If you want ShareGPT-style training data, use `2_convert_dataset_sharegpt.py`
- If you want charts, validation summaries, or a dataset card, use `3_dataquality_check.py`
