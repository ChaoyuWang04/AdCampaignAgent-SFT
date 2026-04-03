# AdCampaignAgent Seed 数据覆盖说明

本文档基于当前 [`0_generate_base_dataset.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/0_generate_base_dataset.py) 与 [`workflow/`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/workflow) 下的 YAML 规则做静态分析，不引用任何已生成的 `data/raw/*.json` 文件。

## 口径说明

- `总样本量`：按当前代码配置，理论生成总量为 `2850` 条。
- `固定条数`：代码里直接写死或通过整除分配得到，属于确定值。
- `期望条数`：通过 `random.choice`、`random.random()` 做均匀随机采样得到，单次实际生成不保证完全相等，文中用 `≈` 表示。
- `占比`：
  - 若写“占总量”，分母为 `2850`
  - 若写“占该 workflow”，分母为该 workflow 的样本总数

## 总体结构

| Workflow | 条数 | 占总量 |
|---|---:|---:|
| 素材搜寻 | 360 | 12.63% |
| 素材上传 | 240 | 8.42% |
| 单指标效果查询 | 360 | 12.63% |
| 多维深度分析 | 900 | 31.58% |
| 异常诊断与优化 | 450 | 15.79% |
| 知识问答 | 240 | 8.42% |
| 拒答 | 300 | 10.53% |

当前主训练集明显偏向分析类任务：

- 深度分析 + 异常诊断合计 `1350` 条，占总量 `47.37%`
- 搜索 + 上传合计 `600` 条，占总量 `21.05%`
- 知识问答 + 拒答合计 `540` 条，占总量 `18.95%`
- 单指标查询 `360` 条，占总量 `12.63%`

## Workflow 1：素材搜寻

### 覆盖范围

- 总量：`360`
- 细场景：仅 `creative_search` 一个 scene
- 查询模板：
  - 明确需求模板 `26` 条
  - 含糊需求模板 `23` 条
- 追问设计：
  - 追问概率 `20%`
  - 期望追问样本 `≈72` 条，占该 workflow `20%`
  - 期望直接检索样本 `≈288` 条，占该 workflow `80%`

### 工具链覆盖

4 种 tool plan，均匀采样，期望各 `≈90` 条：

1. `search_trending_creatives`
2. `search_competitor_ads`
3. `search_trending_creatives -> get_trending_hooks`
4. `search_competitor_ads -> search_trending_creatives`

### 设计解读

- 正向能力：热门素材搜索、竞品素材搜索、热门钩子补充
- 反向/边界能力：有，但不是拒答，而是“信息不足先追问”
- 追问形态：只有单轮追问，没有二次追问链
- 并行工具：没有
- 串行工具：有，且包含单工具和双工具链

## Workflow 2：素材上传

### 覆盖范围

- 总量：`240`
- 核心分流：
  - 上传成功主线 `≈180` 条，占该 workflow `75%`
  - 校验失败/重传主线 `≈60` 条，占该 workflow `25%`

### 细场景覆盖

按均匀采样的期望值：

| Scene | 期望条数 | 占该 workflow |
|---|---:|---:|
| `upload_success` | ≈90 | 37.5% |
| `upload_partial_fail` | ≈90 | 37.5% |
| `validate_fail_size` | ≈30 | 12.5% |
| `validate_fail_format` | ≈30 | 12.5% |

### 工具链覆盖

- 成功路径：
  - `validate_creative_spec -> upload_creative_asset`
  - `validate_creative_spec -> batch_upload_creatives`
- 失败路径：
  - `validate_creative_spec`

### 设计解读

- 正向能力：单素材上传、批量上传
- 反向例子：有，且是明确的“先校验不通过，不应继续上传”
- 追问：没有
- 并行工具：没有
- 串行工具：有，且上传前强制校验

## Workflow 3：单指标效果查询

### 覆盖范围

- 总量：`360`
- 查询模板：
  - 明确查询模板 `35` 条
  - 含糊查询模板 `15` 条
- 追问设计：
  - 追问概率 `20%`
  - 期望追问样本 `≈72` 条，占该 workflow `20%`
  - 期望直接查询样本 `≈288` 条，占该 workflow `80%`

### 细场景覆盖

该 workflow 的 `scene_tag` 不是手工指定，而是通过 `infer_metric_scene()` 从 query 文本推断。按模板静态分析，期望分布如下：

| Scene | 期望条数 | 占该 workflow |
|---|---:|---:|
| `query_roas` | ≈93.26 | 25.90% |
| `query_spend` | ≈83.66 | 23.24% |
| `query_retention` | ≈68.57 | 19.05% |
| `query_ctr` | ≈50.74 | 14.10% |
| `query_installs` | ≈47.31 | 13.14% |
| `query_cpm` | ≈16.46 | 4.57% |

### 工具链覆盖

3 种 plan，均匀采样，期望各 `≈120` 条：

1. `get_campaign_metrics`
2. `get_creative_performance`
3. `get_appsflyer_report`

### 设计解读

- 正向能力：单指标拉数、单维度检查
- 反向/边界能力：有，通过 `campaign_id_missing` 触发单轮追问
- 追问形态：只有单轮追问
- 并行工具：没有
- 串行工具：本质上是单工具调用

## Workflow 4：多维深度分析

### 覆盖范围

- 总量：`900`
- 是全数据集中权重最大的 workflow，占总量 `31.58%`
- 含糊分析请求追问概率：`15%`
  - 期望追问样本 `≈135` 条
  - 期望直接分析样本 `≈765` 条

### 细场景覆盖

共有 `10` 个深度分析 scene，按均匀采样，期望各 `≈90` 条，占该 workflow 各 `10%`：

| Scene | 期望条数 |
|---|---:|
| `healthy` | ≈90 |
| `roas_warning` | ≈90 |
| `roas_danger` | ≈90 |
| `ret_warning` | ≈90 |
| `ret_danger` | ≈90 |
| `both_warning` | ≈90 |
| `both_danger` | ≈90 |
| `creative_fatigue` | ≈90 |
| `budget_underdelivery` | ≈90 |
| `insufficient_data` | ≈90 |

如果继续按“追问 vs 非追问”拆开理解，则每个 scene 内部期望为：

- 非追问直接分析 `≈76.5`
- 含糊问题先追问 `≈13.5`

### 工具链覆盖

4 种 plan，均匀采样，期望各 `≈225` 条：

1. 并行：`get_campaign_metrics + get_creative_performance + get_benchmark_data`
2. 并行后串行：`get_appsflyer_report + get_campaign_metrics`，再 `get_benchmark_data`
3. 并行后串行：`get_campaign_metrics + get_appsflyer_report + get_creative_performance`，再 `get_benchmark_data`
4. 纯串行：`compare_campaigns -> get_benchmark_data`

### 设计解读

- 正向能力：完整分析、基准对比、跨源分析
- 反向/边界能力：
  - 有 `insufficient_data` 早期样本不足场景
  - 有含糊需求先追问
- 追问形态：只有单轮追问，没有连续多轮澄清链
- 并行工具：有，是全数据集唯一明确覆盖并行 tool calling 的 workflow
- 串行工具：有
- 复杂推理：强，属于主力训练来源

## Workflow 5：异常诊断与优化

### 覆盖范围

- 总量：`450`
- 专注高风险/异常状态诊断
- 共有 `5` 个 scene，按均匀采样，期望各 `≈90` 条，占该 workflow 各 `20%`

| Scene | 期望条数 |
|---|---:|
| `roas_danger` | ≈90 |
| `ret_danger` | ≈90 |
| `both_danger` | ≈90 |
| `creative_fatigue` | ≈90 |
| `budget_underdelivery` | ≈90 |

### 工具链覆盖

3 种 plan，均匀采样，期望各 `≈150` 条：

1. `detect_anomalies -> get_optimization_playbook`
2. `detect_anomalies -> get_campaign_metrics -> get_optimization_playbook`
3. `detect_anomalies -> get_creative_performance -> get_optimization_playbook`

### 设计解读

- 正向能力：异常定位、归因、动作建议
- 反向例子：没有拒答型反向例子，但覆盖了“坏状态 / 高风险状态”这类负面业务样本
- 追问：没有
- 并行工具：没有
- 串行工具：强，且全部是多工具链

## Workflow 6：知识问答

### 覆盖范围

- 总量：`240`
- 知识类 query 模板总数：`44`
- 该 workflow 的细分 `scene_tag` 由 query 文本和 `domain_map` 规则推断，不是均匀手工分配

### 细场景覆盖

按 44 条模板静态映射后的期望分布：

| Scene | 期望条数 | 占该 workflow |
|---|---:|---:|
| `knowledge_base` | ≈92.73 | 38.64% |
| `bidding_strategy` | ≈54.55 | 22.73% |
| `creative_guideline` | ≈38.18 | 15.91% |
| `industry_benchmark` | ≈38.18 | 15.91% |
| `platform_policy` | ≈16.36 | 6.82% |

### 工具链覆盖

4 种 plan，均匀采样，期望各 `≈60` 条：

1. `query_knowledge_base`
2. `get_benchmark_data`
3. `get_platform_policy`
4. `query_knowledge_base -> get_benchmark_data`

### 设计解读

- 正向能力：投放知识、创意指南、行业 benchmark、平台政策
- 反向例子：没有
- 追问：没有
- 并行工具：没有
- 串行工具：有，但只在第 4 种 plan 中出现双工具链

## Workflow 7：拒答

### 覆盖范围

- 总量：`300`
- 该 workflow 不是随机比例，而是代码按 `300 // 3` 强制均分，因此每类都是确定值 `100`

| Scene / refusal_type | 条数 | 占该 workflow |
|---|---:|---:|
| `off_topic` | 100 | 33.33% |
| `unauthorized_operation` | 100 | 33.33% |
| `insufficient_data_to_answer` | 100 | 33.33% |

### 模板覆盖

- `off_topic` 模板 `30` 条
- `unauthorized_operation` 模板 `26` 条
- `insufficient_data_to_answer` 模板 `20` 条

### 设计解读

- 这是最明确的反向样本池
- 不应调用工具
- 不应直接满足用户请求
- 应学会拒答、边界控制和权限约束

## 能力标签覆盖总览

### 1. 反向样本 / 边界样本

最明确的反向样本有两类：

- `拒答`：`300` 条，固定，占总量 `10.53%`
- `信息不足先追问`：期望 `≈279` 条，占总量 `≈9.79%`
  - 素材搜寻 `≈72`
  - 单指标查询 `≈72`
  - 深度分析 `≈135`

如果把这两类都视为“非直接满足用户需求”的边界样本，则边界样本总覆盖约为：

- `≈579` 条
- 占总量 `≈20.32%`

此外，`workflow 2` 的校验失败 `≈60` 条、`workflow 4` 的 `insufficient_data` `≈90` 条，也属于业务负面/异常样本，但不是拒答。

### 2. 追问覆盖

- 有追问样本：是
- 追问总量：期望 `≈279`
- 追问比例：`≈9.79%`
- 追问原因类型：
  - `platform_or_genre_missing`
  - `campaign_id_missing`
  - `campaign_id_and_timerange_missing`

注意：

- 当前只覆盖“单轮追问”
- 没有“追问后用户仍然模糊，再继续二次追问”的多轮澄清链

### 3. 串行 / 并行工具调用

- 明确并行工具调用：有
  - 仅来自 `workflow 4`
  - 3/4 的 tool plan 含并行组
  - 期望并行样本 `≈675`
  - 占总量 `≈23.68%`

- 纯串行或单工具样本：有
  - 期望 `≈1875`
  - 占总量 `≈65.79%`

- 无工具样本：有
  - 来自 `workflow 7`
  - 固定 `300`
  - 占总量 `10.53%`

### 4. 单工具 / 多工具链

按 `tool_chain` 长度静态分析：

- 多工具链样本：期望 `≈1770`
  - 占总量 `≈62.11%`
- 单工具链样本：期望 `≈780`
  - 占总量 `≈27.37%`
- 无工具样本：`300`
  - 占总量 `10.53%`

多工具链主要集中在：

- 素材搜寻
- 素材上传
- 多维深度分析
- 异常诊断与优化
- 部分知识问答

### 5. 正向需求类型

当前正向需求主要覆盖：

- 素材搜索参考
- 素材上传与校验
- 单指标查询
- 多维分析
- 异常诊断与优化建议
- 知识问答

未作为主任务单独成类覆盖的包括：

- 闲聊类 direct answer
- 无工具但专业解释型短答
- 连续多轮需求澄清
- 复杂权限确认后再执行的交互式任务

## 完整性结论

从“产品/训练设计说明书”的角度看，当前 seed 规则已经比较完整地覆盖了一个广告投放 agent 的主干能力：

- 有主任务正向样本
- 有拒答和边界反向样本
- 有信息不足先追问
- 有单工具、串行多工具、并行多工具
- 有健康、预警、危险、疲劳、欠量、样本不足等业务状态

但如果目标是“更完善”，当前仍有三个明显空白：

1. 没有真正的多轮追问链
2. 没有大量“无工具但专业直接回答”的正向短答样本
3. 并行调用只集中在 `workflow 4`，其他 workflow 没有并行结构

## 建议

如果后续要继续增强训练覆盖，优先级建议如下：

1. 增加“二次追问/多轮澄清”规则
2. 增加“专业 direct answer”正向样本，不依赖工具也不拒答
3. 在搜索或诊断任务里补充更多并行工具组合
4. 对 `workflow 3` 的 `query_cpm`、`query_installs` 等低占比子场景做定向增广
