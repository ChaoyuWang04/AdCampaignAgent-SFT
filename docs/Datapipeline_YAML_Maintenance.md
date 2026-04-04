# Datapipeline YAML 维护规范

本文档说明当前 `src/datapipeline/workflow/*.yaml` 的维护方式、增量规则和修改后必须同步的代码/文档项。

## 0. 历史背景

当前这套维护规则不是凭空设计出来的，而是来自一轮已经完成的 `required_slots` 治理。那一轮改造解决了 4 个核心问题：

1. query 缺关键槽位时，seed 仍然可能错误地产生 tool call
2. `build_tool_arguments()` 可能从上下文兜底，掩盖 query 本身缺信息的问题
3. clarify 的触发条件分散在各 workflow 中，不够统一
4. intent / tool / required_slots 的一致性校验覆盖不足

这轮治理完成后，datapipeline 当前形成了 3 个稳定约束：

- required slot 由 YAML 显式声明
- seed 生成统一基于缺槽位判断 direct 或 clarify
- validator 会校验 tool_chain 与 required_slots 是否一致

因此后续维护 YAML 时，不要再回到“query 大致合理就先塞进去”的旧做法，而应该把 `required_slots` 当成 bucket 设计的一部分一起维护。

## 1. 当前源码分工

YAML 不是独立生效的，当前 datapipeline 由 4 层共同定义：

1. [`src/datapipeline/workflow/*.yaml`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/workflow)
   - 定义 workflow、bucket、scene、query 模板、tool_plan、required_slots
2. [`src/datapipeline/0_generate_base_dataset.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/0_generate_base_dataset.py)
   - 把 YAML 实例化为 seed
   - 决定 clarify 还是 direct
3. [`src/datapipeline/2_convert_dataset.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/2_convert_dataset.py)
   - 把 seed 转成 OpenAI Messages 样本
   - 决定 tool arguments、mock tool result、final assistant 回复
4. [`src/datapipeline/validate_intent_bindings.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/validate_intent_bindings.py)
   - 校验 intent、tool_chain、required_slots 是否一致

结论：**改 YAML 不是只改配置**。只要 YAML 改动改变了语义、slot 要求或 refusal type，就必须检查这 4 层是否仍一致。

## 2. 什么时候改 query，什么时候改 bucket，什么时候改 scene

### 改 query 模板

适用条件：

- intent 不变
- tool_plan 不变
- required_slots 不变
- final response 逻辑不需要新分支

例子：

- 给 `campaign_metrics` 增加一条新的 ROAS 查询说法
- 给 `off_topic` 补一条新的域外问题模板

### 新增 bucket

适用条件：

- 同一 workflow 内出现新的稳定意图
- 需要不同 tool_plan
- 或需要不同 required_slots
- 或需要明显不同的 final response 逻辑

例子：

- workflow 3 里把 `campaign_metrics`、`creative_metrics`、`appsflyer_report` 分开
- workflow 7 把 `unauthorized_internal` 和 `unauthorized_external` 分开

### 新增 scene

适用条件：

- intent 不变
- tool_plan 基本不变
- 但 mock 数值分布、异常标签或末轮总结风格需要区分

例子：

- workflow 4 的 `roas_warning / roas_danger / creative_fatigue`
- workflow 5 的 `budget_underdelivery / creative_fatigue`

### 新增 workflow

只有在下面三项同时成立时才建议新开 workflow：

- 用户目标类别明显不同
- 复用现有 workflow 会让 bucket/scene 边界变脏
- tool 行为和 final answer 结构已经不适合挂在现有 workflow 下

## 3. YAML 设计硬规则

### 3.1 query 与 required_slots 必须一致

如果 bucket 写了：

```yaml
required_slots: ["app_id"]
```

那么 direct query 必须能显式提供 `app_id`，否则就会被转 clarify。

不要再出现这种错误：

```yaml
queries:
  - "拉一下{campaign_id}最近7天的收入归因"
required_slots: ["app_id"]
```

### 3.2 不要保留死 clarify 配置

如果一个 bucket 的所有 query 都已经自带某个槽位，就不要保留永远不会触发的：

- `required_slots`
- `clarification_reason`
- `answer_templates`

除非你明确要保留它作为未来扩展接口，并且文档里说明“当前不可达”。

### 3.3 clarify-only 是当前默认语义

当前实现里，只要样本因为缺槽位进入 clarify，并且 `tool_plan` 被清空，那么 convert 后的标准形态就是：

```text
system -> user -> assistant(追问) -> user(补充)
```

不会继续调工具。

这意味着：

- 你可以通过 YAML 增加 clarify-only 样本
- 但**不能**只靠 YAML 实现“追问后继续 tool call”

如果未来需要 clarify 后继续执行工具，必须同时改：

- [`0_generate_base_dataset.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/0_generate_base_dataset.py)
- [`2_convert_dataset.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/2_convert_dataset.py)

### 3.4 tool_plan 的 group 只在表达阶段边界时有意义

下面这种写法只是冗余：

```yaml
- mode: "serial"
  tools: ["a"]
- mode: "serial"
  tools: ["b"]
- mode: "serial"
  tools: ["c"]
```

如果没有真实的阶段边界，应合并成：

```yaml
- mode: "serial"
  tools: ["a", "b", "c"]
```

只有在这种情况下才保留多个 group：

- 需要先 `parallel`
- 然后再 `serial`
- 或者后续代码真的会消费 group 边界

### 3.5 refusal_type 必须按拒绝理由分开

不要把“内部高风险越权”和“外部未授权/违规访问”混到一个 refusal_type。

原则是：

- 同一个 refusal_type 内，assistant 的拒绝理由应该稳定一致
- 如果拒绝理由不同，就应该拆 refusal_type

## 4. 语义设计原则

下面这些原则来自早期 `intent_matrix` 审查的稳定结论，已经从“阶段性问题清单”沉淀为长期维护规则。

### 4.1 Seed 层

- 不允许“先随机 query，再随机 tool_plan”
- `bucket` 是第一层语义单位，`scene` 是第二层表现单位
- `scene_tag` 应服务于结果表达，不应承担全部 intent 分类职责

### 4.2 Tool 参数层

- 参数必须能追溯到 query 显式信息或追问补充信息
- 关键槽位缺失时必须转 clarify，不能静默回退到上下文
- 只有不影响语义的次要字段允许随机，例如 `top_k`、部分 mock `ad_group_id`

### 4.3 Final Response 层

- 终态回复必须消费至少一个 tool 返回的关键信息
- 不允许只说“已查询完成”“以上是结果”
- 不同工具链必须对应不同摘要模板

### 4.4 拒答与追问边界

- 信息不足优先进入 clarify，不应误塞进 refusal
- refusal 样本不得带业务工具调用
- 如果拒答理由不同，应优先拆 refusal_type，而不是在同一类型里混写

### 4.5 什么时候允许多工具链

- 同一 bucket 内只保留语义稳定的工具组合
- 如果某个 query 只有在非常特定条件下才需要第二个工具，不应把该组合设成默认 bucket 行为
- 只有当 query 本身明确表达复合意图时，才考虑 hybrid bucket 或多工具组合

## 5. 增量修改 checklist

每次改 YAML，至少走完下面这份清单。

### Step 1：先判断改动类型

- 只是补 query 模板
- 还是改了 required_slots
- 还是改了 tool_plan
- 还是改了 refusal_type / scene_tag / intent_bucket

### Step 2：补测试

优先补这几类测试：

- loader 测试：YAML 字段存在性和结构
- generator 测试：生成后的 `intent_bucket / scene_tag / tool_chain / clarification_reason`
- convert 测试：tool arguments、refusal 文案、final answer
- validator 测试：required_slots 与 tool_chain 一致性

### Step 3：运行测试

最少跑：

```bash
uv run pytest tests/datapipeline -q
```

如果改了 refusal / convert / tool arguments，建议顺手跑 targeted test。

### Step 4：同步文档

至少检查：

- [Datapipeline_Seed.md](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/docs/Datapipeline_Seed.md)
- [Data_WorkflowPreview.md](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/docs/Data_WorkflowPreview.md)

如果改动影响：

- bucket 模板数
- clarify 占比
- refusal type 数量
- scene/tool 链绑定

就必须同步文档。

### Step 5：必要时重新生成数据

如果仓库里还维护一批“当前推荐 seed 文件”，并且你希望它们和最新 YAML 保持一致，就要重新执行：

```bash
uv run python src/datapipeline/0_generate_base_dataset.py
uv run python src/datapipeline/1_split_dataset.py
uv run python src/datapipeline/2_convert_dataset.py
uv run python src/datapipeline/3_conversation_splitter.py
```

## 6. 自动验证关注点

虽然验证逻辑分散在测试和 [`validate_intent_bindings.py`](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/datapipeline/validate_intent_bindings.py) 中，但长期应持续覆盖下面 4 类检查：

### 6.1 intent / tool 绑定一致性

- 每条 seed 都应能被 `intent -> allowed_tools` 规则验证
- clarify / refusal 样本应满足 `tool_chain == []`

### 6.2 参数来源一致性

典型规则：

- query 提到 `Playrix`，`competitor_name` 必须是 `Playrix`
- query 提到 `CPM benchmark`，`metric` 不能退化成 `roas`
- query 提到 `按CTR排序`，`sort_by` 必须是 `ctr`

### 6.3 final answer 消费 tool result

- `get_campaign_metrics` 至少应在终态文本里体现 `roas / ctr / cpi / spend / installs` 之一
- `get_benchmark_data` 至少应体现 `benchmark / p25 / p50 / p75` 之一
- `upload_creative_asset` 至少应体现 `asset_id / review_status`

### 6.4 clarify / refusal 一致性

- 信息不足类 query 应落到 clarify，而不是 refusal
- refusal 样本不应伪装成正常业务回答

## 7. 未来增量规则

### 7.1 优先做“局部增量”，避免大改

优先顺序：

1. 补 query 模板
2. 调整 bucket 归属
3. 调整 required_slots
4. 调整 scene/tool 链绑定
5. 只有必要时再开新 workflow

### 7.2 优先维持 intent-tool 稳定性

对训练数据最重要的不是模板多，而是：

- query 语义稳定
- tool_chain 稳定
- refusal 理由稳定
- final answer 稳定消费 tool result

宁可少加几条 query，也不要让一个 bucket 内混入不同工具语义。

### 7.3 任何新增模板都要问自己 4 个问题

1. 这条 query 属于现有 bucket 吗？
2. 它需要的槽位和当前 required_slots 一致吗？
3. 它会不会把一个合理请求误教成 refusal？
4. 它的 final answer / refusal 文案是否仍然语义正确？

只要有一个答案是否定的，就不应该直接塞进现有 bucket。

### 7.4 统计文档以“当前 YAML”为准，不要混用旧 seed 快照

如果未来还要保留历史 seed 分布分析，请单独写“历史快照文档”。  
当前的产品和训练决策，应以：

- 当前 YAML
- 当前 generator / convert 代码
- 当前 tests

这三者共同定义的“静态规则版本”为准。
