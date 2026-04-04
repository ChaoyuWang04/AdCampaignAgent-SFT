# AdCampaignAgent Seed 静态覆盖说明

本文档基于当前 [`0_generate_base_dataset.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/0_generate_base_dataset.py) 与 [`workflow/`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/workflow) 下的 7 个 YAML 规则做静态分析，不引用任何历史 `data/raw/*.json` 结果。

## 口径说明

- `总样本量`：按 YAML 中 `count` 直接求和，当前理论总量固定为 `2750`。
- `direct`：不需要先追问、可以直接进入 tool call 或 refusal 的样本。
- `clarify`：因为 `clarify_probability` 或 `required_slots` 缺失而转为追问的样本。
- `refusal`：workflow 7 里的无工具拒答样本。
- `期望条数`：对 bucket 加权采样或 scene 均匀采样后的理论期望值，单次生成不保证完全相等，文中统一用 `≈` 表示。

## 总体结构

| Workflow | 条数 | 占总量 |
|---|---:|---:|
| 素材搜寻 | 360 | 13.09% |
| 素材上传 | 240 | 8.73% |
| 单指标效果查询 | 360 | 13.09% |
| 多维深度分析 | 900 | 32.73% |
| 异常诊断与优化 | 450 | 16.36% |
| 知识问答 | 240 | 8.73% |
| 拒答 | 200 | 7.27% |

当前训练集仍然明显偏分析类任务：

- 深度分析 + 异常诊断合计 `1350` 条，占总量 `49.09%`
- 搜索 + 上传合计 `600` 条，占总量 `21.82%`
- 知识问答 + 拒答合计 `440` 条，占总量 `16.00%`
- 单指标查询 `360` 条，占总量 `13.09%`

## 总体标签分布

按当前 YAML 和生成逻辑静态估算：

- `clarify` 样本总量：`≈965.64`
- 占总量：`≈35.11%`
- `direct` 业务样本：`≈1584.36`
- 占总量：`≈57.61%`
- `refusal` 样本：`200`
- 占总量：`7.27%`

和早期版本相比，当前这一版有 4 个关键变化：

1. `workflow 1 / 3 / 6` 已完全改成 `intent bucket -> tool plan` 绑定，不再随机选 tool。
2. `workflow 4` 的 clarify 已显式区分 `clarify_missing_scope` 与业务 `scene_tag`。
3. `workflow 5` 的 `ret_danger` 已从 campaign metrics 诊断切到 AppsFlyer 诊断。
4. `workflow 7` 已拆成 `off_topic / unauthorized_internal / unauthorized_external` 三类拒答。

## Workflow 1：素材搜寻

### 覆盖范围

- 总量：`360`
- bucket 模板数：
  - `competitor_ads`: `7`
  - `trending_creatives`: `16`
  - `trending_with_hooks`: `8`
- 固定 clarify 概率：`20%`
  - 固定追问样本：`72`

### bucket 分布

| Bucket | 模板数 | bucket 权重 | 模板缺槽位率 | 期望 direct | 期望 clarify |
|---|---:|---:|---:|---:|---:|
| `competitor_ads` | 7 | 22.58% | 28.57% | ≈46.45 | ≈18.58 |
| `trending_creatives` | 16 | 51.61% | 37.50% | ≈92.90 | ≈55.74 |
| `trending_with_hooks` | 8 | 25.81% | 0% | ≈74.32 | 0 |
| `clarify_probability` 直接追问 | - | - | - | - | 72 |

合计：

- direct `≈213.68`
- clarify `≈146.32`

### 工具链覆盖

- `competitor_ads` -> `search_competitor_ads`
- `trending_creatives` -> `search_trending_creatives`
- `trending_with_hooks` -> `search_trending_creatives -> get_trending_hooks`

### 设计解读

- 正向能力：热门素材、竞品广告、热门钩子
- 边界能力：主要体现为 `platform_missing` / `platform_or_genre_missing`
- 并行工具：没有
- 串行工具：有，但只在 `trending_with_hooks`

## Workflow 2：素材上传

### 覆盖范围

- 总量：`240`
- `fail_probability = 0.25`
  - `validate_only_retry` 期望：`60`
- 成功路径总量：`180`

### bucket 分布

| Bucket | 模板数 | 成功路径内占比 | 模板缺槽位率 | 期望 direct | 期望 clarify |
|---|---:|---:|---:|---:|---:|
| `single_upload` | 5 | 26.32% | 0% | ≈47.37 | 0 |
| `batch_upload` | 14 | 73.68% | 7.14% | ≈123.16 | ≈9.47 |
| `validate_only_retry` | - | - | - | 60 | 0 |

合计：

- direct `≈230.53`
- clarify `≈9.47`

### 工具链覆盖

- `single_upload` -> `validate_creative_spec -> upload_creative_asset`
- `batch_upload` -> `validate_creative_spec -> batch_upload_creatives`
- `validate_only_retry` -> `validate_creative_spec`

### 设计解读

- 正向能力：单传、批传、上传前校验
- 边界能力：校验失败和缺 `campaign_id` 的追问
- 并行工具：没有
- 串行工具：强，且上传前校验为硬约束

## Workflow 3：单指标效果查询

### 覆盖范围

- 总量：`360`
- 固定 clarify 概率：`20%`
  - 固定追问样本：`72`
- bucket 模板数：
  - `campaign_metrics`: `28`
  - `creative_metrics`: `6`
  - `appsflyer_report`: `6`

### bucket 分布

| Bucket | 模板数 | bucket 权重 | 模板缺槽位率 | 期望 direct | 期望 clarify |
|---|---:|---:|---:|---:|---:|
| `campaign_metrics` | 28 | 70.00% | 0% | ≈201.60 | 0 |
| `creative_metrics` | 6 | 15.00% | 0% | ≈43.20 | 0 |
| `appsflyer_report` | 6 | 15.00% | 0% | ≈43.20 | 0 |
| `clarify_probability` 直接追问 | - | - | - | - | 72 |

合计：

- direct `288`
- clarify `72`

### scene 覆盖

- `campaign_metrics`
  - 继续通过 [`infer_metric_scene()`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/0_generate_base_dataset.py) 映射到 `query_roas / query_retention / query_ctr / query_spend / query_installs / query_cpm`
- `creative_metrics`
  - 固定 `creative_metrics`
- `appsflyer_report`
  - 固定 `appsflyer_report`
- clarify
  - 固定 `clarify_missing_campaign`

### 工具链覆盖

- `campaign_metrics` -> `get_campaign_metrics`
- `creative_metrics` -> `get_creative_performance`
- `appsflyer_report` -> `get_appsflyer_report`

### 设计解读

- 正向能力：campaign 聚合拉数、创意维度表现、AppsFlyer 单报表查询
- 边界能力：主要体现为 `campaign_id_missing`
- 并行工具：没有
- 串行工具：本质上都是单工具调用

## Workflow 4：多维深度分析

### 覆盖范围

- 总量：`900`
- 固定 ambiguous clarify 概率：`15%`
  - `clarify_missing_scope` 期望：`135`
- 其余 `765` 条 direct 路径按 `10` 个 scene 均匀采样，每个 scene 的 direct 入口基数为 `76.5`

### scene 分布

| Scene | intent_bucket | 模板缺槽位率 | 期望 direct | 来自 ambiguous 的 clarify | 来自 scene 缺槽位的 clarify |
|---|---|---:|---:|---:|---:|
| `healthy` | `holistic_campaign_analysis` | 40% | ≈45.90 | 13.50 | ≈30.60 |
| `roas_warning` | `holistic_campaign_analysis` | 60% | ≈30.60 | 13.50 | ≈45.90 |
| `roas_danger` | `holistic_campaign_analysis` | 80% | ≈15.30 | 13.50 | ≈61.20 |
| `ret_warning` | `retention_diagnosis` | 90% | ≈7.65 | 13.50 | ≈68.85 |
| `ret_danger` | `retention_diagnosis` | 80% | ≈15.30 | 13.50 | ≈61.20 |
| `both_warning` | `combined_diagnosis` | 70% | ≈22.95 | 13.50 | ≈53.55 |
| `both_danger` | `combined_diagnosis` | 90% | ≈7.65 | 13.50 | ≈68.85 |
| `creative_fatigue` | `creative_diagnosis` | 70% | ≈22.95 | 13.50 | ≈53.55 |
| `budget_underdelivery` | `holistic_campaign_analysis` | 50% | ≈38.25 | 13.50 | ≈38.25 |
| `insufficient_data` | `holistic_campaign_analysis` | 60% | ≈30.60 | 13.50 | ≈45.90 |

合计：

- direct `≈237.15`
- clarify `≈662.85`

### 工具链覆盖

- `healthy / roas_warning / roas_danger / creative_fatigue / budget_underdelivery / insufficient_data`
  - `get_campaign_metrics + get_creative_performance + get_benchmark_data`
- `ret_warning`
  - `get_appsflyer_report + get_campaign_metrics -> get_benchmark_data`
- `ret_danger / both_warning / both_danger`
  - `get_campaign_metrics + get_appsflyer_report + get_creative_performance -> get_benchmark_data`

### 设计解读

- 正向能力：完整分析、跨源诊断、benchmark 对比
- 边界能力：主要体现为 `timerange_missing` 和 `campaign_id_and_timerange_missing`
- 并行工具：有，是当前主力并行样本来源
- 串行工具：有，表现为“并行取数后串行 benchmark”

## Workflow 5：异常诊断与优化

### 覆盖范围

- 总量：`450`
- `5` 个 scene 均匀采样，各 `≈90`
- 当前模板全部显式带 `campaign_id`，静态看 clarify 为 `0`

### scene 分布

| Scene | 期望条数 | 期望 clarify |
|---|---:|---:|
| `roas_danger` | ≈90 | 0 |
| `ret_danger` | ≈90 | 0 |
| `both_danger` | ≈90 | 0 |
| `creative_fatigue` | ≈90 | 0 |
| `budget_underdelivery` | ≈90 | 0 |

### 工具链覆盖

- `roas_danger / both_danger / budget_underdelivery`
  - `detect_anomalies -> get_campaign_metrics -> get_optimization_playbook`
- `ret_danger`
  - `detect_anomalies -> get_appsflyer_report -> get_optimization_playbook`
- `creative_fatigue`
  - `detect_anomalies -> get_creative_performance -> get_optimization_playbook`

### 设计解读

- 正向能力：异常定位、留存/投放诊断、动作建议
- 追问：当前静态为 `0`
- 并行工具：没有
- 串行工具：强，全部是多工具串行链

## Workflow 6：知识问答

### 覆盖范围

- 总量：`240`
- bucket 模板数：
  - `bidding_strategy`: `14`
  - `creative_guideline`: `9`
  - `platform_policy`: `9`
  - `industry_benchmark`: `16`

### bucket 分布

| Bucket | 模板数 | bucket 权重 | 模板缺槽位率 | 期望 direct | 期望 clarify |
|---|---:|---:|---:|---:|---:|
| `bidding_strategy` | 14 | 29.17% | 0% | ≈70.00 | 0 |
| `creative_guideline` | 9 | 18.75% | 0% | ≈45.00 | 0 |
| `platform_policy` | 9 | 18.75% | 33.33% | ≈30.00 | ≈15.00 |
| `industry_benchmark` | 16 | 33.33% | 75.00% | ≈20.00 | ≈60.00 |

合计：

- direct `165`
- clarify `75`

### 工具链覆盖

- `bidding_strategy` -> `query_knowledge_base`
- `creative_guideline` -> `query_knowledge_base`
- `platform_policy` -> `get_platform_policy`
  - 当前同时包含 direct query 和缺平台的 clarify-only query
- `industry_benchmark` -> `get_benchmark_data`
  - 当前少量 query 可 direct，多数会因为缺 `platform / region / genre` 之一而转 clarify

### 设计解读

- 正向能力：出价知识、创意指南、平台政策、benchmark
- 边界能力：主要体现在 `platform_missing` 与 `platform_region_or_genre_missing`
- 并行工具：没有
- 串行工具：没有并行，但 bucket 绑定清晰

## Workflow 7：拒答

### 覆盖范围

- 总量：`200`
- refusal type 当前按 3 类尽量均分，余数按顺序补到前面的类型

| refusal_type | 条数 | 占该 workflow |
|---|---:|---:|
| `off_topic` | 67 | 33.50% |
| `unauthorized_internal` | 67 | 33.50% |
| `unauthorized_external` | 66 | 33.00% |

### 设计解读

- `off_topic`：域外问题，统一落到能力边界拒答
- `unauthorized_internal`：内部高风险越权操作，如删 campaign、改预算、导出敏感数据
- `unauthorized_external`：对外部未授权/违规访问，如入侵竞品账户、抓竞品数据、导出竞品素材
- 不应调用工具
- 不应进入 clarify

## 能力标签覆盖总览

### 1. 反向样本 / 边界样本

- 明确拒答样本：`200`
- clarify 样本：`≈965.64`
- 如果把两者都视为“非直接满足用户需求”的边界样本，则边界样本总量约：
  - `≈1165.64`
  - 占总量 `≈42.39%`

### 2. 追问覆盖

- 有追问样本：是
- 追问总量：`≈965.64`
- 追问比例：`≈35.11%`
- 当前主要追问原因：
  - `platform_missing`
  - `platform_or_genre_missing`
  - `campaign_id_missing`
  - `timerange_missing`
  - `campaign_id_and_timerange_missing`
  - `platform_region_or_genre_missing`

注意：

- 当前只覆盖“单轮追问”
- clarify-only 样本在 convert 后的标准形态是：
  - `system -> user -> assistant -> user`
- 如果未来想支持“追问后继续 tool call”，这不是改 YAML 能完成的，需要同时修改 seed / convert 逻辑

### 3. 并行 / 串行工具调用

- 明确并行工具调用：有
  - 主要来自 `workflow 4`
- 串行工具调用：有
  - `workflow 1.trending_with_hooks`
  - `workflow 2`
  - `workflow 5`
  - `workflow 4` 的并行后串行链路
- 无工具样本：有
  - `workflow 7`
  - 所有 clarify-only 样本

### 4. 单工具 / 多工具链

- 单工具 bucket：
  - `workflow 1.competitor_ads`
  - `workflow 1.trending_creatives`
  - `workflow 3.*`
  - `workflow 6.bidding_strategy`
  - `workflow 6.creative_guideline`
  - `workflow 6.platform_policy`
  - `workflow 6.industry_benchmark`
- 多工具链 bucket：
  - `workflow 1.trending_with_hooks`
  - `workflow 2.single_upload / batch_upload`
  - `workflow 4.*`
  - `workflow 5.*`

## 和旧版本相比的关键变化

- `workflow 1` 的 hooks 检索模板已扩到 `8` 条，不再按旧版 `3` 条统计
- `workflow 3` 的 `creative_metrics` 现在是 `6` 条模板，`appsflyer_report` 已全部改成 `app_id` 驱动
- `workflow 4` 的 clarify scene 已固定为 `clarify_missing_scope`，时间回答使用真实 `date_range`
- `workflow 5` 的 `ret_danger` 已切到 AppsFlyer 诊断，playbook 不再复用 `low_ctr`
- `workflow 6` 已把 3 条平台规格类 query 从 `creative_guideline` 迁到 `platform_policy`
- `workflow 7` 已从二分类 refusal 改成三分类 refusal

维护规则请配合阅读：

- [Datapipeline YAML 维护规范](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/docs/Datapipeline_YAML_Maintenance.md)
