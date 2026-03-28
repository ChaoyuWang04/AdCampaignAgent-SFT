"""
Ad Campaign Agent - Seed Data Generator
Generates seed conversation records for SFT training (without final dialogue content)
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# Global Business Constants
# ─────────────────────────────────────────────

PLATFORMS = ["Google", "Meta", "Tiktok", "Applovin", "Unity"]
GAME_GENRES = ["casual", "puzzle", "hyper_casual", "strategy", "rpg"]
REGIONS = ["US", "JP", "SEA", "KR", "EU"]

# ROAS safety baselines (D7 / D30), by platform × genre
ROAS_BASELINES = {
    "Google": {"casual": (0.80, 1.20), "puzzle": (0.85, 1.30),
                   "hyper_casual": (0.60, 0.90), "strategy": (0.90, 1.40), "rpg": (0.95, 1.50)},
    "Meta":       {"casual": (0.75, 1.10), "puzzle": (0.80, 1.20),
                   "hyper_casual": (0.55, 0.85), "strategy": (0.85, 1.30), "rpg": (0.90, 1.40)},
    "Tiktok":     {"casual": (0.72, 1.00), "puzzle": (0.75, 1.10),
                   "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Applovin":     {"casual": (0.68, 1.00), "puzzle": (0.73, 1.10),
                    "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Unity":     {"casual": (0.58, 1.00), "puzzle": (0.53, 1.10),
                    "hyper_casual": (0.52, 0.80), "strategy": (0.87, 1.20), "rpg": (0.83, 1.30)},
}

# Retention safety baselines (D1 / D7), by genre
RET_BASELINES = {
    "casual":       {"d1": 0.35, "d7": 0.12},
    "puzzle":       {"d1": 0.38, "d7": 0.14},
    "hyper_casual": {"d1": 0.40, "d7": 0.15},
    "strategy":     {"d1": 0.30, "d7": 0.10},
    "rpg":          {"d1": 0.28, "d7": 0.09},
}

# Workflow definitions
WORKFLOW_NAMES = {
    1: {"zh": "素材搜寻", "en": "Creative Search"},
    2: {"zh": "素材上传", "en": "Creative Upload"},
    3: {"zh": "单指标效果查询", "en": "Single Metric Query"},
    4: {"zh": "多维深度分析", "en": "Multi-Dimensional Deep Analysis"},
    5: {"zh": "异常诊断与优化", "en": "Anomaly Diagnosis & Optimization"},
    6: {"zh": "知识问答", "en": "Knowledge Q&A"},
    7: {"zh": "拒答", "en": "Refusal"},
}

# Predefined tool chains (Decision 1: predefined)
TOOL_CHAINS = {
    1: [["search_trending_creatives"],
        ["search_competitor_ads"],
        ["search_trending_creatives", "get_trending_hooks"],
        ["search_competitor_ads", "search_trending_creatives"]],

    2: [["validate_creative_spec", "upload_creative_asset"],
        ["validate_creative_spec", "batch_upload_creatives"],
        ["validate_creative_spec"]],           # Validation failed, skip upload

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

    7: [],  # Refusal does not invoke any tool
}

# Scene tag list (Decision 2: ROAS/RET as the core axis)
SCENE_TAGS = [
    "healthy",
    "roas_warning",
    "roas_danger",
    "ret_warning",
    "ret_danger",
    "both_warning",
    "both_danger",
    "creative_fatigue",
    "budget_underdelivery",
    "insufficient_data",
]

# Refusal subtypes
REFUSAL_TYPES = ["off_topic", "unauthorized_operation", "insufficient_data_to_answer"]

# User roles
USER_ROLES = {
    "zh": ["UA Manager", "Creative Lead", "Growth Lead", "运营主管", "投放优化师"],
    "en": ["UA Manager", "Creative Lead", "Growth Lead", "Operations Manager", "Campaign Optimizer"],
}

TEXT = {
    "zh": {
        "progress": "进度",
        "start": "▶ 开始生成 Ad Agent 种子数据集...",
        "done": "✅ 生成完成，共 {count} 条",
        "workflow_distribution": "\n📊 工作流分布:",
        "workflow_count": "  {name}: {count} 条",
        "scene_distribution": "\n🏷  场景标签分布 (Top 10):",
        "scene_count": "  {name}: {count} 条",
        "clarify_count": "\n🔁 需要追问的样本: {count} 条 ({pct:.1f}%)",
        "saved": "\n💾 已经保存至: {path}",
        "lang_prompt": "请选择语言 (zh/en): ",
        "invalid_lang": "❌ 语言输入无效，请输入 zh 或 en。",
    },
    "en": {
        "progress": "Progress",
        "start": "▶ Starting Ad Agent seed dataset generation...",
        "done": "✅ Generation complete, total {count} records",
        "workflow_distribution": "\n📊 Workflow distribution:",
        "workflow_count": "  {name}: {count} records",
        "scene_distribution": "\n🏷  Scene tag distribution (Top 10):",
        "scene_count": "  {name}: {count} records",
        "clarify_count": "\n🔁 Samples requiring clarification: {count} ({pct:.1f}%)",
        "saved": "\n💾 Saved to: {path}",
        "lang_prompt": "Choose language (zh/en): ",
        "invalid_lang": "❌ Invalid language. Please enter zh or en.",
    },
}

# Simulated Campaign / App ID pools
def _make_campaign_ids(n=60):
    return [f"CMP_{random.randint(1000, 9999)}" for _ in range(n)]

def _make_app_ids():
    prefixes = ["com.guru", "com.funplay", "com.gamestar", "io.mobilegame"]
    genres = ["puzzle", "casual", "match3", "runner", "merge"]
    return [f"{p}.{g}{random.randint(1,9):02d}"
            for p in prefixes for g in genres]

CAMPAIGN_IDS = _make_campaign_ids(500)
APP_IDS = _make_app_ids()


# ─────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────

def random_date_range(window_days=7, offset_max=14):
    """Generate a random [start, end] date range"""
    end = datetime(2026, 3, 1) - timedelta(days=random.randint(0, offset_max))
    start = end - timedelta(days=window_days)
    return {
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
    }

def random_context(lang: str):
    """Generate a business context snapshot for one conversation"""
    platform = random.choice(PLATFORMS)
    genre = random.choice(GAME_GENRES)
    return {
        "platform": platform,
        "game_genre": genre,
        "region": random.choice(REGIONS),
        "campaign_id": random.choice(CAMPAIGN_IDS),
        "app_id": random.choice(APP_IDS),
        "user_role": random.choice(USER_ROLES[lang]),
        "roas_baseline_d7": ROAS_BASELINES[platform][genre][0],
        "roas_baseline_d30": ROAS_BASELINES[platform][genre][1],
        "ret_baseline_d1": RET_BASELINES[genre]["d1"],
        "ret_baseline_d7": RET_BASELINES[genre]["d7"],
        "date_range": random_date_range(),
    }


# ─────────────────────────────────────────────
# Main Generator Class
# ─────────────────────────────────────────────

class AdDatasetGenerator:

    def __init__(self, lang: str):
        if lang not in {"zh", "en"}:
            raise ValueError("lang must be 'zh' or 'en'")
        self.lang = lang
        self.progress = {"completed": 0, "total": 0}

    def _update_progress(self):
        self.progress["completed"] += 1
        c = self.progress["completed"]
        t = self.progress["total"]
        print(f"\r{TEXT[self.lang]['progress']}: {c}/{t} ({100*c/t:.1f}%)", end="", flush=True)

    def _base_record(self, workflow: int, ctx: dict) -> dict:
        """Base fields shared by all workflows"""
        return {
            "workflow": workflow,
            "workflow_name": WORKFLOW_NAMES[workflow][self.lang],
            "user_role": ctx["user_role"],
            "platform": ctx["platform"],
            "game_genre": ctx["game_genre"],
            "region": ctx["region"],
            "campaign_id": ctx["campaign_id"],
            "app_id": ctx["app_id"],
            "date_range": ctx["date_range"],
            # Safety baselines (for use in the mock tool_result generation phase)
            "roas_baseline_d7": ctx["roas_baseline_d7"],
            "roas_baseline_d30": ctx["roas_baseline_d30"],
            "ret_baseline_d1": ctx["ret_baseline_d1"],
            "ret_baseline_d7": ctx["ret_baseline_d7"],
            # Conversation control fields
            "user_query": "",
            "needs_clarification": False,
            "clarification_reason": None,
            "clarification_answer": None,
            "scene_tag": None,
            "tool_chain": [],
            "refusal_type": None,
        }

    # ── Workflow 1: Creative Search ──────────────────────

    def gen_workflow1_creative_search(self, count: int) -> list:
        """Creative search: with and without clarification follow-up"""
        if self.lang == "zh":
            queries_clear = [
                "帮我搜一下{platform}上最近{genre}品类的热门素材",
                "查一下{competitor}最近在{platform}上投了什么广告",
                "{region}市场上，{genre}游戏最近什么素材类型CTR高？",
                "搜一下竞品{competitor}在{platform}的广告创意",
                "我需要看看最近{platform}上puzzle游戏的热门钩子",
                "帮我找找{genre}品类在{region}表现好的视频素材",
                "最近有哪些{genre}游戏广告在{platform}跑量很好？",
                "给我看看{competitor}最近的广告长什么样",
            ]
            queries_ambiguous = [
                "帮我搜一下最近的热门素材",
                "看看竞品最近投了什么",
                "找一些素材参考",
                "搜一下行业里表现好的广告",
                "有没有好的素材灵感？",
            ]
            clarification_answers = [
                f"平台选{p}，品类是{g}，地区{r}"
                for p in PLATFORMS for g in GAME_GENRES[:3] for r in REGIONS[:3]
            ]
        else:
            queries_clear = [
                "Find me the top-performing creatives for {genre} games on {platform} recently",
                "Look up what ads {competitor} has been running on {platform} lately",
                "In the {region} market, which creative types have the highest CTR for {genre} games?",
                "Search for competitor {competitor}'s ad creatives on {platform}",
                "I want to see the trending hooks for puzzle games on {platform} recently",
                "Help me find high-performing video creatives for {genre} games in {region}",
                "Which {genre} game ads have been scaling well on {platform} recently?",
                "Show me what {competitor}'s recent ads look like",
            ]
            queries_ambiguous = [
                "Find me some trending creatives recently",
                "Check what competitors have been running lately",
                "Find some creative references for me",
                "Search for high-performing ads in the industry",
                "Any good creative inspiration out there?",
            ]
            clarification_answers = [
                f"Platform is {p}, genre is {g}, region is {r}"
                for p in PLATFORMS for g in GAME_GENRES[:3] for r in REGIONS[:3]
            ]
        competitors = ["Playrix", "Rollic", "Voodoo", "Jam City", "SciPlay"]

        data = []
        for _ in range(count):
            ctx = random_context(self.lang)
            rec = self._base_record(1, ctx)
            needs_clarify = random.random() < 0.2   # 20% require clarification

            if needs_clarify:
                rec["user_query"] = random.choice(queries_ambiguous)
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "platform_or_genre_missing"
                rec["clarification_answer"] = random.choice(clarification_answers)
            else:
                tmpl = random.choice(queries_clear)
                rec["user_query"] = (tmpl
                    .replace("{platform}", ctx["platform"])
                    .replace("{genre}", ctx["game_genre"])
                    .replace("{region}", ctx["region"])
                    .replace("{competitor}", random.choice(competitors)))
                rec["needs_clarification"] = False

            rec["scene_tag"] = "creative_search"
            rec["tool_chain"] = random.choice(TOOL_CHAINS[1])
            data.append(rec)
            self._update_progress()
        return data

    # ── Workflow 2: Creative Upload ──────────────────────

    def gen_workflow2_upload(self, count: int) -> list:
        """Creative upload: validate → upload, including validation failure scenarios"""
        if self.lang == "zh":
            queries = [
                "我有一批新素材要上传到{campaign_id}，帮我上传",
                "把这个视频上传到campaign {campaign_id}",
                "我需要把新做的素材挂到{platform}的{campaign_id}上",
                "上传素材到{campaign_id}，共3个视频",
                "帮我批量上传这批{genre}素材",
            ]
            fail_queries = [
                "这个视频素材上传一下",
                "帮我把这个图片广告传上去",
                "上传这个素材到{platform}",
            ]
        else:
            queries = [
                "I have a new batch of creatives to upload to {campaign_id}, please upload them",
                "Upload this video to campaign {campaign_id}",
                "I need to attach the new creatives to {platform} campaign {campaign_id}",
                "Upload creatives to {campaign_id}, 3 videos total",
                "Help me batch upload this set of {genre} creatives",
            ]
            fail_queries = [
                "Upload this video creative",
                "Help me upload this image ad",
                "Upload this creative to {platform}",
            ]
        upload_scenes = ["upload_success", "validate_fail_size",
                         "validate_fail_format", "upload_partial_fail"]

        data = []
        for _ in range(count):
            ctx = random_context(self.lang)
            rec = self._base_record(2, ctx)
            is_fail = random.random() < 0.25   # 25% validation failure scenarios

            if is_fail:
                rec["user_query"] = (random.choice(fail_queries)
                    .replace("{platform}", ctx["platform"]))
                rec["scene_tag"] = random.choice(
                    ["validate_fail_size", "validate_fail_format"])
                rec["tool_chain"] = ["validate_creative_spec"]   # Validation failed, skip upload
            else:
                rec["user_query"] = (random.choice(queries)
                    .replace("{campaign_id}", ctx["campaign_id"])
                    .replace("{platform}", ctx["platform"])
                    .replace("{genre}", ctx["game_genre"]))
                rec["scene_tag"] = random.choice(
                    ["upload_success", "upload_partial_fail"])
                rec["tool_chain"] = random.choice(TOOL_CHAINS[2][:2])

            data.append(rec)
            self._update_progress()
        return data

    # ── Workflow 3: Single Metric Query ──────────────────

    def gen_workflow3_single_query(self, count: int) -> list:
        """Simple metric queries with a single tool call"""
        if self.lang == "zh":
            queries = [
                "查一下{campaign_id}上周的ROAS",
                "{campaign_id}最近7天的D1留存是多少？",
                "看看{campaign_id}的花费情况",
                "{campaign_id}各国家的安装量怎么样？",
                "给我拉一下{campaign_id}最近的CTR数据",
                "{app_id}上周的留存报告",
                "查一下{campaign_id}按素材拆分的CPM",
                "{campaign_id}的D7 ROAS达标了吗？",
                "看看{app_id}最近的收入归因数据",
                "{campaign_id}昨天的预算消耗正常吗？",
            ]
            ambiguous = [
                "查一下ROAS", "留存数据怎么样？", "花了多少预算？",
                "效果怎么样？", "数据拉一下",
            ]
            clarify_answers = [
                f"campaign是{cid}" for cid in random.sample(CAMPAIGN_IDS, 10)
            ]
        else:
            queries = [
                "Check the ROAS for {campaign_id} last week",
                "What is the D1 retention for {campaign_id} over the last 7 days?",
                "Show me the spend for {campaign_id}",
                "How are installs looking by country for {campaign_id}?",
                "Pull the CTR data for {campaign_id} recently",
                "Last week's retention report for {app_id}",
                "Check CPM broken down by creative for {campaign_id}",
                "Has {campaign_id}'s D7 ROAS hit the target?",
                "Show me the revenue attribution data for {app_id} recently",
                "Is {campaign_id}'s budget spend normal yesterday?",
            ]
            ambiguous = [
                "Check the ROAS", "How's the retention?", "How much budget was spent?",
                "How's performance?", "Pull the data",
            ]
            clarify_answers = [
                f"The campaign is {cid}" for cid in random.sample(CAMPAIGN_IDS, 10)
            ]

        data = []
        for _ in range(count):
            ctx = random_context(self.lang)
            rec = self._base_record(3, ctx)
            needs_clarify = random.random() < 0.2

            if needs_clarify:
                rec["user_query"] = random.choice(ambiguous)
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "campaign_id_missing"
                rec["clarification_answer"] = random.choice(clarify_answers)
            else:
                rec["user_query"] = (random.choice(queries)
                    .replace("{campaign_id}", ctx["campaign_id"])
                    .replace("{app_id}", ctx["app_id"]))

            rec["scene_tag"] = random.choice(SCENE_TAGS[:7])
            rec["tool_chain"] = random.choice(TOOL_CHAINS[3])
            data.append(rec)
            self._update_progress()
        return data

    # ── Workflow 4: Multi-Dimensional Deep Analysis ──────────────────

    def gen_workflow4_deep_analysis(self, count: int) -> list:
        """Core scenario: 2-4 chained tool calls, dual ROAS/RET analysis"""
        if self.lang == "zh":
            scene_query_map = {
                "healthy": [
                    "{campaign_id}整体跑得不错，帮我出一份完整分析报告",
                    "分析一下{campaign_id}上周的整体表现，看哪里还能优化",
                    "{campaign_id}各维度数据都正常，帮我总结一下",
                ],
                "roas_warning": [
                    "{campaign_id}的ROAS感觉低了，帮我分析一下原因",
                    "上周{campaign_id}的回收不太好，详细看一下",
                    "ROAS好像没到基准线，帮我排查一下{campaign_id}",
                ],
                "roas_danger": [
                    "{campaign_id}的ROAS严重低于预期，紧急分析",
                    "回收率崩了，{campaign_id}出什么问题了？",
                    "ROAS跌破安全线了，{campaign_id}要怎么处理？",
                ],
                "ret_warning": [
                    "{campaign_id}留存有点低，帮我看看是素材问题还是产品问题",
                    "D7留存没达标，分析一下{campaign_id}",
                    "留存率比基准线低了一些，{campaign_id}的数据详细看一下",
                ],
                "ret_danger": [
                    "{campaign_id}留存率很差，是不是素材吸引了错误用户？",
                    "D1留存跌得厉害，{campaign_id}要全面分析",
                    "留存远低于基线，{campaign_id}帮我深度诊断一下",
                ],
                "both_warning": [
                    "{campaign_id}最近ROAS和留存都有点问题，帮我综合分析",
                    "整体表现不太好，{campaign_id}各维度都看一下",
                    "ROAS和RET双双偏低，{campaign_id}怎么优化？",
                ],
                "both_danger": [
                    "{campaign_id}全线告警，ROAS和留存都跌破基准，紧急处理",
                    "数据很差，{campaign_id}帮我出一个完整的问题分析",
                    "ROAS和留存同时崩了，{campaign_id}是什么情况？",
                ],
                "creative_fatigue": [
                    "{campaign_id}的ROAS还行但CTR一直在下滑，素材是不是疲了？",
                    "素材好像跑疲了，{campaign_id}CTR周环比下降很多",
                    "留存ROAS都达标但量开始掉，{campaign_id}分析一下",
                ],
                "budget_underdelivery": [
                    "{campaign_id}预算花不出去，CPM太高了，帮我分析",
                    "投放欠量严重，{campaign_id}是竞争太激烈吗？",
                    "{campaign_id}预算消耗只有目标的60%，怎么回事？",
                ],
                "insufficient_data": [
                    "{campaign_id}刚上线两天，现在数据能说明什么问题？",
                    "新campaign{campaign_id}数据够用吗，能分析吗？",
                    "才跑了不到3天的{campaign_id}，留存和ROAS有参考价值吗？",
                ],
            }
            ambiguous_queries = [
                "帮我分析一下最近的投放效果",
                "整体表现怎么样？",
                "出一份投放分析报告",
                "看看数据，有没有问题",
                "综合分析一下",
            ]
            clarify_answers = [
                f"看{cid}，时间是上周"
                for cid in random.sample(CAMPAIGN_IDS, 10)
            ]
        else:
            scene_query_map = {
                "healthy": [
                    "{campaign_id} is performing well overall, please generate a full analysis report",
                    "Analyze the overall performance of {campaign_id} last week and identify optimization opportunities",
                    "All metrics for {campaign_id} look normal, please summarize the results",
                ],
                "roas_warning": [
                    "ROAS for {campaign_id} seems low, help me analyze the cause",
                    "Last week's payback for {campaign_id} wasn't great, take a detailed look",
                    "ROAS looks like it missed the baseline, please investigate {campaign_id}",
                ],
                "roas_danger": [
                    "ROAS for {campaign_id} is severely below expectations, urgent analysis needed",
                    "Payback has collapsed, what happened with {campaign_id}?",
                    "ROAS has dropped below the safety threshold, what should we do with {campaign_id}?",
                ],
                "ret_warning": [
                    "Retention for {campaign_id} is a bit low, help me check if it's a creative issue or a product issue",
                    "D7 retention hasn't hit target, analyze {campaign_id}",
                    "Retention rate is slightly below baseline, take a detailed look at {campaign_id}'s data",
                ],
                "ret_danger": [
                    "Retention for {campaign_id} is very poor, is the creative attracting the wrong users?",
                    "D1 retention dropped sharply, run a full analysis on {campaign_id}",
                    "Retention is far below baseline, please do a deep diagnosis on {campaign_id}",
                ],
                "both_warning": [
                    "Both ROAS and retention have been slightly off for {campaign_id} recently, please do a comprehensive analysis",
                    "Overall performance is not great, look at all dimensions for {campaign_id}",
                    "Both ROAS and retention are below target, how should we optimize {campaign_id}?",
                ],
                "both_danger": [
                    "{campaign_id} is in full alert mode, ROAS and retention have both broken baseline thresholds, urgent action needed",
                    "Data looks very bad, please produce a complete problem analysis for {campaign_id}",
                    "ROAS and retention crashed at the same time, what is going on with {campaign_id}?",
                ],
                "creative_fatigue": [
                    "ROAS for {campaign_id} is fine but CTR keeps declining, is the creative fatiguing?",
                    "Creatives seem to be burning out, CTR for {campaign_id} dropped a lot week-over-week",
                    "Retention and ROAS are both on target but volume is starting to drop, analyze {campaign_id}",
                ],
                "budget_underdelivery": [
                    "{campaign_id} can't spend its budget, CPM is too high, please analyze",
                    "Severe underdelivery on spend, is competition too fierce for {campaign_id}?",
                    "Budget consumption for {campaign_id} is only 60% of target, what's happening?",
                ],
                "insufficient_data": [
                    "{campaign_id} just launched two days ago, what can the data tell us right now?",
                    "Is there enough data for new campaign {campaign_id} to run an analysis?",
                    "{campaign_id} has only been running for less than 3 days, are the retention and ROAS figures meaningful?",
                ],
            }
            ambiguous_queries = [
                "Help me analyze the recent campaign performance",
                "How is overall performance looking?",
                "Generate a campaign analysis report",
                "Look at the data, are there any issues?",
                "Give me a comprehensive analysis",
            ]
            clarify_answers = [
                f"Look at {cid}, timeframe is last week"
                for cid in random.sample(CAMPAIGN_IDS, 10)
            ]

        data = []
        for _ in range(count):
            ctx = random_context(self.lang)
            rec = self._base_record(4, ctx)
            scene = random.choice(SCENE_TAGS)
            needs_clarify = random.random() < 0.15  # 15% require clarification

            if needs_clarify:
                rec["user_query"] = random.choice(ambiguous_queries)
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "campaign_id_and_timerange_missing"
                rec["clarification_answer"] = random.choice(clarify_answers)
            else:
                tmpl = random.choice(scene_query_map[scene])
                rec["user_query"] = tmpl.replace("{campaign_id}", ctx["campaign_id"])

            rec["scene_tag"] = scene
            rec["tool_chain"] = random.choice(TOOL_CHAINS[4])
            data.append(rec)
            self._update_progress()
        return data

    # ── Workflow 5: Anomaly Diagnosis & Optimization ──────────────────

    def gen_workflow5_anomaly(self, count: int) -> list:
        """detect_anomalies → get_optimization_playbook"""
        if self.lang == "zh":
            scene_query_map = {
                "roas_danger": [
                    "{campaign_id}的ROAS今天突然跌了很多，帮我诊断",
                    "ROAS异常下跌，{campaign_id}触发告警了",
                    "{campaign_id}回收指标出现异常，帮我排查",
                ],
                "ret_danger": [
                    "{campaign_id}的D1留存今天异常，帮我看看",
                    "留存率突然跌了，{campaign_id}是怎么回事",
                    "{campaign_id}新增用户留存异常下降",
                ],
                "both_danger": [
                    "{campaign_id}同时出现ROAS和留存双告警，紧急诊断",
                    "多个指标同时异常，{campaign_id}帮我全面诊断",
                ],
                "creative_fatigue": [
                    "{campaign_id}CTR连续3天下滑超过20%，是素材疲劳吗？",
                    "投放量开始下掉了，{campaign_id}帮我诊断一下",
                ],
                "budget_underdelivery": [
                    "{campaign_id}欠量很严重，帮我诊断原因",
                    "预算消耗异常偏低，{campaign_id}出什么问题了",
                ],
            }
        else:
            scene_query_map = {
                "roas_danger": [
                    "ROAS for {campaign_id} dropped sharply today, please diagnose",
                    "ROAS anomaly detected, {campaign_id} has triggered an alert",
                    "Payback metrics are abnormal for {campaign_id}, please investigate",
                ],
                "ret_danger": [
                    "D1 retention for {campaign_id} looks abnormal today, please check",
                    "Retention rate suddenly dropped, what's going on with {campaign_id}?",
                    "New user retention dropped abnormally for {campaign_id}",
                ],
                "both_danger": [
                    "Both ROAS and retention are alerting at the same time for {campaign_id}, urgent diagnosis needed",
                    "Multiple metrics are anomalous simultaneously, please run a full diagnosis on {campaign_id}",
                ],
                "creative_fatigue": [
                    "CTR for {campaign_id} has declined more than 20% for 3 consecutive days, is this creative fatigue?",
                    "Volume is starting to drop on {campaign_id}, please run a diagnosis",
                ],
                "budget_underdelivery": [
                    "Severe underdelivery on {campaign_id}, please diagnose the cause",
                    "Budget spend is abnormally low, what went wrong with {campaign_id}?",
                ],
            }

        anomaly_scenes = ["roas_danger", "ret_danger", "both_danger",
                          "creative_fatigue", "budget_underdelivery"]
        data = []
        for _ in range(count):
            ctx = random_context(self.lang)
            rec = self._base_record(5, ctx)
            scene = random.choice(anomaly_scenes)
            tmpl = random.choice(scene_query_map[scene])
            rec["user_query"] = tmpl.replace("{campaign_id}", ctx["campaign_id"])
            rec["scene_tag"] = scene
            rec["tool_chain"] = random.choice(TOOL_CHAINS[5])
            data.append(rec)
            self._update_progress()
        return data

    # ── Workflow 6: Knowledge Q&A ──────────────────────

    def gen_workflow6_knowledge(self, count: int) -> list:
        """RAG knowledge retrieval scenarios"""
        if self.lang == "zh":
            queries = [
                "tCPA和tROAS出价策略有什么区别，什么时候用哪个？",
                "UAC的Smart Bidding学习期一般多久？",
                "Meta的ABO和CBO有什么区别？",
                "出价策略从tCPA切换到tROAS需要注意什么？",
                "视频广告的前3秒钩子怎么设计才能提高CTR？",
                "hyper-casual游戏适合哪些广告格式？",
                "什么样的素材容易在TikTok上跑量？",
                "playable广告的设计要点是什么？",
                "Google UAC对游戏广告有哪些内容限制？",
                "Meta广告的定向规则最近有什么变化？",
                "TikTok对博彩类游戏广告有什么限制？",
                "Google对游戏内购内容的展示有什么规定？",
                "casual游戏在US市场的D7 ROAS基准是多少？",
                "puzzle游戏的行业平均D1留存是什么水平？",
                "TikTok上hyper-casual游戏的平均CPM是多少？",
                "SEA市场的CPI行业基准大概是多少？",
            ]
            domain_map = {
                "tCPA": "bidding_strategy", "UAC": "bidding_strategy",
                "ABO": "bidding_strategy", "出价策略": "bidding_strategy",
                "钩子": "creative_guideline", "hyper-casual": "creative_guideline",
                "TikTok上跑量": "creative_guideline", "playable": "creative_guideline",
                "内容限制": "platform_policy", "定向规则": "platform_policy",
                "博彩": "platform_policy", "内购": "platform_policy",
                "ROAS基准": "industry_benchmark", "留存": "industry_benchmark",
                "CPM": "industry_benchmark", "CPI": "industry_benchmark",
            }
        else:
            queries = [
                "What's the difference between tCPA and tROAS bidding, and when should I use each?",
                "How long is the Smart Bidding learning period for UAC typically?",
                "What's the difference between ABO and CBO on Meta?",
                "What should I watch out for when switching bidding strategy from tCPA to tROAS?",
                "How should I design the first 3 seconds of a video ad to improve CTR?",
                "What ad formats work best for hyper-casual games?",
                "What kind of creatives tend to scale well on TikTok?",
                "What are the key design principles for playable ads?",
                "What content restrictions does Google UAC have for game ads?",
                "What recent changes have been made to Meta's ad targeting rules?",
                "What restrictions does TikTok have for gambling-related game ads?",
                "What are Google's regulations for displaying in-app purchase content?",
                "What is the D7 ROAS benchmark for casual games in the US market?",
                "What is the industry average D1 retention rate for puzzle games?",
                "What is the average CPM for hyper-casual games on TikTok?",
                "What is the industry CPI benchmark for the SEA market?",
            ]
            domain_map = {
                "tCPA": "bidding_strategy", "UAC": "bidding_strategy",
                "ABO": "bidding_strategy", "bidding strategy": "bidding_strategy",
                "hooks": "creative_guideline", "hyper-casual": "creative_guideline",
                "scale well on TikTok": "creative_guideline", "playable": "creative_guideline",
                "content restrictions": "platform_policy", "targeting rules": "platform_policy",
                "gambling": "platform_policy", "in-app purchase": "platform_policy",
                "ROAS benchmark": "industry_benchmark", "retention": "industry_benchmark",
                "CPM": "industry_benchmark", "CPI": "industry_benchmark",
            }

        data = []
        for _ in range(count):
            ctx = random_context(self.lang)
            rec = self._base_record(6, ctx)
            q = random.choice(queries)
            rec["user_query"] = q
            # Auto-infer domain
            domain = "knowledge_base"
            for kw, d in domain_map.items():
                if kw in q:
                    domain = d
                    break
            rec["scene_tag"] = domain
            rec["tool_chain"] = random.choice(TOOL_CHAINS[6])
            data.append(rec)
            self._update_progress()
        return data

    # ── Workflow 7: Refusal ──────────────────────────

    def gen_workflow7_refusal(self, count: int) -> list:
        """Three categories of refusal scenarios"""
        if self.lang == "zh":
            refusal_templates = {
                "off_topic": [
                    "帮我写一段Python代码",
                    "今天天气怎么样？",
                    "推荐几部电影",
                    "帮我翻译一下这段英文",
                    "区块链是什么？",
                    "帮我分析一下股票",
                    "如何学习机器学习？",
                    "1+1等于几",
                    "帮我写一首诗",
                    "给我讲个笑话",
                ],
                "unauthorized_operation": [
                    "帮我删掉{campaign_id}这个campaign",
                    "把竞品{competitor}的广告账户数据给我",
                    "直接修改{campaign_id}的出价为0.1美元",
                    "把我们所有campaign的预算全部清零",
                    "帮我入侵一下竞品的广告账号",
                    "强制暂停所有正在跑的广告",
                    "把其他团队的campaign数据导出来",
                ],
                "insufficient_data_to_answer": [
                    "ROAS怎么样？",
                    "留存达标了吗？",
                    "效果好吗？",
                    "数据正常吗？",
                    "投放情况怎么样？",
                    "有没有异常？",
                ],
            }
        else:
            refusal_templates = {
                "off_topic": [
                    "Write me a Python script",
                    "What's the weather like today?",
                    "Recommend some movies",
                    "Help me translate this paragraph",
                    "What is blockchain?",
                    "Help me analyze some stocks",
                    "How do I learn machine learning?",
                    "What is 1+1?",
                    "Write me a poem",
                    "Tell me a joke",
                ],
                "unauthorized_operation": [
                    "Delete campaign {campaign_id} for me",
                    "Give me the ad account data for competitor {competitor}",
                    "Directly set the bid for {campaign_id} to $0.10",
                    "Zero out the budget for all our campaigns",
                    "Help me hack into a competitor's ad account",
                    "Force pause all currently running ads",
                    "Export campaign data from other teams",
                ],
                "insufficient_data_to_answer": [
                    "How's the ROAS?",
                    "Did retention hit the target?",
                    "Is performance good?",
                    "Is the data normal?",
                    "How's the campaign going?",
                    "Are there any anomalies?",
                ],
            }
        competitors = ["Playrix", "Voodoo", "Rollic", "Jam City"]

        data = []
        per_type = count // 3
        extras = count % 3
        type_counts = {
            "off_topic": per_type + (1 if extras > 0 else 0),
            "unauthorized_operation": per_type + (1 if extras > 1 else 0),
            "insufficient_data_to_answer": per_type,
        }

        for rtype, n in type_counts.items():
            for _ in range(n):
                ctx = random_context(self.lang)
                rec = self._base_record(7, ctx)
                tmpl = random.choice(refusal_templates[rtype])
                rec["user_query"] = (tmpl
                    .replace("{campaign_id}", ctx["campaign_id"])
                    .replace("{competitor}", random.choice(competitors)))
                rec["scene_tag"] = rtype
                rec["refusal_type"] = rtype
                rec["tool_chain"] = []
                data.append(rec)
                self._update_progress()
        return data

    # ── Main Generation Entry Point ────────────────────────────

    def generate(self, output_path: str = None):
        """
        Generate the complete seed dataset.
        Record count per workflow (total ~1000):
          WF1 Creative Search              120
          WF2 Creative Upload               80
          WF3 Single Metric Query          120
          WF4 Multi-Dimensional Analysis   350  ← Core, largest share
          WF5 Anomaly Diagnosis            150
          WF6 Knowledge Q&A                 80
          WF7 Refusal                      100
        """
        task_plan = [
            (self.gen_workflow1_creative_search, 120),
            (self.gen_workflow2_upload,           80),
            (self.gen_workflow3_single_query,    120),
            (self.gen_workflow4_deep_analysis,   350),
            (self.gen_workflow5_anomaly,         150),
            (self.gen_workflow6_knowledge,        80),
            (self.gen_workflow7_refusal,         100),
        ]
        self.progress["total"] = sum(n for _, n in task_plan)

        text = TEXT[self.lang]
        print(text["start"])
        all_records = []

        for fn, n in task_plan:
            all_records.extend(fn(n))

        random.shuffle(all_records)

        # ── Statistics ──
        print(f"\n\n{text['done'].format(count=len(all_records))}")
        wf_counter = {}
        scene_counter = {}
        clarify_count = 0
        for r in all_records:
            wf_counter[r["workflow_name"]] = wf_counter.get(r["workflow_name"], 0) + 1
            scene_counter[r["scene_tag"]] = scene_counter.get(r["scene_tag"], 0) + 1
            if r["needs_clarification"]:
                clarify_count += 1

        print(text["workflow_distribution"])
        for wf, cnt in sorted(wf_counter.items()):
            print(text["workflow_count"].format(name=wf, count=cnt))

        print(text["scene_distribution"])
        for tag, cnt in sorted(scene_counter.items(), key=lambda x: -x[1])[:10]:
            print(text["scene_count"].format(name=tag, count=cnt))

        print(text["clarify_count"].format(
            count=clarify_count,
            pct=100 * clarify_count / len(all_records),
        ))

        # ── Save ──
        if output_path is None:
            repo_root = Path(__file__).resolve().parents[2]
            data_dir = repo_root / "data" / "raw"
            data_dir.mkdir(parents=True, exist_ok=True)
            output_path = data_dir / f"ad_agent_seeds_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.lang}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
        print(text["saved"].format(path=output_path))
        return all_records


# ─────────────────────────────────────────────
def choose_language() -> str:
    while True:
        lang = input(TEXT["en"]["lang_prompt"]).strip().lower()
        if lang in {"zh", "en"}:
            return lang
        print(TEXT["en"]["invalid_lang"])


if __name__ == "__main__":
    gen = AdDatasetGenerator(choose_language())
    gen.generate()


"""
▶ Starting Ad Agent seed dataset generation...
Progress: 1000/1000 (100.0%)

✅ Generation complete, total 1000 records

📊 Workflow distribution:
  Multi-Dimensional Deep Analysis: 350 records
  Anomaly Diagnosis & Optimization: 150 records
  Creative Search: 120 records
  Single Metric Query: 120 records
  Refusal: 100 records
  Creative Upload: 80 records
  Knowledge Q&A: 80 records

🏷  Scene tag distribution:
  roas_warning: ~70 records
  ret_warning: ~65 records
  ...

🔁 Samples requiring clarification: ~170 (17.0%)
"""
