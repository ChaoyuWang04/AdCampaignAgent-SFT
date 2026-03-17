# Ad Campaign Agent SFT Dataset — Quality Report

> Generated: 2026-03-16 22:45
> Source file: `ad_agent_sft_20260316_224504_en_sharegpt.json`
> Format detected: **SHAREGPT** → normalized to OpenAI Messages

---

## 📋 Overview

| Metric | Value |
|--------|-------|
| Total conversations | **1,000** |
| Input format | SHAREGPT |
| With tool calls | 900 (90.0%) |
| With clarification turn | 102 (10.2%) |
| Refusal conversations | 100 (10.0%) |
| Unique tools covered | 15 |
| Distinct scene tags | 23 |
| Format errors | ✅ 0 — clean |
| Platforms | Applovin, Google, Meta, Tiktok, Unity |
| Game genres | casual, hyper_casual, puzzle, rpg, strategy |

---

## 1. Workflow Distribution

![workflow distribution](fig1_workflow.png)

| Workflow | Count | % |
|----------|------:|--:|
| Multi-Dimensional Deep Analysis | 350 | 35.0% |
| Anomaly Diagnosis & Optimization | 150 | 15.0% |
| Single Metric Query | 120 | 12.0% |
| Creative Search | 120 | 12.0% |
| Refusal | 100 | 10.0% |
| Creative Upload | 80 | 8.0% |
| Knowledge Q&A | 80 | 8.0% |

---

## 2. Scene Tag Distribution

![scene tag distribution](fig2_scene.png)

| Scene Tag | Count | % |
|-----------|------:|--:|
| `creative_search` | 120 | 12.0% |
| `roas_danger` | 94 | 9.4% |
| `both_danger` | 90 | 9.0% |
| `ret_danger` | 85 | 8.5% |
| `healthy` | 60 | 6.0% |
| `creative_fatigue` | 59 | 5.9% |
| `both_warning` | 58 | 5.8% |
| `budget_underdelivery` | 47 | 4.7% |
| `ret_warning` | 46 | 4.6% |
| `roas_warning` | 44 | 4.4% |
| `insufficient_data` | 37 | 3.7% |
| `off_topic` | 34 | 3.4% |
| `unauthorized_operation` | 33 | 3.3% |
| `insufficient_data_to_answer` | 33 | 3.3% |
| `upload_partial_fail` | 31 | 3.1% |
| `upload_success` | 30 | 3.0% |
| `creative_guideline` | 27 | 2.7% |
| `bidding_strategy` | 21 | 2.1% |
| `industry_benchmark` | 15 | 1.5% |
| `platform_policy` | 15 | 1.5% |
| `validate_fail_size` | 10 | 1.0% |
| `validate_fail_format` | 9 | 0.9% |
| `knowledge_base` | 2 | 0.2% |

---

## 3. Conversation Length

![turn distribution](fig3_turn_dist.png)

| Stat | Value |
|------|-------|
| Min | 3 turns |
| Max | 13 turns |
| Mean | 7.18 turns |
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
| Total / conv | 275 | 691 | 689 | 1048 | 1137 |
| User turns | 3 | 15 | 16 | 22 | 27 |
| Assistant turns | 48 | 188 | 212 | 298 | 374 |

---

## 5. Tool Call Statistics

![tool frequency](fig5_tool_freq.png)

### Tool Chain Length

| Chain Length | Count | % |
|-------------|------:|--:|
| 0 tool(s) | 100 | 10.0% |
| 1 tool(s) | 258 | 25.8% |
| 2 tool(s) | 282 | 28.2% |
| 3 tool(s) | 273 | 27.3% |
| 4 tool(s) | 87 | 8.7% |

### Individual Tool Call Frequency

| Tool | Calls | % of tool-call convs |
|------|------:|---------------------:|
| `get_benchmark_data` | 395 | 43.9% |
| `get_campaign_metrics` | 351 | 39.0% |
| `get_creative_performance` | 264 | 29.3% |
| `get_appsflyer_report` | 220 | 24.4% |
| `detect_anomalies` | 150 | 16.7% |
| `get_optimization_playbook` | 150 | 16.7% |
| `search_trending_creatives` | 96 | 10.7% |
| `compare_campaigns` | 82 | 9.1% |
| `validate_creative_spec` | 80 | 8.9% |
| `search_competitor_ads` | 52 | 5.8% |
| `batch_upload_creatives` | 39 | 4.3% |
| `get_trending_hooks` | 38 | 4.2% |
| `query_knowledge_base` | 32 | 3.6% |
| `upload_creative_asset` | 22 | 2.4% |
| `get_platform_policy` | 18 | 2.0% |

### Top 15 Tool Chain Combinations

| Chain | Count |
|-------|------:|
| `(no tools)` | 100 |
| `get_appsflyer_report → get_campaign_metrics → get_benchmark_...` | 91 |
| `get_campaign_metrics → get_creative_performance → get_benchm...` | 90 |
| `get_campaign_metrics → get_appsflyer_report → get_creative_p...` | 87 |
| `compare_campaigns → get_benchmark_data` | 82 |
| `detect_anomalies → get_optimization_playbook` | 58 |
| `detect_anomalies → get_campaign_metrics → get_optimization_p...` | 49 |
| `get_creative_performance` | 44 |
| `detect_anomalies → get_creative_performance → get_optimizati...` | 43 |
| `get_appsflyer_report` | 42 |
| `validate_creative_spec → batch_upload_creatives` | 39 |
| `search_trending_creatives → get_trending_hooks` | 38 |
| `get_campaign_metrics` | 34 |
| `get_benchmark_data` | 30 |
| `search_trending_creatives` | 30 |

---

## 6. Platform & Genre Diversity

![platform and genre](fig6_platform_genre.png)

### Platform

| Platform | Count | % |
|----------|------:|--:|
| Applovin | 215 | 21.5% |
| Unity | 211 | 21.1% |
| Meta | 204 | 20.4% |
| Google | 186 | 18.6% |
| Tiktok | 184 | 18.4% |

### Game Genre

| Genre | Count | % |
|-------|------:|--:|
| rpg | 209 | 20.9% |
| hyper_casual | 204 | 20.4% |
| casual | 199 | 19.9% |
| puzzle | 198 | 19.8% |
| strategy | 190 | 19.0% |

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
