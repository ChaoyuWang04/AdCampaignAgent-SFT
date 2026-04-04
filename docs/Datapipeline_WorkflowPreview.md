# AdCampaignAgent 当前 Workflow 预览

本文档不再复述某一批历史 seed 文件的快照，而是直接描述**当前 7 个 YAML + datapipeline 实现**实际定义的 workflow 结构。  
如果你在改 YAML，请优先看这份文档和 [Datapipeline YAML 维护规范](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/docs/Datapipeline_YAML_Maintenance.md)。

## 总览

| ID | Workflow | 主要目标 | 当前是否会追问 | 是否调用工具 |
|---|---|---|---|---|
| 1 | 素材搜寻 | 搜热门素材、竞品广告、热门 hooks | 是 | 是 |
| 2 | 素材上传 | 校验素材规格并上传 | 是，但占比很低 | 是 |
| 3 | 单指标效果查询 | 查询单类投放指标 | 是 | 是 |
| 4 | 多维深度分析 | 做跨源深度分析与 benchmark 对比 | 是，且 clarify 占比最高 | 是 |
| 5 | 异常诊断与优化 | 做异常定位并输出 playbook | 否 | 是 |
| 6 | 知识问答 | 回答投放知识、政策、benchmark 问题 | 是，但只在部分 bucket | 是 |
| 7 | 拒答 | 对域外问题和未授权请求拒答 | 否 | 否 |

## Workflow 1：素材搜寻

### 当前 bucket

- `competitor_ads`
- `trending_creatives`
- `trending_with_hooks`
- `creative_search_clarify`（clarify-only）

### 当前工具链

- `search_competitor_ads`
- `search_trending_creatives`
- `search_trending_creatives -> get_trending_hooks`

### 当前注意点

- `trending_with_hooks` 是 workflow 1 唯一稳定的多工具链
- `platform` / `genre` 缺失会转 clarify-only，不会在补充后继续执行工具

## Workflow 2：素材上传

### 当前 bucket

- `single_upload`
- `batch_upload`
- `validate_only_retry`

### 当前 scene_tag

- `single_upload_success`
- `single_upload_partial_fail`
- `batch_upload_success`
- `batch_upload_partial_fail`
- `validate_fail_size`
- `validate_fail_format`

### 当前工具链

- `validate_creative_spec -> upload_creative_asset`
- `validate_creative_spec -> batch_upload_creatives`
- `validate_creative_spec`

### 当前注意点

- 上传前校验是硬约束，不允许跳过
- `batch_upload` 里缺 `campaign_id` 的模板会转 clarify-only

## Workflow 3：单指标效果查询

### 当前 bucket

- `campaign_metrics`
- `creative_metrics`
- `appsflyer_report`
- `clarify_missing_campaign`（clarify-only）

### 当前工具链

- `get_campaign_metrics`
- `get_creative_performance`
- `get_appsflyer_report`

### 当前注意点

- `appsflyer_report` 现在已经全部按 `app_id` 驱动，不再混入 `campaign_id` 模板
- clarify_probability 仍然统一落到 `campaign_id_missing` 这条 clarify-only 路径

## Workflow 4：多维深度分析

### 当前 scene_tag

- `healthy`
- `roas_warning`
- `roas_danger`
- `ret_warning`
- `ret_danger`
- `both_warning`
- `both_danger`
- `creative_fatigue`
- `budget_underdelivery`
- `insufficient_data`
- `clarify_missing_scope`（clarify-only）

### 当前 intent bucket

- `holistic_campaign_analysis`
- `retention_diagnosis`
- `combined_diagnosis`
- `creative_diagnosis`
- `clarify_missing_scope`

### 当前工具链

- `parallel(get_campaign_metrics, get_creative_performance, get_benchmark_data)`
- `parallel(get_appsflyer_report, get_campaign_metrics) -> get_benchmark_data`
- `parallel(get_campaign_metrics, get_appsflyer_report, get_creative_performance) -> get_benchmark_data`

### 当前注意点

- workflow 4 是当前最大的 clarify 来源
- ambiguous query 会直接进入 `clarify_missing_scope`
- scene query 主要因为缺 `date_range` 转 clarify

## Workflow 5：异常诊断与优化

### 当前 scene_tag

- `roas_danger`
- `ret_danger`
- `both_danger`
- `creative_fatigue`
- `budget_underdelivery`

### 当前工具链

- `detect_anomalies -> get_campaign_metrics -> get_optimization_playbook`
- `detect_anomalies -> get_appsflyer_report -> get_optimization_playbook`
- `detect_anomalies -> get_creative_performance -> get_optimization_playbook`

### 当前注意点

- `ret_danger` 已经不再走 `get_campaign_metrics`
- workflow 5 的 tool_plan 现在统一是“单个 serial group + 多工具”，不再拆成 3 个单工具 group

## Workflow 6：知识问答

### 当前 bucket

- `bidding_strategy`
- `creative_guideline`
- `platform_policy`
- `industry_benchmark`

### 当前工具链

- `query_knowledge_base`
- `get_platform_policy`
- `get_benchmark_data`

### 当前注意点

- `platform_policy` 现在同时包含：
  - 带平台名的 direct query
  - 缺平台的 clarify-only query
- 3 条平台规格类 query 已从 `creative_guideline` 迁入 `platform_policy`
- `industry_benchmark` 当前少量 query 可 direct，多数 query 会转 clarify-only

## Workflow 7：拒答

### 当前 refusal_type

- `off_topic`
- `unauthorized_internal`
- `unauthorized_external`

### 当前结束方式

- 固定为 `system -> user -> assistant(refusal)`
- 不走工具
- 不走 clarify

### 当前注意点

- `unauthorized_internal` 用于内部高风险越权操作
- `unauthorized_external` 用于竞品数据抓取、未授权访问、外部违规请求
- 不要再把两类请求混到一个 refusal_type 里

## 当前维护建议

1. 需要改静态覆盖、bucket 权重、clarify 占比时，优先更新 YAML，再同步 [Datapipeline_Seed.md](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/docs/Datapipeline_Seed.md)。
2. 需要改 scene 与 tool 的绑定关系时，先看是否属于“同 intent 下的表现差异”；如果是，优先改 `scene_tag`，不要贸然新开 workflow。
3. 如果希望“追问后继续调工具”，这不是改 YAML 能做到的，需要同时改 seed 生成和 convert 逻辑。
