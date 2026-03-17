# Ad Campaign Agent SFT Dataset — Quality Report

> Generated: 2026-03-16 21:48
> Source file: `ad_agent_sft_20260316_214235_cn_sharegpt.json`
> Format detected: **SHAREGPT** → normalized to OpenAI Messages

---

## 📋 Overview

| Metric | Value |
|--------|-------|
| Total conversations | **1,000** |
| Input format | SHAREGPT |
| With tool calls | 900 (90.0%) |
| With clarification turn | 96 (9.6%) |
| Refusal conversations | 100 (10.0%) |
| Unique tools covered | 15 |
| Distinct scene tags | 22 |
| Format errors | ✅ 0 — clean |
| Platforms | Applovin, Google, Meta, Tiktok, Unity |
| Game genres | casual, hyper_casual, puzzle, rpg, strategy |

---

## 1. Workflow Distribution

![workflow distribution](fig1_workflow.png)

| Workflow | Count | % |
|----------|------:|--:|
| 多维深度分析 | 350 | 35.0% |
| 异常诊断与优化 | 150 | 15.0% |
| 素材搜寻 | 120 | 12.0% |
| 单指标效果查询 | 120 | 12.0% |
| 拒答 | 100 | 10.0% |
| 知识问答 | 80 | 8.0% |
| 素材上传 | 80 | 8.0% |

---

## 2. Scene Tag Distribution

![scene tag distribution](fig2_scene.png)

| Scene Tag | Count | % |
|-----------|------:|--:|
| `creative_search` | 120 | 12.0% |
| `roas_danger` | 96 | 9.6% |
| `both_danger` | 90 | 9.0% |
| `ret_danger` | 80 | 8.0% |
| `budget_underdelivery` | 65 | 6.5% |
| `ret_warning` | 62 | 6.2% |
| `creative_fatigue` | 48 | 4.8% |
| `roas_warning` | 48 | 4.8% |
| `healthy` | 48 | 4.8% |
| `both_warning` | 47 | 4.7% |
| `insufficient_data` | 36 | 3.6% |
| `off_topic` | 34 | 3.4% |
| `insufficient_data_to_answer` | 33 | 3.3% |
| `unauthorized_operation` | 33 | 3.3% |
| `upload_partial_fail` | 33 | 3.3% |
| `upload_success` | 29 | 2.9% |
| `creative_guideline` | 28 | 2.8% |
| `bidding_strategy` | 24 | 2.4% |
| `industry_benchmark` | 15 | 1.5% |
| `platform_policy` | 13 | 1.3% |
| `validate_fail_size` | 10 | 1.0% |
| `validate_fail_format` | 8 | 0.8% |

---

## 3. Conversation Length

![turn distribution](fig3_turn_dist.png)

| Stat | Value |
|------|-------|
| Min | 3 turns |
| Max | 13 turns |
| Mean | 7.20 turns |
| Median | 7.0 turns |
| Std dev | 2.36 |
| p25 | 5 |
| p75 | 9 |
| p90 | 11 |

---

## 4. Token Distribution (approx)

> Estimation method: Chinese characters ≈ 1 token/char, English ≈ 1 token/4 chars

![token distribution](fig4_token_dist.png)

| Scope | Min | Mean | Median | p90 | Max |
|-------|----:|-----:|-------:|----:|----:|
| Total / conv | 264 | 673 | 653 | 1036 | 1125 |
| User turns | 4 | 15 | 15 | 19 | 26 |
| Assistant turns | 48 | 185 | 210 | 291 | 354 |

---

## 5. Tool Call Statistics

![tool frequency](fig5_tool_freq.png)

### Tool Chain Length

| Chain Length | Count | % |
|-------------|------:|--:|
| 0 tool(s) | 100 | 10.0% |
| 1 tool(s) | 250 | 25.0% |
| 2 tool(s) | 291 | 29.1% |
| 3 tool(s) | 265 | 26.5% |
| 4 tool(s) | 94 | 9.4% |

### Individual Tool Call Frequency

| Tool | Calls | % of tool-call convs |
|------|------:|---------------------:|
| `get_benchmark_data` | 387 | 43.0% |
| `get_campaign_metrics` | 357 | 39.7% |
| `get_creative_performance` | 247 | 27.4% |
| `get_appsflyer_report` | 220 | 24.4% |
| `detect_anomalies` | 150 | 16.7% |
| `get_optimization_playbook` | 150 | 16.7% |
| `compare_campaigns` | 99 | 11.0% |
| `search_trending_creatives` | 94 | 10.4% |
| `validate_creative_spec` | 80 | 8.9% |
| `search_competitor_ads` | 60 | 6.7% |
| `query_knowledge_base` | 39 | 4.3% |
| `upload_creative_asset` | 35 | 3.9% |
| `get_trending_hooks` | 35 | 3.9% |
| `batch_upload_creatives` | 27 | 3.0% |
| `get_platform_policy` | 23 | 2.6% |

### Top 15 Tool Chain Combinations

| Chain | Count |
|-------|------:|
| `(no tools)` | 100 |
| `compare_campaigns → get_benchmark_data` | 99 |
| `get_campaign_metrics → get_appsflyer_report → get_creative_p...` | 94 |
| `get_appsflyer_report → get_campaign_metrics → get_benchmark_...` | 88 |
| `get_campaign_metrics → get_creative_performance → get_benchm...` | 69 |
| `detect_anomalies → get_campaign_metrics → get_optimization_p...` | 64 |
| `detect_anomalies → get_creative_performance → get_optimizati...` | 44 |
| `detect_anomalies → get_optimization_playbook` | 42 |
| `get_campaign_metrics` | 42 |
| `get_creative_performance` | 40 |
| `get_appsflyer_report` | 38 |
| `validate_creative_spec → upload_creative_asset` | 35 |
| `search_trending_creatives → get_trending_hooks` | 35 |
| `search_competitor_ads → search_trending_creatives` | 34 |
| `validate_creative_spec → batch_upload_creatives` | 27 |

---

## 6. Platform & Genre Diversity

![platform and genre](fig6_platform_genre.png)

### Platform

| Platform | Count | % |
|----------|------:|--:|
| Unity | 215 | 21.5% |
| Tiktok | 207 | 20.7% |
| Applovin | 205 | 20.5% |
| Google | 188 | 18.8% |
| Meta | 185 | 18.5% |

### Game Genre

| Genre | Count | % |
|-------|------:|--:|
| rpg | 227 | 22.7% |
| casual | 202 | 20.2% |
| hyper_casual | 202 | 20.2% |
| puzzle | 196 | 19.6% |
| strategy | 173 | 17.3% |

---

## 7. Last Turn Type Distribution

| Turn Type | Count | % |
|-----------|------:|--:|
| `assistant_text` | 1000 | 100.0% |

---

## 8. Format Validation

| Check | Result |
|-------|--------|
| tool_call_id pairing | ✅ All matched |
| Last turn non-empty | ✅ OK |
| System message first | ✅ OK |



---

*Report generated by `3_analyze_dataset.py`*
