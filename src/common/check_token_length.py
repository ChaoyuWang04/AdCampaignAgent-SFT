from transformers import AutoTokenizer
import json

tok = AutoTokenizer.from_pretrained('models/Qwen3-1.7B', trust_remote_code=True)

with open('src/tools/all_tools.json') as f:
    tools = json.load(f)

with open('data/ready2train/message/ad_agent_sft_20260326_181224_zh_train_message.json') as f:
    data = json.load(f)

lengths = []
for d in data:
    result = tok.apply_chat_template(d['messages'], tools=tools, tokenize=True)
    ids = result['input_ids']
    if isinstance(ids[0], list):
        ids = ids[0]
    lengths.append(len(ids))

lengths.sort()
n = len(lengths)
print(f'count={n}')
print(f'min={lengths[0]}')
print(f'mean={sum(lengths)//n}')
print(f'p75={lengths[int(n*0.75)]}')
print(f'p90={lengths[int(n*0.90)]}')
print(f'p95={lengths[int(n*0.95)]}')
print(f'p99={lengths[int(n*0.99)]}')
print(f'max={lengths[-1]}')