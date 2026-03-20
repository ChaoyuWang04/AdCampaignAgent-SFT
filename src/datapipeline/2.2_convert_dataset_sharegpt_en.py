"""
Ad Campaign Agent - Phase 2: Conversation Generator
Input:  seed JSON (from 1.1_ad_gen_data_cn.py / 1.2_ad_gen_data_en.py)
Output: ShareGPT format JSON (HuggingFace / LLaMA Factory ready)
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Any
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────
# 1. System Prompt
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional mobile game advertising AI assistant (Ad Campaign Agent), serving the UA (User Acquisition) team.

## Core Responsibilities
- Evaluate campaign health with ROAS and user retention (Retention) safety baselines as the core metrics
- Identify metric anomalies and provide structured optimization recommendations
- Search for trending creatives, manage creative uploads
- Answer questions on bidding strategies, platform policies, industry benchmarks, and other professional topics

## Working Principles
- Always explicitly state whether ROAS / Retention meets the safety baseline during analysis — let data speak
- Proactively ask for missing information when needed, one key question at a time
- Must call validate_creative_spec to check specs before uploading any creative
- Politely decline requests that are out of scope or involve unauthorized operations, and explain why"""


# ─────────────────────────────────────────────────────────────
# 2. Scene Config —— controls metric deviation ranges relative to baselines per scene
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

# Non-ROAS/RET scenes: no baseline calculation needed
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
    Core metrics are computed once in __init__ to ensure data consistency across tools within a conversation.
    """

    def __init__(self, seed: Dict):
        self.seed = seed
        self.scene = seed.get("scene_tag", "healthy")
        self.cfg = SCENE_CFG.get(self.scene, {})

        # Baselines
        self.roas_bl_d7  = seed.get("roas_baseline_d7",  0.80)
        self.roas_bl_d30 = seed.get("roas_baseline_d30", 1.20)
        self.ret_bl_d1   = seed.get("ret_baseline_d1",   0.35)
        self.ret_bl_d7   = seed.get("ret_baseline_d7",   0.12)

        self.platform    = seed.get("platform", "google_uac")
        self.genre       = seed.get("game_genre", "casual")
        self.region      = seed.get("region", "US")
        self.campaign_id = seed.get("campaign_id", "CMP_0000")
        self.app_id      = seed.get("app_id", "com.example.game")
        self.date_range  = seed.get("date_range", {"start": "2026-03-01", "end": "2026-03-07"})

        # Pre-compute core metrics (shared across tools)
        if self.scene not in NON_METRIC_SCENES:
            rm = self.cfg.get("roas_mult", (1.0, 1.0))
            rtm = self.cfg.get("ret_mult",  (1.0, 1.0))
            self._roas_d7  = round(self.roas_bl_d7  * random.uniform(*rm),  3)
            self._roas_d30 = round(self.roas_bl_d30 * (self._roas_d7 / max(self.roas_bl_d7, 0.01))
                                   * random.uniform(0.95, 1.05), 3)
            self._ret_d1   = round(self.ret_bl_d1   * random.uniform(*rtm), 3)
            self._ret_d7   = round(self.ret_bl_d7   * (self._ret_d1 / max(self.ret_bl_d1, 0.01))
                                   * random.uniform(0.95, 1.05), 3)
        else:
            self._roas_d7  = self.roas_bl_d7
            self._roas_d30 = self.roas_bl_d30
            self._ret_d1   = self.ret_bl_d1
            self._ret_d7   = self.ret_bl_d7

        cr = self.cfg.get("ctr_range", (0.025, 0.045))
        cm = self.cfg.get("cpi_mult",  (0.90, 1.10))
        base_cpi = {"google_uac": 1.8, "meta": 1.5, "tiktok": 1.2, "applovin": 1.0}.get(self.platform, 1.5)
        self._ctr     = round(random.uniform(*cr), 4)
        self._cpi     = round(base_cpi * random.uniform(*cm), 2)
        self._spend   = round(random.uniform(3000, 28000), 2)
        self._installs = max(1, int(self._spend / max(self._cpi, 0.1)))
        self._cpm     = round(self._cpi * self._ctr * 1000, 2) if self._ctr > 0 else 8.0

    # ── helpers ──────────────────────────────────────────────

    def _ok(self, data: Any) -> str:
        return json.dumps({"status": "success", "data": data}, ensure_ascii=False)

    def _err(self, msg: str) -> str:
        return json.dumps({"status": "error", "message": msg}, ensure_ascii=False)

    # ── Category 1: Creative Search ──────────────────────────

    def search_trending_creatives(self, **kwargs) -> str:
        platform = kwargs.get("platform", self.platform)
        genre    = kwargs.get("game_genre", self.genre)
        top_k    = kwargs.get("top_k", 10)
        items = []
        for i in range(min(top_k, 8)):
            items.append({
                "creative_id": f"CR_{random.randint(10000,99999)}",
                "platform": platform,
                "genre": genre,
                "format": random.choice(["video_15s", "video_30s", "playable"]),
                "hook_type": random.choice(["gameplay_fail", "challenge", "ugc_style", "tutorial"]),
                "estimated_ctr": round(random.uniform(0.030, 0.075), 4),
                "heat_score": round(random.uniform(70, 99), 1),
                "thumbnail_url": f"https://cdn.example.com/thumb/{random.randint(1000,9999)}.jpg",
            })
        return self._ok({"results": items, "total": len(items), "platform": platform})

    def search_competitor_ads(self, **kwargs) -> str:
        competitor = kwargs.get("competitor_name", "Playrix")
        platform   = kwargs.get("platform", self.platform)
        limit      = kwargs.get("limit", 20)
        items = []
        for i in range(min(limit, 6)):
            items.append({
                "ad_id": f"AD_{random.randint(10000,99999)}",
                "competitor": competitor,
                "platform": platform,
                "format": random.choice(["video_15s", "video_30s", "image"]),
                "creative_theme": random.choice(["puzzle_difficulty", "emotional_story", "speed_challenge"]),
                "estimated_spend": f"${random.randint(5,80)}K/week",
                "first_seen": f"2026-03-{random.randint(1,10):02d}",
            })
        return self._ok({"competitor": competitor, "ads": items})

    def get_trending_hooks(self, **kwargs) -> str:
        genre = kwargs.get("game_genre", self.genre)
        templates = [
            {"hook": "90% of players can't beat the first level", "type": "challenge", "avg_ctr": 0.062},
            {"hook": "Can you survive past level 3?", "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[Real player footage] Stuck on this level for 3 days", "type": "ugc_style", "avg_ctr": 0.055},
            {"hook": "This puzzle stumped 99% of people", "type": "difficulty", "avg_ctr": 0.051},
            {"hook": "Help me! I'm losing my mind", "type": "emotional", "avg_ctr": 0.049},
        ]
        return self._ok({"genre": genre, "hooks": templates[:random.randint(3,5)]})

    # ── Category 2: Creative Upload ──────────────────────────

    def validate_creative_spec(self, **kwargs) -> str:
        scene = self.scene
        if scene == "validate_fail_size":
            return self._ok({
                "valid": False,
                "errors": [{"field": "file_size", "message": "File size 58.3MB exceeds platform limit of 50MB",
                            "platform_limit": "50MB", "actual": "58.3MB"}],
            })
        if scene == "validate_fail_format":
            return self._ok({
                "valid": False,
                "errors": [{"field": "resolution", "message": "Resolution 1280x960 does not meet requirements; must be 9:16 or 1:1",
                            "platform_limit": "1080x1920 or 1080x1080", "actual": "1280x960"}],
            })
        return self._ok({"valid": True, "file_size": f"{random.uniform(8,35):.1f}MB",
                         "resolution": "1080x1920", "duration": f"{random.choice([15,30])}s",
                         "format": "MP4", "checks_passed": 5})

    def upload_creative_asset(self, **kwargs) -> str:
        if self.scene == "upload_partial_fail":
            return self._ok({"asset_id": f"ASSET_{random.randint(1000,9999)}", "status": "partial",
                             "warning": "Creative uploaded but review pending; estimated review time 12 hours",
                             "creative_name": kwargs.get("creative_name", "new_creative")})
        return self._ok({"asset_id": f"ASSET_{random.randint(1000,9999)}", "status": "uploaded",
                         "creative_name": kwargs.get("creative_name", "new_creative"),
                         "campaign_id": kwargs.get("campaign_id", self.campaign_id),
                         "review_status": "pending", "estimated_review": "2-4 hours"})

    def batch_upload_creatives(self, **kwargs) -> str:
        files = kwargs.get("file_paths", ["file1.mp4", "file2.mp4", "file3.mp4"])
        n = len(files)
        failed = random.randint(0, 1) if self.scene == "upload_partial_fail" else 0
        success = n - failed
        results = [{"file": f, "status": "uploaded", "asset_id": f"ASSET_{random.randint(1000,9999)}"}
                   for f in files[:success]]
        if failed:
            results.append({"file": files[-1], "status": "failed", "reason": "file_size_exceeded"})
        return self._ok({"total": n, "success": success, "failed": failed, "results": results})

    # ── Category 3: Campaign Analysis ────────────────────────

    def get_campaign_metrics(self, **kwargs) -> str:
        metrics_req = kwargs.get("metrics", ["roas", "retention_d1", "retention_d7", "ctr", "cpi", "spend"])
        breakdown   = kwargs.get("breakdown", "daily")

        result = {
            "campaign_id": self.campaign_id,
            "date_range": self.date_range,
            "breakdown": breakdown,
            "metrics": {}
        }
        for m in metrics_req:
            if m == "roas":          result["metrics"][m] = {"d7": self._roas_d7, "d30": self._roas_d30}
            elif m == "retention_d1": result["metrics"][m] = self._ret_d1
            elif m == "retention_d7": result["metrics"][m] = self._ret_d7
            elif m == "ctr":          result["metrics"][m] = self._ctr
            elif m == "cpi":          result["metrics"][m] = self._cpi
            elif m == "spend":        result["metrics"][m] = self._spend
            elif m == "impressions":  result["metrics"][m] = int(self._spend / max(self._cpm / 1000, 0.001))
            elif m == "installs":     result["metrics"][m] = self._installs
            elif m == "cpm":          result["metrics"][m] = self._cpm

        # Inject week-over-week CTR decline signal for creative_fatigue scene
        if self.scene == "creative_fatigue":
            result["ctr_wow_change"] = round(random.uniform(-0.38, -0.28), 3)
            result["fatigue_signal"] = "CTR has declined for 3+ consecutive days; recommend refreshing creatives"

        # budget_underdelivery scene
        if self.scene == "budget_underdelivery":
            result["budget_delivery_rate"] = round(random.uniform(0.38, 0.62), 2)
            result["cpm_trend"] = "consistently rising"

        return self._ok(result)

    def get_creative_performance(self, **kwargs) -> str:
        sort_by = kwargs.get("sort_by", "ctr")
        top_k   = kwargs.get("top_k", 10)

        creatives = []
        for i in range(min(top_k, 6)):
            # First creative is the best performer; subsequent ones decay
            decay = 1 - i * 0.12
            cr_ctr  = round(self._ctr * decay * random.uniform(0.90, 1.10), 4)
            cr_cpi  = round(self._cpi * (1 + i * 0.08) * random.uniform(0.95, 1.05), 2)
            cr_roas = round(self._roas_d7 * decay * random.uniform(0.92, 1.08), 3)

            creatives.append({
                "creative_id": f"CR_{random.randint(10000,99999)}",
                "name": f"{self.genre}_video_{i+1:02d}_{random.choice(['US','JP','SEA'])}",
                "format": random.choice(["video_15s", "video_30s", "playable"]),
                "ctr": cr_ctr,
                "cpi": cr_cpi,
                "roas_d7": cr_roas,
                "spend": round(self._spend * (0.35 / (i + 1)), 2),
                "installs": max(1, int(self._installs * (0.35 / (i + 1)))),
                "status": "active" if i < 3 else "fatiguing" if self.scene == "creative_fatigue" else "active",
            })

        return self._ok({"campaign_id": self.campaign_id, "sort_by": sort_by,
                         "creatives": creatives, "date_range": self.date_range})

    def get_appsflyer_report(self, **kwargs) -> str:
        report_type = kwargs.get("report_type", "retention")
        return self._ok({
            "app_id": self.app_id,
            "report_type": report_type,
            "date_range": self.date_range,
            "data": {
                "retention_d1": self._ret_d1,
                "retention_d7": self._ret_d7,
                "installs":     self._installs,
                "revenue_d7":   round(self._roas_d7 * self._spend, 2),
                "revenue_d30":  round(self._roas_d30 * self._spend, 2),
                "top_media_source": self.platform,
            }
        })

    def compare_campaigns(self, **kwargs) -> str:
        campaign_ids = kwargs.get("campaign_ids", [self.campaign_id, "CMP_9999"])
        comparisons = []
        for i, cid in enumerate(campaign_ids):
            decay = 1 if i == 0 else random.uniform(0.70, 0.95)
            comparisons.append({
                "campaign_id": cid,
                "roas_d7":  round(self._roas_d7 * decay, 3),
                "ret_d1":   round(self._ret_d1 * decay, 3),
                "ret_d7":   round(self._ret_d7 * decay, 3),
                "cpi":      round(self._cpi * (1 / decay), 2),
                "spend":    round(self._spend * decay, 2),
                "installs": int(self._installs * decay),
            })
        return self._ok({"comparison": comparisons, "date_range": self.date_range})

    def detect_anomalies(self, **kwargs) -> str:
        metric = kwargs.get("metric", "roas")
        scene_to_anomaly = {
            "roas_danger":          [{"metric": "roas_d7", "severity": "critical",
                                      "value": self._roas_d7, "baseline": self.roas_bl_d7,
                                      "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                                      "possible_causes": ["CPI rising rapidly", "Increased share of low-quality traffic", "CVR drop due to creative fatigue"]}],
            "roas_warning":         [{"metric": "roas_d7", "severity": "warning",
                                      "value": self._roas_d7, "baseline": self.roas_bl_d7,
                                      "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                                      "possible_causes": ["Slightly elevated CPI", "Declining performance of some creatives"]}],
            "ret_danger":           [{"metric": "retention_d1", "severity": "critical",
                                      "value": self._ret_d1, "baseline": self.ret_bl_d1,
                                      "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                                      "possible_causes": ["Creative attracting wrong user segment", "Issues with first-time user experience", "Imprecise geo targeting"]}],
            "both_danger":          [{"metric": "roas_d7", "severity": "critical",
                                      "value": self._roas_d7, "baseline": self.roas_bl_d7,
                                      "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                                      "possible_causes": ["Overall delivery quality deteriorating"]},
                                     {"metric": "retention_d1", "severity": "critical",
                                      "value": self._ret_d1, "baseline": self.ret_bl_d1,
                                      "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                                      "possible_causes": ["Extremely poor user quality", "Severe mismatch between creative and actual gameplay"]}],
            "creative_fatigue":     [{"metric": "ctr", "severity": "warning",
                                      "value": self._ctr, "wow_change": "-32%",
                                      "possible_causes": ["Primary creative overexposed", "Audience largely saturated", "New creatives needed"]}],
            "budget_underdelivery": [{"metric": "budget_delivery_rate", "severity": "warning",
                                      "value": "52%", "possible_causes": ["CPM surged significantly", "High competition", "Bid too low"]}],
        }
        anomalies = scene_to_anomaly.get(self.scene, [])
        return self._ok({"campaign_id": self.campaign_id, "anomalies": anomalies,
                         "check_time": "2026-03-08T09:00:00Z"})

    def get_optimization_playbook(self, **kwargs) -> str:
        issue = kwargs.get("issue_type", "high_cpi")
        playbooks = {
            "high_cpi":            {"steps": ["Review CPI distribution across ad groups; pause ad groups where CPI > 2x target",
                                               "Audit audience targeting of high-CPI creatives; narrow to core segments",
                                               "Try switching bid strategy to tCPA with a reasonable CPA target",
                                               "Add new creatives to reduce reliance on current high-CPI assets"]},
            "low_ctr":             {"steps": ["Analyze common traits of top-CTR creatives (hook type, duration, style)",
                                               "Pause creatives with CTR < 50% of industry average",
                                               "Reference competitors' recent high-CTR creative directions to refresh the creative library",
                                               "A/B test different hook types"]},
            "low_roas":            {"steps": ["Identify the exact time ROAS started declining; cross-reference with creative changes and bid adjustments",
                                               "Break down ROAS by creative, geo, and ad group to isolate underperforming dimensions",
                                               "Raise bid floor; pause ad groups where ROAS < 70% of baseline",
                                               "Sync with the product team to confirm whether retention has deteriorated simultaneously"]},
            "budget_underdelivery":{"steps": ["Check if current bid is below the platform's recommended minimum",
                                               "Moderately raise tCPA/tROAS targets to give the platform more auction opportunities",
                                               "Broaden audience targeting",
                                               "Check creative review status; ensure sufficient approved creatives are available"]},
            "creative_fatigue":    {"steps": ["Launch new creative tests immediately, covering different hook types",
                                               "Pause creatives with week-over-week CTR decline > 30%",
                                               "Reference the trending creative library for new creative directions",
                                               "Moderately raise CPM bids to maintain reach while accelerating creative iteration"]},
        }
        scene_issue_map = {
            "roas_danger": "low_roas", "roas_warning": "low_roas",
            "ret_danger": "low_ctr", "ret_warning": "low_ctr",
            "both_danger": "low_roas", "both_warning": "low_roas",
            "creative_fatigue": "creative_fatigue",
            "budget_underdelivery": "budget_underdelivery",
        }
        resolved_issue = scene_issue_map.get(self.scene, issue)
        pb = playbooks.get(resolved_issue or "low_roas", playbooks["low_roas"])
        return self._ok({"issue_type": resolved_issue, "playbook": pb,
                         "estimated_impact": "medium-high", "implementation_time": "1-2 days"})

    # ── Category 4: Knowledge Q&A ────────────────────────────

    def query_knowledge_base(self, **kwargs) -> str:
        question = kwargs.get("question", "")
        domain   = kwargs.get("domain", "bidding_strategy")
        chunks = {
            "bidding_strategy":  [{"source": "Bidding Strategy Handbook v2.3", "content":
                                    "tCPA is suitable for campaigns with sufficient installs (>50/week) and a clear optimization goal; "
                                    "tROAS is suited for mature campaigns with sufficient in-app purchase data; "
                                    "The learning period typically requires 7-14 days — avoid frequent bid changes during this time."},
                                   {"source": "UAC Best Practices", "content":
                                    "Smart Bidding learning period is approximately 7 days; recommend adjustments of no more than 20% per week."}],
            "creative_guideline":[{"source": "Creative Spec Guide 2026Q1", "content":
                                    "The first 3 seconds of a video are the golden hook zone — show core gameplay or a high-difficulty challenge directly; "
                                    "Optimal length for hyper-casual is 15s, vertical 9:16; "
                                    "Playable ads should be 30-60s, ensuring core gameplay is experienced within 15s."}],
            "platform_policy":   [{"source": "Google Ads Policy Center", "content":
                                    "Game ads must clearly display PEGI/ESRB ratings; "
                                    "In-app purchase disclosures must meet transparency requirements; "
                                    "Gambling-adjacent content requires a dedicated whitelist application."}],
            "industry_benchmark":[{"source": "2026Q1 Mobile Game Advertising Report", "content":
                                    f"D7 ROAS benchmark for {self.genre} genre in {self.region} market is "
                                    f"{self.roas_bl_d7:.2f}; D1 retention benchmark is {self.ret_bl_d1:.2%}; "
                                    "Industry median CPI varies widely by region and platform; US market is approximately $1.5-3.0."}],
        }
        results = chunks.get(domain, chunks["bidding_strategy"])
        return self._ok({"question": question, "domain": domain,
                         "chunks": results, "total": len(results)})

    def get_benchmark_data(self, **kwargs) -> str:
        metric  = kwargs.get("metric", "roas")
        returns = {
            "roas":         {"d7": {"p25": round(self.roas_bl_d7*0.75,3),
                                    "p50": round(self.roas_bl_d7,3),
                                    "p75": round(self.roas_bl_d7*1.25,3)},
                             "d30":{"p25": round(self.roas_bl_d30*0.75,3),
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
        }
        data = returns.get(metric, returns["roas"])
        return self._ok({"metric": metric, "genre": self.genre,
                         "region": self.region, "platform": self.platform,
                         "benchmark": data})

    def get_platform_policy(self, **kwargs) -> str:
        platform    = kwargs.get("platform", self.platform)
        policy_type = kwargs.get("policy_type", "ad_format")
        policies = {
            "ad_format":           f"{platform} supported game ad formats: video (15s/30s), playable, native image; vertical 9:16 is the recommended format.",
            "content_restriction": f"{platform} prohibits violent/graphic content and misleading gameplay screenshots; age ratings must be displayed.",
            "targeting":           f"{platform} supports custom audiences, lookalike audiences, and interest targeting; COPPA prohibits targeting users under 13.",
            "billing":             f"{platform} uses CPM/CPC/CPA billing; minimum daily budget is $10.",
        }
        return self._ok({"platform": platform, "policy_type": policy_type,
                         "content": policies.get(policy_type, "Policy document not available for this type")})

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
# 4. Tool Arguments Builder —— generates tool call arguments from seed
# ─────────────────────────────────────────────────────────────

def build_tool_arguments(tool_name: str, seed: Dict) -> Dict:
    """Generate reasonable call arguments for each tool based on the seed record"""
    cid   = seed["campaign_id"]
    aid   = seed["app_id"]
    dr    = seed["date_range"]
    plat  = seed["platform"]
    genre = seed["game_genre"]
    region= seed["region"]

    arg_map = {
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
            "naming_convention": f"{{genre}}_{{region}}_{{date}}_{{index}}"},
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
            "metric": "roas" if "roas" in seed.get("scene_tag","") else
                      "retention_d1" if "ret" in seed.get("scene_tag","") else "ctr",
            "sensitivity": 0.75},
        "get_optimization_playbook": {
            "issue_type": {
                "roas_danger":"low_roas","roas_warning":"low_roas",
                "ret_danger":"low_ctr","ret_warning":"low_ctr",
                "creative_fatigue":"creative_fatigue",
                "budget_underdelivery":"budget_underdelivery",
            }.get(seed.get("scene_tag",""), "low_roas")},
        "query_knowledge_base": {
            "question": seed.get("user_query","bidding strategy"),
            "domain": seed.get("scene_tag","bidding_strategy"),
            "search_mode": "hybrid", "top_k": 5},
        "get_benchmark_data": {
            "metric": "roas", "game_genre": genre,
            "region": region, "platform": plat},
        "get_platform_policy": {
            "platform": plat,
            "policy_type": random.choice(["ad_format","content_restriction"])},
    }
    return arg_map.get(tool_name, {})


# ─────────────────────────────────────────────────────────────
# 5. Response Templates —— generates the final assistant turn based on workflow and scene
# ─────────────────────────────────────────────────────────────

def build_final_response(seed: Dict, executor: MockToolExecutor, tool_results: List[Dict]) -> str:
    """Generate a structured natural-language final-turn reply based on scene_tag"""
    scene    = seed.get("scene_tag", "healthy")
    cid      = seed["campaign_id"]
    roas_d7  = executor._roas_d7
    roas_bl  = executor.roas_bl_d7
    ret_d1   = executor._ret_d1
    ret_bl   = executor.ret_bl_d1
    ret_d7   = executor._ret_d7
    ret_bl7  = executor.ret_bl_d7
    ctr      = executor._ctr
    cpi      = executor._cpi
    spend    = executor._spend

    roas_status = "✅ On Target" if roas_d7 >= roas_bl else ("⚠️ Warning" if roas_d7 >= roas_bl * 0.80 else "🚨 Critical")
    ret_status  = "✅ On Target" if ret_d1  >= ret_bl  else ("⚠️ Warning" if ret_d1  >= ret_bl  * 0.80 else "🚨 Critical")
    roas_pct    = (roas_d7 / roas_bl - 1) * 100
    ret_pct     = (ret_d1  / ret_bl  - 1) * 100

    templates = {
        "healthy": f"""**{cid} Campaign Health Report**

**Core Metrics vs. Safety Baseline**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, {roas_status}, {roas_pct:+.1f}% above)
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, {ret_status}, {ret_pct:+.1f}% above)
- D7 Retention: {ret_d7:.1%} (Baseline {ret_bl7:.1%})

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} | Spend: ${spend:,.0f}

**Conclusion**: The campaign is performing healthily overall; both ROAS and retention exceed the safety baseline.
**Recommendation**: Maintain the current creative direction and consider scaling budget to test new geos or audiences.""",

        "roas_warning": f"""**{cid} ROAS Warning Analysis**

**Core Metrics vs. Safety Baseline**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, {roas_status}, {abs(roas_pct):.1f}% below) ⚠️
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, {ret_status})

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} (elevated) | Spend: ${spend:,.0f}

**Diagnosis**: D7 ROAS is below baseline but still within the warning zone (80–100%), primarily driven by rising CPI reducing payback efficiency.

**Optimization Recommendations**:
1. Review high-CPI ad groups and pause any unit where CPI exceeds 1.5x target
2. Prioritize top ROAS creatives and reallocate budget away from underperformers
3. Monitor the next 3 days; escalate to danger protocol if the decline continues""",

        "roas_danger": f"""**{cid} ROAS Critical Alert 🚨**

**Core Metrics vs. Safety Baseline**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, {roas_status}, **drop of {abs(roas_pct):.1f}%**)
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, {ret_status})

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} (severely elevated) | Spend: ${spend:,.0f}

**Immediate Action Plan**:
1. **Immediately** pause ad groups where ROAS < 60% of baseline to stop the bleed
2. Reduce overall daily budget by 30–50%; retain only the top 2 historically best-performing ad groups
3. Engage the creative team urgently for new assets — prioritize testing different audience targeting
4. Investigate whether there are platform-level account quality issues""",

        "ret_warning": f"""**{cid} User Retention Warning Analysis**

**Core Metrics vs. Safety Baseline**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, {roas_status})
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, {ret_status}, {abs(ret_pct):.1f}% below) ⚠️

**Diagnosis**: ROAS is on target but D1 retention is below baseline, indicating that creatives are driving installs effectively but struggling to retain new users long-term. This typically occurs when creative tone mismatches actual gameplay, or audience targeting has drifted from the core user profile.

**Optimization Recommendations**:
1. Analyze high-CTR but low-retention creatives for potential "clickbait" patterns
2. Use AppsFlyer data to identify high-retention media sources and increase their budget allocation
3. Sync with the product team to confirm whether onboarding drop-off is a factor""",

        "ret_danger": f"""**{cid} User Retention Critical Alert 🚨**

**Core Metrics vs. Safety Baseline**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, {roas_status})
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, {ret_status}, **drop of {abs(ret_pct):.1f}%**)
- D7 Retention: {ret_d7:.1%} (Baseline {ret_bl7:.1%})

**Diagnosis**: Both D1 and D7 retention are severely below baseline while ROAS remains acceptable — suggesting users are churning quickly after install but generating some short-term revenue. Strongly suspected to be a wrong audience issue (attracting high-payer but low-retention users).

**Immediate Action Plan**:
1. Immediately pause ad groups where D1 retention < 60% of baseline
2. Conduct a full creative audit; pull any creative that significantly misrepresents actual gameplay
3. Reset targeting by rebuilding Lookalike audiences from historically high-retention users
4. Urgently engage the product team to rule out onboarding bugs""",

        "both_warning": f"""**{cid} ROAS + Retention Dual Warning**

**Core Metrics vs. Safety Baseline**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, {roas_status}, {abs(roas_pct):.1f}% below) ⚠️
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, {ret_status}, {abs(ret_pct):.1f}% below) ⚠️

**Supporting Metrics**
- CTR: {ctr:.2%} | CPI: ${cpi:.2f} | Spend: ${spend:,.0f}

**Diagnosis**: ROAS and retention declining in tandem typically points to deteriorating traffic quality — possibly caused by overly broad audience targeting or primary creatives entering fatigue, causing the platform to serve non-core users.

**Recommendation**: Tighten targeting, review weekly CTR trends for creatives, and assess whether fatigue has set in.""",

        "both_danger": f"""**{cid} Full-System Alert — Immediate Intervention Required 🚨🚨**

**Core Metrics vs. Safety Baseline**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, drop of {abs(roas_pct):.1f}%) 🚨
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, drop of {abs(ret_pct):.1f}%) 🚨

**Current Status**: Both ROAS and retention have breached the safety baseline by more than 20% simultaneously — this is the highest-priority anomaly classification.

**Immediate Action Checklist**:
1. Pause all ad groups where ROAS < 70% of baseline (retain only the top 1–2 historically best units)
2. Reduce overall daily budget by 50% to cap total losses
3. Convene an emergency cross-functional review with the creative and product teams (investigate both ad-side and product-side factors)
4. Submit a root-cause analysis report within 24 hours""",

        "creative_fatigue": f"""**{cid} Creative Fatigue Warning**

**Core Metrics**
- D7 ROAS: {roas_d7:.3f} (Baseline {roas_bl:.3f}, ✅ still on target)
- D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%}, ✅ still on target)
- CTR: {ctr:.2%} (**week-over-week decline ~32%**) ⚠️

**Diagnosis**: ROAS and retention are still above baseline, but persistent CTR decline signals that creatives are entering fatigue. Without intervention, ROAS will be impacted within 1–2 weeks.

**Recommendations**:
1. Launch at least 3–5 new creatives this week, covering diverse hook types
2. Pause primary creatives with week-over-week CTR decline > 30%
3. Reference trending competitor creative directions for inspiration""",

        "budget_underdelivery": f"""**{cid} Budget Underdelivery Analysis**

**Delivery Status**
- Budget delivery rate: ~52% (target 95%+) ⚠️
- CPM: consistently rising; competition is high
- ROAS / Retention: still on target, but volume is insufficient

**Diagnosis**: Underdelivery is primarily caused by rising CPM reducing auction win rates; the current bid strategy is struggling to compete effectively.

**Recommendations**:
1. Raise the tCPA target by 10–15% to give the platform more room to bid
2. Broaden audience targeting (consider testing Broad Audience)
3. Increase the number of available creatives to give the platform more combinations to test""",

        "insufficient_data": f"""**{cid} Data Notice**

This campaign has been running for fewer than 3 days, and current data volume is limited. Key metrics should be treated as preliminary only:

- Preliminary D1 Retention: {ret_d1:.1%} (Baseline {ret_bl:.1%} — insufficient sample size, interpret with caution)
- Preliminary ROAS Trend: not yet statistically significant

**Recommendation**: Continue monitoring until day 5–7 before conducting a formal evaluation. Avoid optimizing prematurely based on limited data, as it may disrupt the learning period.""",
    }

    # Non-ROAS/RET scenes use simplified templates
    if scene == "creative_search":
        return f"Search complete. The results above show the top-performing trending creatives for {seed.get('game_genre', 'this genre')} on {seed.get('platform', 'the platform')}. Focus on creatives with a heat score > 85 and CTR > 0.045 as the primary reference for your next creative iteration."
    if scene in ("upload_success",):
        return f"Creative successfully uploaded to {cid}. Review typically takes 2–4 hours. Once live, monitor CTR and CPI performance closely during the first 48 hours."
    if scene in ("validate_fail_size", "validate_fail_format"):
        return "Creative spec validation failed. Please adjust the file according to the error details above and re-upload. Feel free to ask if you need help with platform-specific format requirements."
    if scene in ("bidding_strategy","creative_guideline","platform_policy","industry_benchmark","knowledge_base"):
        return "Here are the knowledge base results. If you need further details on a specific point, or want to apply this to your current campaign data, feel free to ask."

    return templates.get(scene, templates["healthy"])


# ─────────────────────────────────────────────────────────────
# 6. Conversation Builder
# ─────────────────────────────────────────────────────────────

def tool_call_turn(tool_name: str, arguments: Dict) -> Dict:
    """Generate a gpt tool call turn (ShareGPT format)"""
    return {
        "from": "gpt",
        "value": f'<tool_call>{{"name": "{tool_name}", "arguments": {json.dumps(arguments, ensure_ascii=False)}}}</tool_call>'
    }

def tool_result_turn(result: str) -> Dict:
    return {"from": "tool", "value": result}

def build_conversation(seed: Dict) -> Dict:
    """Convert a single seed record into a complete ShareGPT-format conversation"""

    executor   = MockToolExecutor(seed)
    tool_chain = seed.get("tool_chain", [])
    scene      = seed.get("scene_tag", "healthy")
    workflow   = seed.get("workflow", 0)

    conversations = [{"from": "system", "value": SYSTEM_PROMPT}]

    # ── Clarification flow ────────────────────────────────────
    if seed.get("needs_clarification"):
        conversations.append({"from": "human",  "value": seed["user_query"]})
        clarify_q = _build_clarify_question(seed)
        conversations.append({"from": "gpt",    "value": clarify_q})
        conversations.append({"from": "human",  "value": seed.get("clarification_answer", "")})
        # Continue with normal flow after clarification
    else:
        conversations.append({"from": "human", "value": seed["user_query"]})

    # ── Refusal — return directly ─────────────────────────────
    if workflow == 7:
        conversations.append({"from": "gpt", "value": _build_refusal(seed)})
        return _wrap(seed, conversations)

    # ── Tool chain execution ──────────────────────────────────
    tool_results = []
    for tool_name in tool_chain:
        arguments = build_tool_arguments(tool_name, seed)
        result    = executor.execute(tool_name, arguments)
        conversations.append(tool_call_turn(tool_name, arguments))
        conversations.append(tool_result_turn(result))
        tool_results.append({"tool": tool_name, "result": result})

    # ── Final assistant turn ──────────────────────────────────
    final_resp = build_final_response(seed, executor, tool_results)
    conversations.append({"from": "gpt", "value": final_resp})

    return _wrap(seed, conversations)


def _build_clarify_question(seed: Dict) -> str:
    reason = seed.get("clarification_reason", "")
    questions = {
        "campaign_id_missing":               "Which campaign would you like to check? Please provide the Campaign ID and I'll pull the data right away.",
        "campaign_id_and_timerange_missing":  "Which campaign would you like to analyze, and what date range should I use?",
        "platform_or_genre_missing":          "Which platform would you like to search creatives on, and what is the game genre?",
    }
    return questions.get(reason, "Could you provide more information so I can look this up accurately?")


def _build_refusal(seed: Dict) -> str:
    rtype = seed.get("refusal_type", "off_topic")
    refusals = {
        "off_topic": "I'm sorry — I'm an AI assistant specialized in mobile game ad campaign management, and this request falls outside my area of service. For campaign data analysis, creative search, campaign optimization, and related topics, feel free to ask anytime.",
        "unauthorized_operation": "I'm sorry, but this operation (deleting or modifying account-level data) is beyond my authorization scope. To avoid irreversible consequences, I'm unable to execute this type of action. For account-level changes, please use the platform's back-end directly or contact your account manager.",
        "insufficient_data_to_answer": "I understand your question, but I'm missing required information (Campaign ID or date range) to provide an accurate analysis. Please share the specific Campaign ID and I'll pull the data for you.",
    }
    return refusals.get(rtype, refusals["off_topic"])


def _wrap(seed: Dict, conversations: List[Dict]) -> Dict:
    """Wrap into the final ShareGPT record"""
    return {
        "conversations": conversations,
        # Metadata (can be ignored during training; useful for analysis)
        "_meta": {
            "workflow": seed.get("workflow"),
            "workflow_name": seed.get("workflow_name"),
            "scene_tag": seed.get("scene_tag"),
            "platform": seed.get("platform"),
            "game_genre": seed.get("game_genre"),
            "tool_chain": seed.get("tool_chain"),
        }
    }


# ─────────────────────────────────────────────────────────────
# 7. Main
# ─────────────────────────────────────────────────────────────

def main(input_path: str = "ad_agent_seeds.json",
         output_path: str = "ad_agent_sft_dataset.json"):

    seeds = json.loads(Path(input_path).read_text(encoding="utf-8"))
    print(f"✅ Loaded seed records: {len(seeds)}")

    conversations = []
    failed = 0

    for seed in tqdm(seeds, desc="Generating conversations"):
        try:
            conv = build_conversation(seed)
            conversations.append(conv)
        except Exception as e:
            failed += 1
            tqdm.write(f"⚠️  Skipping one record: {e}")

    # ── Stats ──
    wf_counter    = {}
    scene_counter = {}
    turn_lengths  = []
    for c in conversations:
        meta = c.get("_meta", {})
        wf   = meta.get("workflow_name", "unknown")
        sc   = meta.get("scene_tag", "unknown")
        wf_counter[wf]    = wf_counter.get(wf, 0) + 1
        scene_counter[sc] = scene_counter.get(sc, 0) + 1
        turn_lengths.append(len(c["conversations"]))

    print(f"\n✅ Generation complete: {len(conversations)} conversations, {failed} failed")
    print(f"📊 Average turns per conversation: {sum(turn_lengths)/max(len(turn_lengths),1):.1f}")

    print("\n📋 Workflow distribution:")
    for wf, cnt in sorted(wf_counter.items()):
        print(f"  {wf}: {cnt}")

    print("\n🏷  Scene distribution (Top 12):")
    for sc, cnt in sorted(scene_counter.items(), key=lambda x: -x[1])[:12]:
        print(f"  {sc}: {cnt}")

    Path(output_path).write_text(
        json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 Saved to: {output_path}")


if __name__ == "__main__":

    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"

    inp = input("Input JSON file name: ").strip()

    # Search in data/ first, then script dir as fallback
    candidate = data_dir / inp
    if not candidate.exists():
        candidate = script_dir / inp
    if not candidate.exists():
        print(f"❌ File not found: {inp} (searched in {data_dir} and {script_dir})")
        exit(1)

    inp_path = candidate
    print(f"📂 Found input: {inp_path}")

    # Auto-derive output path in data/ with same naming convention
    stem = inp_path.stem  # filename without extension
    if "seeds" in stem:
        out_stem = stem.replace("seeds", "sft")
    else:
        out_stem = stem + "_sft"
    
    data_dir.mkdir(exist_ok=True)
    out_path = data_dir / f"{out_stem}_sharegpt.json"
    print(f"💾 Output will be saved to: {out_path}")

    main(str(inp_path), str(out_path))
