#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ad Campaign Agent - Phase 2: Conversation Generator
Format: OpenAI Messages (role/content/tool_calls/tool_call_id)
Input:  ad_agent_seeds_*.json  (from 1.1_ad_gen_data_cn.py / 1.2_ad_gen_data_en.py)
Output: ad_agent_sft_dataset.json (HuggingFace / LLaMA Factory ready)
"""

import json
import uuid
import random
from pathlib import Path
from typing import Dict, List, Tuple, Any
from tqdm import tqdm


# ─────────────────────────────────────────────────────────────
# 1. System Prompt
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "zh": """你是一个专业的移动游戏广告投放 AI 助手（Ad Campaign Agent），服务于 UA（用户获取）团队。

## 核心职责
- 以 ROAS 和用户留存（Retention）安全基线为核心，评估 Campaign 健康状态
- 识别指标异常，给出结构化优化建议
- 搜索热门素材、管理素材上传流程
- 回答出价策略、平台政策、行业 benchmark 等专业知识

## 工作原则
- 分析时始终明确指出 ROAS / Retention 是否达到安全基线，数据说话
- 信息不足时主动追问，一次只问一个关键信息
- 上传素材前必须先调用 validate_creative_spec 校验规格
- 超出能力范围或涉及越权操作时，礼貌拒绝并说明原因""",
    "en": """You are a professional mobile game advertising AI assistant (Ad Campaign Agent) serving the UA (User Acquisition) team.

## Core Responsibilities
- Evaluate campaign health with ROAS and user Retention safety baselines as the primary metrics
- Identify metric anomalies and provide structured optimization recommendations
- Search for trending creatives and manage creative upload workflows
- Answer professional questions on bidding strategies, platform policies, and industry benchmarks

## Working Principles
- Always explicitly state whether ROAS / Retention meets the safety baseline when analyzing — let the data speak
- Proactively ask for missing information when needed; ask only one key question at a time
- Always call validate_creative_spec to check specifications before uploading creatives
- Politely decline and explain the reason when a request is out of scope or involves unauthorized operations""",
}

UI_TEXT = {
    "zh": {
        "loaded": "✅ 加载种子记录：{count} 条",
        "desc": "生成对话",
        "skip": "⚠️  跳过：{error}",
        "done": "\n✅ 生成完成：{count} 条对话，失败 {failed} 条",
        "avg_turns": "📊 平均消息轮数：{value:.1f} turns",
        "workflow_distribution": "\n📋 工作流分布:",
        "scene_distribution": "\n🏷  场景分布 (Top 12):",
        "saved": "\n💾 已保存：{path}",
        "lang_prompt": "请选择语言 (zh/en): ",
        "invalid_lang": "❌ 语言输入无效，请输入 zh 或 en。",
        "file_prompt": "Input JSON file name: ",
        "file_not_found": "❌ 数据文件没有找到: {name} (在 {data_dir} 和 {script_dir} 两个路径中)",
        "found_input": "📂 Found input: {path}",
        "output_path": "💾 输出的结果已保存至: {path}",
    },
    "en": {
        "loaded": "✅ Loaded seed records: {count}",
        "desc": "Generating conversations",
        "skip": "⚠️  Skipped: {error}",
        "done": "\n✅ Generation complete: {count} conversations, {failed} failed",
        "avg_turns": "📊 Average message turns: {value:.1f} turns",
        "workflow_distribution": "\n📋 Workflow distribution:",
        "scene_distribution": "\n🏷  Scene distribution (Top 12):",
        "saved": "\n💾 Saved: {path}",
        "lang_prompt": "Choose language (zh/en): ",
        "invalid_lang": "❌ Invalid language. Please enter zh or en.",
        "file_prompt": "Input JSON file name: ",
        "file_not_found": "❌ File not found: {name} (searched in {data_dir} and {script_dir})",
        "found_input": "📂 Found input: {path}",
        "output_path": "💾 Output will be saved to: {path}",
    },
}


# ─────────────────────────────────────────────────────────────
# 2. Scene Config
# ─────────────────────────────────────────────────────────────

SCENE_CFG = {
    "healthy":              {"roas_mult": (1.05, 1.25), "ret_mult": (1.05, 1.20),
                             "ctr_range": (0.030, 0.055), "cpi_mult": (0.80, 0.93)},
    "roas_warning":         {"roas_mult": (0.80, 0.90), "ret_mult": (0.98, 1.08),
                             "ctr_range": (0.022, 0.035), "cpi_mult": (1.05, 1.18)},
    "roas_danger":          {"roas_mult": (0.48, 0.74), "ret_mult": (0.95, 1.05),
                             "ctr_range": (0.018, 0.030), "cpi_mult": (1.22, 1.55)},
    "ret_warning":          {"roas_mult": (0.98, 1.08), "ret_mult": (0.80, 0.90),
                             "ctr_range": (0.032, 0.055), "cpi_mult": (0.88, 0.98)},
    "ret_danger":           {"roas_mult": (0.95, 1.05), "ret_mult": (0.48, 0.74),
                             "ctr_range": (0.038, 0.065), "cpi_mult": (0.78, 0.92)},
    "both_warning":         {"roas_mult": (0.80, 0.90), "ret_mult": (0.80, 0.90),
                             "ctr_range": (0.020, 0.032), "cpi_mult": (1.12, 1.28)},
    "both_danger":          {"roas_mult": (0.45, 0.68), "ret_mult": (0.45, 0.68),
                             "ctr_range": (0.014, 0.025), "cpi_mult": (1.32, 1.65)},
    "creative_fatigue":     {"roas_mult": (1.00, 1.10), "ret_mult": (1.00, 1.10),
                             "ctr_range": (0.012, 0.022), "cpi_mult": (1.08, 1.20)},
    "budget_underdelivery": {"roas_mult": (1.00, 1.12), "ret_mult": (1.00, 1.12),
                             "ctr_range": (0.025, 0.042), "cpi_mult": (1.00, 1.10)},
    "insufficient_data":    {"roas_mult": (0.90, 1.10), "ret_mult": (0.90, 1.10),
                             "ctr_range": (0.020, 0.045), "cpi_mult": (0.90, 1.10)},
}

NON_METRIC_SCENES = {
    "creative_search", "upload_success", "validate_fail_size",
    "validate_fail_format", "upload_partial_fail",
    "bidding_strategy", "creative_guideline", "platform_policy",
    "industry_benchmark", "knowledge_base",
    "off_topic", "unauthorized_operation", "insufficient_data_to_answer",
}


# ─────────────────────────────────────────────────────────────
# 3. MockToolExecutor
# ─────────────────────────────────────────────────────────────

class MockToolExecutor:
    """
    Generates numerically consistent mock tool results based on scene_tag + seed baselines.
    Core metrics are computed once in __init__ to ensure data consistency across all tools within the same conversation.
    """

    def __init__(self, seed: Dict, lang: str):
        self.seed        = seed
        self.lang        = lang
        self.scene       = seed.get("scene_tag", "healthy")
        self.cfg         = SCENE_CFG.get(self.scene, {})
        self.roas_bl_d7  = seed.get("roas_baseline_d7",  0.80)
        self.roas_bl_d30 = seed.get("roas_baseline_d30", 1.20)
        self.ret_bl_d1   = seed.get("ret_baseline_d1",   0.35)
        self.ret_bl_d7   = seed.get("ret_baseline_d7",   0.12)
        self.platform    = seed.get("platform",    "google_uac")
        self.genre       = seed.get("game_genre",  "casual")
        self.region      = seed.get("region",      "US")
        self.campaign_id = seed.get("campaign_id", "CMP_0000")
        self.app_id      = seed.get("app_id",      "com.example.game")
        self.date_range  = seed.get("date_range",  {"start": "2026-03-01", "end": "2026-03-07"})

        # Pre-compute core metrics (shared across all tools to ensure data consistency)
        if self.scene not in NON_METRIC_SCENES:
            rm  = self.cfg.get("roas_mult", (1.0, 1.0))
            rtm = self.cfg.get("ret_mult",  (1.0, 1.0))
            self._roas_d7  = round(self.roas_bl_d7 * random.uniform(*rm), 3)
            self._roas_d30 = round(
                self.roas_bl_d30
                * (self._roas_d7 / max(self.roas_bl_d7, 0.01))
                * random.uniform(0.95, 1.05), 3)
            self._ret_d1 = round(self.ret_bl_d1 * random.uniform(*rtm), 3)
            self._ret_d7 = round(
                self.ret_bl_d7
                * (self._ret_d1 / max(self.ret_bl_d1, 0.01))
                * random.uniform(0.95, 1.05), 3)
        else:
            self._roas_d7  = self.roas_bl_d7
            self._roas_d30 = self.roas_bl_d30
            self._ret_d1   = self.ret_bl_d1
            self._ret_d7   = self.ret_bl_d7

        cr             = self.cfg.get("ctr_range", (0.025, 0.045))
        cm             = self.cfg.get("cpi_mult",  (0.90, 1.10))
        base_cpi       = {"google_uac": 1.8, "meta": 1.5,
                          "tiktok": 1.2, "applovin": 1.0}.get(self.platform, 1.5)
        self._ctr      = round(random.uniform(*cr), 4)
        self._cpi      = round(base_cpi * random.uniform(*cm), 2)
        self._spend    = round(random.uniform(3000, 28000), 2)
        self._installs = max(1, int(self._spend / max(self._cpi, 0.1)))
        self._cpm      = round(self._cpi * self._ctr * 1000, 2) if self._ctr > 0 else 8.0

    # ── helpers ──────────────────────────────────────────────

    def _ok(self, data: Any) -> str:
        return json.dumps({"status": "success", "data": data}, ensure_ascii=False)

    def _err(self, msg: str) -> str:
        return json.dumps({"status": "error", "message": msg}, ensure_ascii=False)

    # ── Category 1: Creative Search ──────────────────────────

    def search_trending_creatives(self, **kw) -> str:
        items = [{
            "creative_id":   f"CR_{random.randint(10000,99999)}",
            "platform":      kw.get("platform", self.platform),
            "genre":         kw.get("game_genre", self.genre),
            "format":        random.choice(["video_15s", "video_30s", "playable"]),
            "hook_type":     random.choice(["gameplay_fail", "challenge", "ugc_style", "tutorial"]),
            "estimated_ctr": round(random.uniform(0.030, 0.075), 4),
            "heat_score":    round(random.uniform(70, 99), 1),
            "thumbnail_url": f"https://cdn.example.com/thumb/{random.randint(1000,9999)}.jpg",
        } for _ in range(min(kw.get("top_k", 10), 8))]
        return self._ok({"results": items, "total": len(items)})

    def search_competitor_ads(self, **kw) -> str:
        ads = [{
            "ad_id":           f"AD_{random.randint(10000,99999)}",
            "competitor":      kw.get("competitor_name", "Playrix"),
            "platform":        kw.get("platform", self.platform),
            "format":          random.choice(["video_15s", "video_30s", "image"]),
            "creative_theme":  random.choice(["puzzle_difficulty", "emotional_story", "speed_challenge"]),
            "estimated_spend": f"${random.randint(5,80)}K/week",
            "first_seen":      f"2026-03-{random.randint(1,10):02d}",
        } for _ in range(min(kw.get("limit", 20), 6))]
        return self._ok({"competitor": kw.get("competitor_name", "Playrix"), "ads": ads})

    def get_trending_hooks(self, **kw) -> str:
        hooks = [
            {"hook": "90%的人第一关都过不了", "type": "challenge", "avg_ctr": 0.062},
            {"hook": "你能撑过第3关吗？", "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[真实玩家录屏] 我卡了3天的关", "type": "ugc_style", "avg_ctr": 0.055},
            {"hook": "这个谜题难倒了99%的人", "type": "difficulty", "avg_ctr": 0.051},
            {"hook": "帮帮我！我快崩了", "type": "emotional", "avg_ctr": 0.049},
        ] if self.lang == "zh" else [
            {"hook": "90% of players can't pass the first level", "type": "challenge", "avg_ctr": 0.062},
            {"hook": "Can you survive past level 3?", "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[Real player recording] Stuck on this for 3 days", "type": "ugc_style", "avg_ctr": 0.055},
            {"hook": "This puzzle stumped 99% of people", "type": "difficulty", "avg_ctr": 0.051},
            {"hook": "Help! I'm about to rage quit", "type": "emotional", "avg_ctr": 0.049},
        ]
        return self._ok({"genre": kw.get("game_genre", self.genre),
                         "hooks": hooks[:random.randint(3, 5)]})

    # ── Category 2: Creative Upload ──────────────────────────

    def validate_creative_spec(self, **kw) -> str:
        if self.scene == "validate_fail_size":
            return self._ok({"valid": False, "errors": [{
                "field": "file_size",
                "message": "文件大小 58.3MB 超过平台上限 50MB" if self.lang == "zh" else "File size 58.3MB exceeds platform limit of 50MB",
                "platform_limit": "50MB", "actual": "58.3MB"}]})
        if self.scene == "validate_fail_format":
            return self._ok({"valid": False, "errors": [{
                "field": "resolution",
                "message": "分辨率 1280x960 不符合要求，需为 9:16 或 1:1" if self.lang == "zh" else "Resolution 1280x960 does not meet requirements; must be 9:16 or 1:1",
                "platform_limit": "1080x1920 or 1080x1080", "actual": "1280x960"}]})
        return self._ok({"valid": True,
                         "file_size": f"{random.uniform(8,35):.1f}MB",
                         "resolution": "1080x1920",
                         "duration": f"{random.choice([15,30])}s",
                         "format": "MP4", "checks_passed": 5})

    def upload_creative_asset(self, **kw) -> str:
        if self.scene == "upload_partial_fail":
            return self._ok({"asset_id": f"ASSET_{random.randint(1000,9999)}",
                             "status": "partial",
                             "warning": "素材已上传但审核待定，预计12小时内完成审核" if self.lang == "zh" else "Asset uploaded but review is pending; estimated review time is 12 hours"})
        return self._ok({"asset_id": f"ASSET_{random.randint(1000,9999)}",
                         "status": "uploaded",
                         "creative_name": kw.get("creative_name", "new_creative"),
                         "campaign_id": kw.get("campaign_id", self.campaign_id),
                         "review_status": "pending",
                         "estimated_review": "2-4 hours"})

    def batch_upload_creatives(self, **kw) -> str:
        files   = kw.get("file_paths", ["f1.mp4", "f2.mp4", "f3.mp4"])
        failed  = random.randint(0, 1) if self.scene == "upload_partial_fail" else 0
        success = len(files) - failed
        results = [{"file": f, "status": "uploaded",
                    "asset_id": f"ASSET_{random.randint(1000,9999)}"}
                   for f in files[:success]]
        if failed:
            results.append({"file": files[-1], "status": "failed",
                             "reason": "file_size_exceeded"})
        return self._ok({"total": len(files), "success": success,
                         "failed": failed, "results": results})

    # ── Category 3: Campaign Analysis ────────────────────────

    def get_campaign_metrics(self, **kw) -> str:
        metrics_req = kw.get("metrics",
            ["roas","retention_d1","retention_d7","ctr","cpi","spend","installs"])
        result = {"campaign_id": self.campaign_id,
                  "date_range": self.date_range,
                  "breakdown": kw.get("breakdown", "daily"),
                  "metrics": {}}
        for m in metrics_req:
            if   m == "roas":           result["metrics"][m] = {"d7": self._roas_d7, "d30": self._roas_d30}
            elif m == "retention_d1":   result["metrics"][m] = self._ret_d1
            elif m == "retention_d7":   result["metrics"][m] = self._ret_d7
            elif m == "ctr":            result["metrics"][m] = self._ctr
            elif m == "cpi":            result["metrics"][m] = self._cpi
            elif m == "spend":          result["metrics"][m] = self._spend
            elif m == "installs":       result["metrics"][m] = self._installs
            elif m == "cpm":            result["metrics"][m] = self._cpm
            elif m == "impressions":    result["metrics"][m] = int(self._spend / max(self._cpm/1000, 0.001))
        if self.scene == "creative_fatigue":
            result["ctr_wow_change"]  = round(random.uniform(-0.38, -0.28), 3)
            result["fatigue_signal"]  = "CTR 连续下滑超过3天，建议换量" if self.lang == "zh" else "CTR has been declining for 3+ consecutive days; creative refresh recommended"
        if self.scene == "budget_underdelivery":
            result["budget_delivery_rate"] = round(random.uniform(0.38, 0.62), 2)
            result["cpm_trend"]            = "持续走高" if self.lang == "zh" else "Consistently rising"
        return self._ok(result)

    def get_creative_performance(self, **kw) -> str:
        top_k     = kw.get("top_k", 10)
        creatives = []
        for i in range(min(top_k, 6)):
            decay = 1 - i * 0.12
            creatives.append({
                "creative_id": f"CR_{random.randint(10000,99999)}",
                "name":    f"{self.genre}_video_{i+1:02d}_{random.choice(['US','JP','SEA'])}",
                "format":  random.choice(["video_15s", "video_30s", "playable"]),
                "ctr":     round(self._ctr  * decay * random.uniform(0.90, 1.10), 4),
                "cpi":     round(self._cpi  * (1 + i*0.08) * random.uniform(0.95, 1.05), 2),
                "roas_d7": round(self._roas_d7 * decay * random.uniform(0.92, 1.08), 3),
                "spend":   round(self._spend * (0.35 / (i+1)), 2),
                "installs":max(1, int(self._installs * (0.35 / (i+1)))),
                "status":  "fatiguing" if (i >= 3 and self.scene == "creative_fatigue") else "active",
            })
        return self._ok({"campaign_id": self.campaign_id,
                         "sort_by": kw.get("sort_by", "ctr"),
                         "creatives": creatives,
                         "date_range": self.date_range})

    def get_appsflyer_report(self, **kw) -> str:
        return self._ok({
            "app_id":       self.app_id,
            "report_type":  kw.get("report_type", "retention"),
            "date_range":   self.date_range,
            "data": {
                "retention_d1":     self._ret_d1,
                "retention_d7":     self._ret_d7,
                "installs":         self._installs,
                "revenue_d7":       round(self._roas_d7  * self._spend, 2),
                "revenue_d30":      round(self._roas_d30 * self._spend, 2),
                "top_media_source": self.platform,
            }
        })

    def compare_campaigns(self, **kw) -> str:
        campaign_ids = kw.get("campaign_ids", [self.campaign_id, "CMP_9999"])
        comparisons  = []
        for i, cid in enumerate(campaign_ids):
            decay = 1 if i == 0 else random.uniform(0.70, 0.95)
            comparisons.append({
                "campaign_id": cid,
                "roas_d7":     round(self._roas_d7 * decay, 3),
                "ret_d1":      round(self._ret_d1  * decay, 3),
                "ret_d7":      round(self._ret_d7  * decay, 3),
                "cpi":         round(self._cpi / decay, 2),
                "spend":       round(self._spend   * decay, 2),
                "installs":    int(self._installs  * decay),
            })
        return self._ok({"comparison": comparisons, "date_range": self.date_range})

    def detect_anomalies(self, **kw) -> str:
        anomaly_map = {
            "roas_danger": [{"metric": "roas_d7", "severity": "critical",
                "value": self._roas_d7, "baseline": self.roas_bl_d7,
                "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                "possible_causes": ["CPI rising rapidly", "Increased low-quality traffic share", "CVR declining due to creative fatigue"]}],
            "roas_warning": [{"metric": "roas_d7", "severity": "warning",
                "value": self._roas_d7, "baseline": self.roas_bl_d7,
                "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                "possible_causes": ["Slightly elevated CPI", "Performance decline in some creatives"]}],
            "ret_danger": [{"metric": "retention_d1", "severity": "critical",
                "value": self._ret_d1, "baseline": self.ret_bl_d1,
                "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                "possible_causes": ["Creative attracting wrong user segment", "Issue in first-time user experience", "Inaccurate geo targeting"]}],
            "both_danger": [
                {"metric": "roas_d7", "severity": "critical",
                 "value": self._roas_d7, "baseline": self.roas_bl_d7,
                 "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                 "possible_causes": ["Overall campaign quality deteriorating"]},
                {"metric": "retention_d1", "severity": "critical",
                 "value": self._ret_d1, "baseline": self.ret_bl_d1,
                 "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                 "possible_causes": ["Extremely poor user quality", "Severe mismatch between creative and actual game content"]}],
            "creative_fatigue": [{"metric": "ctr", "severity": "warning",
                "value": self._ctr, "wow_change": "-32%",
                "possible_causes": ["Overexposure of primary creatives", "Audience largely saturated", "New creatives needed"]}],
            "budget_underdelivery": [{"metric": "budget_delivery_rate", "severity": "warning",
                "value": "52%",
                "possible_causes": ["CPM surged significantly", "Intense competition", "Bid too low"]}],
        }
        return self._ok({"campaign_id": self.campaign_id,
                         "anomalies": anomaly_map.get(self.scene, []),
                         "check_time": "2026-03-08T09:00:00Z"})

    def get_optimization_playbook(self, **kw) -> str:
        playbooks = {
            "low_roas":            ["Review CPI distribution across ad groups; pause units where CPI > 2x target",
                                    "Audit audience targeting for high-CPI creatives; narrow to core user segments",
                                    "Try switching bidding strategy to tCPA",
                                    "Add new creatives to reduce dependency on high-CPI assets"],
            "low_ctr":             ["Analyze common traits of top CTR creatives",
                                    "Pause creatives with CTR below 50% of industry average",
                                    "Reference competitor high-CTR creative directions and refresh creative library",
                                    "A/B test different hook types"],
            "creative_fatigue":    ["Launch 3-5 new creatives immediately covering different hook types",
                                    "Pause creatives with CTR week-over-week decline > 30%",
                                    "Slightly increase CPM bid to maintain impressions while accelerating creative rotation"],
            "budget_underdelivery":["Check if current bid is below the platform's recommended minimum",
                                    "Moderately raise tCPA/tROAS target to open up more auction opportunities",
                                    "Expand audience targeting scope"],
        }
        issue_map = {
            "roas_danger": "low_roas",   "roas_warning": "low_roas",
            "ret_danger":  "low_ctr",    "ret_warning":  "low_ctr",
            "both_danger": "low_roas",   "both_warning": "low_roas",
            "creative_fatigue":     "creative_fatigue",
            "budget_underdelivery": "budget_underdelivery",
        }
        resolved = issue_map.get(self.scene, kw.get("issue_type", "low_roas"))
        steps    = playbooks.get(resolved or "low_roas", playbooks["low_roas"])
        return self._ok({"issue_type": resolved, "steps": steps,
                         "estimated_impact": "medium-high",
                         "implementation_time": "1-2 days"})

    # ── Category 4: Knowledge Q&A ────────────────────────────

    def query_knowledge_base(self, **kw) -> str:
        domain = kw.get("domain", "bidding_strategy")
        chunks = {
            "bidding_strategy": [
                {"source": "UA Strategy Handbook v2.3",
                 "content": "tCPA is suitable for campaigns with sufficient installs (>50/week); "
                            "tROAS is suited for mature campaigns with enough in-app purchase data; "
                            "the learning period typically takes 7-14 days — avoid frequent bid adjustments during this time."},
                {"source": "UAC Best Practices",
                 "content": "Smart Bidding learning period is approximately 7 days; recommended to limit weekly bid adjustments to no more than 20%."}],
            "creative_guideline": [
                {"source": "Creative Specifications 2026 Q1",
                 "content": "The first 3 seconds of video are the golden hook window — show core gameplay or a high-difficulty challenge directly; "
                            "optimal length for hyper-casual is 15s, vertical 9:16; "
                            "recommended playable ad duration is 30-60s."}],
            "platform_policy": [
                {"source": "Google Ads Policy Center",
                 "content": "Game ads must clearly display PEGI/ESRB ratings; "
                            "in-app purchase disclosures must meet transparency requirements; "
                            "gambling-related content requires a special whitelist application."}],
            "industry_benchmark": [
                {"source": "2026 Q1 Mobile Game Advertising Report",
                 "content": f"The D7 ROAS benchmark for {self.genre} in the {self.region} market is approximately "
                            f"{self.roas_bl_d7:.2f}, and the D1 retention benchmark is approximately {self.ret_bl_d1:.1%}; "
                            "median CPI in the US market is approximately $1.5-3.0."}],
        }
        results = chunks.get(domain, chunks["bidding_strategy"])
        return self._ok({"question": kw.get("question", ""),
                         "domain": domain, "chunks": results,
                         "total": len(results)})

    def get_benchmark_data(self, **kw) -> str:
        metric  = kw.get("metric", "roas")
        data = {
            "roas":         {"d7":  {"p25": round(self.roas_bl_d7*0.75,3),
                                     "p50": round(self.roas_bl_d7,3),
                                     "p75": round(self.roas_bl_d7*1.25,3)},
                             "d30": {"p25": round(self.roas_bl_d30*0.75,3),
                                     "p50": round(self.roas_bl_d30,3),
                                     "p75": round(self.roas_bl_d30*1.25,3)}},
            "retention_d1": {"p25": round(self.ret_bl_d1*0.80,3),
                             "p50": round(self.ret_bl_d1,3),
                             "p75": round(self.ret_bl_d1*1.20,3)},
            "retention_d7": {"p25": round(self.ret_bl_d7*0.80,3),
                             "p50": round(self.ret_bl_d7,3),
                             "p75": round(self.ret_bl_d7*1.20,3)},
            "ctr":          {"p25": 0.018, "p50": 0.030, "p75": 0.048},
            "cpi":          {"p25": 0.90,  "p50": 1.60,  "p75": 2.80},
        }.get(metric, {})
        return self._ok({"metric": metric, "genre": self.genre,
                         "region": self.region, "platform": self.platform,
                         "benchmark": data})

    def get_platform_policy(self, **kw) -> str:
        platform    = kw.get("platform", self.platform)
        policy_type = kw.get("policy_type", "ad_format")
        policies = {
            "ad_format":           f"{platform} supports the following game ad formats: video (15s/30s), playable, native image; vertical 9:16 is the recommended format.",
            "content_restriction": f"{platform} prohibits graphic violence and deceptive game screenshots; age rating labels are required.",
            "targeting":           f"{platform} supports custom audiences, lookalike audiences, and interest targeting; COPPA prohibits targeting users under 13.",
            "billing":             f"{platform} uses CPM/CPC/CPA billing methods; minimum daily budget is $10.",
        }
        return self._ok({"platform": platform, "policy_type": policy_type,
                         "content": policies.get(policy_type, "Policy document not available")})

    # ── Unified Dispatcher ───────────────────────────────────

    def execute(self, tool_name: str, arguments: Dict) -> str:
        dispatch = {
            "search_trending_creatives": self.search_trending_creatives,
            "search_competitor_ads":     self.search_competitor_ads,
            "get_trending_hooks":         self.get_trending_hooks,
            "validate_creative_spec":    self.validate_creative_spec,
            "upload_creative_asset":     self.upload_creative_asset,
            "batch_upload_creatives":    self.batch_upload_creatives,
            "get_campaign_metrics":      self.get_campaign_metrics,
            "get_creative_performance":  self.get_creative_performance,
            "get_appsflyer_report":      self.get_appsflyer_report,
            "compare_campaigns":         self.compare_campaigns,
            "detect_anomalies":          self.detect_anomalies,
            "get_optimization_playbook": self.get_optimization_playbook,
            "query_knowledge_base":      self.query_knowledge_base,
            "get_benchmark_data":        self.get_benchmark_data,
            "get_platform_policy":       self.get_platform_policy,
        }
        fn = dispatch.get(tool_name)
        return fn(**arguments) if fn else self._err(f"Unknown tool: {tool_name}")


# ─────────────────────────────────────────────────────────────
# 4. Tool Arguments Builder
# ─────────────────────────────────────────────────────────────

def build_tool_arguments(tool_name: str, seed: Dict) -> Dict:
    cid    = seed["campaign_id"]
    aid    = seed["app_id"]
    dr     = seed["date_range"]
    plat   = seed["platform"]
    genre  = seed["game_genre"]
    region = seed["region"]
    scene  = seed.get("scene_tag", "")

    return {
        "search_trending_creatives": {
            "platform": plat, "game_genre": genre, "region": region,
            "time_range": 7, "top_k": 10},
        "search_competitor_ads": {
            "competitor_name": random.choice(["Playrix","Voodoo","Rollic","Jam City"]),
            "platform": plat, "limit": 20},
        "get_trending_hooks": {
            "game_genre": genre,
            "creative_type": random.choice(["video","playable"])},
        "validate_creative_spec": {
            "file_path": f"assets/{genre}_video_{random.randint(1,9):02d}.mp4",
            "platform": plat,
            "ad_format": random.choice(["interstitial","rewarded"])},
        "upload_creative_asset": {
            "file_path": f"assets/{genre}_video_{random.randint(1,9):02d}.mp4",
            "asset_type": "video", "campaign_id": cid,
            "ad_group_id": f"AG_{random.randint(100,999)}",
            "creative_name": f"{genre}_{region}_{dr['start']}_v{random.randint(1,9)}"},
        "batch_upload_creatives": {
            "file_paths": [f"assets/{genre}_v{i}.mp4" for i in range(1,4)],
            "campaign_id": cid,
            "naming_convention": "{genre}_{region}_{date}_{index}"},
        "get_campaign_metrics": {
            "campaign_id": cid,
            "metrics": ["roas","retention_d1","retention_d7","ctr","cpi","spend","installs"],
            "date_range": dr, "breakdown": "daily"},
        "get_creative_performance": {
            "campaign_id": cid, "sort_by": "ctr",
            "top_k": 10, "date_range": dr},
        "get_appsflyer_report": {
            "app_id": aid, "report_type": "retention",
            "date_range": dr, "groupby": ["media_source","country"]},
        "compare_campaigns": {
            "campaign_ids": [cid, f"CMP_{random.randint(1000,9999)}"],
            "metrics": ["roas","retention_d1","cpi","spend"],
            "date_range": dr},
        "detect_anomalies": {
            "campaign_id": cid,
            "metric": ("roas"         if "roas" in scene else
                       "retention_d1" if "ret"  in scene else "ctr"),
            "sensitivity": 0.75},
        "get_optimization_playbook": {
            "issue_type": {
                "roas_danger":"low_roas","roas_warning":"low_roas",
                "ret_danger":"low_ctr", "ret_warning":"low_ctr",
                "creative_fatigue":"creative_fatigue",
                "budget_underdelivery":"budget_underdelivery",
            }.get(scene, "low_roas")},
        "query_knowledge_base": {
            "question": seed.get("user_query", "UA strategy"),
            "domain":   scene if scene in
                        {"bidding_strategy","creative_guideline",
                         "platform_policy","industry_benchmark"}
                        else "bidding_strategy",
            "search_mode": "hybrid", "top_k": 5},
        "get_benchmark_data": {
            "metric": "roas", "game_genre": genre,
            "region": region, "platform": plat},
        "get_platform_policy": {
            "platform": plat,
            "policy_type": random.choice(["ad_format","content_restriction"])},
    }.get(tool_name, {})


# ─────────────────────────────────────────────────────────────
# 5. Final Response Templates
# ─────────────────────────────────────────────────────────────

def build_final_response(seed: Dict, ex: MockToolExecutor) -> str:
    scene   = seed.get("scene_tag", "healthy")
    cid     = seed["campaign_id"]
    rbl     = ex.roas_bl_d7
    rtbl    = ex.ret_bl_d1
    rbl7    = ex.ret_bl_d7
    r7      = ex._roas_d7
    d1      = ex._ret_d1
    d7      = ex._ret_d7
    ctr     = ex._ctr
    cpi     = ex._cpi
    spend   = ex._spend
    if ex.lang == "zh":
        rs = "✅ 达标" if r7 >= rbl else ("⚠️ 预警" if r7 >= rbl*0.80 else "🚨 告警")
        rts = "✅ 达标" if d1 >= rtbl else ("⚠️ 预警" if d1 >= rtbl*0.80 else "🚨 告警")
        rp = (r7/rbl - 1) * 100
        dp = (d1/rtbl - 1) * 100
        tpl = {
            "healthy": f"""**{cid} 投放健康报告**\n\n**核心指标 vs 安全基线**\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}，超出 {rp:+.1f}%）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}，超出 {dp:+.1f}%）\n- D7 留存：{d7:.1%}（基线 {rbl7:.1%}）\n\n**辅助指标**\n- CTR：{ctr:.2%} | CPI：${cpi:.2f} | 花费：${spend:,.0f}\n\n**结论**：当前 Campaign 整体健康，ROAS 和留存均超过安全基线。""",
            "roas_warning": f"""**{cid} ROAS 预警分析**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}，偏低 {abs(rp):.1f}%）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}）\n\n**建议**：检查高 CPI 的 Ad Group，并持续观察 3 天趋势。""",
            "roas_danger": f"""**{cid} ROAS 严重告警 🚨**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}，跌幅 {abs(rp):.1f}%）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}）\n\n**建议**：立即暂停低 ROAS 单元，降低预算并补充新素材。""",
            "ret_warning": f"""**{cid} 用户留存预警分析**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}，偏低 {abs(dp):.1f}%）\n\n**建议**：分析高 CTR 但低留存的素材，并结合 AppsFlyer 数据排查。""",
            "ret_danger": f"""**{cid} 用户留存严重告警 🚨**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}，跌幅 {abs(dp):.1f}%）\n- D7 留存：{d7:.1%}（基线 {rbl7:.1%}）\n\n**建议**：暂停低留存单元，审查素材与定向，并联系产品团队排查。""",
            "both_warning": f"""**{cid} ROAS + 留存双项预警**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}，偏低 {abs(rp):.1f}%）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}，偏低 {abs(dp):.1f}%）\n\n**建议**：收紧定向，审查素材 CTR 周趋势。""",
            "both_danger": f"""**{cid} 全线告警 —— 需要立即介入 🚨🚨**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，跌幅 {abs(rp):.1f}%）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，跌幅 {abs(dp):.1f}%）\n\n**建议**：立即降预算、暂停低效单元并联合排查。""",
            "creative_fatigue": f"""**{cid} 素材疲劳预警**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，✅ 仍达标）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，✅ 仍达标）\n- CTR：{ctr:.2%}（周环比下滑约 32%）\n\n**建议**：本周内上线 3-5 个新素材并下线疲劳素材。""",
            "budget_underdelivery": f"""**{cid} 预算欠量分析**\n\n- 预算消耗率：约 52%\n- CPM：持续走高\n\n**建议**：上调 tCPA 目标，扩大定向并补充素材。""",
            "insufficient_data": f"""**{cid} 数据说明**\n\n当前 Campaign 投放时间较短，主要指标仅供参考，建议继续观察至第 5-7 天。""",
        }
        if scene == "creative_search":
            return f"已为您搜索完毕。以上是 {seed.get('platform','平台')} 上 {seed.get('game_genre','该品类')} 品类近期表现最好的热门素材。"
        if scene == "upload_success":
            return f"素材已成功上传至 {cid}，审核通常需要 2-4 小时。"
        if scene in ("validate_fail_size", "validate_fail_format"):
            return "素材规格校验未通过，请根据上方错误信息调整后重新上传。"
        if scene in ("bidding_strategy","creative_guideline","platform_policy","industry_benchmark","knowledge_base"):
            return "以上是知识库检索结果。如需进一步了解某个具体细节，请继续提问。"
        return tpl.get(scene, tpl["healthy"])
    rs      = "✅ On target" if r7 >= rbl  else ("⚠️ Warning" if r7 >= rbl*0.80  else "🚨 Critical")
    rts     = "✅ On target" if d1 >= rtbl else ("⚠️ Warning" if d1 >= rtbl*0.80 else "🚨 Critical")
    rp      = (r7/rbl  - 1) * 100
    dp      = (d1/rtbl - 1) * 100

    tpl = {
        "healthy": f"""**{cid} Campaign Health Report**

**Core Metrics vs Safety Baseline**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs}, {rp:+.1f}% above baseline)
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts}, {dp:+.1f}% above baseline)
- D7 Retention: {d7:.1%} (baseline {rbl7:.1%})

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} | Spend: ${spend:,.0f}

**Conclusion**: The campaign is overall healthy — both ROAS and retention exceed the safety baseline.
**Recommendation**: Maintain the current creative direction; consider gradually increasing budget to test new regions or audiences.""",

        "roas_warning": f"""**{cid} ROAS Warning Analysis**

**Core Metrics vs Safety Baseline**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs}, {abs(rp):.1f}% below baseline)
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts})

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} (elevated) | Spend: ${spend:,.0f}

**Diagnosis**: D7 ROAS is in the warning zone (80-100% of baseline), primarily due to rising CPI reducing return efficiency.

**Optimization Recommendations**:
1. Review high-CPI ad groups; pause units where CPI > 1.5x target
2. Prioritize budget toward high-ROAS creatives; reduce spend on underperformers
3. Monitor for 3 more days; escalate to danger-level response if decline continues""",

        "roas_danger": f"""**{cid} ROAS Critical Alert 🚨**

**Core Metrics vs Safety Baseline**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs}, {abs(rp):.1f}% below baseline)
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts})

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} (severely elevated) | Spend: ${spend:,.0f}

**Urgent Action Plan**:
1. **Immediately** pause ad groups where ROAS < 60% of baseline
2. Reduce overall daily budget by 30-50%; retain only the top 2 historically best-performing ad groups
3. Contact the creative team for emergency new creative production; test different audience targeting
4. Investigate whether there is an account-level quality issue""",

        "ret_warning": f"""**{cid} User Retention Warning Analysis**

**Core Metrics vs Safety Baseline**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs})
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts}, {abs(dp):.1f}% below baseline)

**Diagnosis**: ROAS is on target but D1 retention is below baseline — the creative is attracting installs but new users are not being retained long-term. Common causes: mismatch between creative tone and actual game experience, or audience targeting bias.

**Recommendations**:
1. Analyze high-CTR but low-retention creatives to check for misleading or clickbait content
2. Use AppsFlyer data to identify high-retention media sources and increase their budget share
3. Confirm with the product team whether there is abnormal early drop-off in the onboarding flow""",

        "ret_danger": f"""**{cid} User Retention Critical Alert 🚨**

**Core Metrics vs Safety Baseline**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs})
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts}, {abs(dp):.1f}% below baseline)
- D7 Retention: {d7:.1%} (baseline {rbl7:.1%})

**Diagnosis**: Both D1 and D7 retention are critically below baseline while ROAS remains acceptable — strongly suggests the creative is attracting the wrong user segment (high payment intent but low game stickiness).

**Urgent Action Plan**:
1. Immediately pause ad groups where D1 retention < 60% of baseline
2. Comprehensively audit creatives; pause any with significant mismatch from actual gameplay
3. Reset targeting; rebuild lookalike audiences from historically high-retention users
4. Work with the product team to rule out onboarding bugs""",

        "both_warning": f"""**{cid} ROAS + Retention Dual Warning**

**Core Metrics vs Safety Baseline**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs}, {abs(rp):.1f}% below baseline)
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts}, {abs(dp):.1f}% below baseline)

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} | Spend: ${spend:,.0f}

**Diagnosis**: ROAS and retention are declining in tandem, typically indicating deteriorating traffic quality — audience targeting may be too broad, or primary creatives may be entering fatigue.

**Recommendations**: Tighten targeting, review weekly CTR trends for key creatives, and assess whether creative fatigue has set in.""",

        "both_danger": f"""**{cid} Full-Scale Alert — Immediate Intervention Required 🚨🚨**

**Core Metrics vs Safety Baseline**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {abs(rp):.1f}% below baseline) 🚨
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {abs(dp):.1f}% below baseline) 🚨

**Current Status**: Both ROAS and retention have fallen more than 20% below the safety baseline — this is the highest-priority anomaly.

**Immediate Action Checklist**:
1. Pause all ad groups where ROAS < 70% of baseline; retain only the top 1-2 historically best-performing units
2. Cut overall daily budget by 50% to limit total losses
3. Convene a joint review with the creative team and product team
4. Submit a root-cause analysis report within 24 hours""",

        "creative_fatigue": f"""**{cid} Creative Fatigue Warning**

**Core Metrics**
- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, ✅ still on target)
- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, ✅ still on target)
- CTR: {ctr:.2%} (**week-over-week decline ~32%**) ⚠️

**Diagnosis**: ROAS and retention are currently still on target, but the sustained CTR decline is an early warning signal of creative fatigue — if left unaddressed, ROAS will be impacted within 1-2 weeks.

**Recommendations**:
1. Launch at least 3-5 new creatives this week covering different hook types
2. Pause primary creatives with CTR declining more than 30% week-over-week
3. Reference competitor recent high-performing creative directions""",

        "budget_underdelivery": f"""**{cid} Budget Underdelivery Analysis**

**Delivery Status**
- Budget delivery rate: ~52% (target 95%+) ⚠️
- CPM: consistently rising; intense competition
- ROAS / Retention: still on target, but volume is insufficient

**Diagnosis**: Rising CPM is reducing auction win rates; the current bid can no longer win consistently in the auction.

**Recommendations**:
1. Raise the tCPA target by 10-15% to give the platform more bidding room
2. Expand audience targeting scope (consider Broad Audience)
3. Increase the number of available creatives to give the platform more combinations to test""",

        "insufficient_data": f"""**{cid} Data Notice**

This campaign has been running for a short time (fewer than 3 days), and current data is limited and should be treated as preliminary:

- Early D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, sample size too small — interpret with caution)
- Early ROAS trend: has not yet reached statistical significance

**Recommendation**: Continue observing until day 5-7 before conducting a formal evaluation, to avoid premature optimization that disrupts the learning period.""",
    }

    # Non-ROAS/Retention scenes
    if scene == "creative_search":
        return (f"Search complete. Above are the top-performing trending creatives "
                f"for the {seed.get('game_genre', 'target')} genre on {seed.get('platform', 'the platform')}. "
                "Focus on creatives with a heat score > 85 and CTR > 0.045 as the primary direction for your next creative iteration.")
    if scene == "upload_success":
        return (f"Creative successfully uploaded to {cid}; review typically takes 2-4 hours. "
                "Once live, monitor CTR and CPI performance closely during the first 48 hours.")
    if scene in ("validate_fail_size", "validate_fail_format"):
        return "Creative spec validation failed. Please adjust based on the error details above and re-upload. Feel free to ask if you need platform spec requirements."
    if scene in ("bidding_strategy","creative_guideline","platform_policy",
                 "industry_benchmark","knowledge_base"):
        return "Here are the knowledge base retrieval results. If you need further detail on any specific point, or want to run analysis against your current campaign data, feel free to continue."

    return tpl.get(scene, tpl["healthy"])


# ─────────────────────────────────────────────────────────────
# 6. Conversation Builder (OpenAI Messages format)
# ─────────────────────────────────────────────────────────────

def make_tool_call_message(tool_name: str, arguments: Dict) -> Tuple[Dict, str]:
    """Generate an assistant tool_call message; returns (message, call_id)"""
    call_id = f"call_{uuid.uuid4().hex[:8]}"
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id":   call_id,
            "type": "function",
            "function": {
                "name":      tool_name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            }
        }]
    }, call_id


def make_tool_result_message(result: str, call_id: str) -> Dict:
    """Generate a tool result message; call_id must strictly match the corresponding tool_call"""
    return {"role": "tool", "content": result, "tool_call_id": call_id}


def build_clarify_question(seed: Dict, lang: str) -> str:
    reason = seed.get("clarification_reason", "")
    if lang == "zh":
        return {
            "campaign_id_missing": "请问您想查看哪个 Campaign 的数据？提供 Campaign ID 后我马上帮您拉取。",
            "campaign_id_and_timerange_missing": "请问您想分析哪个 Campaign？需要查看哪个时间段的数据？",
            "platform_or_genre_missing": "请问您想搜索哪个平台的素材？游戏品类是什么？",
        }.get(reason, "请提供更多信息，以便我为您准确查询。")
    return {
        "campaign_id_missing": "Which campaign would you like to check? Please provide the Campaign ID and I'll pull the data right away.",
        "campaign_id_and_timerange_missing": "Which campaign would you like to analyze, and what time range should I look at?",
        "platform_or_genre_missing": "Which platform would you like to search creatives for, and what is the game genre?",
    }.get(reason, "Please provide more information so I can look this up accurately.")


def build_refusal(seed: Dict, lang: str) -> str:
    if lang == "zh":
        return {
            "off_topic":
                "抱歉，我是专注于移动游戏广告投放的 AI 助手，这个问题超出了我的服务范围。"
                "如有投放数据分析、素材搜索、Campaign 优化等需求，随时可以问我。",
            "unauthorized_operation":
                "抱歉，删除/修改账户级数据属于高风险操作，超出了我的权限范围。"
                "为避免不可逆的影响，此类操作请通过平台后台或联系您的账户经理处理。",
            "insufficient_data_to_answer":
                "您的问题我理解，但缺少必要信息（Campaign ID 或时间范围）无法给出准确分析。"
                "请提供具体的 Campaign ID，我来帮您查看数据。",
        }.get(seed.get("refusal_type", "off_topic"), "抱歉，这个问题超出了我的服务范围。")
    return {
        "off_topic":
            "Sorry, I am an AI assistant focused on mobile game ad campaign management, and this request is outside my scope. "
            "For campaign data analysis, creative search, or optimization, feel free to ask anytime.",
        "unauthorized_operation":
            "Sorry, deleting or modifying account-level data is a high-risk operation that exceeds my authorization. "
            "To avoid irreversible impact, please handle this through the platform dashboard or contact your account manager.",
        "insufficient_data_to_answer":
            "I understand your question, but without the necessary information (Campaign ID or time range) I cannot provide an accurate analysis. "
            "Please provide the specific Campaign ID and I will pull the data for you.",
    }.get(seed.get("refusal_type", "off_topic"),
          "Sorry, this request is outside my scope.")


def build_conversation(seed: Dict, lang: str) -> Dict:
    executor   = MockToolExecutor(seed, lang)
    tool_chain = seed.get("tool_chain", [])
    workflow   = seed.get("workflow", 0)

    messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPTS[lang]}]

    # ── Clarification flow ────────────────────────────────────
    if seed.get("needs_clarification"):
        messages.append({"role": "user",      "content": seed["user_query"]})
        messages.append({"role": "assistant", "content": build_clarify_question(seed, lang)})
        messages.append({"role": "user",      "content": seed.get("clarification_answer", "")})
    else:
        messages.append({"role": "user", "content": seed["user_query"]})

    # ── Refusal flow ends immediately ─────────────────────────
    if workflow == 7:
        messages.append({"role": "assistant", "content": build_refusal(seed, lang)})
        return _wrap(seed, messages)

    # ── Tool chain: each tool gets its own assistant turn + tool turn ─
    for tool_name in tool_chain:
        arguments            = build_tool_arguments(tool_name, seed)
        result               = executor.execute(tool_name, arguments)
        asst_msg, call_id    = make_tool_call_message(tool_name, arguments)
        messages.append(asst_msg)
        messages.append(make_tool_result_message(result, call_id))

    # ── Final assistant natural language response ─────────────
    messages.append({"role": "assistant", "content": build_final_response(seed, executor)})

    return _wrap(seed, messages)


def _wrap(seed: Dict, messages: List[Dict]) -> Dict:
    return {
        "messages": messages,
        "_meta": {
            "workflow":      seed.get("workflow"),
            "workflow_name": seed.get("workflow_name"),
            "scene_tag":     seed.get("scene_tag"),
            "platform":      seed.get("platform"),
            "game_genre":    seed.get("game_genre"),
            "tool_chain":    seed.get("tool_chain"),
        }
    }


# ─────────────────────────────────────────────────────────────
# 7. Main
# ─────────────────────────────────────────────────────────────

def main(input_path: str  = "ad_agent_seeds.json",
         output_path: str = "ad_agent_sft_dataset.json",
         lang: str = "en"):
    ui = UI_TEXT[lang]

    seeds = json.loads(Path(input_path).read_text(encoding="utf-8"))
    print(ui["loaded"].format(count=len(seeds)))

    records, failed = [], 0
    for seed in tqdm(seeds, desc=ui["desc"]):
        try:
            records.append(build_conversation(seed, lang))
        except Exception as e:
            failed += 1
            tqdm.write(ui["skip"].format(error=e))

    # ── Statistics ────────────────────────────────────────────
    wf_cnt, sc_cnt, turn_lens = {}, {}, []
    for r in records:
        m = r["_meta"]
        wf_cnt[m["workflow_name"]] = wf_cnt.get(m["workflow_name"], 0) + 1
        sc_cnt[m["scene_tag"]]     = sc_cnt.get(m["scene_tag"], 0) + 1
        turn_lens.append(len(r["messages"]))

    print(ui["done"].format(count=len(records), failed=failed))
    print(ui["avg_turns"].format(value=sum(turn_lens)/max(len(turn_lens),1)))

    print(ui["workflow_distribution"])
    for wf, n in sorted(wf_cnt.items()):
        print(f"  {wf}: {n}")

    print(ui["scene_distribution"])
    for sc, n in sorted(sc_cnt.items(), key=lambda x: -x[1])[:12]:
        print(f"  {sc}: {n}")

    Path(output_path).write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(ui["saved"].format(path=output_path))


if __name__ == "__main__":
    while True:
        lang = input(UI_TEXT["en"]["lang_prompt"]).strip().lower()
        if lang in {"zh", "en"}:
            break
        print(UI_TEXT["en"]["invalid_lang"])

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[1]
    data_dir = repo_root / "data"

    ui = UI_TEXT[lang]
    inp = input(ui["file_prompt"]).strip()

    # Search in data/ first, then script dir as fallback
    candidate = data_dir / inp
    if not candidate.exists():
        candidate = script_dir / inp
    if not candidate.exists():
        print(ui["file_not_found"].format(name=inp, data_dir=data_dir, script_dir=script_dir))
        exit(1)

    inp_path = candidate
    print(ui["found_input"].format(path=inp_path))

    # Auto-derive output path in data/ with same naming convention
    stem = inp_path.stem  # filename without extension
    if "seeds" in stem:
        out_stem = stem.replace("seeds", "sft")
    else:
        out_stem = stem + "_sft"
    
    data_dir.mkdir(exist_ok=True)
    out_path = data_dir / f"{out_stem}_message.json"
    print(ui["output_path"].format(path=out_path))

    main(str(inp_path), str(out_path), lang)
