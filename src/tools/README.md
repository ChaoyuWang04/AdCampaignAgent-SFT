# `src/tools`

该目录现在承载的是 Ad Campaign Agent 的运行时工具实现，不再是旅行助手工具。

## 设计原则

- `all_tools.json` 只保存 function-calling schema，且采用最小必需参数。
- 每个工具单独一个 Python 文件，文件名与工具名一致，便于按工具追踪和替换。
- 非 RAG 工具优先支持真实 `OpenAI API` 调用。
  - 读取环境变量：`OPENAI_API_KEY`
  - 可选覆盖：`OPENAI_BASE_URL`、`OPENAI_MODEL`
  - 模型输出会先做 JSON 解析；解析失败或未配置 key 时自动 fallback 到预置结果。
- RAG 工具只走本地 `rag-system` 查询，不走 OpenAI。
  - 读取环境变量：`RAG_API_URL`
  - 默认地址：`http://127.0.0.1:8010`
  - 查询失败时自动 fallback 到预置结果。
- 公共逻辑集中在 [src/tools/_shared.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/tools/_shared.py)，包括：
  - OpenAI 调用
  - JSON 片段提取与解析
  - RAG `/search` 接口调用
  - RAG 结果归一化

## 工具清单

### 非 RAG 工具

- `search_trending_creatives`
  - 最小参数：`platform`、`game_genre`
- `search_competitor_ads`
  - 最小参数：`competitor_name`、`platform`
- `get_trending_hooks`
  - 最小参数：`game_genre`
- `validate_creative_spec`
  - 最小参数：`file_path`、`platform`
- `upload_creative_asset`
  - 最小参数：`file_path`、`campaign_id`
- `batch_upload_creatives`
  - 最小参数：`file_paths`、`campaign_id`
- `get_campaign_metrics`
  - 最小参数：`campaign_id`
- `get_creative_performance`
  - 最小参数：`campaign_id`
- `get_appsflyer_report`
  - 最小参数：`app_id`
- `compare_campaigns`
  - 最小参数：`campaign_ids`
- `detect_anomalies`
  - 最小参数：`campaign_id`
- `get_optimization_playbook`
  - 最小参数：`issue_type`

### RAG 工具

- `query_knowledge_base`
  - 最小参数：`question`
- `get_benchmark_data`
  - 最小参数：`metric`、`game_genre`
- `get_platform_policy`
  - 最小参数：`platform`、`policy_type`

## 实际调用方式

### 1. Python 直接调用

```python
from src.tools import get_campaign_metrics, query_knowledge_base

metrics = get_campaign_metrics(campaign_id="CMP_1024")
knowledge = query_knowledge_base(question="tROAS 和 tCPA 的区别是什么？")
```

### 2. 通过 `all_tools.json` 给模型注册 function tools

```python
import json
from pathlib import Path

tools = json.loads(Path("src/tools/all_tools.json").read_text(encoding="utf-8"))
```

### 3. 非 RAG 工具的真实调用条件

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

未配置 `OPENAI_API_KEY` 时，非 RAG 工具会直接返回内置 fallback 结果。

### 4. RAG 工具的真实调用条件

```bash
export RAG_API_URL="http://127.0.0.1:8010"
```

`query_knowledge_base`、`get_benchmark_data`、`get_platform_policy` 会调用：

- `POST /search`

当前仓库里的 `rag-system` 仍是通用/旧版搜索接口，因此这里的广告知识查询是通过拼接广告语义查询词来做封装；如果未来有广告域专用索引或专用 API，可以只替换对应工具文件，不需要改 schema。

## 与数据流水线的对应关系

- 工具名来源：[src/datapipeline/generate_base_dataset.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/generate_base_dataset.py)
- 参数样例来源：[src/datapipeline/convert_dataset.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/convert_dataset.py)
- 本次 `all_tools.json` 采用“最小必需参数”策略，不强制暴露转换脚本中的全部可选参数。
