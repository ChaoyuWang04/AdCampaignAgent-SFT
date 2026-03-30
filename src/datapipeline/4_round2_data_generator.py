#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round 2 SFT Data Generator
Generates targeted补强 datasets for each Round 1 model variant.

Output: data/continue/r2_{experiment}_train.json + _eval.json
multi_last: symlinks to existing nonmulti train/test data.
"""

import json
import uuid
import random
import shutil
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any

random.seed(42)

# ─────────────────────────────────────────────
# 1. Business Constants (from 0_generate_base_dataset.py)
# ─────────────────────────────────────────────

PLATFORMS = ["Google", "Meta", "Tiktok", "Applovin", "Unity"]
GAME_GENRES = ["casual", "puzzle", "hyper_casual", "strategy", "rpg"]
REGIONS = ["US", "JP", "SEA", "KR", "EU"]

ROAS_BASELINES = {
    "Google":   {"casual": (0.80, 1.20), "puzzle": (0.85, 1.30),
                 "hyper_casual": (0.60, 0.90), "strategy": (0.90, 1.40), "rpg": (0.95, 1.50)},
    "Meta":     {"casual": (0.75, 1.10), "puzzle": (0.80, 1.20),
                 "hyper_casual": (0.55, 0.85), "strategy": (0.85, 1.30), "rpg": (0.90, 1.40)},
    "Tiktok":   {"casual": (0.72, 1.00), "puzzle": (0.75, 1.10),
                 "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Applovin": {"casual": (0.68, 1.00), "puzzle": (0.73, 1.10),
                 "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Unity":    {"casual": (0.58, 1.00), "puzzle": (0.53, 1.10),
                 "hyper_casual": (0.52, 0.80), "strategy": (0.87, 1.20), "rpg": (0.83, 1.30)},
}

RET_BASELINES = {
    "casual":       {"d1": 0.35, "d7": 0.12},
    "puzzle":       {"d1": 0.38, "d7": 0.14},
    "hyper_casual": {"d1": 0.40, "d7": 0.15},
    "strategy":     {"d1": 0.30, "d7": 0.10},
    "rpg":          {"d1": 0.28, "d7": 0.09},
}

WORKFLOW_NAMES = {
    1: {"zh": "素材搜寻",        "en": "Creative Search"},
    2: {"zh": "素材上传",        "en": "Creative Upload"},
    3: {"zh": "单指标效果查询",   "en": "Single Metric Query"},
    4: {"zh": "多维深度分析",     "en": "Multi-Dimensional Deep Analysis"},
    5: {"zh": "异常诊断与优化",   "en": "Anomaly Diagnosis & Optimization"},
    6: {"zh": "知识问答",        "en": "Knowledge Q&A"},
    7: {"zh": "拒答",            "en": "Refusal"},
}

TOOL_CHAINS = {
    1: [["search_trending_creatives"],
        ["search_competitor_ads"],
        ["search_trending_creatives", "get_trending_hooks"],
        ["search_competitor_ads", "search_trending_creatives"]],
    2: [["validate_creative_spec", "upload_creative_asset"],
        ["validate_creative_spec", "batch_upload_creatives"],
        ["validate_creative_spec"]],
    3: [["get_campaign_metrics"],
        ["get_creative_performance"],
        ["get_appsflyer_report"]],
    4: [["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"],
        ["get_appsflyer_report", "get_campaign_metrics", "get_benchmark_data"],
        ["get_campaign_metrics", "get_appsflyer_report",
         "get_creative_performance", "get_benchmark_data"],
        ["compare_campaigns", "get_benchmark_data"]],
    5: [["detect_anomalies", "get_optimization_playbook"],
        ["detect_anomalies", "get_campaign_metrics", "get_optimization_playbook"],
        ["detect_anomalies", "get_creative_performance", "get_optimization_playbook"]],
    6: [["query_knowledge_base"],
        ["get_benchmark_data"],
        ["get_platform_policy"],
        ["query_knowledge_base", "get_benchmark_data"]],
    7: [],
}

SCENE_TAGS = [
    "healthy", "roas_warning", "roas_danger", "ret_warning", "ret_danger",
    "both_warning", "both_danger", "creative_fatigue", "budget_underdelivery", "insufficient_data",
]

USER_ROLES = {
    "zh": ["UA Manager", "Creative Lead", "Growth Lead", "运营主管", "投放优化师"],
    "en": ["UA Manager", "Creative Lead", "Growth Lead", "Operations Manager", "Campaign Optimizer"],
}

COMPETITORS = ["Playrix", "Voodoo", "Rollic", "Jam City", "SciPlay"]


def _make_campaign_ids(n=500):
    return [f"CMP_{random.randint(1000, 9999)}" for _ in range(n)]


def _make_app_ids():
    prefixes = ["com.guru", "com.funplay", "com.gamestar", "io.mobilegame"]
    genres = ["puzzle", "casual", "match3", "runner", "merge"]
    return [f"{p}.{g}{random.randint(1,9):02d}" for p in prefixes for g in genres]


CAMPAIGN_IDS = _make_campaign_ids(500)
APP_IDS = _make_app_ids()


def random_date_range(window_days=7, offset_max=14):
    end = datetime(2026, 3, 1) - timedelta(days=random.randint(0, offset_max))
    start = end - timedelta(days=window_days)
    return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}


def random_context(lang: str) -> Dict:
    platform = random.choice(PLATFORMS)
    genre = random.choice(GAME_GENRES)
    return {
        "platform":          platform,
        "game_genre":        genre,
        "region":            random.choice(REGIONS),
        "campaign_id":       random.choice(CAMPAIGN_IDS),
        "app_id":            random.choice(APP_IDS),
        "user_role":         random.choice(USER_ROLES[lang]),
        "roas_baseline_d7":  ROAS_BASELINES[platform][genre][0],
        "roas_baseline_d30": ROAS_BASELINES[platform][genre][1],
        "ret_baseline_d1":   RET_BASELINES[genre]["d1"],
        "ret_baseline_d7":   RET_BASELINES[genre]["d7"],
        "date_range":        random_date_range(),
    }


# ─────────────────────────────────────────────
# 2. System Prompts (from 2_convert_dataset.py)
# ─────────────────────────────────────────────

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

# ─────────────────────────────────────────────
# 3. Scene Config (from 2_convert_dataset.py)
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# 4. MockToolExecutor (from 2_convert_dataset.py)
# ─────────────────────────────────────────────

class MockToolExecutor:
    def __init__(self, seed: Dict, lang: str):
        self.seed        = seed
        self.lang        = lang
        self.scene       = seed.get("scene_tag", "healthy")
        self.cfg         = SCENE_CFG.get(self.scene, {})
        self.roas_bl_d7  = seed.get("roas_baseline_d7",  0.80)
        self.roas_bl_d30 = seed.get("roas_baseline_d30", 1.20)
        self.ret_bl_d1   = seed.get("ret_baseline_d1",   0.35)
        self.ret_bl_d7   = seed.get("ret_baseline_d7",   0.12)
        self.platform    = seed.get("platform",    "Google")
        self.genre       = seed.get("game_genre",  "casual")
        self.region      = seed.get("region",      "US")
        self.campaign_id = seed.get("campaign_id", "CMP_0000")
        self.app_id      = seed.get("app_id",      "com.example.game")
        self.date_range  = seed.get("date_range",  {"start": "2026-03-01", "end": "2026-03-07"})

        if self.scene not in NON_METRIC_SCENES:
            rm  = self.cfg.get("roas_mult", (1.0, 1.0))
            rtm = self.cfg.get("ret_mult",  (1.0, 1.0))
            self._roas_d7  = round(self.roas_bl_d7 * random.uniform(*rm), 3)
            self._roas_d30 = round(
                self.roas_bl_d30 * (self._roas_d7 / max(self.roas_bl_d7, 0.01))
                * random.uniform(0.95, 1.05), 3)
            self._ret_d1 = round(self.ret_bl_d1 * random.uniform(*rtm), 3)
            self._ret_d7 = round(
                self.ret_bl_d7 * (self._ret_d1 / max(self.ret_bl_d1, 0.01))
                * random.uniform(0.95, 1.05), 3)
        else:
            self._roas_d7  = self.roas_bl_d7
            self._roas_d30 = self.roas_bl_d30
            self._ret_d1   = self.ret_bl_d1
            self._ret_d7   = self.ret_bl_d7

        cr       = self.cfg.get("ctr_range", (0.025, 0.045))
        cm       = self.cfg.get("cpi_mult",  (0.90, 1.10))
        base_cpi = {"Google": 1.8, "Meta": 1.5, "Tiktok": 1.2, "Applovin": 1.0}.get(self.platform, 1.5)
        self._ctr      = round(random.uniform(*cr), 4)
        self._cpi      = round(base_cpi * random.uniform(*cm), 2)
        self._spend    = round(random.uniform(3000, 28000), 2)
        self._installs = max(1, int(self._spend / max(self._cpi, 0.1)))
        self._cpm      = round(self._cpi * self._ctr * 1000, 2) if self._ctr > 0 else 8.0

    def _ok(self, data: Any) -> str:
        return json.dumps({"status": "success", "data": data}, ensure_ascii=False)

    def _err(self, msg: str) -> str:
        return json.dumps({"status": "error", "message": msg}, ensure_ascii=False)

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
            {"hook": "你能撑过第3关吗？",     "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[真实玩家录屏] 我卡了3天的关", "type": "ugc_style", "avg_ctr": 0.055},
            {"hook": "这个谜题难倒了99%的人", "type": "difficulty", "avg_ctr": 0.051},
            {"hook": "帮帮我！我快崩了",       "type": "emotional",  "avg_ctr": 0.049},
        ] if self.lang == "zh" else [
            {"hook": "90% of players can't pass the first level", "type": "challenge", "avg_ctr": 0.062},
            {"hook": "Can you survive past level 3?",              "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[Real player recording] Stuck on this for 3 days", "type": "ugc_style", "avg_ctr": 0.055},
            {"hook": "This puzzle stumped 99% of people",          "type": "difficulty", "avg_ctr": 0.051},
            {"hook": "Help! I'm about to rage quit",               "type": "emotional",  "avg_ctr": 0.049},
        ]
        return self._ok({"genre": kw.get("game_genre", self.genre),
                         "hooks": hooks[:random.randint(3, 5)]})

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
        return self._ok({"valid": True, "file_size": f"{random.uniform(8,35):.1f}MB",
                         "resolution": "1080x1920", "duration": f"{random.choice([15,30])}s",
                         "format": "MP4", "checks_passed": 5})

    def upload_creative_asset(self, **kw) -> str:
        return self._ok({"asset_id": f"ASSET_{random.randint(1000,9999)}", "status": "uploaded",
                         "creative_name": kw.get("creative_name", "new_creative"),
                         "campaign_id": kw.get("campaign_id", self.campaign_id),
                         "review_status": "pending", "estimated_review": "2-4 hours"})

    def batch_upload_creatives(self, **kw) -> str:
        files = kw.get("file_paths", ["f1.mp4", "f2.mp4", "f3.mp4"])
        results = [{"file": f, "status": "uploaded", "asset_id": f"ASSET_{random.randint(1000,9999)}"} for f in files]
        return self._ok({"total": len(files), "success": len(files), "failed": 0, "results": results})

    def get_campaign_metrics(self, **kw) -> str:
        metrics_req = kw.get("metrics", ["roas","retention_d1","retention_d7","ctr","cpi","spend","installs"])
        result = {"campaign_id": self.campaign_id, "date_range": self.date_range,
                  "breakdown": kw.get("breakdown", "daily"), "metrics": {}}
        for m in metrics_req:
            if   m == "roas":          result["metrics"][m] = {"d7": self._roas_d7, "d30": self._roas_d30}
            elif m == "retention_d1":  result["metrics"][m] = self._ret_d1
            elif m == "retention_d7":  result["metrics"][m] = self._ret_d7
            elif m == "ctr":           result["metrics"][m] = self._ctr
            elif m == "cpi":           result["metrics"][m] = self._cpi
            elif m == "spend":         result["metrics"][m] = self._spend
            elif m == "installs":      result["metrics"][m] = self._installs
            elif m == "cpm":           result["metrics"][m] = self._cpm
            elif m == "impressions":   result["metrics"][m] = int(self._spend / max(self._cpm/1000, 0.001))
        if self.scene == "creative_fatigue":
            result["ctr_wow_change"] = round(random.uniform(-0.38, -0.28), 3)
            result["fatigue_signal"] = "CTR 连续下滑超过3天，建议换量" if self.lang == "zh" else "CTR has been declining for 3+ consecutive days; creative refresh recommended"
        if self.scene == "budget_underdelivery":
            result["budget_delivery_rate"] = round(random.uniform(0.38, 0.62), 2)
            result["cpm_trend"] = "持续走高" if self.lang == "zh" else "Consistently rising"
        return self._ok(result)

    def get_creative_performance(self, **kw) -> str:
        top_k = kw.get("top_k", 10)
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
        return self._ok({"campaign_id": self.campaign_id, "sort_by": kw.get("sort_by", "ctr"),
                         "creatives": creatives, "date_range": self.date_range})

    def get_appsflyer_report(self, **kw) -> str:
        return self._ok({
            "app_id": self.app_id, "report_type": kw.get("report_type", "retention"),
            "date_range": self.date_range,
            "data": {"retention_d1": self._ret_d1, "retention_d7": self._ret_d7,
                     "installs": self._installs,
                     "revenue_d7":  round(self._roas_d7  * self._spend, 2),
                     "revenue_d30": round(self._roas_d30 * self._spend, 2),
                     "top_media_source": self.platform}
        })

    def compare_campaigns(self, **kw) -> str:
        campaign_ids = kw.get("campaign_ids", [self.campaign_id, "CMP_9999"])
        comparisons = []
        for i, cid in enumerate(campaign_ids):
            decay = 1 if i == 0 else random.uniform(0.70, 0.95)
            comparisons.append({
                "campaign_id": cid,
                "roas_d7":  round(self._roas_d7 * decay, 3),
                "ret_d1":   round(self._ret_d1  * decay, 3),
                "ret_d7":   round(self._ret_d7  * decay, 3),
                "cpi":      round(self._cpi / decay, 2),
                "spend":    round(self._spend   * decay, 2),
                "installs": int(self._installs  * decay),
            })
        return self._ok({"comparison": comparisons, "date_range": self.date_range})

    def detect_anomalies(self, **kw) -> str:
        anomaly_map = {
            "roas_danger":  [{"metric": "roas_d7", "severity": "critical",
                "value": self._roas_d7, "baseline": self.roas_bl_d7,
                "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                "possible_causes": ["CPI rising rapidly", "Increased low-quality traffic", "CVR declining due to creative fatigue"]}],
            "roas_warning": [{"metric": "roas_d7", "severity": "warning",
                "value": self._roas_d7, "baseline": self.roas_bl_d7,
                "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                "possible_causes": ["Slightly elevated CPI", "Performance decline in some creatives"]}],
            "ret_danger":   [{"metric": "retention_d1", "severity": "critical",
                "value": self._ret_d1, "baseline": self.ret_bl_d1,
                "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                "possible_causes": ["Creative attracting wrong user segment", "Inaccurate geo targeting"]}],
            "both_danger":  [
                {"metric": "roas_d7", "severity": "critical",
                 "value": self._roas_d7, "baseline": self.roas_bl_d7,
                 "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                 "possible_causes": ["Overall campaign quality deteriorating"]},
                {"metric": "retention_d1", "severity": "critical",
                 "value": self._ret_d1, "baseline": self.ret_bl_d1,
                 "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                 "possible_causes": ["Severe mismatch between creative and actual game content"]}],
            "creative_fatigue": [{"metric": "ctr", "severity": "warning",
                "value": self._ctr, "wow_change": "-32%",
                "possible_causes": ["Overexposure of primary creatives", "Audience largely saturated"]}],
            "budget_underdelivery": [{"metric": "budget_delivery_rate", "severity": "warning",
                "value": "52%",
                "possible_causes": ["CPM surged significantly", "Bid too low"]}],
        }
        return self._ok({"campaign_id": self.campaign_id,
                         "anomalies": anomaly_map.get(self.scene, []),
                         "check_time": "2026-03-08T09:00:00Z"})

    def get_optimization_playbook(self, **kw) -> str:
        playbooks = {
            "low_roas":         ["Review CPI distribution; pause units where CPI > 2x target",
                                 "Audit audience targeting for high-CPI creatives",
                                 "Try switching bidding strategy to tCPA",
                                 "Add new creatives to reduce dependency on high-CPI assets"],
            "low_ctr":          ["Analyze common traits of top CTR creatives",
                                 "Pause creatives with CTR below 50% of industry average",
                                 "A/B test different hook types"],
            "creative_fatigue": ["Launch 3-5 new creatives immediately",
                                 "Pause creatives with CTR week-over-week decline > 30%",
                                 "Slightly increase CPM bid to maintain impressions"],
            "budget_underdelivery": ["Check if current bid is below platform's recommended minimum",
                                     "Moderately raise tCPA/tROAS target",
                                     "Expand audience targeting scope"],
        }
        issue_map = {
            "roas_danger": "low_roas", "roas_warning": "low_roas",
            "ret_danger":  "low_ctr",  "ret_warning":  "low_ctr",
            "both_danger": "low_roas", "both_warning": "low_roas",
            "creative_fatigue":     "creative_fatigue",
            "budget_underdelivery": "budget_underdelivery",
        }
        resolved = issue_map.get(self.scene, kw.get("issue_type", "low_roas"))
        steps = playbooks.get(resolved or "low_roas", playbooks["low_roas"])
        return self._ok({"issue_type": resolved, "steps": steps,
                         "estimated_impact": "medium-high", "implementation_time": "1-2 days"})

    def query_knowledge_base(self, **kw) -> str:
        domain = kw.get("domain", "bidding_strategy")
        chunks = {
            "bidding_strategy": [
                {"source": "UA Strategy Handbook v2.3",
                 "content": "tCPA is suitable for campaigns with sufficient installs (>50/week); "
                            "tROAS is suited for mature campaigns with enough in-app purchase data; "
                            "the learning period typically takes 7-14 days."}],
            "creative_guideline": [
                {"source": "Creative Specifications 2026 Q1",
                 "content": "The first 3 seconds of video are the golden hook window; "
                            "optimal length for hyper-casual is 15s, vertical 9:16; "
                            "recommended playable ad duration is 30-60s."}],
            "platform_policy": [
                {"source": "Google Ads Policy Center",
                 "content": "Game ads must clearly display PEGI/ESRB ratings; "
                            "in-app purchase disclosures must meet transparency requirements."}],
            "industry_benchmark": [
                {"source": "2026 Q1 Mobile Game Advertising Report",
                 "content": f"The D7 ROAS benchmark for {self.genre} in the {self.region} market is approximately "
                            f"{self.roas_bl_d7:.2f}, and the D1 retention benchmark is approximately {self.ret_bl_d1:.1%}."}],
        }
        results = chunks.get(domain, chunks["bidding_strategy"])
        return self._ok({"question": kw.get("question", ""), "domain": domain,
                         "chunks": results, "total": len(results)})

    def get_benchmark_data(self, **kw) -> str:
        metric = kw.get("metric", "roas")
        data = {
            "roas": {"d7":  {"p25": round(self.roas_bl_d7*0.75,3),
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
            "ctr": {"p25": 0.018, "p50": 0.030, "p75": 0.048},
            "cpi": {"p25": 0.90,  "p50": 1.60,  "p75": 2.80},
        }.get(metric, {})
        return self._ok({"metric": metric, "genre": self.genre, "region": self.region,
                         "platform": self.platform, "benchmark": data})

    def get_platform_policy(self, **kw) -> str:
        platform    = kw.get("platform", self.platform)
        policy_type = kw.get("policy_type", "ad_format")
        policies = {
            "ad_format":           f"{platform} supports video (15s/30s), playable, native image; vertical 9:16 is recommended.",
            "content_restriction": f"{platform} prohibits graphic violence and deceptive game screenshots; age rating labels are required.",
            "targeting":           f"{platform} supports custom audiences, lookalike audiences, and interest targeting.",
            "billing":             f"{platform} uses CPM/CPC/CPA billing; minimum daily budget is $10.",
        }
        return self._ok({"platform": platform, "policy_type": policy_type,
                         "content": policies.get(policy_type, "Policy document not available")})

    def execute(self, tool_name: str, arguments: Dict) -> str:
        dispatch = {
            "search_trending_creatives": self.search_trending_creatives,
            "search_competitor_ads":     self.search_competitor_ads,
            "get_trending_hooks":        self.get_trending_hooks,
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


# ─────────────────────────────────────────────
# 5. Message Builders (from 2_convert_dataset.py)
# ─────────────────────────────────────────────

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
            "competitor_name": random.choice(COMPETITORS),
            "platform": plat, "limit": 20},
        "get_trending_hooks": {
            "game_genre": genre,
            "creative_type": random.choice(["video", "playable"])},
        "validate_creative_spec": {
            "file_path": f"assets/{genre}_video_{random.randint(1,9):02d}.mp4",
            "platform": plat,
            "ad_format": random.choice(["interstitial", "rewarded"])},
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
            "metric": ("roas" if "roas" in scene else "retention_d1" if "ret" in scene else "ctr"),
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
            "domain": scene if scene in
                      {"bidding_strategy","creative_guideline","platform_policy","industry_benchmark"}
                      else "bidding_strategy",
            "search_mode": "hybrid", "top_k": 5},
        "get_benchmark_data": {
            "metric": "roas", "game_genre": genre,
            "region": region, "platform": plat},
        "get_platform_policy": {
            "platform": plat,
            "policy_type": random.choice(["ad_format","content_restriction"])},
    }.get(tool_name, {})


def build_final_response(seed: Dict, ex: MockToolExecutor) -> str:
    scene  = seed.get("scene_tag", "healthy")
    cid    = seed["campaign_id"]
    rbl    = ex.roas_bl_d7
    rtbl   = ex.ret_bl_d1
    rbl7   = ex.ret_bl_d7
    r7     = ex._roas_d7
    d1     = ex._ret_d1
    d7     = ex._ret_d7
    ctr    = ex._ctr
    cpi    = ex._cpi
    spend  = ex._spend
    if ex.lang == "zh":
        rs  = "✅ 达标" if r7 >= rbl  else ("⚠️ 预警" if r7 >= rbl*0.80  else "🚨 告警")
        rts = "✅ 达标" if d1 >= rtbl else ("⚠️ 预警" if d1 >= rtbl*0.80 else "🚨 告警")
        rp  = (r7/rbl  - 1) * 100
        dp  = (d1/rtbl - 1) * 100
        tpl = {
            "healthy":    f"**{cid} 投放健康报告**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}，超出 {rp:+.1f}%）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}，超出 {dp:+.1f}%）\n\n**结论**：当前 Campaign 整体健康，ROAS 和留存均超过安全基线。",
            "roas_warning": f"**{cid} ROAS 预警分析**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}，偏低 {abs(rp):.1f}%）\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}）\n\n**建议**：检查高 CPI 的 Ad Group，持续观察 3 天趋势。",
            "roas_danger":  f"**{cid} ROAS 严重告警 🚨**\n\n- D7 ROAS：{r7:.3f}（基线 {rbl:.3f}，{rs}，跌幅 {abs(rp):.1f}%）\n\n**建议**：立即暂停低 ROAS 单元，降低预算并补充新素材。",
            "ret_warning":  f"**{cid} 用户留存预警**\n\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}，偏低 {abs(dp):.1f}%）\n\n**建议**：分析高 CTR 但低留存的素材。",
            "ret_danger":   f"**{cid} 用户留存严重告警 🚨**\n\n- D1 留存：{d1:.1%}（基线 {rtbl:.1%}，{rts}，跌幅 {abs(dp):.1f}%）\n- D7 留存：{d7:.1%}（基线 {rbl7:.1%}）\n\n**建议**：暂停低留存单元，审查素材与定向。",
            "both_warning": f"**{cid} ROAS + 留存双项预警**\n\n- D7 ROAS：{r7:.3f}（偏低 {abs(rp):.1f}%）\n- D1 留存：{d1:.1%}（偏低 {abs(dp):.1f}%）\n\n**建议**：收紧定向，审查素材 CTR 周趋势。",
            "both_danger":  f"**{cid} 全线告警 🚨🚨**\n\n- D7 ROAS：{r7:.3f}（跌幅 {abs(rp):.1f}%）\n- D1 留存：{d1:.1%}（跌幅 {abs(dp):.1f}%）\n\n**建议**：立即降预算、暂停低效单元并联合排查。",
            "creative_fatigue":     f"**{cid} 素材疲劳预警**\n\n- CTR：{ctr:.2%}（周环比下滑约 32%）\n\n**建议**：本周内上线 3-5 个新素材。",
            "budget_underdelivery": f"**{cid} 预算欠量分析**\n\n- 预算消耗率：约 52%\n\n**建议**：上调 tCPA 目标，扩大定向。",
            "insufficient_data":    f"**{cid} 数据说明**\n\n当前 Campaign 投放时间较短，建议继续观察至第 5-7 天。",
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

    # English
    rs  = "✅ On target" if r7 >= rbl  else ("⚠️ Warning" if r7 >= rbl*0.80  else "🚨 Critical")
    rts = "✅ On target" if d1 >= rtbl else ("⚠️ Warning" if d1 >= rtbl*0.80 else "🚨 Critical")
    rp  = (r7/rbl  - 1) * 100
    dp  = (d1/rtbl - 1) * 100
    tpl = {
        "healthy":    f"**{cid} Campaign Health Report**\n\n- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs}, {rp:+.1f}%)\n- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts}, {dp:+.1f}%)\n\n**Conclusion**: Campaign is healthy — both ROAS and retention exceed the safety baseline.",
        "roas_warning": f"**{cid} ROAS Warning**\n\n- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs}, {abs(rp):.1f}% below)\n\n**Recommendation**: Review high-CPI ad groups; monitor for 3 more days.",
        "roas_danger":  f"**{cid} ROAS Critical Alert 🚨**\n\n- D7 ROAS: {r7:.3f} (baseline {rbl:.3f}, {rs}, {abs(rp):.1f}% below)\n\n**Urgent**: Pause underperforming ad groups and reduce budget.",
        "ret_warning":  f"**{cid} Retention Warning**\n\n- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts}, {abs(dp):.1f}% below)\n\n**Recommendation**: Analyze high-CTR but low-retention creatives.",
        "ret_danger":   f"**{cid} Retention Critical Alert 🚨**\n\n- D1 Retention: {d1:.1%} (baseline {rtbl:.1%}, {rts}, {abs(dp):.1f}% below)\n\n**Urgent**: Pause low-retention ad groups and audit creatives.",
        "both_warning": f"**{cid} ROAS + Retention Dual Warning**\n\n- D7 ROAS: {r7:.3f} ({abs(rp):.1f}% below)\n- D1 Retention: {d1:.1%} ({abs(dp):.1f}% below)\n\n**Recommendation**: Tighten targeting and review creative CTR trends.",
        "both_danger":  f"**{cid} Full-Scale Alert 🚨🚨**\n\n- D7 ROAS: {r7:.3f} ({abs(rp):.1f}% below)\n- D1 Retention: {d1:.1%} ({abs(dp):.1f}% below)\n\n**Urgent**: Pause all underperforming units and cut budget by 50%.",
        "creative_fatigue":     f"**{cid} Creative Fatigue Warning**\n\n- CTR: {ctr:.2%} (week-over-week decline ~32%)\n\n**Recommendation**: Launch 3-5 new creatives this week.",
        "budget_underdelivery": f"**{cid} Budget Underdelivery**\n\n- Budget delivery rate: ~52%\n\n**Recommendation**: Raise tCPA target and expand audience targeting.",
        "insufficient_data":    f"**{cid} Data Notice**\n\nThis campaign has been running briefly. Continue observing until day 5-7 before formal evaluation.",
    }
    if scene == "creative_search":
        return f"Search complete. Above are the top-performing trending creatives for {seed.get('game_genre','target')} on {seed.get('platform','the platform')}."
    if scene == "upload_success":
        return f"Creative successfully uploaded to {cid}; review typically takes 2-4 hours."
    if scene in ("validate_fail_size", "validate_fail_format"):
        return "Creative spec validation failed. Please adjust based on the error details above and re-upload."
    if scene in ("bidding_strategy","creative_guideline","platform_policy","industry_benchmark","knowledge_base"):
        return "Here are the knowledge base retrieval results. Feel free to ask for more detail on any specific point."
    return tpl.get(scene, tpl["healthy"])


def build_clarify_question(seed: Dict, lang: str) -> str:
    reason = seed.get("clarification_reason", "")
    if lang == "zh":
        return {
            "campaign_id_missing":              "请问您想查看哪个 Campaign 的数据？提供 Campaign ID 后我马上帮您拉取。",
            "campaign_id_and_timerange_missing": "请问您想分析哪个 Campaign？需要查看哪个时间段的数据？",
            "platform_or_genre_missing":         "请问您想搜索哪个平台的素材？游戏品类是什么？",
            "app_id_missing":                    "请问是哪个 App 的数据？提供 App ID 后我来帮您查询。",
        }.get(reason, "请提供更多信息，以便我为您准确查询。")
    return {
        "campaign_id_missing":              "Which campaign would you like to check? Please provide the Campaign ID.",
        "campaign_id_and_timerange_missing": "Which campaign would you like to analyze, and what time range?",
        "platform_or_genre_missing":         "Which platform would you like to search creatives for, and what is the game genre?",
        "app_id_missing":                    "Which app's data would you like? Please provide the App ID.",
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
        }.get(seed.get("refusal_type", "off_topic"), "抱歉，这个问题超出了我的服务范围。")
    return {
        "off_topic":
            "Sorry, I am an AI assistant focused on mobile game ad campaign management, and this request is outside my scope. "
            "For campaign data analysis, creative search, or optimization, feel free to ask anytime.",
        "unauthorized_operation":
            "Sorry, deleting or modifying account-level data is a high-risk operation that exceeds my authorization. "
            "Please handle this through the platform dashboard or contact your account manager.",
    }.get(seed.get("refusal_type", "off_topic"), "Sorry, this request is outside my scope.")


def make_tool_call_message(tool_name: str, arguments: Dict) -> Tuple[Dict, str]:
    call_id = f"call_{uuid.uuid4().hex[:8]}"
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
            }
        }]
    }, call_id


def make_tool_result_message(result: str, call_id: str) -> Dict:
    return {"role": "tool", "content": result, "tool_call_id": call_id}


def build_message_record(seed: Dict, lang: str) -> Dict:
    executor   = MockToolExecutor(seed, lang)
    tool_chain = seed.get("tool_chain", [])
    workflow   = seed.get("workflow", 0)

    messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPTS[lang]}]

    if seed.get("needs_clarification"):
        messages.append({"role": "user",      "content": seed["user_query"]})
        messages.append({"role": "assistant", "content": build_clarify_question(seed, lang)})
        answer = seed.get("clarification_answer") or ""
        if answer:
            messages.append({"role": "user", "content": answer})
    else:
        messages.append({"role": "user", "content": seed["user_query"]})

    if workflow == 7:
        messages.append({"role": "assistant", "content": build_refusal(seed, lang)})
        return _wrap(seed, messages)

    for tool_name in tool_chain:
        arguments         = build_tool_arguments(tool_name, seed)
        result            = executor.execute(tool_name, arguments)
        asst_msg, call_id = make_tool_call_message(tool_name, arguments)
        messages.append(asst_msg)
        messages.append(make_tool_result_message(result, call_id))

    messages.append({"role": "assistant", "content": build_final_response(seed, executor)})
    return _wrap(seed, messages)


def _wrap(seed: Dict, messages: List[Dict]) -> Dict:
    """Internal wrap — caller adds round/sample_type to _meta after returning."""
    return {
        "messages": messages,
        "_meta": {
            "workflow":      seed.get("workflow"),
            "workflow_name": seed.get("workflow_name"),
            "scene_tag":     seed.get("scene_tag"),
            "platform":      seed.get("platform"),
            "game_genre":    seed.get("game_genre"),
            "tool_chain":    seed.get("tool_chain", []),
        }
    }


# ─────────────────────────────────────────────
# 6. Round 2 Sample Generators
# ─────────────────────────────────────────────

# ── OOS query bank (expanded over Round 1 to increase diversity) ──
OOS_QUERIES = {
    "zh": {
        "off_topic": [
            "帮我写一段Python代码",
            "今天天气怎么样？",
            "推荐几部好看的电影",
            "帮我翻译一下这段英文",
            "区块链是什么？",
            "帮我分析一下股票市场",
            "如何学习机器学习？",
            "1+1等于几？",
            "帮我写一首诗",
            "给我讲个笑话",
            "帮我写一段产品介绍文案",
            "怎么做红烧肉？",
            "推荐几本畅销书",
            "帮我起草一封辞职信",
            "比特币现在多少钱",
            "帮我设计一个公司logo的思路",
            "如何优化MySQL数据库查询性能",
            "推荐一个减肥计划",
            "帮我写一首歌词",
            "怎么申请美国签证",
        ],
        "unauthorized_operation": [
            "帮我删掉{campaign_id}这个campaign",
            "把竞品{competitor}的广告账户数据给我",
            "直接修改{campaign_id}的出价为0.1美元",
            "把我们所有campaign的预算全部清零",
            "帮我入侵一下竞品的广告账号",
            "强制暂停所有正在跑的广告",
            "把其他团队的campaign数据导出来",
            "帮我黑掉{competitor}的广告账号",
            "删除账号下所有历史数据",
            "把{competitor}的广告创意偷下来",
        ],
    },
    "en": {
        "off_topic": [
            "Write me a Python script",
            "What's the weather like today?",
            "Recommend some good movies",
            "Help me translate this paragraph",
            "What is blockchain?",
            "Help me analyze the stock market",
            "How do I learn machine learning?",
            "What is 1+1?",
            "Write me a poem",
            "Tell me a joke",
            "Write me a product description",
            "How do I make fried rice?",
            "Recommend some bestselling books",
            "Draft a resignation letter for me",
            "What is Bitcoin trading at right now?",
            "Give me logo design ideas for a company",
            "How do I optimize MySQL query performance?",
            "Give me a weight loss plan",
            "Write me some song lyrics",
            "How do I apply for a US visa?",
        ],
        "unauthorized_operation": [
            "Delete campaign {campaign_id} for me",
            "Give me the ad account data for competitor {competitor}",
            "Directly set the bid for {campaign_id} to $0.10",
            "Zero out the budget for all our campaigns",
            "Help me hack into a competitor's ad account",
            "Force pause all currently running ads",
            "Export campaign data from other teams",
            "Help me hack {competitor}'s ad account",
            "Delete all historical data from the account",
            "Steal {competitor}'s ad creatives",
        ],
    },
}

# ── Clarify query bank ──
CLARIFY_QUERIES = {
    "zh": [
        "查一下ROAS",
        "留存数据怎么样？",
        "花了多少预算？",
        "效果怎么样？",
        "数据拉一下",
        "最近的ROAS怎么样？",
        "留存达标了吗？",
        "投放效果好吗？",
        "帮我查一下最近的数据",
        "有没有异常指标？",
        "Campaign效果如何？",
        "帮我分析一下投放情况",
        "数据有没有下跌？",
        "这周的ROI正常吗？",
        "帮我拉一下最近的报告",
        "帮我搜一下最近的热门素材",
        "看看竞品最近投了什么",
        "找一些素材参考",
    ],
    "en": [
        "Check the ROAS",
        "How's the retention?",
        "How much budget was spent?",
        "How's performance?",
        "Pull the data",
        "How's the ROAS recently?",
        "Did retention hit the target?",
        "Is performance good?",
        "Pull me the latest data",
        "Are there any anomalies?",
        "How is the campaign performing?",
        "Help me analyze the campaign situation",
        "Has the data dropped?",
        "Is ROI normal this week?",
        "Pull me a recent report",
        "Find me some trending creatives recently",
        "Check what competitors have been running",
        "Find some creative references",
    ],
}

CLARIFY_REASONS = [
    "campaign_id_missing",
    "campaign_id_and_timerange_missing",
    "platform_or_genre_missing",
    "app_id_missing",
]


def gen_oos_samples(count: int, lang: str = "zh") -> List[Dict]:
    """Generate OOS (refusal) samples — workflow 7, off_topic + unauthorized_operation."""
    records = []
    for _ in range(count):
        ctx    = random_context(lang)
        rtype  = random.choice(["off_topic", "unauthorized_operation"])
        tmpl   = random.choice(OOS_QUERIES[lang][rtype])
        query  = (tmpl
                  .replace("{campaign_id}", ctx["campaign_id"])
                  .replace("{competitor}", random.choice(COMPETITORS)))
        seed = {"refusal_type": rtype, "workflow": 7,
                "workflow_name": WORKFLOW_NAMES[7][lang], **ctx}

        messages = [
            {"role": "system",    "content": SYSTEM_PROMPTS[lang]},
            {"role": "user",      "content": query},
            {"role": "assistant", "content": build_refusal(seed, lang)},
        ]
        records.append({
            "messages": messages,
            "_meta": {
                "workflow":      7,
                "workflow_name": WORKFLOW_NAMES[7][lang],
                "scene_tag":     rtype,
                "platform":      ctx["platform"],
                "game_genre":    ctx["game_genre"],
                "tool_chain":    [],
                "round":         2,
                "sample_type":   "oos",
            }
        })
    return records


def gen_clarify_samples(count: int, lang: str = "zh") -> List[Dict]:
    """Generate clarify samples — model asks ONE clarifying question, no tool calls."""
    records = []
    for _ in range(count):
        ctx    = random_context(lang)
        query  = random.choice(CLARIFY_QUERIES[lang])
        reason = random.choice(CLARIFY_REASONS)
        seed   = {"clarification_reason": reason, **ctx}

        messages = [
            {"role": "system",    "content": SYSTEM_PROMPTS[lang]},
            {"role": "user",      "content": query},
            {"role": "assistant", "content": build_clarify_question(seed, lang)},
        ]
        records.append({
            "messages": messages,
            "_meta": {
                "workflow":           3,
                "workflow_name":      WORKFLOW_NAMES[3][lang],
                "scene_tag":          "insufficient_data",
                "platform":           ctx["platform"],
                "game_genre":         ctx["game_genre"],
                "tool_chain":         [],
                "needs_clarification": True,
                "round":              2,
                "sample_type":        "clarify",
            }
        })
    return records


# Single-tool workflow configurations
_SINGLE_TOOL_CFGS = [
    # (workflow_num, tool_name, scene, zh_queries, en_queries)
    (1, "search_trending_creatives", "creative_search",
     ["帮我搜一下{platform}上最近{genre}品类的热门素材",
      "{region}市场上，{genre}游戏最近什么素材类型CTR高？",
      "帮我找找{genre}品类在{region}表现好的视频素材",
      "最近有哪些{genre}游戏广告在{platform}跑量很好？"],
     ["Find top-performing creatives for {genre} games on {platform} recently",
      "Which creative types have the highest CTR for {genre} games in {region}?",
      "Help me find high-performing video creatives for {genre} games in {region}",
      "Which {genre} game ads have been scaling well on {platform} recently?"]),
    (1, "search_competitor_ads", "creative_search",
     ["查一下{competitor}最近在{platform}上投了什么广告",
      "搜一下竞品{competitor}在{platform}的广告创意",
      "给我看看{competitor}最近的广告长什么样"],
     ["Look up what ads {competitor} has been running on {platform} lately",
      "Search for competitor {competitor}'s ad creatives on {platform}",
      "Show me what {competitor}'s recent ads look like"]),
    (2, "validate_creative_spec", None,
     ["帮我校验一下这个视频素材的规格",
      "上传前先验证一下素材是否符合{platform}的规格",
      "这个{platform}素材规格对吗？",
      "帮我检查一下这个视频文件的规格"],
     ["Please validate the specs of this video creative",
      "Before uploading, verify the creative meets {platform}'s specs",
      "Are these creative specs correct for {platform}?",
      "Help me check the specs of this video file"]),
    (3, "get_campaign_metrics", None,
     ["查一下{campaign_id}上周的ROAS",
      "{campaign_id}最近7天的D1留存是多少？",
      "看看{campaign_id}的花费情况",
      "{campaign_id}的D7 ROAS达标了吗？",
      "{campaign_id}昨天的预算消耗正常吗？"],
     ["Check the ROAS for {campaign_id} last week",
      "What is the D1 retention for {campaign_id} over the last 7 days?",
      "Show me the spend for {campaign_id}",
      "Has {campaign_id}'s D7 ROAS hit the target?",
      "Is {campaign_id}'s budget spend normal yesterday?"]),
    (3, "get_creative_performance", None,
     ["查一下{campaign_id}各素材的表现",
      "{campaign_id}按素材拆分的CTR怎么样？",
      "哪个素材跑得最好？CTR最高的是哪个？",
      "{campaign_id}最近素材表现如何？"],
     ["Check the creative performance breakdown for {campaign_id}",
      "What is the CTR by creative for {campaign_id}?",
      "Which creative is performing best? What has the highest CTR?",
      "How are creatives performing recently for {campaign_id}?"]),
    (3, "get_appsflyer_report", None,
     ["{app_id}上周的留存报告",
      "看看{app_id}最近的收入归因数据",
      "{app_id}的D7留存报告",
      "{app_id}按渠道拆分的安装量怎么样？"],
     ["Last week's retention report for {app_id}",
      "Show me the revenue attribution data for {app_id}",
      "D7 retention report for {app_id}",
      "How are installs looking by media source for {app_id}?"]),
    (6, "query_knowledge_base", "bidding_strategy",
     ["tCPA和tROAS出价策略有什么区别？",
      "UAC的Smart Bidding学习期一般多久？",
      "出价策略从tCPA切换到tROAS需要注意什么？"],
     ["What's the difference between tCPA and tROAS bidding?",
      "How long is the Smart Bidding learning period for UAC typically?",
      "What should I watch out for when switching from tCPA to tROAS?"]),
    (6, "query_knowledge_base", "creative_guideline",
     ["视频广告的前3秒钩子怎么设计才能提高CTR？",
      "hyper-casual游戏适合哪些广告格式？",
      "什么样的素材容易在TikTok上跑量？",
      "playable广告的设计要点是什么？"],
     ["How should I design the first 3 seconds of a video ad to improve CTR?",
      "What ad formats work best for hyper-casual games?",
      "What kind of creatives tend to scale well on TikTok?",
      "What are the key design principles for playable ads?"]),
    (6, "get_benchmark_data", "industry_benchmark",
     ["casual游戏在US市场的D7 ROAS基准是多少？",
      "puzzle游戏的行业平均D1留存是什么水平？",
      "TikTok上hyper-casual游戏的平均CPM是多少？"],
     ["What is the D7 ROAS benchmark for casual games in the US market?",
      "What is the industry average D1 retention rate for puzzle games?",
      "What is the average CPM for hyper-casual games on TikTok?"]),
    (6, "get_platform_policy", "platform_policy",
     ["Google UAC对游戏广告有哪些内容限制？",
      "Meta广告的定向规则最近有什么变化？",
      "TikTok的广告格式限制是什么？",
      "Google对游戏内购内容的展示有什么规定？"],
     ["What content restrictions does Google UAC have for game ads?",
      "What recent changes have been made to Meta's ad targeting rules?",
      "What are TikTok's ad format restrictions?",
      "What are Google's regulations for displaying in-app purchase content?"]),
]

_WF2_SCENES = ["upload_success", "validate_fail_size", "validate_fail_format"]
_WF3_SCENES = SCENE_TAGS[:7]  # healthy through both_danger


def gen_tool_call_samples(count: int, lang: str = "zh") -> List[Dict]:
    """Generate standard single-tool call samples."""
    records = []
    lang_idx = 0 if lang == "zh" else 1

    for _ in range(count):
        ctx = random_context(lang)
        cfg = random.choice(_SINGLE_TOOL_CFGS)
        wf_num, tool_name, fixed_scene, zh_qs, en_qs = cfg
        queries = zh_qs if lang == "zh" else en_qs

        # Pick scene
        if fixed_scene is not None:
            scene = fixed_scene
        elif wf_num == 2:
            scene = random.choice(_WF2_SCENES)
        else:
            scene = random.choice(_WF3_SCENES)

        tmpl  = random.choice(queries)
        query = (tmpl
                 .replace("{campaign_id}", ctx["campaign_id"])
                 .replace("{app_id}",      ctx["app_id"])
                 .replace("{platform}",    ctx["platform"])
                 .replace("{genre}",       ctx["game_genre"])
                 .replace("{region}",      ctx["region"])
                 .replace("{competitor}",  random.choice(COMPETITORS)))

        seed = {
            "workflow":           wf_num,
            "workflow_name":      WORKFLOW_NAMES[wf_num][lang],
            "user_query":         query,
            "needs_clarification":False,
            "clarification_reason": None,
            "clarification_answer": None,
            "scene_tag":          scene,
            "tool_chain":         [tool_name],
            "refusal_type":       None,
            **ctx,
        }

        record = build_message_record(seed, lang)
        record["_meta"]["round"]       = 2
        record["_meta"]["sample_type"] = "tool_call"
        records.append(record)
    return records


# ─────────────────────────────────────────────
# 7. Dataset Assembly + Main
# ─────────────────────────────────────────────

EXPERIMENT_RATIOS = {
    "nonmulti_all":  {"oos": 0.60, "clarify": 0.30, "tool_call": 0.10},
    "nonmulti_last": {"oos": 0.30, "clarify": 0.00, "tool_call": 0.70},
    "multi_all":     {"oos": 0.50, "clarify": 0.10, "tool_call": 0.40},
}


def build_dataset(experiment: str, n_train: int, n_eval: int,
                  lang: str = "zh") -> Tuple[List[Dict], List[Dict]]:
    total   = n_train + n_eval
    ratios  = EXPERIMENT_RATIOS[experiment]
    n_oos   = int(total * ratios["oos"])
    n_clar  = int(total * ratios["clarify"])
    n_tool  = total - n_oos - n_clar  # remainder to hit exact total

    print(f"  [{experiment}] oos={n_oos} clarify={n_clar} tool_call={n_tool} total={total}")

    all_records: List[Dict] = []
    if n_oos  > 0: all_records.extend(gen_oos_samples(n_oos,   lang))
    if n_clar > 0: all_records.extend(gen_clarify_samples(n_clar, lang))
    if n_tool > 0: all_records.extend(gen_tool_call_samples(n_tool, lang))

    random.shuffle(all_records)
    return all_records[:n_train], all_records[n_train:n_train + n_eval]


def main():
    parser = argparse.ArgumentParser(description="Round 2 SFT data generator")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: <repo_root>/data/continue)")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"],
                        help="Language for generated samples (default: zh)")
    parser.add_argument("--n-train", type=int, default=500, help="Train samples per experiment")
    parser.add_argument("--n-eval",  type=int, default=100, help="Eval samples per experiment")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir   = Path(args.output_dir) if args.output_dir else repo_root / "data" / "continue"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output dir : {out_dir}")
    print(f"Language   : {args.lang}")
    print(f"Train size : {args.n_train} | Eval size : {args.n_eval}")
    print()

    # ── Generate 3 experiments ──────────────────────────────
    for exp in ("nonmulti_all", "nonmulti_last", "multi_all"):
        train, eval_ = build_dataset(exp, args.n_train, args.n_eval, args.lang)
        train_path   = out_dir / f"r2_{exp}_train.json"
        eval_path    = out_dir / f"r2_{exp}_eval.json"
        train_path.write_text(json.dumps(train, ensure_ascii=False, indent=2), encoding="utf-8")
        eval_path.write_text(json.dumps(eval_,  ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved: {train_path.name} ({len(train)}) + {eval_path.name} ({len(eval_)})")

    print()

    # ── multi_last: symlink from ready2train ────────────────
    msg_dir   = repo_root / "data" / "ready2train" / "message"
    # Find the latest train/test message files
    train_srcs = sorted(msg_dir.glob("*_zh_train_message.json"))
    eval_srcs  = sorted(msg_dir.glob("*_zh_test_message.json"))

    if not train_srcs or not eval_srcs:
        print("  WARNING: Could not find nonmulti source files for multi_last, skipping symlink.")
    else:
        src_train = train_srcs[-1]
        src_eval  = eval_srcs[-1]
        dst_train = out_dir / "r2_multi_last_train.json"
        dst_eval  = out_dir / "r2_multi_last_eval.json"
        for src, dst in [(src_train, dst_train), (src_eval, dst_eval)]:
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            try:
                dst.symlink_to(src.resolve())
                print(f"  Symlinked: {dst.name} -> {src.name}")
            except OSError:
                shutil.copy2(src, dst)
                print(f"  Copied  : {dst.name} <- {src.name}")

    print()
    print("Done. Files in", out_dir)


if __name__ == "__main__":
    main()
