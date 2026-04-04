#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ad Campaign Agent - Phase 2: Conversation Generator
仅输出 OpenAI Messages 格式，仅保留中文支持。
"""

import json
import random
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tqdm import tqdm


SYSTEM_PROMPT = """你是一个专业的移动游戏广告投放 AI 助手（Ad Campaign Agent），服务于 UA（用户获取）团队。

## 核心职责
- 以 ROAS 和用户留存（Retention）安全基线为核心，评估 Campaign 健康状态
- 识别指标异常，给出结构化优化建议
- 搜索热门素材、管理素材上传流程
- 回答出价策略、平台政策、行业 benchmark 等专业知识

## 工作原则
- 分析时始终明确指出 ROAS / Retention 是否达到安全基线，数据说话
- 信息不足时主动追问，一次只问一个关键信息
- 上传素材前必须先调用 validate_creative_spec 校验规格
- 超出能力范围或涉及越权操作时，礼貌拒绝并说明原因"""

UI_TEXT = {
    "loaded": "✅ 加载种子记录：{count} 条",
    "desc": "生成对话",
    "skip": "⚠️  跳过：{error}",
    "done": "\n✅ 生成完成：{count} 条对话，失败 {failed} 条",
    "avg_turns": "📊 平均消息轮数：{value:.1f} turns",
    "workflow_distribution": "\n📋 工作流分布:",
    "scene_distribution": "\n🏷  场景分布 (Top 12):",
    "saved": "\n💾 已保存：{path}",
    "file_prompt": "请输入 seed JSON 文件名: ",
    "file_not_found": "❌ 数据文件没有找到: {name} (在 {processed_dir} 路径中)",
    "found_input": "📂 Found input: {path}",
    "output_path": "💾 输出的结果已保存至: {path}",
}

SCENE_CFG = {
    "healthy": {"roas_mult": (1.05, 1.25), "ret_mult": (1.05, 1.20), "ctr_range": (0.030, 0.055), "cpi_mult": (0.80, 0.93)},
    "roas_warning": {"roas_mult": (0.80, 0.90), "ret_mult": (0.98, 1.08), "ctr_range": (0.022, 0.035), "cpi_mult": (1.05, 1.18)},
    "roas_danger": {"roas_mult": (0.48, 0.74), "ret_mult": (0.95, 1.05), "ctr_range": (0.018, 0.030), "cpi_mult": (1.22, 1.55)},
    "ret_warning": {"roas_mult": (0.98, 1.08), "ret_mult": (0.80, 0.90), "ctr_range": (0.032, 0.055), "cpi_mult": (0.88, 0.98)},
    "ret_danger": {"roas_mult": (0.95, 1.05), "ret_mult": (0.48, 0.74), "ctr_range": (0.038, 0.065), "cpi_mult": (0.78, 0.92)},
    "both_warning": {"roas_mult": (0.80, 0.90), "ret_mult": (0.80, 0.90), "ctr_range": (0.020, 0.032), "cpi_mult": (1.12, 1.28)},
    "both_danger": {"roas_mult": (0.45, 0.68), "ret_mult": (0.45, 0.68), "ctr_range": (0.014, 0.025), "cpi_mult": (1.32, 1.65)},
    "creative_fatigue": {"roas_mult": (1.00, 1.10), "ret_mult": (1.00, 1.10), "ctr_range": (0.012, 0.022), "cpi_mult": (1.08, 1.20)},
    "budget_underdelivery": {"roas_mult": (1.00, 1.12), "ret_mult": (1.00, 1.12), "ctr_range": (0.025, 0.042), "cpi_mult": (1.00, 1.10)},
    "insufficient_data": {"roas_mult": (0.90, 1.10), "ret_mult": (0.90, 1.10), "ctr_range": (0.020, 0.045), "cpi_mult": (0.90, 1.10)},
}

NON_METRIC_SCENES = {
    "creative_search",
    "creative_search_clarify",
    "competitor_ads_search",
    "trending_creatives_search",
    "trending_with_hooks_search",
    "upload_success",
    "single_upload_success",
    "batch_upload_success",
    "validate_fail_size",
    "validate_fail_format",
    "upload_partial_fail",
    "single_upload_partial_fail",
    "batch_upload_partial_fail",
    "bidding_strategy",
    "creative_guideline",
    "platform_policy",
    "industry_benchmark",
    "knowledge_base",
    "off_topic",
    "unauthorized_operation",
    "insufficient_data_to_answer",
    "query_roas",
    "query_retention",
    "query_ctr",
    "query_spend",
    "query_installs",
    "query_cpm",
    "creative_metrics",
    "appsflyer_report",
    "clarify_missing_campaign",
    "clarify_missing_scope",
}

PLATFORM_TOKENS = {
    "Google": ["Google", "google", "UAC", "Google UAC"],
    "Meta": ["Meta", "meta", "Facebook"],
    "Tiktok": ["TikTok", "Tiktok", "tiktok"],
    "Applovin": ["Applovin", "AppLovin", "applovin"],
    "Unity": ["Unity", "unity", "Unity Ads"],
}
GENRE_TOKENS = {
    "hyper_casual": ["hyper-casual", "hyper_casual", "hyper casual", "超休闲"],
    "casual": ["casual", "休闲"],
    "puzzle": ["puzzle", "解谜"],
    "strategy": ["strategy"],
    "rpg": ["rpg", "RPG"],
}
REGION_TOKENS = ["US", "JP", "SEA", "KR", "EU"]
COMPETITORS = ["Playrix", "Voodoo", "Rollic", "Jam City", "SciPlay"]


class MockToolExecutor:
    def __init__(self, seed: Dict):
        self.seed = seed
        self.scene = seed.get("scene_tag", "healthy")
        self.cfg = SCENE_CFG.get(self.scene, {})
        self.roas_bl_d7 = seed.get("roas_baseline_d7", 0.80)
        self.roas_bl_d30 = seed.get("roas_baseline_d30", 1.20)
        self.ret_bl_d1 = seed.get("ret_baseline_d1", 0.35)
        self.ret_bl_d7 = seed.get("ret_baseline_d7", 0.12)
        self.platform = seed.get("platform", "Google")
        self.genre = seed.get("game_genre", "casual")
        self.region = seed.get("region", "US")
        self.campaign_id = seed.get("campaign_id", "CMP_0000")
        self.app_id = seed.get("app_id", "com.example.game")
        self.date_range = seed.get("date_range", {"start": "2026-03-01", "end": "2026-03-07"})

        if self.scene not in NON_METRIC_SCENES:
            roas_mult = self.cfg.get("roas_mult", (1.0, 1.0))
            ret_mult = self.cfg.get("ret_mult", (1.0, 1.0))
            self._roas_d7 = round(self.roas_bl_d7 * random.uniform(*roas_mult), 3)
            self._roas_d30 = round(
                self.roas_bl_d30 * (self._roas_d7 / max(self.roas_bl_d7, 0.01)) * random.uniform(0.95, 1.05),
                3,
            )
            self._ret_d1 = round(self.ret_bl_d1 * random.uniform(*ret_mult), 3)
            self._ret_d7 = round(
                self.ret_bl_d7 * (self._ret_d1 / max(self.ret_bl_d1, 0.01)) * random.uniform(0.95, 1.05),
                3,
            )
        else:
            self._roas_d7 = self.roas_bl_d7
            self._roas_d30 = self.roas_bl_d30
            self._ret_d1 = self.ret_bl_d1
            self._ret_d7 = self.ret_bl_d7

        ctr_range = self.cfg.get("ctr_range", (0.025, 0.045))
        cpi_mult = self.cfg.get("cpi_mult", (0.90, 1.10))
        base_cpi = {"Google": 1.8, "Meta": 1.5, "Tiktok": 1.2, "Applovin": 1.0}.get(self.platform, 1.5)
        self._ctr = round(random.uniform(*ctr_range), 4)
        self._cpi = round(base_cpi * random.uniform(*cpi_mult), 2)
        self._spend = round(random.uniform(3000, 28000), 2)
        self._installs = max(1, int(self._spend / max(self._cpi, 0.1)))
        self._cpm = round(self._cpi * self._ctr * 1000, 2) if self._ctr > 0 else 8.0

    def _ok(self, data: Any) -> str:
        return json.dumps({"status": "success", "data": data}, ensure_ascii=False)

    def _err(self, message: str) -> str:
        return json.dumps({"status": "error", "message": message}, ensure_ascii=False)

    def search_trending_creatives(self, **kw) -> str:
        items = [{
            "creative_id": f"CR_{random.randint(10000, 99999)}",
            "platform": kw.get("platform", self.platform),
            "genre": kw.get("game_genre", self.genre),
            "format": random.choice(["video_15s", "video_30s", "playable"]),
            "hook_type": random.choice(["gameplay_fail", "challenge", "ugc_style", "tutorial"]),
            "estimated_ctr": round(random.uniform(0.030, 0.075), 4),
            "heat_score": round(random.uniform(70, 99), 1),
            "thumbnail_url": f"https://cdn.example.com/thumb/{random.randint(1000, 9999)}.jpg",
        } for _ in range(min(kw.get("top_k", 10), 8))]
        return self._ok({"results": items, "total": len(items)})

    def search_competitor_ads(self, **kw) -> str:
        ads = [{
            "ad_id": f"AD_{random.randint(10000, 99999)}",
            "competitor": kw.get("competitor_name", "Playrix"),
            "platform": kw.get("platform", self.platform),
            "format": random.choice(["video_15s", "video_30s", "image"]),
            "creative_theme": random.choice(["puzzle_difficulty", "emotional_story", "speed_challenge"]),
            "estimated_spend": f"${random.randint(5, 80)}K/week",
            "first_seen": f"2026-03-{random.randint(1, 10):02d}",
        } for _ in range(min(kw.get("limit", 20), 6))]
        return self._ok({"competitor": kw.get("competitor_name", "Playrix"), "ads": ads})

    def get_trending_hooks(self, **kw) -> str:
        hooks = [
            {"hook": "90%的人第一关都过不了", "type": "challenge", "avg_ctr": 0.062},
            {"hook": "你能撑过第3关吗？", "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[真实玩家录屏] 我卡了3天的关", "type": "ugc_style", "avg_ctr": 0.055},
            {"hook": "这个谜题难倒了99%的人", "type": "difficulty", "avg_ctr": 0.051},
            {"hook": "帮帮我！我快崩了", "type": "emotional", "avg_ctr": 0.049},
        ]
        return self._ok({"genre": kw.get("game_genre", self.genre), "hooks": hooks[:random.randint(3, 5)]})

    def validate_creative_spec(self, **kw) -> str:
        if self.scene == "validate_fail_size":
            return self._ok({"valid": False, "errors": [{
                "field": "file_size",
                "message": "文件大小 58.3MB 超过平台上限 50MB",
                "platform_limit": "50MB",
                "actual": "58.3MB",
            }]})
        if self.scene == "validate_fail_format":
            return self._ok({"valid": False, "errors": [{
                "field": "resolution",
                "message": "分辨率 1280x960 不符合要求，需为 9:16 或 1:1",
                "platform_limit": "1080x1920 or 1080x1080",
                "actual": "1280x960",
            }]})
        return self._ok({
            "valid": True,
            "file_size": f"{random.uniform(8, 35):.1f}MB",
            "resolution": "1080x1920",
            "duration": f"{random.choice([15, 30])}s",
            "format": "MP4",
            "checks_passed": 5,
        })

    def upload_creative_asset(self, **kw) -> str:
        if self.scene in {"upload_partial_fail", "single_upload_partial_fail"}:
            return self._ok({
                "asset_id": f"ASSET_{random.randint(1000, 9999)}",
                "status": "partial",
                "warning": "素材已上传但审核待定，预计12小时内完成审核",
            })
        return self._ok({
            "asset_id": f"ASSET_{random.randint(1000, 9999)}",
            "status": "uploaded",
            "creative_name": kw.get("creative_name", "new_creative"),
            "campaign_id": kw.get("campaign_id", self.campaign_id),
            "review_status": "pending",
            "estimated_review": "2-4 hours",
        })

    def batch_upload_creatives(self, **kw) -> str:
        files = kw.get("file_paths", ["f1.mp4", "f2.mp4", "f3.mp4"])
        failed = random.randint(0, 1) if self.scene in {"upload_partial_fail", "batch_upload_partial_fail"} else 0
        success = len(files) - failed
        results = [{"file": file_path, "status": "uploaded", "asset_id": f"ASSET_{random.randint(1000, 9999)}"} for file_path in files[:success]]
        if failed:
            results.append({"file": files[-1], "status": "failed", "reason": "file_size_exceeded"})
        return self._ok({"total": len(files), "success": success, "failed": failed, "results": results})

    def get_campaign_metrics(self, **kw) -> str:
        metrics_req = kw.get("metrics", ["roas", "retention_d1", "retention_d7", "ctr", "cpi", "spend", "installs"])
        result = {"campaign_id": self.campaign_id, "date_range": self.date_range, "breakdown": kw.get("breakdown", "daily"), "metrics": {}}
        for metric in metrics_req:
            if metric == "roas":
                result["metrics"][metric] = {"d7": self._roas_d7, "d30": self._roas_d30}
            elif metric == "retention_d1":
                result["metrics"][metric] = self._ret_d1
            elif metric == "retention_d7":
                result["metrics"][metric] = self._ret_d7
            elif metric == "ctr":
                result["metrics"][metric] = self._ctr
            elif metric == "cpi":
                result["metrics"][metric] = self._cpi
            elif metric == "spend":
                result["metrics"][metric] = self._spend
            elif metric == "installs":
                result["metrics"][metric] = self._installs
            elif metric == "cpm":
                result["metrics"][metric] = self._cpm
            elif metric == "impressions":
                result["metrics"][metric] = int(self._spend / max(self._cpm / 1000, 0.001))
        if self.scene == "creative_fatigue":
            result["ctr_wow_change"] = round(random.uniform(-0.38, -0.28), 3)
            result["fatigue_signal"] = "CTR 连续下滑超过3天，建议换量"
        if self.scene == "budget_underdelivery":
            result["budget_delivery_rate"] = round(random.uniform(0.38, 0.62), 2)
            result["cpm_trend"] = "持续走高"
        return self._ok(result)

    def get_creative_performance(self, **kw) -> str:
        top_k = kw.get("top_k", 10)
        creatives = []
        for index in range(min(top_k, 6)):
            decay = 1 - index * 0.12
            creatives.append({
                "creative_id": f"CR_{random.randint(10000, 99999)}",
                "name": f"{self.genre}_video_{index + 1:02d}_{random.choice(['US', 'JP', 'SEA'])}",
                "format": random.choice(["video_15s", "video_30s", "playable"]),
                "ctr": round(self._ctr * decay * random.uniform(0.90, 1.10), 4),
                "cpi": round(self._cpi * (1 + index * 0.08) * random.uniform(0.95, 1.05), 2),
                "roas_d7": round(self._roas_d7 * decay * random.uniform(0.92, 1.08), 3),
                "spend": round(self._spend * (0.35 / (index + 1)), 2),
                "installs": max(1, int(self._installs * (0.35 / (index + 1)))),
                "status": "fatiguing" if (index >= 3 and self.scene == "creative_fatigue") else "active",
            })
        return self._ok({"campaign_id": self.campaign_id, "sort_by": kw.get("sort_by", "ctr"), "creatives": creatives, "date_range": self.date_range})

    def get_appsflyer_report(self, **kw) -> str:
        return self._ok({
            "app_id": self.app_id,
            "report_type": kw.get("report_type", "retention"),
            "date_range": self.date_range,
            "data": {
                "retention_d1": self._ret_d1,
                "retention_d7": self._ret_d7,
                "installs": self._installs,
                "revenue_d7": round(self._roas_d7 * self._spend, 2),
                "revenue_d30": round(self._roas_d30 * self._spend, 2),
                "top_media_source": self.platform,
            },
        })

    def compare_campaigns(self, **kw) -> str:
        campaign_ids = kw.get("campaign_ids", [self.campaign_id, "CMP_9999"])
        comparisons = []
        for index, campaign_id in enumerate(campaign_ids):
            decay = 1 if index == 0 else random.uniform(0.70, 0.95)
            comparisons.append({
                "campaign_id": campaign_id,
                "roas_d7": round(self._roas_d7 * decay, 3),
                "ret_d1": round(self._ret_d1 * decay, 3),
                "ret_d7": round(self._ret_d7 * decay, 3),
                "cpi": round(self._cpi / decay, 2),
                "spend": round(self._spend * decay, 2),
                "installs": int(self._installs * decay),
            })
        return self._ok({"comparison": comparisons, "date_range": self.date_range})

    def detect_anomalies(self, **kw) -> str:
        anomaly_map = {
            "roas_danger": [{"metric": "roas_d7", "severity": "critical", "value": self._roas_d7, "baseline": self.roas_bl_d7, "deviation": f"{((self._roas_d7 / self.roas_bl_d7) - 1) * 100:.1f}%", "possible_causes": ["CPI rising rapidly", "Increased low-quality traffic share", "CVR declining due to creative fatigue"]}],
            "roas_warning": [{"metric": "roas_d7", "severity": "warning", "value": self._roas_d7, "baseline": self.roas_bl_d7, "deviation": f"{((self._roas_d7 / self.roas_bl_d7) - 1) * 100:.1f}%", "possible_causes": ["Slightly elevated CPI", "Performance decline in some creatives"]}],
            "ret_danger": [{"metric": "retention_d1", "severity": "critical", "value": self._ret_d1, "baseline": self.ret_bl_d1, "deviation": f"{((self._ret_d1 / self.ret_bl_d1) - 1) * 100:.1f}%", "possible_causes": ["Creative attracting wrong user segment", "Issue in first-time user experience", "Inaccurate geo targeting"]}],
            "both_danger": [
                {"metric": "roas_d7", "severity": "critical", "value": self._roas_d7, "baseline": self.roas_bl_d7, "deviation": f"{((self._roas_d7 / self.roas_bl_d7) - 1) * 100:.1f}%", "possible_causes": ["Overall campaign quality deteriorating"]},
                {"metric": "retention_d1", "severity": "critical", "value": self._ret_d1, "baseline": self.ret_bl_d1, "deviation": f"{((self._ret_d1 / self.ret_bl_d1) - 1) * 100:.1f}%", "possible_causes": ["Extremely poor user quality", "Severe mismatch between creative and actual game content"]},
            ],
            "creative_fatigue": [{"metric": "ctr", "severity": "warning", "value": self._ctr, "wow_change": "-32%", "possible_causes": ["Overexposure of primary creatives", "Audience largely saturated", "New creatives needed"]}],
            "budget_underdelivery": [{"metric": "budget_delivery_rate", "severity": "warning", "value": "52%", "possible_causes": ["CPM surged significantly", "Intense competition", "Bid too low"]}],
        }
        return self._ok({"campaign_id": self.campaign_id, "anomalies": anomaly_map.get(self.scene, []), "check_time": "2026-03-08T09:00:00Z"})

    def get_optimization_playbook(self, **kw) -> str:
        playbooks = {
            "low_roas": ["Review CPI distribution across ad groups; pause units where CPI > 2x target", "Audit audience targeting for high-CPI creatives; narrow to core user segments", "Try switching bidding strategy to tCPA", "Add new creatives to reduce dependency on high-CPI assets"],
            "low_ctr": ["Analyze common traits of top CTR creatives", "Pause creatives with CTR below 50% of industry average", "Reference competitor high-CTR creative directions and refresh creative library", "A/B test different hook types"],
            "low_retention": ["Review acquisition channel quality and compare media-source retention cohorts", "Audit whether creatives are overselling or mismatching the in-game experience", "Tighten targeting to reduce low-intent traffic and exclude poor-quality placements", "Coordinate with product to inspect first-session funnel drop-offs and onboarding friction"],
            "creative_fatigue": ["Launch 3-5 new creatives immediately covering different hook types", "Pause creatives with CTR week-over-week decline > 30%", "Slightly increase CPM bid to maintain impressions while accelerating creative rotation"],
            "budget_underdelivery": ["Check if current bid is below the platform's recommended minimum", "Moderately raise tCPA/tROAS target to open up more auction opportunities", "Expand audience targeting scope"],
        }
        issue_map = {
            "roas_danger": "low_roas",
            "roas_warning": "low_roas",
            "ret_danger": "low_retention",
            "ret_warning": "low_retention",
            "both_danger": "low_roas",
            "both_warning": "low_roas",
            "creative_fatigue": "creative_fatigue",
            "budget_underdelivery": "budget_underdelivery",
        }
        resolved = issue_map.get(self.scene, kw.get("issue_type", "low_roas"))
        return self._ok({"issue_type": resolved, "steps": playbooks.get(resolved or "low_roas", playbooks["low_roas"]), "estimated_impact": "medium-high", "implementation_time": "1-2 days"})

    def query_knowledge_base(self, **kw) -> str:
        domain = kw.get("domain", "bidding_strategy")
        chunks = {
            "bidding_strategy": [
                {"source": "UA Strategy Handbook v2.3", "content": "tCPA 适合安装量充足（>50/week）的 Campaign；tROAS 适合有足够内购数据的成熟 Campaign；学习期通常 7-14 天，期间避免频繁调价。"},
                {"source": "UAC Best Practices", "content": "Smart Bidding 学习期通常约 7 天，建议每周调价幅度不超过 20%。"},
            ],
            "creative_guideline": [
                {"source": "Creative Specifications 2026 Q1", "content": "视频前 3 秒是黄金钩子窗口，应直接展示核心玩法或高难关卡；hyper-casual 最优长度通常为 15 秒，竖版 9:16；playable 广告建议时长 30-60 秒。"},
            ],
            "platform_policy": [
                {"source": "Google Ads Policy Center", "content": "游戏广告需明确展示 PEGI/ESRB 分级；内购展示需符合透明披露要求；博彩类内容需额外白名单资质。"},
            ],
            "industry_benchmark": [
                {"source": "2026 Q1 Mobile Game Advertising Report", "content": f"{self.region} 市场 {self.genre} 品类 D7 ROAS 基准约为 {self.roas_bl_d7:.2f}，D1 留存基准约为 {self.ret_bl_d1:.1%}；US 市场 CPI 中位数通常在 $1.5-3.0。"},
            ],
        }
        return self._ok({"question": kw.get("question", ""), "domain": domain, "chunks": chunks.get(domain, chunks["bidding_strategy"]), "total": len(chunks.get(domain, chunks["bidding_strategy"]))})

    def get_benchmark_data(self, **kw) -> str:
        metric = kw.get("metric", "roas")
        benchmark = {
            "roas": {"d7": {"p25": round(self.roas_bl_d7 * 0.75, 3), "p50": round(self.roas_bl_d7, 3), "p75": round(self.roas_bl_d7 * 1.25, 3)}, "d30": {"p25": round(self.roas_bl_d30 * 0.75, 3), "p50": round(self.roas_bl_d30, 3), "p75": round(self.roas_bl_d30 * 1.25, 3)}},
            "retention_d1": {"p25": round(self.ret_bl_d1 * 0.80, 3), "p50": round(self.ret_bl_d1, 3), "p75": round(self.ret_bl_d1 * 1.20, 3)},
            "retention_d7": {"p25": round(self.ret_bl_d7 * 0.80, 3), "p50": round(self.ret_bl_d7, 3), "p75": round(self.ret_bl_d7 * 1.20, 3)},
            "ctr": {"p25": 0.018, "p50": 0.030, "p75": 0.048},
            "cpi": {"p25": 0.90, "p50": 1.60, "p75": 2.80},
        }.get(metric, {})
        return self._ok({
            "metric": metric,
            "genre": kw.get("game_genre", self.genre),
            "region": kw.get("region", self.region),
            "platform": kw.get("platform", self.platform),
            "benchmark": benchmark,
        })

    def get_platform_policy(self, **kw) -> str:
        platform = kw.get("platform", self.platform)
        policy_type = kw.get("policy_type", "ad_format")
        policies = {
            "ad_format": f"{platform} 支持 video(15s/30s)、playable、native image 等游戏广告格式，推荐优先使用 9:16 竖版。",
            "content_restriction": f"{platform} 禁止过度血腥暴力和误导性游戏截图，需明确展示年龄分级信息。",
            "targeting": f"{platform} 支持自定义受众、相似受众和兴趣定向，COPPA 下禁止对 13 岁以下用户定向。",
            "billing": f"{platform} 支持 CPM/CPC/CPA 等计费模式，最低日预算通常为 $10。",
        }
        return self._ok({"platform": platform, "policy_type": policy_type, "content": policies.get(policy_type, "暂无对应政策说明")})

    def execute(self, tool_name: str, arguments: Dict) -> str:
        dispatch = {
            "search_trending_creatives": self.search_trending_creatives,
            "search_competitor_ads": self.search_competitor_ads,
            "get_trending_hooks": self.get_trending_hooks,
            "validate_creative_spec": self.validate_creative_spec,
            "upload_creative_asset": self.upload_creative_asset,
            "batch_upload_creatives": self.batch_upload_creatives,
            "get_campaign_metrics": self.get_campaign_metrics,
            "get_creative_performance": self.get_creative_performance,
            "get_appsflyer_report": self.get_appsflyer_report,
            "compare_campaigns": self.compare_campaigns,
            "detect_anomalies": self.detect_anomalies,
            "get_optimization_playbook": self.get_optimization_playbook,
            "query_knowledge_base": self.query_knowledge_base,
            "get_benchmark_data": self.get_benchmark_data,
            "get_platform_policy": self.get_platform_policy,
        }
        function = dispatch.get(tool_name)
        return function(**arguments) if function else self._err(f"Unknown tool: {tool_name}")


def build_tool_arguments(tool_name: str, seed: Dict) -> Dict:
    campaign_id = seed["campaign_id"]
    app_id = seed["app_id"]
    date_range = seed["date_range"]
    platform = seed["platform"]
    genre = seed["game_genre"]
    region = seed["region"]
    scene = seed.get("scene_tag", "")
    query = seed.get("user_query", "")
    intent_bucket = seed.get("intent_bucket", "")
    query_slots = seed.get("query_slots", {})

    def extract_platform(default: str) -> str:
        for canonical, tokens in PLATFORM_TOKENS.items():
            if any(token in query for token in tokens):
                return canonical
        return query_slots.get("platform", "")

    def extract_genre(default: str) -> str:
        lowered = query.lower()
        for canonical, tokens in GENRE_TOKENS.items():
            if any(token.lower() in lowered for token in tokens):
                return canonical
        return query_slots.get("game_genre", "")

    def extract_region(default: str) -> str:
        for token in REGION_TOKENS:
            if token in query:
                return token
        return query_slots.get("region", "")

    def extract_campaign(default: str) -> str:
        match = re.search(r"CMP_\d+", query)
        if match:
            return match.group(0)
        return query_slots.get("campaign_id", "")

    def extract_app(default: str) -> str:
        match = re.search(r"(?:[a-zA-Z0-9_]+\.)+[a-zA-Z0-9_]+", query)
        if match:
            return match.group(0)
        return query_slots.get("app_id", "")

    def extract_competitor(default: str) -> str:
        for competitor in COMPETITORS:
            if competitor in query:
                return competitor
        return query_slots.get("competitor_name", "")

    def infer_sort_by() -> str:
        lowered = query.lower()
        if "cpm" in lowered:
            return "cpm"
        if "cpi" in lowered:
            return "cpi"
        if "roas" in lowered or "回收" in query:
            return "roas_d7"
        return "ctr"

    def infer_metric_names() -> list[str]:
        explicit = query_slots.get("metrics")
        if explicit:
            return explicit
        lowered = query.lower()
        metrics: list[str] = []
        if "roas" in lowered or "回收" in query:
            metrics.append("roas")
        if "留存" in query or "retention" in lowered:
            metrics.extend(["retention_d1", "retention_d7"])
        if "ctr" in lowered or "点击" in query:
            metrics.append("ctr")
        if "cpi" in lowered:
            metrics.append("cpi")
        if "cpm" in lowered:
            metrics.append("cpm")
        if "花费" in query or "预算" in query or "消耗" in query or "spend" in lowered:
            metrics.append("spend")
        if "安装" in query or "installs" in lowered:
            metrics.append("installs")
        return metrics or ["roas"]

    def infer_report_type() -> str:
        if "归因" in query or "revenue" in query.lower():
            return "attribution"
        return "retention"

    def infer_knowledge_domain() -> str:
        if intent_bucket in {"bidding_strategy", "creative_guideline", "platform_policy", "industry_benchmark"}:
            return intent_bucket
        return scene if scene in {"bidding_strategy", "creative_guideline", "platform_policy", "industry_benchmark"} else "bidding_strategy"

    def infer_benchmark_metric() -> str:
        explicit_metric = query_slots.get("benchmark_metric")
        if explicit_metric:
            return explicit_metric
        lowered = query.lower()
        if "cpm" in lowered:
            return "cpm"
        if "cpi" in lowered:
            return "cpi"
        if "ctr" in lowered or scene == "creative_fatigue":
            return "ctr"
        if "留存" in query or "retention" in lowered or scene in {"ret_warning", "ret_danger"}:
            return "retention_d1"
        return "roas"

    def infer_policy_type() -> str:
        if any(token in query for token in ["限制", "风险", "政策", "审核"]):
            return "content_restriction"
        if any(token in query for token in ["尺寸", "比例", "格式", "规格", "时长"]):
            return "ad_format"
        return "content_restriction"

    resolved_platform = extract_platform(platform)
    resolved_genre = extract_genre(genre)
    resolved_region = extract_region(region)
    resolved_campaign = extract_campaign(campaign_id)
    resolved_app = extract_app(app_id)
    resolved_competitor = extract_competitor("Playrix")

    return {
        "search_trending_creatives": {"platform": resolved_platform, "game_genre": resolved_genre, "region": resolved_region, "time_range": 7, "top_k": 10},
        "search_competitor_ads": {"competitor_name": resolved_competitor, "platform": resolved_platform, "limit": 20},
        "get_trending_hooks": {"game_genre": resolved_genre, "creative_type": "playable" if "playable" in query.lower() else "video"},
        "validate_creative_spec": {"file_path": f"assets/{resolved_genre}_video_{random.randint(1, 9):02d}.mp4", "platform": resolved_platform, "ad_format": random.choice(["interstitial", "rewarded"])},
        "upload_creative_asset": {"file_path": f"assets/{resolved_genre}_video_{random.randint(1, 9):02d}.mp4", "asset_type": "video", "campaign_id": resolved_campaign, "ad_group_id": f"AG_{random.randint(100, 999)}", "creative_name": f"{resolved_genre}_{resolved_region}_{date_range['start']}_v{random.randint(1, 9)}"},
        "batch_upload_creatives": {"file_paths": [f"assets/{resolved_genre}_v{i}.mp4" for i in range(1, 4)], "campaign_id": resolved_campaign, "naming_convention": "{genre}_{region}_{date}_{index}"},
        "get_campaign_metrics": {"campaign_id": resolved_campaign, "metrics": infer_metric_names() if intent_bucket == "campaign_metrics" else ["roas", "retention_d1", "retention_d7", "ctr", "cpi", "spend", "installs"], "date_range": date_range, "breakdown": "daily"},
        "get_creative_performance": {"campaign_id": resolved_campaign, "sort_by": infer_sort_by(), "top_k": 10, "date_range": date_range},
        "get_appsflyer_report": {"app_id": resolved_app, "report_type": infer_report_type(), "date_range": date_range, "groupby": ["media_source", "country"] if "国家" in query or "country" in query.lower() or "来源" in query or "渠道" in query else ["media_source"]},
        "compare_campaigns": {"campaign_ids": [resolved_campaign, f"CMP_{random.randint(1000, 9999)}"], "metrics": ["roas", "retention_d1", "cpi", "spend"], "date_range": date_range},
        "detect_anomalies": {"campaign_id": resolved_campaign, "metric": "roas" if "roas" in scene else ("retention_d1" if "ret" in scene else "ctr"), "sensitivity": 0.75},
        "get_optimization_playbook": {"issue_type": {"roas_danger": "low_roas", "roas_warning": "low_roas", "ret_danger": "low_retention", "ret_warning": "low_retention", "creative_fatigue": "creative_fatigue", "budget_underdelivery": "budget_underdelivery"}.get(scene, "low_roas")},
        "query_knowledge_base": {"question": seed.get("user_query", "UA strategy"), "domain": infer_knowledge_domain(), "search_mode": "hybrid", "top_k": 5},
        "get_benchmark_data": {"metric": infer_benchmark_metric(), "game_genre": resolved_genre, "region": resolved_region, "platform": resolved_platform},
        "get_platform_policy": {"platform": resolved_platform, "policy_type": infer_policy_type()},
    }.get(tool_name, {})


def _parse_tool_payload(result: str) -> dict[str, Any]:
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_final_response(seed: Dict, ex: MockToolExecutor, tool_results: list[tuple[str, dict[str, Any]]]) -> str:
    scene = seed.get("scene_tag", "healthy")
    intent_bucket = seed.get("intent_bucket", "")
    campaign_id = seed["campaign_id"]
    roas_baseline = ex.roas_bl_d7
    retention_baseline_d1 = ex.ret_bl_d1
    retention_baseline_d7 = ex.ret_bl_d7
    roas_d7 = ex._roas_d7
    retention_d1 = ex._ret_d1
    retention_d7 = ex._ret_d7
    ctr = ex._ctr
    cpi = ex._cpi
    spend = ex._spend
    roas_status = "✅ 达标" if roas_d7 >= roas_baseline else ("⚠️ 预警" if roas_d7 >= roas_baseline * 0.80 else "🚨 告警")
    ret_status = "✅ 达标" if retention_d1 >= retention_baseline_d1 else ("⚠️ 预警" if retention_d1 >= retention_baseline_d1 * 0.80 else "🚨 告警")
    roas_pct = (roas_d7 / roas_baseline - 1) * 100
    ret_pct = (retention_d1 / retention_baseline_d1 - 1) * 100

    templates = {
        "healthy": f"""**{campaign_id} 投放健康报告**\n\n**核心指标 vs 安全基线**\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，{roas_status}，超出 {roas_pct:+.1f}%）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，{ret_status}，超出 {ret_pct:+.1f}%）\n- D7 留存：{retention_d7:.1%}（基线 {retention_baseline_d7:.1%}）\n\n**辅助指标**\n- CTR：{ctr:.2%} | CPI：${cpi:.2f} | 花费：${spend:,.0f}\n\n**结论**：当前 Campaign 整体健康，ROAS 和留存均超过安全基线。""",
        "roas_warning": f"""**{campaign_id} ROAS 预警分析**\n\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，{roas_status}，偏低 {abs(roas_pct):.1f}%）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，{ret_status}）\n\n**建议**：检查高 CPI 的 Ad Group，并持续观察 3 天趋势。""",
        "roas_danger": f"""**{campaign_id} ROAS 严重告警 🚨**\n\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，{roas_status}，跌幅 {abs(roas_pct):.1f}%）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，{ret_status}）\n\n**建议**：立即暂停低 ROAS 单元，降低预算并补充新素材。""",
        "ret_warning": f"""**{campaign_id} 用户留存预警分析**\n\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，{roas_status}）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，{ret_status}，偏低 {abs(ret_pct):.1f}%）\n\n**建议**：分析高 CTR 但低留存的素材，并结合 AppsFlyer 数据排查。""",
        "ret_danger": f"""**{campaign_id} 用户留存严重告警 🚨**\n\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，{roas_status}）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，{ret_status}，跌幅 {abs(ret_pct):.1f}%）\n- D7 留存：{retention_d7:.1%}（基线 {retention_baseline_d7:.1%}）\n\n**建议**：暂停低留存单元，审查素材与定向，并联系产品团队排查。""",
        "both_warning": f"""**{campaign_id} ROAS + 留存双项预警**\n\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，{roas_status}，偏低 {abs(roas_pct):.1f}%）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，{ret_status}，偏低 {abs(ret_pct):.1f}%）\n\n**建议**：收紧定向，审查素材 CTR 周趋势。""",
        "both_danger": f"""**{campaign_id} 全线告警 —— 需要立即介入 🚨🚨**\n\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，跌幅 {abs(roas_pct):.1f}%）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，跌幅 {abs(ret_pct):.1f}%）\n\n**建议**：立即降预算、暂停低效单元并联合排查。""",
        "creative_fatigue": f"""**{campaign_id} 素材疲劳预警**\n\n- D7 ROAS：{roas_d7:.3f}（基线 {roas_baseline:.3f}，✅ 仍达标）\n- D1 留存：{retention_d1:.1%}（基线 {retention_baseline_d1:.1%}，✅ 仍达标）\n- CTR：{ctr:.2%}（周环比下滑约 32%）\n\n**建议**：本周内上线 3-5 个新素材并下线疲劳素材。""",
        "budget_underdelivery": f"""**{campaign_id} 预算欠量分析**\n\n- 预算消耗率：约 52%\n- CPM：持续走高\n\n**建议**：上调 tCPA 目标，扩大定向并补充素材。""",
        "insufficient_data": f"""**{campaign_id} 数据说明**\n\n当前 Campaign 投放时间较短，主要指标仅供参考，建议继续观察至第 5-7 天。""",
    }
    result_map = {tool_name: payload for tool_name, payload in tool_results}
    if seed.get("workflow") == 1:
        if intent_bucket == "competitor_ads":
            ads_payload = result_map.get("search_competitor_ads", {})
            ads = ads_payload.get("data", {}).get("ads", [])
            competitor = ads_payload.get("data", {}).get("competitor", seed.get("query_slots", {}).get("competitor_name", "竞品"))
            platform_name = ads[0].get("platform") if ads else seed.get("platform", "平台")
            highlights = [
                f"{item.get('ad_id')}（{item.get('format')}，主题 {item.get('creative_theme')}）"
                for item in ads[:3]
            ]
            return f"{competitor} 最近在 {platform_name} 主要在投这些广告：{'；'.join(highlights)}。"
        if intent_bucket == "trending_with_hooks":
            creative_payload = result_map.get("search_trending_creatives", {})
            hook_payload = result_map.get("get_trending_hooks", {})
            creatives = creative_payload.get("data", {}).get("results", [])
            hooks = hook_payload.get("data", {}).get("hooks", [])
            platform_name = creatives[0].get("platform") if creatives else seed.get("platform", "平台")
            genre_name = creatives[0].get("genre") if creatives else hook_payload.get("data", {}).get("genre", seed.get("game_genre", "该品类"))
            creative_text = "；".join(
                f"{item.get('creative_id')}（{item.get('format')}，{item.get('hook_type')}）"
                for item in creatives[:2]
            )
            hook_text = "；".join(item.get("hook", "") for item in hooks[:3])
            return f"{platform_name} 上 {genre_name} 最近跑得好的素材包括：{creative_text}。常见高表现钩子有：{hook_text}。"
        creative_payload = result_map.get("search_trending_creatives", {})
        creatives = creative_payload.get("data", {}).get("results", [])
        platform_name = creatives[0].get("platform") if creatives else seed.get("platform", "平台")
        genre_name = creatives[0].get("genre") if creatives else seed.get("game_genre", "该品类")
        highlights = [
            f"{item.get('creative_id')}（{item.get('format')}，CTR {item.get('estimated_ctr', 0):.1%}）"
            for item in creatives[:3]
        ]
        return f"{platform_name} 上 {genre_name} 最近表现较强的素材有：{'；'.join(highlights)}。"
    if scene in {"upload_success", "single_upload_success", "batch_upload_success", "single_upload_partial_fail", "batch_upload_partial_fail"}:
        upload_payload = result_map.get("upload_creative_asset", {}).get("data", {})
        if upload_payload:
            return f"{upload_payload.get('creative_name', '素材')} 已成功上传至 {upload_payload.get('campaign_id', campaign_id)}，asset_id 为 {upload_payload.get('asset_id')}，当前审核状态为 {upload_payload.get('review_status')}。"
        batch_payload = result_map.get("batch_upload_creatives", {}).get("data", {})
        if batch_payload:
            details = "；".join(
                f"{item.get('file')} -> {item.get('status')}"
                for item in batch_payload.get("results", [])[:2]
            )
            return f"共上传 {batch_payload.get('total')} 个素材，成功 {batch_payload.get('success')} 个，失败 {batch_payload.get('failed')} 个。{details}"
        return f"素材已成功上传至 {campaign_id}，审核通常需要 2-4 小时。"
    if scene in ("validate_fail_size", "validate_fail_format"):
        validation_payload = result_map.get("validate_creative_spec", {}).get("data", {})
        errors = validation_payload.get("errors", [])
        if errors:
            first = errors[0]
            return f"素材规格校验未通过：{first.get('field')} 存在问题，{first.get('message')}。请调整后重新上传。"
        return "素材规格校验未通过，请根据上方错误信息调整后重新上传。"
    if scene == "creative_metrics":
        creative_payload = result_map.get("get_creative_performance", {}).get("data", {})
        creatives = creative_payload.get("creatives", [])
        sort_by = creative_payload.get("sort_by", "ctr")
        summary = "；".join(
            f"{item.get('creative_id')}（{sort_by}: {item.get(sort_by, item.get('ctr'))}）"
            for item in creatives[:2]
        )
        return f"{campaign_id} 按素材维度表现较好的创意有：{summary}。"
    if scene == "appsflyer_report":
        appsflyer_payload = result_map.get("get_appsflyer_report", {}).get("data", {})
        report_type = appsflyer_payload.get("report_type")
        data = appsflyer_payload.get("data", {})
        if report_type == "attribution":
            return f"{appsflyer_payload.get('app_id', seed.get('app_id'))} 最近的归因数据里，主要来源是 {data.get('top_media_source')}，D7 收入约为 ${data.get('revenue_d7', 0):,.0f}。"
        return f"{appsflyer_payload.get('app_id', seed.get('app_id'))} 最近留存表现为：D1 留存 {data.get('retention_d1', 0):.1%}，D7 留存 {data.get('retention_d7', 0):.1%}。"
    if intent_bucket == "campaign_metrics":
        metrics_payload = result_map.get("get_campaign_metrics", {}).get("data", {}).get("metrics", {})
        parts: list[str] = []
        if "roas" in metrics_payload:
            roas = metrics_payload["roas"]
            parts.append(f"D7 ROAS {roas.get('d7', roas_d7):.3f}")
            if "d30" in roas:
                parts.append(f"D30 ROAS {roas.get('d30', ex._roas_d30):.3f}")
        if "retention_d1" in metrics_payload:
            parts.append(f"D1 留存 {metrics_payload['retention_d1']:.1%}")
        if "retention_d7" in metrics_payload:
            parts.append(f"D7 留存 {metrics_payload['retention_d7']:.1%}")
        if "ctr" in metrics_payload:
            parts.append(f"CTR {metrics_payload['ctr']:.2%}")
        if "cpi" in metrics_payload:
            parts.append(f"CPI ${metrics_payload['cpi']:.2f}")
        if "cpm" in metrics_payload:
            parts.append(f"CPM ${metrics_payload['cpm']:.2f}")
        if "spend" in metrics_payload:
            parts.append(f"花费 ${metrics_payload['spend']:,.0f}")
        if "installs" in metrics_payload:
            parts.append(f"安装量 {metrics_payload['installs']}")
        return f"{campaign_id} 最近数据为：{'，'.join(parts)}。"
    if scene == "query_roas":
        metrics_payload = result_map.get("get_campaign_metrics", {}).get("data", {}).get("metrics", {})
        roas = metrics_payload.get("roas", {})
        return f"{campaign_id} 当前查询到的核心回收数据如下：D7 ROAS 为 {roas.get('d7', roas_d7):.3f}，D30 ROAS 为 {roas.get('d30', ex._roas_d30):.3f}。如果需要，我可以继续按天、按国家或按素材维度展开。"
    if scene == "query_retention":
        metrics_payload = result_map.get("get_campaign_metrics", {}).get("data", {}).get("metrics", {})
        return f"{campaign_id} 当前留存数据如下：D1 留存 {metrics_payload.get('retention_d1', retention_d1):.1%}，D7 留存 {metrics_payload.get('retention_d7', retention_d7):.1%}。如果你要，我可以继续结合 AppsFlyer 维度拆分来源和地区。"
    if scene == "query_ctr":
        metrics_payload = result_map.get("get_campaign_metrics", {}).get("data", {}).get("metrics", {})
        return f"{campaign_id} 当前 CTR 为 {metrics_payload.get('ctr', ctr):.2%}。如果需要进一步判断素材吸引力，我可以继续帮你拉 CPM、CPI 或按素材拆分表现。"
    if scene == "query_spend":
        metrics_payload = result_map.get("get_campaign_metrics", {}).get("data", {}).get("metrics", {})
        return f"{campaign_id} 当前查询到的花费为 ${metrics_payload.get('spend', spend):,.0f}。如果你想看预算消耗节奏，我可以继续按天或按广告组拆开。"
    if scene == "query_installs":
        metrics_payload = result_map.get("get_campaign_metrics", {}).get("data", {}).get("metrics", {})
        return f"{campaign_id} 当前安装量为 {metrics_payload.get('installs', ex._installs)}。如果需要，我可以继续按国家、媒体来源或时间维度展开安装分布。"
    if scene == "query_cpm":
        metrics_payload = result_map.get("get_campaign_metrics", {}).get("data", {}).get("metrics", {})
        return f"{campaign_id} 当前 CPM 为 ${metrics_payload.get('cpm', ex._cpm):.2f}。如果你要判断流量成本是否异常，我也可以继续补充 CTR、CPI 和消耗数据。"
    if scene in ("bidding_strategy", "creative_guideline", "platform_policy", "industry_benchmark", "knowledge_base"):
        if "get_platform_policy" in result_map:
            payload = result_map["get_platform_policy"].get("data", {})
            return f"{payload.get('platform', seed.get('platform'))} 关于该问题的政策要求是：{payload.get('content', '暂无对应政策说明')}。"
        if "get_benchmark_data" in result_map:
            payload = result_map["get_benchmark_data"].get("data", {})
            benchmark = payload.get("benchmark", {})
            return f"{payload.get('platform', seed.get('platform'))} 上 {payload.get('genre', seed.get('game_genre'))} 的 {payload.get('metric', 'benchmark')} benchmark 参考为：{benchmark}。"
        if "query_knowledge_base" in result_map:
            chunks = result_map["query_knowledge_base"].get("data", {}).get("chunks", [])
            summary = "；".join(chunk.get("content", "") for chunk in chunks[:2])
            return f"结合知识库资料，关键结论是：{summary}"
    return templates.get(scene, templates["healthy"])


def make_tool_call_message(tool_name: str, arguments: Dict) -> Tuple[Dict, str]:
    call_id = f"call_{uuid.uuid4().hex[:8]}"
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": tool_name, "arguments": json.dumps(arguments, ensure_ascii=False)},
        }],
    }, call_id


def make_tool_result_message(result: str, call_id: str) -> Dict:
    return {"role": "tool", "content": result, "tool_call_id": call_id}


def build_clarify_question(seed: Dict) -> str:
    return {
        "campaign_id_missing": "请问您想查看哪个 Campaign 的数据？提供 Campaign ID 后我马上帮您拉取。",
        "campaign_id_and_timerange_missing": "请问您想分析哪个 Campaign？需要查看哪个时间段的数据？",
        "timerange_missing": "请问您想看哪个时间段的数据？例如最近7天、上周或本月。",
        "platform_or_genre_missing": "请问您想搜索哪个平台的素材？游戏品类是什么？",
        "platform_missing": "请问您想看哪个平台的数据或规则？",
        "app_id_missing": "请问您想查看哪个 App 的数据？提供 App ID 后我继续帮您查。",
        "platform_region_or_genre_missing": "请问您要看哪个平台、哪个地区、哪个品类的 benchmark？",
    }.get(seed.get("clarification_reason", ""), "请提供更多信息，以便我为您准确查询。")


def build_refusal(seed: Dict) -> str:
    return {
        "off_topic": "抱歉，我是专注于移动游戏广告投放的 AI 助手，这个问题超出了我的服务范围。如有投放数据分析、素材搜索、Campaign 优化等需求，随时可以问我。",
        "unauthorized_internal": "抱歉，删除、修改或导出账户级敏感数据属于高风险操作，超出了我的执行权限。为避免不可逆影响，请通过平台后台的正式审批流程或联系账户管理员处理。",
        "unauthorized_external": "抱歉，获取竞品账户数据、访问未授权系统或导出竞品素材属于违规甚至违法行为，我不能协助这类请求。",
    }.get(seed.get("refusal_type", "off_topic"), "抱歉，这个问题超出了我的服务范围。")


def build_message_record(seed: Dict) -> Dict:
    executor = MockToolExecutor(seed)
    tool_plan = seed.get("tool_plan", [])
    workflow = seed.get("workflow", 0)
    messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if seed.get("needs_clarification"):
        messages.append({"role": "user", "content": seed["user_query"]})
        messages.append({"role": "assistant", "content": build_clarify_question(seed)})
        answer = seed.get("clarification_answer") or ""
        if answer:
            messages.append({"role": "user", "content": answer})
            if not tool_plan:
                return wrap_record(seed, messages)
        else:
            return wrap_record(seed, messages)
    else:
        messages.append({"role": "user", "content": seed["user_query"]})

    if workflow == 7:
        messages.append({"role": "assistant", "content": build_refusal(seed)})
        return wrap_record(seed, messages)

    collected_results: list[tuple[str, dict[str, Any]]] = []
    for group in tool_plan:
        mode = group["mode"]
        tools = group["tools"]
        if mode == "parallel" and len(tools) > 1:
            tool_calls_payload: List[Dict[str, Any]] = []
            pending_results: List[Tuple[str, str, Dict[str, Any]]] = []
            for tool_name in tools:
                arguments = build_tool_arguments(tool_name, seed)
                call_id = f"call_{uuid.uuid4().hex[:8]}"
                tool_calls_payload.append({"id": call_id, "type": "function", "function": {"name": tool_name, "arguments": json.dumps(arguments, ensure_ascii=False)}})
                pending_results.append((call_id, tool_name, arguments))
            messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_payload})
            for call_id, tool_name, arguments in pending_results:
                result = executor.execute(tool_name, arguments)
                messages.append(make_tool_result_message(result, call_id))
                collected_results.append((tool_name, _parse_tool_payload(result)))
        else:
            for tool_name in tools:
                arguments = build_tool_arguments(tool_name, seed)
                assistant_message, call_id = make_tool_call_message(tool_name, arguments)
                messages.append(assistant_message)
                result = executor.execute(tool_name, arguments)
                messages.append(make_tool_result_message(result, call_id))
                collected_results.append((tool_name, _parse_tool_payload(result)))

    messages.append({"role": "assistant", "content": build_final_response(seed, executor, collected_results)})
    return wrap_record(seed, messages)


def wrap_record(seed: Dict, messages: List[Dict]) -> Dict:
    return {
        "messages": messages,
        "_meta": {
            "workflow": seed.get("workflow"),
            "workflow_name": seed.get("workflow_name"),
            "scene_tag": seed.get("scene_tag"),
            "platform": seed.get("platform"),
            "game_genre": seed.get("game_genre"),
            "tool_chain": seed.get("tool_chain"),
            "tool_plan": seed.get("tool_plan"),
            "has_parallel": seed.get("has_parallel", False),
        },
    }


def build_record(seed: Dict) -> Dict:
    return build_message_record(seed)


def resolve_input_path(input_name: str) -> Path:
    processed_dir = Path(__file__).resolve().parents[2] / "data" / "processed"
    candidate = processed_dir / input_name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(UI_TEXT["file_not_found"].format(name=input_name, processed_dir=processed_dir))


def derive_output_path(input_path: Path) -> Path:
    ready_dir = Path(__file__).resolve().parents[2] / "data" / "ready2train"
    ready_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    out_stem = stem.replace("seeds", "sft") if "seeds" in stem else f"{stem}_sft"
    return ready_dir / f"{out_stem}.json"


def main(input_path: str = "ad_agent_seeds.json", output_path: str = "ad_agent_sft_dataset.json") -> None:
    seeds = json.loads(Path(input_path).read_text(encoding="utf-8"))
    print(UI_TEXT["loaded"].format(count=len(seeds)))

    records: list[dict] = []
    failed = 0
    for seed in tqdm(seeds, desc=UI_TEXT["desc"]):
        try:
            records.append(build_record(seed))
        except Exception as error:
            failed += 1
            tqdm.write(UI_TEXT["skip"].format(error=error))

    workflow_count: dict[str, int] = {}
    scene_count: dict[str, int] = {}
    turn_lengths: list[int] = []
    parallel_count = 0
    for record in records:
        meta = record["_meta"]
        workflow_count[meta["workflow_name"]] = workflow_count.get(meta["workflow_name"], 0) + 1
        scene_count[meta["scene_tag"]] = scene_count.get(meta["scene_tag"], 0) + 1
        turn_lengths.append(len(record["messages"]))
        if meta.get("has_parallel"):
            parallel_count += 1

    print(UI_TEXT["done"].format(count=len(records), failed=failed))
    print(UI_TEXT["avg_turns"].format(value=sum(turn_lengths) / max(len(turn_lengths), 1)))
    print(f"  并行样本数: {parallel_count} ({100 * parallel_count / max(len(records), 1):.1f}%)")

    print(UI_TEXT["workflow_distribution"])
    for workflow_name, number in sorted(workflow_count.items()):
        print(f"  {workflow_name}: {number}")

    print(UI_TEXT["scene_distribution"])
    for scene_tag, number in sorted(scene_count.items(), key=lambda item: -item[1])[:12]:
        print(f"  {scene_tag}: {number}")

    Path(output_path).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(UI_TEXT["saved"].format(path=output_path))


if __name__ == "__main__":
    input_name = input(UI_TEXT["file_prompt"]).strip()
    try:
        input_path = resolve_input_path(input_name)
    except FileNotFoundError:
        processed_dir = Path(__file__).resolve().parents[2] / "data" / "processed"
        print(UI_TEXT["file_not_found"].format(name=input_name, processed_dir=processed_dir))
        raise SystemExit(1)

    print(UI_TEXT["found_input"].format(path=input_path))
    output_path = derive_output_path(input_path)
    print(UI_TEXT["output_path"].format(path=output_path))
    main(str(input_path), str(output_path))
