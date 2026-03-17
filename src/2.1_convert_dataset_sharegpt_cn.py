"""
Ad Campaign Agent - Phase 2: Conversation Generator
Input:  seed JSON (from 1_ad_gen_data.py)
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

SYSTEM_PROMPT = """你是一个专业的移动游戏广告投放 AI 助手（Ad Campaign Agent），服务于 UA（用户获取）团队。

## 核心职责
- 以 ROAS 和用户留存（Retention）安全基线为核心，评估 Campaign 健康状态
- 识别指标异常，给出结构化优化建议
- 搜索热门素材、管理素材上传
- 回答出价策略、平台政策、行业 benchmark 等专业问题

## 工作原则
- 分析时始终明确指出 ROAS / Retention 是否达到安全基线，数据说话
- 信息不足时主动追问，一次只问一个关键信息
- 上传素材前必须先调用 validate_creative_spec 校验规格
- 超出能力范围或涉及越权操作时礼貌拒绝，并说明原因"""


# ─────────────────────────────────────────────────────────────
# 2. Scene Config —— 控制各场景下指标相对基线的偏差范围
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

# 非 ROAS/RET 场景：不需要基线计算
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
    根据 scene_tag + seed baselines 生成数值一致的 mock tool results。
    核心指标在 __init__ 里一次性计算，保证同一对话内各 tool 数据不矛盾。
    """

    def __init__(self, seed: Dict):
        self.seed = seed
        self.scene = seed.get("scene_tag", "healthy")
        self.cfg = SCENE_CFG.get(self.scene, {})

        # 基线
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

        # 预计算核心指标（供各 tool 共用）
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

    # ── Category 1: 素材搜寻 ─────────────────────────────────

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
            {"hook": "90%的人第一关都过不了", "type": "challenge", "avg_ctr": 0.062},
            {"hook": "你能撑过第3关吗？", "type": "challenge", "avg_ctr": 0.058},
            {"hook": "[真实玩家录屏] 我卡了3天的关", "type": "ugc_style", "avg_ctr": 0.055},
            {"hook": "这个谜题难倒了99%的人", "type": "difficulty", "avg_ctr": 0.051},
            {"hook": "帮帮我！我快崩了", "type": "emotional", "avg_ctr": 0.049},
        ]
        return self._ok({"genre": genre, "hooks": templates[:random.randint(3,5)]})

    # ── Category 2: 素材上传 ─────────────────────────────────

    def validate_creative_spec(self, **kwargs) -> str:
        scene = self.scene
        if scene == "validate_fail_size":
            return self._ok({
                "valid": False,
                "errors": [{"field": "file_size", "message": "文件大小 58.3MB 超过平台上限 50MB",
                            "platform_limit": "50MB", "actual": "58.3MB"}],
            })
        if scene == "validate_fail_format":
            return self._ok({
                "valid": False,
                "errors": [{"field": "resolution", "message": "分辨率 1280x960 不符合要求，需为 9:16 或 1:1",
                            "platform_limit": "1080x1920 or 1080x1080", "actual": "1280x960"}],
            })
        return self._ok({"valid": True, "file_size": f"{random.uniform(8,35):.1f}MB",
                         "resolution": "1080x1920", "duration": f"{random.choice([15,30])}s",
                         "format": "MP4", "checks_passed": 5})

    def upload_creative_asset(self, **kwargs) -> str:
        if self.scene == "upload_partial_fail":
            return self._ok({"asset_id": f"ASSET_{random.randint(1000,9999)}", "status": "partial",
                             "warning": "素材已上传但审核待定，预计12小时内完成审核",
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

    # ── Category 3: Campaign 分析 ────────────────────────────

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

        # creative_fatigue 场景注入周环比 CTR 下滑信号
        if self.scene == "creative_fatigue":
            result["ctr_wow_change"] = round(random.uniform(-0.38, -0.28), 3)
            result["fatigue_signal"] = "CTR 连续下滑超过3天，建议换量"

        # budget_underdelivery 场景
        if self.scene == "budget_underdelivery":
            result["budget_delivery_rate"] = round(random.uniform(0.38, 0.62), 2)
            result["cpm_trend"] = "持续走高"

        return self._ok(result)

    def get_creative_performance(self, **kwargs) -> str:
        sort_by = kwargs.get("sort_by", "ctr")
        top_k   = kwargs.get("top_k", 10)

        creatives = []
        for i in range(min(top_k, 6)):
            # 首条素材是当前表现最好的，往后依次衰减
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
                                      "possible_causes": ["CPI 快速上升", "低质量流量占比增加", "素材疲劳导致 CVR 下降"]}],
            "roas_warning":         [{"metric": "roas_d7", "severity": "warning",
                                      "value": self._roas_d7, "baseline": self.roas_bl_d7,
                                      "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                                      "possible_causes": ["CPI 略微偏高", "部分素材效果下滑"]}],
            "ret_danger":           [{"metric": "retention_d1", "severity": "critical",
                                      "value": self._ret_d1, "baseline": self.ret_bl_d1,
                                      "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                                      "possible_causes": ["素材吸引了错误用户群", "首次体验流程有问题", "地区定向不精准"]}],
            "both_danger":          [{"metric": "roas_d7", "severity": "critical",
                                      "value": self._roas_d7, "baseline": self.roas_bl_d7,
                                      "deviation": f"{((self._roas_d7/self.roas_bl_d7)-1)*100:.1f}%",
                                      "possible_causes": ["整体投放质量恶化"]},
                                     {"metric": "retention_d1", "severity": "critical",
                                      "value": self._ret_d1, "baseline": self.ret_bl_d1,
                                      "deviation": f"{((self._ret_d1/self.ret_bl_d1)-1)*100:.1f}%",
                                      "possible_causes": ["用户质量极差", "素材与游戏内容严重不符"]}],
            "creative_fatigue":     [{"metric": "ctr", "severity": "warning",
                                      "value": self._ctr, "wow_change": "-32%",
                                      "possible_causes": ["主力素材曝光过度", "受众已大量触达", "需要补充新素材"]}],
            "budget_underdelivery": [{"metric": "budget_delivery_rate", "severity": "warning",
                                      "value": "52%", "possible_causes": ["CPM 大幅上涨", "竞争激烈", "出价过低"]}],
        }
        anomalies = scene_to_anomaly.get(self.scene, [])
        return self._ok({"campaign_id": self.campaign_id, "anomalies": anomalies,
                         "check_time": "2026-03-08T09:00:00Z"})

    def get_optimization_playbook(self, **kwargs) -> str:
        issue = kwargs.get("issue_type", "high_cpi")
        playbooks = {
            "high_cpi":            {"steps": ["检查各 ad group 的 CPI 分布，暂停 CPI > 目标2倍的 ad group",
                                               "审查高 CPI 素材的受众定向，收窄至核心人群",
                                               "尝试切换出价策略为 tCPA，设定合理 CPA 目标",
                                               "补充新素材，降低对当前高CPI素材的依赖"]},
            "low_ctr":             {"steps": ["分析 Top CTR 素材的共同特征（钩子类型、时长、风格）",
                                               "下线 CTR < 行业均值50%的素材",
                                               "参考竞品近期高 CTR 创意方向，更新素材库",
                                               "A/B 测试不同钩子类型"]},
            "low_roas":            {"steps": ["核查 ROAS 下滑的时间节点，对比素材更换 / 出价调整记录",
                                               "按素材、地区、Ad Group 拆分 ROAS，定位低效维度",
                                               "提高出价门槛，暂停 ROAS < 基线 70% 的 Ad Group",
                                               "联动产品团队确认留存侧有无同步恶化"]},
            "budget_underdelivery":{"steps": ["检查当前出价是否低于平台建议最低出价",
                                               "适当提高 tCPA/tROAS 目标为平台争取更多竞价机会",
                                               "扩大受众定向范围",
                                               "检查素材审核状态，确保有足量通过审核的素材"]},
            "creative_fatigue":    {"steps": ["立即启动新素材测试，覆盖不同钩子类型",
                                               "下线 CTR 周环比下滑 > 30% 的素材",
                                               "参考热门素材库补充新创意方向",
                                               "适当提高 CPM 出价维持曝光，同时加速素材迭代"]},
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

    # ── Category 4: 知识问答 ─────────────────────────────────

    def query_knowledge_base(self, **kwargs) -> str:
        question = kwargs.get("question", "")
        domain   = kwargs.get("domain", "bidding_strategy")
        chunks = {
            "bidding_strategy":  [{"source": "投放策略手册 v2.3", "content":
                                    "tCPA 适合安装量充足（>50次/周）的 Campaign，优化目标明确；"
                                    "tROAS 适合有足够内购数据的成熟 Campaign；"
                                    "学习期通常需要 7-14 天，期间避免频繁调整出价。"},
                                   {"source": "UAC 最佳实践", "content":
                                    "Smart Bidding 学习期约 7 天，建议每周调整幅度不超过 20%。"}],
            "creative_guideline":[{"source": "素材规范 2026Q1", "content":
                                    "视频前3秒为黄金钩子区，建议直接展示核心玩法或高难度挑战；"
                                    "hyper-casual 最优时长 15s，竖版 9:16；"
                                    "playable 广告时长建议 30-60s，确保核心玩法可在 15s 内体验完毕。"}],
            "platform_policy":   [{"source": "Google Ads 政策中心", "content":
                                    "游戏广告需明确标注 PEGI/ESRB 评级；"
                                    "内购展示需符合透明度要求；"
                                    "博彩类内容需申请专项白名单。"}],
            "industry_benchmark":[{"source": "2026Q1 移动游戏广告报告", "content":
                                    f"{self.genre} 品类在 {self.region} 市场的 D7 ROAS 基准为 "
                                    f"{self.roas_bl_d7:.2f}，D1 留存基准为 {self.ret_bl_d1:.2%}；"
                                    "CPI 行业中位数因地区和平台差异较大，US 市场约 $1.5-3.0。"}],
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
            "ad_format":         f"{platform} 支持的游戏广告格式：视频（15s/30s）、playable、原生图片；竖版 9:16 为推荐格式。",
            "content_restriction": f"{platform} 禁止展示暴力血腥、欺骗性游戏截图；需标注年龄分级。",
            "targeting":         f"{platform} 支持自定义受众、相似受众、兴趣定向；COPPA 规定13岁以下用户不可定向。",
            "billing":           f"{platform} 采用 CPM/CPC/CPA 计费方式，最低日预算 $10。",
        }
        return self._ok({"platform": platform, "policy_type": policy_type,
                         "content": policies.get(policy_type, "暂无该政策文档")})

    # ── 统一调度 ─────────────────────────────────────────────

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
# 4. Tool Arguments Builder —— 从种子生成 tool call 参数
# ─────────────────────────────────────────────────────────────

def build_tool_arguments(tool_name: str, seed: Dict) -> Dict:
    """根据种子记录，为每个 tool 生成合理的调用参数"""
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
            "question": seed.get("user_query","投放策略"),
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
# 5. Response Templates —— 根据工作流和场景生成 assistant 末轮回复
# ─────────────────────────────────────────────────────────────

def build_final_response(seed: Dict, executor: MockToolExecutor, tool_results: List[Dict]) -> str:
    """根据 scene_tag 生成结构化的末轮自然语言回复"""
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

    roas_status = "✅ 达标" if roas_d7 >= roas_bl else ("⚠️ 预警" if roas_d7 >= roas_bl * 0.80 else "🚨 告警")
    ret_status  = "✅ 达标" if ret_d1  >= ret_bl  else ("⚠️ 预警" if ret_d1  >= ret_bl  * 0.80 else "🚨 告警")
    roas_pct    = (roas_d7 / roas_bl - 1) * 100
    ret_pct     = (ret_d1  / ret_bl  - 1) * 100

    templates = {
        "healthy": f"""**{cid} 投放健康报告**

**核心指标 vs 安全基线**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，{roas_status}，超出 {roas_pct:+.1f}%）
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，{ret_status}，超出 {ret_pct:+.1f}%）
- D7 留存：{ret_d7:.1%}（基线 {ret_bl7:.1%}）

**辅助指标**
- CTR：{ctr:.2%} | CPI：${cpi:.2f} | 花费：${spend:,.0f}

**结论**：当前 Campaign 整体表现健康，ROAS 和留存均超过安全基线。
**建议**：维持当前素材方向，适当扩大预算测试新地区或新受众。""",

        "roas_warning": f"""**{cid} ROAS 预警分析**

**核心指标 vs 安全基线**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，{roas_status}，偏低 {abs(roas_pct):.1f}%）⚠️
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，{ret_status}）

**辅助指标**
- CTR：{ctr:.2%} | CPI：${cpi:.2f}（偏高）| 花费：${spend:,.0f}

**问题诊断**：D7 ROAS 低于基线但尚在预警区间（80-100%），主要原因可能是 CPI 上升导致回收效率下降。

**优化建议**：
1. 检查高 CPI 的 Ad Group，暂停 CPI 超过目标 1.5 倍的单元
2. 优先推跑现有高 ROAS 素材，减少低效素材预算占比
3. 观察后续 3 天趋势，若持续下滑升级为 danger 处理""",

        "roas_danger": f"""**{cid} ROAS 严重告警 🚨**

**核心指标 vs 安全基线**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，{roas_status}，**跌幅 {abs(roas_pct):.1f}%**）
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，{ret_status}）

**辅助指标**
- CTR：{ctr:.2%} | CPI：${cpi:.2f}（严重偏高）| 花费：${spend:,.0f}

**紧急处理建议**：
1. **立即**暂停 ROAS < 基线 60% 的 Ad Group，控制出血
2. 调低整体日预算 30-50%，优先保留历史 ROAS 最高的 Top 2 Ad Group
3. 联系素材团队紧急补充新创意，重点测试不同用户群体定向
4. 排查是否有平台账户级别的质量问题""",

        "ret_warning": f"""**{cid} 用户留存预警分析**

**核心指标 vs 安全基线**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，{roas_status}）
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，{ret_status}，偏低 {abs(ret_pct):.1f}%）⚠️

**问题诊断**：ROAS 达标但 D1 留存低于基线，说明素材吸量能力正常，但对新用户的长期吸引力不足。这类情况常见于素材与游戏内容调性不符，或定向人群与核心用户画像有偏差。

**优化建议**：
1. 分析高 CTR 但低留存的素材，评估是否存在"标题党"创意
2. 结合 AppsFlyer 数据检查高留存媒体来源，加大其预算占比
3. 与产品团队同步，确认是否为新手引导流失问题""",

        "ret_danger": f"""**{cid} 用户留存严重告警 🚨**

**核心指标 vs 安全基线**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，{roas_status}）
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，{ret_status}，**跌幅 {abs(ret_pct):.1f}%**）
- D7 留存：{ret_d7:.1%}（基线 {ret_bl7:.1%}）

**问题诊断**：D1/D7 留存均严重低于基线，而 ROAS 尚可，说明用户进来后快速流失但短期内产生了一定消费——高度怀疑是错误用户群体（吸引了付费意愿强但留存差的群体）。

**紧急处理建议**：
1. 立即暂停 D1 留存 < 基线 60% 的 Ad Group
2. 全面审查当前素材，下线与游戏实际玩法差异过大的创意
3. 重置定向，从历史高留存用户重新建立 Lookalike
4. 紧急联系产品团队排查新手引导是否有 bug""",

        "both_warning": f"""**{cid} ROAS + 留存双项预警**

**核心指标 vs 安全基线**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，{roas_status}，偏低 {abs(roas_pct):.1f}%）⚠️
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，{ret_status}，偏低 {abs(ret_pct):.1f}%）⚠️

**辅助指标**
- CTR：{ctr:.2%} | CPI：${cpi:.2f} | 花费：${spend:,.0f}

**问题诊断**：ROAS 和留存同步走低，通常指向流量质量下降——可能是受众定向范围过宽、或主力素材开始疲劳导致平台推送给了非核心受众。

**建议**：收紧定向，审查素材 CTR 周趋势，评估是否已进入疲劳期。""",

        "both_danger": f"""**{cid} 全线告警 —— 需要立即介入 🚨🚨**

**核心指标 vs 安全基线**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，跌幅 {abs(roas_pct):.1f}%）🚨
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，跌幅 {abs(ret_pct):.1f}%）🚨

**当前状态**：ROAS 和留存同时跌破安全基线20%以上，属于最高优先级异常。

**立即执行清单**：
1. 暂停所有 ROAS < 基线 70% 的 Ad Group（保留 Top 1-2 个历史最优单元）
2. 整体日预算降低 50%，控制总损失
3. 召集素材团队 + 产品团队联合排查（广告侧 & 产品侧双向问题）
4. 24小时内提交问题分析报告""",

        "creative_fatigue": f"""**{cid} 素材疲劳预警**

**核心指标**
- D7 ROAS：{roas_d7:.3f}（基线 {roas_bl:.3f}，✅ 仍达标）
- D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，✅ 仍达标）
- CTR：{ctr:.2%}（**周环比下滑约 32%**）⚠️

**问题诊断**：ROAS 和留存目前仍在基线以上，但 CTR 持续下滑预示素材进入疲劳期。若不干预，1-2 周内 ROAS 将受到影响。

**建议**：
1. 本周内上线至少 3-5 个新素材（覆盖不同钩子类型）
2. 下线 CTR 周环比下滑 > 30% 的主力素材
3. 参考竞品近期高热度创意方向""",

        "budget_underdelivery": f"""**{cid} 预算欠量分析**

**投放状态**
- 预算消耗率：约 52%（目标 95%+）⚠️
- CPM：持续走高，竞争激烈
- ROAS/留存：仍达标，但量级不足

**问题诊断**：欠量主要原因是 CPM 上涨导致竞价成功率下降，当前出价策略已难以在竞拍中胜出。

**建议**：
1. 适当上调 tCPA 目标 10-15%，为平台提供更多竞价空间
2. 扩大受众定向范围（可尝试 Broad Audience）
3. 增加备用素材数量，确保平台有足够多的创意组合可测试""",

        "insufficient_data": f"""**{cid} 数据说明**

当前 Campaign 投放时间较短（不足3天），现有数据量级有限，主要指标仅供参考：

- 初步 D1 留存：{ret_d1:.1%}（基线 {ret_bl:.1%}，样本量不足，需谨慎解读）
- 初步 ROAS 趋势：尚未达到统计显著性

**建议**：继续观察至第 5-7 天再做正式评估，避免基于少量数据过早优化导致学习期被打断。""",
    }

    # 非 ROAS/RET 场景走简单模板
    if scene == "creative_search":
        return f"已为您搜索完毕。以上是{seed.get('platform','平台')}上{seed.get('game_genre','该品类')}品类近期表现最好的热门素材，建议重点参考热度分 > 85 且 CTR > 0.045 的创意方向进行素材迭代。"
    if scene in ("upload_success",):
        return f"素材已成功上传至 {cid}，审核通常需要 2-4 小时。上线后建议持续关注前48小时的 CTR 和 CPI 表现。"
    if scene in ("validate_fail_size", "validate_fail_format"):
        return "素材规格校验未通过，请根据上方错误信息调整后重新上传。如需了解各平台规格要求，可以问我。"
    if scene in ("bidding_strategy","creative_guideline","platform_policy","industry_benchmark","knowledge_base"):
        return "以上是知识库检索结果。如需进一步了解某个具体细节，或结合您当前 Campaign 数据做分析，请继续提问。"

    return templates.get(scene, templates["healthy"])


# ─────────────────────────────────────────────────────────────
# 6. Conversation Builder
# ─────────────────────────────────────────────────────────────

def tool_call_turn(tool_name: str, arguments: Dict) -> Dict:
    """生成 gpt tool call turn（ShareGPT 格式）"""
    return {
        "from": "gpt",
        "value": f'<tool_call>{{"name": "{tool_name}", "arguments": {json.dumps(arguments, ensure_ascii=False)}}}</tool_call>'
    }

def tool_result_turn(result: str) -> Dict:
    return {"from": "tool", "value": result}

def build_conversation(seed: Dict) -> Dict:
    """将一条种子记录转换为完整 ShareGPT 格式对话"""

    executor   = MockToolExecutor(seed)
    tool_chain = seed.get("tool_chain", [])
    scene      = seed.get("scene_tag", "healthy")
    workflow   = seed.get("workflow", 0)

    conversations = [{"from": "system", "value": SYSTEM_PROMPT}]

    # ── 追问流程 ──────────────────────────────────────
    if seed.get("needs_clarification"):
        conversations.append({"from": "human",  "value": seed["user_query"]})
        clarify_q = _build_clarify_question(seed)
        conversations.append({"from": "gpt",    "value": clarify_q})
        conversations.append({"from": "human",  "value": seed.get("clarification_answer", "")})
        # 追问后继续正常流程
    else:
        conversations.append({"from": "human", "value": seed["user_query"]})

    # ── 拒答直接返回 ──────────────────────────────────
    if workflow == 7:
        conversations.append({"from": "gpt", "value": _build_refusal(seed)})
        return _wrap(seed, conversations)

    # ── 工具链调用 ────────────────────────────────────
    tool_results = []
    for tool_name in tool_chain:
        arguments = build_tool_arguments(tool_name, seed)
        result    = executor.execute(tool_name, arguments)
        conversations.append(tool_call_turn(tool_name, arguments))
        conversations.append(tool_result_turn(result))
        tool_results.append({"tool": tool_name, "result": result})

    # ── 末轮 assistant 回复 ───────────────────────────
    final_resp = build_final_response(seed, executor, tool_results)
    conversations.append({"from": "gpt", "value": final_resp})

    return _wrap(seed, conversations)


def _build_clarify_question(seed: Dict) -> str:
    reason = seed.get("clarification_reason", "")
    questions = {
        "campaign_id_missing":               "请问您想查看哪个 Campaign 的数据？提供 Campaign ID 后我马上帮您拉取。",
        "campaign_id_and_timerange_missing":  "请问您想分析哪个 Campaign？需要查看哪个时间段的数据？",
        "platform_or_genre_missing":          "请问您想搜索哪个平台的素材？游戏品类是什么？",
    }
    return questions.get(reason, "请提供更多信息，以便我为您准确查询。")


def _build_refusal(seed: Dict) -> str:
    rtype = seed.get("refusal_type", "off_topic")
    refusals = {
        "off_topic": "抱歉，我是专注于移动游戏广告投放的 AI 助手，这个问题超出了我的服务范围。如有投放数据分析、素材搜索、Campaign 优化等需求，随时可以问我。",
        "unauthorized_operation": f"抱歉，这个操作（删除/修改账户级数据）超出了我的权限范围，为避免不可逆的影响，我无法执行此类操作。如需进行账户级别变更，请通过平台后台或联系您的账户经理处理。",
        "insufficient_data_to_answer": "您的问题我理解，但缺少必要信息（Campaign ID 或时间范围）无法给出准确分析。请提供具体的 Campaign ID，我来帮您查看数据。",
    }
    return refusals.get(rtype, refusals["off_topic"])


def _wrap(seed: Dict, conversations: List[Dict]) -> Dict:
    """包装成最终 ShareGPT record"""
    return {
        "conversations": conversations,
        # 元数据（训练时可忽略，分析时有用）
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
    print(f"✅ 加载种子记录：{len(seeds)} 条")

    conversations = []
    failed = 0

    for seed in tqdm(seeds, desc="生成对话"):
        try:
            conv = build_conversation(seed)
            conversations.append(conv)
        except Exception as e:
            failed += 1
            tqdm.write(f"⚠️  跳过一条记录：{e}")

    # ── 统计 ──
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

    print(f"\n✅ 生成完成：{len(conversations)} 条对话，失败 {failed} 条")
    print(f"📊 平均对话轮数：{sum(turn_lengths)/max(len(turn_lengths),1):.1f} turns")

    print("\n📋 工作流分布:")
    for wf, cnt in sorted(wf_counter.items()):
        print(f"  {wf}: {cnt}")

    print("\n🏷  场景分布 (Top 12):")
    for sc, cnt in sorted(scene_counter.items(), key=lambda x: -x[1])[:12]:
        print(f"  {sc}: {cnt}")

    Path(output_path).write_text(
        json.dumps(conversations, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 已保存至：{output_path}")


if __name__ == "__main__":

    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"  # A_My/data/

    inp = input("Input JSON file name: ").strip()

    # Search in data/ first, then script dir as fallback
    candidate = data_dir / inp
    if not candidate.exists():
        candidate = script_dir / inp
    if not candidate.exists():
        print(f"❌ 数据文件没有找到: {inp} (在 {data_dir} 和 {script_dir} 两个路径中)")
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
    print(f"💾 输出的结果已保存至: {out_path}")

    main(str(inp_path), str(out_path))