# AdCampaignAgent 数据业务 Workflow 梳理

本文聚焦当前数据集里代表业务场景的 `workflow`，重点记录当前这版数据文件里的实际分布，包括：

- 每个业务 workflow 的总量
- 每个 workflow 的追问 / 非追问 variant 数量
- 每个 workflow 下的 `scene_tag` 分布
- 每个 workflow 下的 `tool_chain` 分布

业务 workflow 的定义来源于 [src/datapipeline/0_generate_base_dataset.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/0_generate_base_dataset.py)，最终对话结构的落地方式来源于 [src/datapipeline/2_convert_dataset.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/2_convert_dataset.py)。

## 统计口径

本文中的“当前数据分布”基于仓库内这批现有 seed 数据，而不是只看生成代码中的理论概率：

- 原始 seed 文件：
  [data/raw/ad_agent_seeds_20260328_041007_zh.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/raw/ad_agent_seeds_20260328_041007_zh.json)
- train split：
  [data/processed/ad_agent_seeds_20260328_041007_zh_train.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/processed/ad_agent_seeds_20260328_041007_zh_train.json)
- test split：
  [data/processed/ad_agent_seeds_20260328_041007_zh_test.json](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/data/processed/ad_agent_seeds_20260328_041007_zh_test.json)

当前这版 seed 总数是 `1000` 条，其中：

- `903` 条不需要追问
- `97` 条需要追问
- 总体追问占比是 `9.7%`

## 统计字段

所有业务 workflow 在 seed 层都共享同一套控制字段：

- `workflow` / `workflow_name`：业务场景编号和名称。
- `user_query`：用户原始问题。
- `needs_clarification`：是否需要先追问。
- `clarification_reason`：为什么要追问。
- `clarification_answer`：用户补充信息。
- `scene_tag`：当前样本所属的细分场景。
- `tool_chain`：该场景下预定义的工具调用链。
- `refusal_type`：只在 Refusal workflow 中使用。

这些字段在 [src/datapipeline/2_convert_dataset.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/2_convert_dataset.py) 中会被落地成对话结构，当前只需要关心两个统计事实：

1. `needs_clarification = true` 的样本会先出现一轮追问，再进入后续流程。
2. 其他业务样本会按 `tool_chain` 串行调用工具，最后再给总结回复。

## Workflow 总览

| ID | Workflow | 主要目标 | 代码层面是否可能追问 | 是否调用工具 |
| --- | --- | --- | --- | --- |
| 1 | Creative Search | 搜热门素材、竞品广告、热门 hooks | 是 | 是 |
| 2 | Creative Upload | 校验素材规格并上传 | 否 | 是 |
| 3 | Single Metric Query | 查询单类投放指标 | 是 | 是 |
| 4 | Multi-Dimensional Deep Analysis | 做多维度深度分析 | 是 | 是 |
| 5 | Anomaly Diagnosis & Optimization | 做异常诊断并给优化建议 | 否 | 是 |
| 6 | Knowledge Q&A | 回答投放知识、政策、benchmark 问题 | 否 | 是 |
| 7 | Refusal | 对越权、离题、信息不足的请求拒答 | 否 | 否 |

### 当前数据集里的 workflow x 追问分布

| Workflow | 总条数 | 追问条数 | 不追问条数 | 追问占比 |
| --- | ---: | ---: | ---: | ---: |
| 素材搜寻 | 120 | 25 | 95 | 20.8% |
| 素材上传 | 80 | 0 | 80 | 0.0% |
| 单指标效果查询 | 120 | 23 | 97 | 19.2% |
| 多维深度分析 | 350 | 49 | 301 | 14.0% |
| 异常诊断与优化 | 150 | 0 | 150 | 0.0% |
| 知识问答 | 80 | 0 | 80 | 0.0% |
| 拒答 | 100 | 0 | 100 | 0.0% |

结论上，当前只有 3 类 workflow 在实际数据里存在追问 variant：

- `素材搜寻`
- `单指标效果查询`
- `多维深度分析`

下面的详细拆分只展开当前主业务 workflow，不单独展开拒答类样本。

## 1. Creative Search

### 业务意图

用户想看热门素材、竞品广告、创意参考或热门 hooks。

### 代码中的可变分支

- 追问分支：
  - 代码里通过 `random.random() < 0.2` 控制，目标大约是 20% 样本进入追问。
  - 触发条件是用户问题缺少平台或品类信息。
  - `clarification_reason = platform_or_genre_missing`。
- 场景分支：
  - `scene_tag` 固定为 `creative_search`，没有再按效果好坏拆场景。
- 工具链分支：
  - `["search_trending_creatives"]`
  - `["search_competitor_ads"]`
  - `["search_trending_creatives", "get_trending_hooks"]`
  - `["search_competitor_ads", "search_trending_creatives"]`

### 当前数据分布

- 总数：`120`
- 追问 variant：`25`
- 不追问 variant：`95`
- 追问占比：`20.8%`

`scene_tag` 分布：

| scene_tag | 条数 |
| --- | ---: |
| creative_search | 120 |

`tool_chain` 分布：

| tool_chain | 条数 |
| --- | ---: |
| `["search_competitor_ads", "search_trending_creatives"]` | 33 |
| `["search_trending_creatives"]` | 31 |
| `["search_trending_creatives", "get_trending_hooks"]` | 28 |
| `["search_competitor_ads"]` | 28 |

### 分支流程

1. 用户直接描述清楚平台、地区、品类，或先给模糊问题后补充信息。
2. 系统根据预定义 `tool_chain` 搜热门素材、搜竞品广告，或补充热门 hooks。
3. 最终返回创意搜索结果总结。

### 结束方式

- 永远以创意搜索结果总结结束。
- 不会进入 ROAS/留存分析模板。

## 2. Creative Upload

### 业务意图

用户要上传素材到某个 campaign，或者批量上传一组素材。

### 代码中的可变分支

- 无追问分支：
  - 这个 workflow 不通过 `needs_clarification` 追问。
- 场景分支：
  - 成功类场景：
    - `upload_success`
    - `upload_partial_fail`
  - 校验失败类场景：
    - `validate_fail_size`
    - `validate_fail_format`
- 工具链分支：
  - 校验失败场景固定走 `["validate_creative_spec"]`
  - 成功类场景从下面两条链里二选一：
    - `["validate_creative_spec", "upload_creative_asset"]`
    - `["validate_creative_spec", "batch_upload_creatives"]`

### 当前数据分布

- 总数：`80`
- 追问 variant：`0`
- 不追问 variant：`80`

`scene_tag` 分布：

| scene_tag | 条数 |
| --- | ---: |
| upload_success | 34 |
| upload_partial_fail | 32 |
| validate_fail_format | 11 |
| validate_fail_size | 3 |

`tool_chain` 分布：

| tool_chain | 条数 |
| --- | ---: |
| `["validate_creative_spec", "batch_upload_creatives"]` | 34 |
| `["validate_creative_spec", "upload_creative_asset"]` | 32 |
| `["validate_creative_spec"]` | 14 |

### 分支流程

1. 先进入素材规格校验。
2. 如果是 `validate_fail_size` 或 `validate_fail_format`：
   - 在校验阶段直接结束。
   - 不继续上传。
3. 如果校验通过：
   - 进入单素材上传或批量上传。
4. 如果场景是 `upload_partial_fail`：
   - 上传接口会返回部分成功或待审核状态。
5. 如果场景是 `upload_success`：
   - 返回正常上传成功状态。

### 结束方式

- 校验失败时输出“规格校验未通过，请调整后重新上传”。
- 上传成功或部分成功时输出“素材已上传，等待审核”的总结。

## 3. Single Metric Query

### 业务意图

用户只想查单类指标，比如 ROAS、留存、花费、CTR、CPM、归因报表。

### 代码中的可变分支

- 追问分支：
  - 代码里通过 `random.random() < 0.2` 控制，目标大约是 20% 样本需要追问。
  - 触发条件是问题里缺少 `campaign_id`。
  - `clarification_reason = campaign_id_missing`。
- 场景分支：
  - 从下面 7 个指标健康场景中随机选择：
    - `healthy`
    - `roas_warning`
    - `roas_danger`
    - `ret_warning`
    - `ret_danger`
    - `both_warning`
    - `both_danger`
- 工具链分支：
  - `["get_campaign_metrics"]`
  - `["get_creative_performance"]`
  - `["get_appsflyer_report"]`

### 当前数据分布

- 总数：`120`
- 追问 variant：`23`
- 不追问 variant：`97`
- 追问占比：`19.2%`

`scene_tag` 分布：

| scene_tag | 条数 |
| --- | ---: |
| roas_danger | 26 |
| healthy | 21 |
| both_danger | 20 |
| ret_danger | 16 |
| both_warning | 14 |
| ret_warning | 14 |
| roas_warning | 9 |

`tool_chain` 分布：

| tool_chain | 条数 |
| --- | ---: |
| `["get_appsflyer_report"]` | 43 |
| `["get_creative_performance"]` | 40 |
| `["get_campaign_metrics"]` | 37 |

### 分支流程

1. 用户要么直接给出 campaign/app，要么先问模糊指标后被追问。
2. 系统从三个单工具链中选一条：
   - campaign 聚合指标查询
   - creative 维度表现查询
   - AppsFlyer 报表查询
3. `scene_tag` 决定 mock 结果中的 ROAS/留存是健康、预警还是告警。
4. 最终按 `scene_tag` 输出对应的分析结论。

### 结束方式

- 始终以单轮指标分析总结结束。
- 不会额外再走诊断 playbook。

## 4. Multi-Dimensional Deep Analysis

### 业务意图

用户希望拿到完整分析报告，系统需要综合 campaign、素材、归因、benchmark 等多个维度一起看。

### 代码中的可变分支

- 追问分支：
  - 代码里通过 `random.random() < 0.15` 控制，目标大约是 15% 样本需要追问。
  - 触发条件是同时缺少 `campaign_id` 和时间范围。
  - `clarification_reason = campaign_id_and_timerange_missing`。
- 场景分支：
  - 从 10 个分析场景中随机选择：
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
- 工具链分支：
  - `["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"]`
  - `["get_appsflyer_report", "get_campaign_metrics", "get_benchmark_data"]`
  - `["get_campaign_metrics", "get_appsflyer_report", "get_creative_performance", "get_benchmark_data"]`
  - `["compare_campaigns", "get_benchmark_data"]`

### 当前数据分布

- 总数：`350`
- 追问 variant：`49`
- 不追问 variant：`301`
- 追问占比：`14.0%`

`scene_tag` 分布：

| scene_tag | 条数 |
| --- | ---: |
| roas_warning | 47 |
| creative_fatigue | 42 |
| healthy | 40 |
| roas_danger | 40 |
| both_warning | 35 |
| both_danger | 31 |
| budget_underdelivery | 31 |
| ret_danger | 29 |
| ret_warning | 28 |
| insufficient_data | 27 |

`tool_chain` 分布：

| tool_chain | 条数 |
| --- | ---: |
| `["compare_campaigns", "get_benchmark_data"]` | 96 |
| `["get_campaign_metrics", "get_appsflyer_report", "get_creative_performance", "get_benchmark_data"]` | 90 |
| `["get_appsflyer_report", "get_campaign_metrics", "get_benchmark_data"]` | 88 |
| `["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"]` | 76 |

### 分支流程

1. 用户请求“完整分析”“综合分析”“分析报告”。
2. 如果关键信息不全，先追问 campaign 和时间范围。
3. 系统按预定义链路串行调多个工具，组合不同视角的数据：
   - campaign 总体表现
   - creative 维度表现
   - AppsFlyer 留存/收入视角
   - benchmark 对照
   - campaign 对比
4. `scene_tag` 决定最终诊断主题：
   - 健康
   - 仅 ROAS 问题
   - 仅留存问题
   - ROAS+留存双问题
   - 素材疲劳
   - 预算欠量
   - 数据不足

### 结束方式

- 输出结构化分析报告。
- 在 `healthy / warning / danger / fatigue / underdelivery / insufficient_data` 之间切换不同模板。

## 5. Anomaly Diagnosis & Optimization

### 业务意图

用户发现数据异常，希望系统先判断异常，再给可执行优化建议。

### 代码中的可变分支

- 无追问分支：
  - 该 workflow 默认直接进入诊断。
- 场景分支：
  - 只从异常类场景中选：
    - `roas_danger`
    - `ret_danger`
    - `both_danger`
    - `creative_fatigue`
    - `budget_underdelivery`
- 工具链分支：
  - `["detect_anomalies", "get_optimization_playbook"]`
  - `["detect_anomalies", "get_campaign_metrics", "get_optimization_playbook"]`
  - `["detect_anomalies", "get_creative_performance", "get_optimization_playbook"]`

### 当前数据分布

- 总数：`150`
- 追问 variant：`0`
- 不追问 variant：`150`

`scene_tag` 分布：

| scene_tag | 条数 |
| --- | ---: |
| creative_fatigue | 38 |
| both_danger | 32 |
| roas_danger | 30 |
| ret_danger | 29 |
| budget_underdelivery | 21 |

`tool_chain` 分布：

| tool_chain | 条数 |
| --- | ---: |
| `["detect_anomalies", "get_campaign_metrics", "get_optimization_playbook"]` | 55 |
| `["detect_anomalies", "get_optimization_playbook"]` | 48 |
| `["detect_anomalies", "get_creative_performance", "get_optimization_playbook"]` | 47 |

### 分支流程

1. 用户描述“突然跌了”“触发告警了”“欠量严重”“CTR 连续下滑”等异常信号。
2. 第一阶段固定先走 `detect_anomalies`。
3. 第二阶段根据链路不同，补充：
   - campaign 层指标
   - creative 层表现
4. 最后统一走 `get_optimization_playbook` 给出动作建议。

### 结束方式

- 总是以“异常诊断 + 优化建议”结束。
- 相比 workflow 4，它更偏告警处置而不是全量分析报告。

## 6. Knowledge Q&A

### 业务意图

用户在问广告投放知识，包括出价策略、素材设计、平台政策、行业 benchmark。

### 代码中的可变分支

- 无追问分支：
  - 该 workflow 默认不追问。
- 场景分支：
  - 先从 query 文本中自动推断 domain。
  - `scene_tag` 可能是：
    - `bidding_strategy`
    - `creative_guideline`
    - `platform_policy`
    - `industry_benchmark`
    - `knowledge_base`
- 工具链分支：
  - `["query_knowledge_base"]`
  - `["get_benchmark_data"]`
  - `["get_platform_policy"]`
  - `["query_knowledge_base", "get_benchmark_data"]`

### 当前数据分布

- 总数：`80`
- 追问 variant：`0`
- 不追问 variant：`80`

`scene_tag` 分布：

| scene_tag | 条数 |
| --- | ---: |
| bidding_strategy | 27 |
| creative_guideline | 21 |
| industry_benchmark | 16 |
| platform_policy | 16 |

当前这版数据里没有抽到 `knowledge_base` 这个兜底 scene。

`tool_chain` 分布：

| tool_chain | 条数 |
| --- | ---: |
| `["get_platform_policy"]` | 25 |
| `["query_knowledge_base"]` | 23 |
| `["get_benchmark_data"]` | 18 |
| `["query_knowledge_base", "get_benchmark_data"]` | 14 |

### 分支流程

1. 用户提出知识型问题。
2. 系统先基于关键字自动识别问题属于哪个 domain：
   - 出价策略类
   - 素材方法论类
   - 平台政策类
   - benchmark 类
   - 无法明确分类时归为 `knowledge_base`
3. 再从预定义工具链中选择单工具或双工具组合。
4. 最终返回知识检索结果总结。

### 结束方式

- 输出“以上是知识库检索结果”类型的总结。
- 不进入效果分析或异常诊断模板。

## 当前数据集切分情况

当前仓库里这版数据的切分情况如下：

| 文件 | 条数 | 追问条数 |
| --- | ---: | ---: |
| raw seed | 1000 | 97 |
| train seed | 779 | 73 |
| test seed | 221 | 24 |

按 [src/datapipeline/1_split_dataset.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/1_split_dataset.py) 的实现，切分时使用的分层 key 是：

- `workflow_name`
- `scene_tag`
- `needs_clarification`

因此 train/test 不只是总量按 `~8:2` 拆分，业务 workflow、scene 和追问分支也会尽量保持同构分布。
