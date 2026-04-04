# Benchmark 参考手册

## 指标说明

| 指标 | 测什么 | 当前判分口径 |
|---|---|---|
| `F1` | Tool call 是否可解析 | 对 `expected_behavior == "tool_call"` 的样本，如果 trace 中完全没有 tool call，记 `0.0`；只要存在可解析 tool call，记 `1.0`。对不要求调工具的样本，这一项跳过。 |
| `F2` | Tool call 格式是否合规 | 在存在 tool call 的前提下，要求每个 tool call 都有合法 `function.name`，且 `function.arguments` 能解析成 `dict`。全部满足记 `1.0`，否则记 `0.0`。 |
| `R1` | 高层行为决策是否正确 | 先从完整 trace 规则化推断行为类别：`tool_call` / `reject` / `clarify` / `direct_answer`，再与 `expected_behavior` 比较；一致记 `1.0`，否则记 `0.0`。 |
| `R2` | 工具选择是否完全正确 | 只对 `expected_behavior == "tool_call"` 的样本评分。要求预测工具序列与 `expected_tools` 完全一致；一致记 `1.0`，否则记 `0.0`。 |
| `R3` | 多工具集合是否接近 gold | 只对 `expected_behavior == "tool_call"` 的样本评分。对预测工具集合和 `expected_tools` 计算 multiset F1，返回 `0.0` 到 `1.0` 的连续分数。 |
| `C1` | Gold 参数是否被完整覆盖 | 只对 `expected_behavior == "tool_call"` 且 `expected_tool_args` 非空的样本评分。按工具名找到第一条匹配调用后，检查 gold 参数中的每个字段是否都被正确填入；某个工具全部字段都正确记 `1.0`，否则记 `0.0`，最后对相关工具取平均。 |
| `C2` | 参数字段级准确率 | 只对 `expected_behavior == "tool_call"` 且 `expected_tool_args` 非空的样本评分。逐字段比较参数值，计算每个工具的字段命中比例，再对相关工具取平均，返回 `0.0` 到 `1.0`。 |
| `S1` | 顺序调用是否正确 | 只对 `case_type == "sequential"` 的样本评分。提取所有 assistant turn 中的工具名序列，与 `expected_sequence` 完全一致记 `1.0`，否则记 `0.0`。 |
| `S2` | 并行调用是否正确 | 只对 `case_type == "parallel"` 的样本评分。检查 `expected_parallel_groups` 中是否至少有一个工具组完整出现在同一条 assistant message 的 `tool_calls` 里；命中记 `1.0`，否则记 `0.0`。 |
| `S3` | 越界请求是否正确拒答 | 只对 `expected_behavior == "reject"` 的样本评分。如果 trace 的高层行为被识别为 `reject`，记 `1.0`；否则记 `0.0`。 |
| `S4` | 信息不足时是否正确追问 | 只对 `expected_behavior == "clarify"` 的样本评分。首先要求行为被识别为 `clarify`；然后检查首条 assistant 回复是否覆盖 `required_missing_slots` 中的关键槽位别名，返回槽位覆盖比例，范围 `0.0` 到 `1.0`。 |
| `S5` | 端到端任务是否成功完成 | 规则化综合指标。`reject` 样本要求 `S3 == 1.0` 且没有工具调用；`clarify` 样本要求 `S4 == 1.0` 且没有工具调用；`sequential` 样本要求 `R1 == 1.0`、`S1 == 1.0` 且存在最终 assistant 收敛回复；`parallel` 样本要求 `R1 == 1.0`、`S2 == 1.0` 且存在最终 assistant 收敛回复；普通 `tool_call` 样本要求行为是 `tool_call`、`R2 == 1.0`、`C2 == 1.0` 且存在最终 assistant 收敛回复。满足对应条件记 `1.0`，否则记 `0.0`。 |

## 工具说明

### `search_trending_creatives`

- 作用：搜索近期热门广告素材，返回高热度创意列表。
- 必填参数：
  - `platform`：投放平台，如 `Meta`、`Google`、`Tiktok`
  - `game_genre`：游戏品类，如 `casual`、`puzzle`、`rpg`
- 可选参数：
  - `region`：目标地区，如 `US`、`JP`、`SEA`

### `search_competitor_ads`

- 作用：查询竞品近期广告投放素材。
- 必填参数：
  - `competitor_name`：竞品名称，如 `Playrix`、`Voodoo`
  - `platform`：投放平台，如 `Meta`、`Google`、`Tiktok`

### `get_trending_hooks`

- 作用：获取当前热门素材常见的开头钩子和 hook 模式。
- 必填参数：
  - `game_genre`：游戏品类，如 `casual`、`puzzle`、`rpg`

### `validate_creative_spec`

- 作用：校验广告素材文件是否符合平台投放规格。
- 必填参数：
  - `file_path`：素材文件路径，如 `assets/casual_video_01.mp4`
  - `platform`：投放平台，如 `Meta`、`Google`、`Tiktok`

### `upload_creative_asset`

- 作用：上传单个广告素材到指定 campaign。
- 必填参数：
  - `file_path`：素材文件路径
  - `campaign_id`：Campaign ID，如 `CMP_1024`

### `batch_upload_creatives`

- 作用：批量上传多个广告素材到指定 campaign。
- 必填参数：
  - `file_paths`：素材文件路径列表
  - `campaign_id`：Campaign ID，如 `CMP_1024`

### `get_campaign_metrics`

- 作用：查询 campaign 层级的核心投放指标。
- 必填参数：
  - `campaign_id`：Campaign ID，如 `CMP_1024`

### `get_creative_performance`

- 作用：查询素材层级的表现数据。
- 必填参数：
  - `campaign_id`：Campaign ID，如 `CMP_1024`

### `get_appsflyer_report`

- 作用：获取 AppsFlyer 归因和留存报表。
- 必填参数：
  - `app_id`：App ID，如 `APP_2048`

### `compare_campaigns`

- 作用：对比多个 campaign 的关键指标表现。
- 必填参数：
  - `campaign_ids`：待对比的 Campaign ID 列表

### `detect_anomalies`

- 作用：检测 campaign 关键指标的异常波动。
- 必填参数：
  - `campaign_id`：Campaign ID，如 `CMP_1024`

### `get_optimization_playbook`

- 作用：根据问题类型返回结构化优化建议。
- 必填参数：
  - `issue_type`：问题类型，如 `low_roas`、`low_ctr`、`creative_fatigue`

### `query_knowledge_base`

- 作用：查询 UA 和广告投放知识库内容。
- 必填参数：
  - `question`：知识问答问题

### `get_benchmark_data`

- 作用：查询行业 benchmark 数据，如 ROAS、Retention、CTR、CPI 基准。
- 必填参数：
  - `metric`：目标指标，如 `roas`、`retention_d1`、`ctr`、`cpi`
  - `game_genre`：游戏品类，如 `casual`、`puzzle`、`rpg`

### `get_platform_policy`

- 作用：查询广告平台政策、格式限制和内容限制。
- 必填参数：
  - `platform`：投放平台，如 `Meta`、`Google`、`Tiktok`
  - `policy_type`：政策类型，如 `ad_format`、`content_restriction`、`targeting`
