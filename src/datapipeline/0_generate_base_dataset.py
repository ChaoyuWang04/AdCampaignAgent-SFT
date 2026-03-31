"""
Ad Campaign Agent - Seed Data Generator
生成用于 SFT 训练的种子数据，仅保留中文数据生产。
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path


PLATFORMS = ["Google", "Meta", "Tiktok", "Applovin", "Unity"]
GAME_GENRES = ["casual", "puzzle", "hyper_casual", "strategy", "rpg"]
REGIONS = ["US", "JP", "SEA", "KR", "EU"]

ROAS_BASELINES = {
    "Google": {"casual": (0.80, 1.20), "puzzle": (0.85, 1.30),
               "hyper_casual": (0.60, 0.90), "strategy": (0.90, 1.40), "rpg": (0.95, 1.50)},
    "Meta": {"casual": (0.75, 1.10), "puzzle": (0.80, 1.20),
             "hyper_casual": (0.55, 0.85), "strategy": (0.85, 1.30), "rpg": (0.90, 1.40)},
    "Tiktok": {"casual": (0.72, 1.00), "puzzle": (0.75, 1.10),
               "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Applovin": {"casual": (0.68, 1.00), "puzzle": (0.73, 1.10),
                 "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Unity": {"casual": (0.58, 1.00), "puzzle": (0.53, 1.10),
              "hyper_casual": (0.52, 0.80), "strategy": (0.87, 1.20), "rpg": (0.83, 1.30)},
}

RET_BASELINES = {
    "casual": {"d1": 0.35, "d7": 0.12},
    "puzzle": {"d1": 0.38, "d7": 0.14},
    "hyper_casual": {"d1": 0.40, "d7": 0.15},
    "strategy": {"d1": 0.30, "d7": 0.10},
    "rpg": {"d1": 0.28, "d7": 0.09},
}

WORKFLOW_NAMES = {
    1: "素材搜寻",
    2: "素材上传",
    3: "单指标效果查询",
    4: "多维深度分析",
    5: "异常诊断与优化",
    6: "知识问答",
    7: "拒答",
}

TOOL_PLANS = {
    1: [
        [{"mode": "serial", "tools": ["search_trending_creatives"]}],
        [{"mode": "serial", "tools": ["search_competitor_ads"]}],
        [{"mode": "serial", "tools": ["search_trending_creatives", "get_trending_hooks"]}],
        [{"mode": "serial", "tools": ["search_competitor_ads", "search_trending_creatives"]}],
    ],
    2: [
        [{"mode": "serial", "tools": ["validate_creative_spec", "upload_creative_asset"]}],
        [{"mode": "serial", "tools": ["validate_creative_spec", "batch_upload_creatives"]}],
        [{"mode": "serial", "tools": ["validate_creative_spec"]}],
    ],
    3: [
        [{"mode": "serial", "tools": ["get_campaign_metrics"]}],
        [{"mode": "serial", "tools": ["get_creative_performance"]}],
        [{"mode": "serial", "tools": ["get_appsflyer_report"]}],
    ],
    4: [
        [{"mode": "parallel", "tools": ["get_campaign_metrics", "get_creative_performance", "get_benchmark_data"]}],
        [
            {"mode": "parallel", "tools": ["get_appsflyer_report", "get_campaign_metrics"]},
            {"mode": "serial", "tools": ["get_benchmark_data"]},
        ],
        [
            {"mode": "parallel", "tools": ["get_campaign_metrics", "get_appsflyer_report", "get_creative_performance"]},
            {"mode": "serial", "tools": ["get_benchmark_data"]},
        ],
        [
            {"mode": "serial", "tools": ["compare_campaigns"]},
            {"mode": "serial", "tools": ["get_benchmark_data"]},
        ],
    ],
    5: [
        [
            {"mode": "serial", "tools": ["detect_anomalies"]},
            {"mode": "serial", "tools": ["get_optimization_playbook"]},
        ],
        [
            {"mode": "serial", "tools": ["detect_anomalies"]},
            {"mode": "serial", "tools": ["get_campaign_metrics"]},
            {"mode": "serial", "tools": ["get_optimization_playbook"]},
        ],
        [
            {"mode": "serial", "tools": ["detect_anomalies"]},
            {"mode": "serial", "tools": ["get_creative_performance"]},
            {"mode": "serial", "tools": ["get_optimization_playbook"]},
        ],
    ],
    6: [
        [{"mode": "serial", "tools": ["query_knowledge_base"]}],
        [{"mode": "serial", "tools": ["get_benchmark_data"]}],
        [{"mode": "serial", "tools": ["get_platform_policy"]}],
        [{"mode": "serial", "tools": ["query_knowledge_base", "get_benchmark_data"]}],
    ],
    7: [[]],
}

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
REFUSAL_TYPES = ["off_topic", "unauthorized_operation", "insufficient_data_to_answer"]
USER_ROLES = ["UA Manager", "Creative Lead", "Growth Lead", "运营主管", "投放优化师"]

TEXT = {
    "progress": "进度",
    "start": "▶ 开始生成 Ad Agent 种子数据集...",
    "done": "✅ 生成完成，共 {count} 条",
    "workflow_distribution": "\n📊 工作流分布:",
    "workflow_count": "  {name}: {count} 条",
    "scene_distribution": "\n🏷  场景标签分布 (Top 10):",
    "scene_count": "  {name}: {count} 条",
    "clarify_count": "\n🔁 需要追问的样本: {count} 条 ({pct:.1f}%)",
    "saved": "\n💾 已保存至: {path}",
}


def _make_campaign_ids(n: int = 60) -> list[str]:
    return [f"CMP_{random.randint(1000, 9999)}" for _ in range(n)]


def _make_app_ids() -> list[str]:
    prefixes = ["com.guru", "com.funplay", "com.gamestar", "io.mobilegame"]
    genres = ["puzzle", "casual", "match3", "runner", "merge"]
    return [f"{prefix}.{genre}{random.randint(1, 9):02d}" for prefix in prefixes for genre in genres]


CAMPAIGN_IDS = _make_campaign_ids(500)
APP_IDS = _make_app_ids()


def random_date_range(window_days: int = 7, offset_max: int = 14) -> dict:
    end = datetime(2026, 3, 1) - timedelta(days=random.randint(0, offset_max))
    start = end - timedelta(days=window_days)
    return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}


def random_context() -> dict:
    platform = random.choice(PLATFORMS)
    genre = random.choice(GAME_GENRES)
    return {
        "platform": platform,
        "game_genre": genre,
        "region": random.choice(REGIONS),
        "campaign_id": random.choice(CAMPAIGN_IDS),
        "app_id": random.choice(APP_IDS),
        "user_role": random.choice(USER_ROLES),
        "roas_baseline_d7": ROAS_BASELINES[platform][genre][0],
        "roas_baseline_d30": ROAS_BASELINES[platform][genre][1],
        "ret_baseline_d1": RET_BASELINES[genre]["d1"],
        "ret_baseline_d7": RET_BASELINES[genre]["d7"],
        "date_range": random_date_range(),
    }


def flatten_tool_plan(tool_plan: list[dict]) -> list[str]:
    flattened: list[str] = []
    for group in tool_plan:
        flattened.extend(group.get("tools", []))
    return flattened


def has_parallel_group(tool_plan: list[dict]) -> bool:
    return any(group.get("mode") == "parallel" and len(group.get("tools", [])) > 1 for group in tool_plan)


METRIC_QUERY_SCENES = [
    "query_roas",
    "query_retention",
    "query_ctr",
    "query_spend",
    "query_installs",
    "query_cpm",
]


def infer_metric_scene(query: str) -> str:
    if any(keyword in query for keyword in ["ROAS", "回收", "roas"]):
        return "query_roas"
    if any(keyword in query for keyword in ["留存", "retention"]):
        return "query_retention"
    if any(keyword in query for keyword in ["CTR", "点击", "ctr"]):
        return "query_ctr"
    if any(keyword in query for keyword in ["花费", "预算", "消耗", "spend"]):
        return "query_spend"
    if any(keyword in query for keyword in ["安装", "installs"]):
        return "query_installs"
    if any(keyword in query for keyword in ["CPM", "cpm"]):
        return "query_cpm"
    return random.choice(METRIC_QUERY_SCENES)


class AdDatasetGenerator:
    def __init__(self):
        self.progress = {"completed": 0, "total": 0}

    def _update_progress(self) -> None:
        self.progress["completed"] += 1
        completed = self.progress["completed"]
        total = self.progress["total"]
        print(f"\r{TEXT['progress']}: {completed}/{total} ({100 * completed / total:.1f}%)", end="", flush=True)

    def _base_record(self, workflow: int, ctx: dict) -> dict:
        return {
            "workflow": workflow,
            "workflow_name": WORKFLOW_NAMES[workflow],
            "user_role": ctx["user_role"],
            "platform": ctx["platform"],
            "game_genre": ctx["game_genre"],
            "region": ctx["region"],
            "campaign_id": ctx["campaign_id"],
            "app_id": ctx["app_id"],
            "date_range": ctx["date_range"],
            "roas_baseline_d7": ctx["roas_baseline_d7"],
            "roas_baseline_d30": ctx["roas_baseline_d30"],
            "ret_baseline_d1": ctx["ret_baseline_d1"],
            "ret_baseline_d7": ctx["ret_baseline_d7"],
            "user_query": "",
            "needs_clarification": False,
            "clarification_reason": None,
            "clarification_answer": None,
            "scene_tag": None,
            "tool_plan": [],
            "tool_chain": [],
            "has_parallel": False,
            "refusal_type": None,
        }

    def gen_workflow1_creative_search(self, count: int) -> list[dict]:
        queries_clear = [
            "帮我搜一下{platform}上最近{genre}品类的热门素材",
            "查一下{competitor}最近在{platform}上投了什么广告",
            "{region}市场上，{genre}游戏最近什么素材类型CTR高？",
            "搜一下竞品{competitor}在{platform}的广告创意",
            "我需要看看最近{platform}上puzzle游戏的热门钩子",
            "帮我找找{genre}品类在{region}表现好的视频素材",
            "最近有哪些{genre}游戏广告在{platform}跑量很好？",
            "给我看看{competitor}最近的广告长什么样",
            "我想看看{platform}最近有哪些{genre}素材跑得特别好",
            "有没有{region}市场最近表现不错的{genre}广告素材",
            "帮我翻一下{platform}上这个月{genre}品类的热门创意",
            "上周{platform}里哪些{genre}广告CTR比较高",
            "我想找一下{competitor}这段时间在{platform}主推的素材方向",
            "看看{region}这边最近有哪些{genre}素材在放量",
            "帮我搜一下最近一周{platform}里跑量最好的{genre}广告",
            "有没有{platform}上{genre}游戏最近用得比较多的素材钩子",
            "查一下{competitor}最近在{region}投的广告素材类型",
            "我想参考一下{platform}上高CTR的{genre}视频创意",
            "最近{genre}品类在{platform}有哪些素材趋势，帮我看下",
            "给我拉一下{platform}近一个月里表现最强的{genre}素材",
            "我想知道{competitor}最近在{platform}都在投什么样的广告",
            "帮我找找{region}市场里近期跑量快的{genre}广告",
            "有没有适合参考的{genre}竞品素材，最好是{platform}上的",
            "上个月{platform}里哪些{genre}创意最容易起量",
            "想看一下{competitor}近期在{platform}的投放素材风格",
            "查查{region}地区最近有哪些{genre}素材既有量又有CTR",
        ]
        queries_ambiguous = [
            "帮我搜一下最近的热门素材",
            "看看竞品最近投了什么",
            "找一些素材参考",
            "搜一下行业里表现好的广告",
            "有没有好的素材灵感？",
            "我想看看最近哪些素材比较火",
            "最近有什么广告创意值得参考吗",
            "帮我找点最近能打的素材",
            "有没有最近跑得不错的广告给我参考一下",
            "我想找一些最近在放量的创意",
            "最近行业里流行什么素材方向",
            "拉一些最近表现不错的广告给我看看",
            "我需要一些最近高表现素材做参考",
            "最近有哪些素材套路比较有用",
            "帮我看看最近什么广告比较能跑",
            "最近竞品都在投什么素材",
            "有没有近期开量不错的创意样本",
            "找一些最近高CTR的素材思路",
            "最近素材方向有啥值得抄作业的",
            "我想看下最近广告素材都在怎么做",
            "给我一些最近有效的素材灵感",
            "最近市场上什么广告比较吃香",
            "帮我捞一些最近表现强的创意",
        ]
        clarification_answers = [
            f"平台选{platform}，品类是{genre}，地区{region}"
            for platform in PLATFORMS
            for genre in GAME_GENRES[:3]
            for region in REGIONS[:3]
        ]
        competitors = ["Playrix", "Rollic", "Voodoo", "Jam City", "SciPlay"]

        data: list[dict] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(1, ctx)
            needs_clarify = random.random() < 0.2
            if needs_clarify:
                rec["user_query"] = random.choice(queries_ambiguous)
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "platform_or_genre_missing"
                rec["clarification_answer"] = random.choice(clarification_answers)
            else:
                rec["user_query"] = (
                    random.choice(queries_clear)
                    .replace("{platform}", ctx["platform"])
                    .replace("{genre}", ctx["game_genre"])
                    .replace("{region}", ctx["region"])
                    .replace("{competitor}", random.choice(competitors))
                )
            rec["scene_tag"] = "creative_search"
            rec["tool_plan"] = random.choice(TOOL_PLANS[1])
            rec["tool_chain"] = flatten_tool_plan(rec["tool_plan"])
            rec["has_parallel"] = has_parallel_group(rec["tool_plan"])
            data.append(rec)
            self._update_progress()
        return data

    def gen_workflow2_upload(self, count: int) -> list[dict]:
        queries = [
            "我有一批新素材要上传到{campaign_id}，帮我上传",
            "把这个视频上传到campaign {campaign_id}",
            "我需要把新做的素材挂到{platform}的{campaign_id}上",
            "上传素材到{campaign_id}，共3个视频",
            "帮我批量上传这批{genre}素材",
            "把这批新视频素材都挂到{campaign_id}下面",
            "我这边有几个新创意，帮我传到{platform}的{campaign_id}",
            "帮我把刚出的{genre}素材上传到{campaign_id}",
            "这组素材今天要上量，先帮我传到{campaign_id}",
            "有一批新广告要上，帮我批量上传到{campaign_id}",
            "把这几个新做的视频先传到{campaign_id}里",
            "我想把新的{genre}创意批量挂到{platform} campaign {campaign_id}",
            "这批素材审核完了，帮我上传到{campaign_id}",
            "给{campaign_id}补一批新素材，麻烦直接上传",
            "我这边整理了几条新广告，帮我传到{campaign_id}",
            "帮我把这组素材发到{platform}那边的{campaign_id}",
            "这几个版本今天要测试，先上传到{campaign_id}",
            "我想给{campaign_id}加几条新素材，你直接帮我传吧",
            "把这批待投放的{genre}素材批量挂上去，campaign 是 {campaign_id}",
        ]
        fail_queries = [
            "这个视频素材上传一下",
            "帮我把这个图片广告传上去",
            "上传这个素材到{platform}",
            "这个素材刚被系统打回来了，你再帮我传一次",
            "上次没传成功，这个视频重新上传一下",
            "这个创意被拒了，我改完了，帮我重传",
            "刚才那条素材好像没过，再上传一遍",
            "这个广告素材重新传到{platform}试一下",
            "帮我把这个被退回的视频再传一次",
            "刚刚上传失败了，这个文件重新帮我走一下",
            "这个素材系统没收进去，你再帮我试试",
            "帮我补传这个广告素材",
            "这条创意改完尺寸了，重新上传一下",
            "上次审核前就挂了，这个素材再传一遍",
            "这个图片广告刚修完格式，帮我重新上传",
            "之前被卡住的那条素材，现在再帮我传一次",
            "这个文件刚处理过，重新丢到{platform}那边上传一下",
        ]

        data: list[dict] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(2, ctx)
            is_fail = random.random() < 0.25
            if is_fail:
                rec["user_query"] = random.choice(fail_queries).replace("{platform}", ctx["platform"])
                rec["scene_tag"] = random.choice(["validate_fail_size", "validate_fail_format"])
                rec["tool_plan"] = random.choice(TOOL_PLANS[2][2:3])
            else:
                rec["user_query"] = (
                    random.choice(queries)
                    .replace("{campaign_id}", ctx["campaign_id"])
                    .replace("{platform}", ctx["platform"])
                    .replace("{genre}", ctx["game_genre"])
                )
                rec["scene_tag"] = random.choice(["upload_success", "upload_partial_fail"])
                rec["tool_plan"] = random.choice(TOOL_PLANS[2][:2])
            rec["tool_chain"] = flatten_tool_plan(rec["tool_plan"])
            rec["has_parallel"] = has_parallel_group(rec["tool_plan"])
            data.append(rec)
            self._update_progress()
        return data

    def gen_workflow3_single_query(self, count: int) -> list[dict]:
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
            "帮我拉一下{campaign_id}昨天的ROAS",
            "看下{campaign_id}最近7天的花费和安装量",
            "我想知道{campaign_id}这个月到现在的CTR表现",
            "查查{campaign_id}上个月的回收情况",
            "{campaign_id}最近三天的D7 ROAS有起色吗？",
            "帮我看看{campaign_id}昨天的CTR是不是掉了",
            "{campaign_id}近一周的CPI是多少",
            "拉一下{campaign_id}最近7天的收入归因",
            "看下{app_id}这周的留存数据",
            "帮我查一下{campaign_id}上周每日花费",
            "{campaign_id}最近30天安装量大概什么水平",
            "看看{campaign_id}这个月预算消耗快不快",
            "{campaign_id}昨天的CPM正常吗",
            "我想拉一下{campaign_id}最近7天的CTR和CPI",
            "帮我看下{campaign_id}当前D1留存有没有达标",
            "查一下{app_id}最近一周的AppsFlyer留存报告",
            "{campaign_id}这几天的ROAS趋势怎么样",
            "看看{campaign_id}近30天花费有没有异常波动",
            "帮我拉一下{campaign_id}昨天到今天的安装量",
            "查查{campaign_id}上个月D1留存表现",
            "这个{campaign_id}最近7天回收效率怎么样",
            "看下{campaign_id}最近一周的CTR达没达标",
            "我想知道{campaign_id}本周的花费节奏",
            "{campaign_id}最近几天的收入归因帮我查一下",
            "拉一下{campaign_id}这周按天拆的ROAS数据",
        ]
        ambiguous = [
            "查一下ROAS",
            "留存数据怎么样？",
            "花了多少预算？",
            "效果怎么样？",
            "数据拉一下",
            "看看回收情况",
            "CTR怎么样",
            "最近花费正常吗",
            "安装量什么情况",
            "帮我看下留存",
            "拉一下最近的数据",
            "最近投放表现怎么样",
            "回收达标了吗",
            "这两天数据好不好",
            "帮我查下效果指标",
        ]
        clarify_answers = [f"campaign是{campaign_id}" for campaign_id in random.sample(CAMPAIGN_IDS, 10)]

        data: list[dict] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(3, ctx)
            if random.random() < 0.2:
                rec["user_query"] = random.choice(ambiguous)
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "campaign_id_missing"
                rec["clarification_answer"] = random.choice(clarify_answers)
            else:
                rec["user_query"] = random.choice(queries).replace("{campaign_id}", ctx["campaign_id"]).replace("{app_id}", ctx["app_id"])
            rec["scene_tag"] = infer_metric_scene(rec["user_query"])
            rec["tool_plan"] = random.choice(TOOL_PLANS[3])
            rec["tool_chain"] = flatten_tool_plan(rec["tool_plan"])
            rec["has_parallel"] = has_parallel_group(rec["tool_plan"])
            data.append(rec)
            self._update_progress()
        return data

    def gen_workflow4_deep_analysis(self, count: int) -> list[dict]:
        scene_query_map = {
            "healthy": [
                "{campaign_id}整体跑得不错，帮我出一份完整分析报告",
                "分析一下{campaign_id}上周的整体表现，看哪里还能优化",
                "{campaign_id}各维度数据都正常，帮我总结一下",
                "{campaign_id}这段时间整体还挺稳的，帮我做个复盘",
                "老板问我{campaign_id}最近表现怎么样，帮我整理一版完整分析",
                "月底要汇报了，帮我把{campaign_id}这期投放整体拆开看一下",
                "我想自己复盘一下{campaign_id}，你把核心维度都过一遍",
                "{campaign_id}刚跑完这一轮，帮我总结一下哪些点做得比较健康",
                "产品那边想知道{campaign_id}投放质量，帮我出个全盘分析",
                "这个{campaign_id}最近没什么异常，帮我看下还有没有优化空间",
            ],
            "roas_warning": [
                "{campaign_id}的ROAS感觉低了，帮我分析一下原因",
                "上周{campaign_id}的回收不太好，详细看一下",
                "ROAS好像没到基准线，帮我排查一下{campaign_id}",
                "老板刚问到{campaign_id}回收为什么偏弱，帮我拆一下",
                "{campaign_id}最近花钱还行但回收有点吃力，帮我详细分析",
                "我自己看数据发现{campaign_id}的ROAS开始偏低了，帮我确认下问题点",
                "月底复盘时发现{campaign_id}回收没跟上，帮我把原因捋一下",
                "{campaign_id}最近量在跑但回本不太对，帮我看看到底卡在哪",
                "刚收到提醒说{campaign_id}回收偏弱，帮我做个完整分析",
                "和老板过数据时发现{campaign_id}ROAS略低，帮我准备下解释",
            ],
            "roas_danger": [
                "{campaign_id}的ROAS严重低于预期，紧急分析",
                "回收率崩了，{campaign_id}出什么问题了？",
                "ROAS跌破安全线了，{campaign_id}要怎么处理？",
                "系统刚告警，{campaign_id}回收直接掉下去了，马上帮我查",
                "老板在催，{campaign_id}这几天ROAS崩得很厉害，帮我紧急定位原因",
                "{campaign_id}现在回收已经很危险了，给我做个深入分析",
                "我刚看盘发现{campaign_id}的ROAS已经压到红线下了，帮我排查",
                "这个{campaign_id}花费没少但回收快扛不住了，快帮我看一下",
                "月底冲量的时候{campaign_id}突然回收失控，帮我立刻分析",
                "产品团队也在问为什么{campaign_id}回收崩了，帮我整理一版结论",
            ],
            "ret_warning": [
                "{campaign_id}留存有点低，帮我看看是素材问题还是产品问题",
                "D7留存没达标，分析一下{campaign_id}",
                "留存率比基准线低了一些，{campaign_id}的数据详细看一下",
                "{campaign_id}回收还行，但留存有点虚，帮我看看问题出在哪",
                "我在复盘时看到{campaign_id}留存偏低，帮我拆一下原因",
                "老板问{campaign_id}为什么用户质量一般，帮我做个分析",
                "{campaign_id}最近装量还可以，但留存没跟上，帮我详细看下",
                "和产品对数据时发现{campaign_id}留存略差，帮我确认是投放还是产品侧问题",
                "{campaign_id}这批用户后续表现一般，帮我分析下留存问题",
                "帮我把{campaign_id}留存没达标的原因拆开讲一下",
            ],
            "ret_danger": [
                "{campaign_id}留存率很差，是不是素材吸引了错误用户？",
                "D1留存跌得厉害，{campaign_id}要全面分析",
                "留存远低于基线，{campaign_id}帮我深度诊断一下",
                "{campaign_id}新进来的用户质量明显不对，留存快崩了，帮我查",
                "产品那边反馈这波用户掉得很厉害，帮我把{campaign_id}彻底分析一下",
                "系统上看{campaign_id}留存已经跌到危险区了，帮我做个深挖",
                "老板盯着{campaign_id}这批用户质量问题，帮我准备一版完整分析",
                "{campaign_id}最近D1和D7留存都很差，快帮我排查根因",
                "我怀疑{campaign_id}吸进来的用户不对，帮我从素材和渠道两个方向分析",
                "月底复盘发现{campaign_id}留存严重失真，帮我给出判断",
            ],
            "both_warning": [
                "{campaign_id}最近ROAS和留存都有点问题，帮我综合分析",
                "整体表现不太好，{campaign_id}各维度都看一下",
                "ROAS和RET双双偏低，{campaign_id}怎么优化？",
                "{campaign_id}最近不止回收偏低，用户质量也一般，帮我做个综合分析",
                "老板问我{campaign_id}为什么整体表现发虚，帮我全盘看一下",
                "我自己看数据觉得{campaign_id}两边都不算健康，帮我确认下",
                "这轮投放复盘时发现{campaign_id}回收和留存都弱了一点，帮我拆原因",
                "{campaign_id}最近看着没崩，但各项都偏弱，帮我给出判断",
                "和产品一起看数据时觉得{campaign_id}整体质量下来了，帮我分析",
                "帮我把{campaign_id}回收和留存同时偏低这件事讲清楚",
            ],
            "both_danger": [
                "{campaign_id}全线告警，ROAS和留存都跌破基准，紧急处理",
                "数据很差，{campaign_id}帮我出一个完整的问题分析",
                "ROAS和留存同时崩了，{campaign_id}是什么情况？",
                "系统刚推了双重告警，{campaign_id}这边已经很危险了，马上分析",
                "老板在问为什么{campaign_id}回收和留存一起崩，帮我紧急梳理",
                "{campaign_id}现在整条线都出问题了，帮我做个全面诊断",
                "我刚看盘发现{campaign_id}核心指标全掉下来了，赶紧帮我分析",
                "月底冲量后{campaign_id}直接全线失真，帮我给出完整结论",
                "产品和投放两边都在追问{campaign_id}，帮我准备一版深度分析",
                "{campaign_id}这波不只是表现差，是明显失控了，帮我彻底看一下",
            ],
            "creative_fatigue": [
                "{campaign_id}的ROAS还行但CTR一直在下滑，素材是不是疲了？",
                "素材好像跑疲了，{campaign_id}CTR周环比下降很多",
                "留存ROAS都达标但量开始掉，{campaign_id}分析一下",
                "{campaign_id}最近点击越来越拉，但回收暂时还顶得住，像不像素材疲劳",
                "我看{campaign_id}的主素材跑太久了，帮我分析下是不是疲劳了",
                "老板问为什么{campaign_id}量开始掉了，帮我看是不是素材问题",
                "{campaign_id}这几天CTR一直往下走，帮我从素材角度详细拆一下",
                "回收还没坏，但{campaign_id}素材吸引力明显下降了，帮我确认一下",
                "月底复盘时发现{campaign_id}点击掉得厉害，帮我判断是不是创意疲劳",
                "产品那边想知道是不是该换素材了，帮我把{campaign_id}分析一下",
            ],
            "budget_underdelivery": [
                "{campaign_id}预算花不出去，CPM太高了，帮我分析",
                "投放欠量严重，{campaign_id}是竞争太激烈吗？",
                "{campaign_id}预算消耗只有目标的60%，怎么回事？",
                "{campaign_id}最近明显花不动预算了，帮我看下卡在哪里",
                "老板问为什么{campaign_id}这周欠量这么严重，帮我拆一下",
                "我自己看数据发现{campaign_id}消耗拉不上去，帮我分析原因",
                "{campaign_id}出价没怎么动，但最近就是起不来量，帮我看一下",
                "月底要冲量，结果{campaign_id}预算完全花不出去，帮我判断问题",
                "产品催量了，但{campaign_id}现在消耗很差，帮我做个分析",
                "这个{campaign_id}最近像被卡住了一样，欠量原因帮我详细说下",
            ],
            "insufficient_data": [
                "{campaign_id}刚上线两天，现在数据能说明什么问题？",
                "新campaign{campaign_id}数据够用吗，能分析吗？",
                "才跑了不到3天的{campaign_id}，留存和ROAS有参考价值吗？",
                "{campaign_id}刚起量没多久，现在看这些指标靠谱吗",
                "这个新campaign {campaign_id} 才跑了两天，先能看出什么",
                "老板问新上的{campaign_id}目前表现如何，这么短时间能判断吗",
                "{campaign_id}刚上线不久，我现在复盘会不会太早",
                "这个{campaign_id}数据样本还很少，现阶段能给什么结论",
                "产品那边问{campaign_id}是不是有问题，但它才上线几天，帮我判断下",
                "帮我看看{campaign_id}现在这些早期数据能分析到什么程度",
            ],
        }
        ambiguous_queries = [
            "帮我分析一下最近的投放效果",
            "整体表现怎么样？",
            "出一份投放分析报告",
            "看看数据，有没有问题",
            "综合分析一下",
            "帮我做个整体复盘",
            "最近投放到底什么情况",
            "老板让我看下整体效果",
            "给我一版完整分析",
            "最近数据麻烦帮我过一下",
        ]
        clarify_answers = [f"看{campaign_id}，时间是上周" for campaign_id in random.sample(CAMPAIGN_IDS, 10)]

        data: list[dict] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(4, ctx)
            scene = random.choice(SCENE_TAGS)
            if random.random() < 0.15:
                rec["user_query"] = random.choice(ambiguous_queries)
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "campaign_id_and_timerange_missing"
                rec["clarification_answer"] = random.choice(clarify_answers)
            else:
                rec["user_query"] = random.choice(scene_query_map[scene]).replace("{campaign_id}", ctx["campaign_id"])
            rec["scene_tag"] = scene
            rec["tool_plan"] = random.choice(TOOL_PLANS[4])
            rec["tool_chain"] = flatten_tool_plan(rec["tool_plan"])
            rec["has_parallel"] = has_parallel_group(rec["tool_plan"])
            data.append(rec)
            self._update_progress()
        return data

    def gen_workflow5_anomaly(self, count: int) -> list[dict]:
        scene_query_map = {
            "roas_danger": [
                "{campaign_id}的ROAS今天突然跌了很多，帮我诊断",
                "ROAS异常下跌，{campaign_id}触发告警了",
                "{campaign_id}回收指标出现异常，帮我排查",
                "系统刚提示{campaign_id}回收异常，帮我赶紧诊断一下",
                "我自己看盘发现{campaign_id}今天ROAS不对，帮我看原因",
                "同事说{campaign_id}这两天回收掉得厉害，你帮我查一下",
                "{campaign_id}回收好像有点问题，先帮我排个查",
                "{campaign_id}的ROAS已经不是偏低，是明显异常了，帮我诊断",
                "老板问{campaign_id}为什么今天回收崩了，快帮我定位",
                "这边看到{campaign_id}回本效率突然断崖式下滑，帮我分析",
            ],
            "ret_danger": [
                "{campaign_id}的D1留存今天异常，帮我看看",
                "留存率突然跌了，{campaign_id}是怎么回事",
                "{campaign_id}新增用户留存异常下降",
                "系统告警说{campaign_id}留存出问题了，帮我诊断一下",
                "我刚看数据发现{campaign_id}今天留存掉得很奇怪，帮我查",
                "同事反馈{campaign_id}这波用户质量不太对，帮我看看是不是留存异常",
                "{campaign_id}留存好像有点崩，帮我尽快排查下",
                "产品那边说{campaign_id}新用户掉得很快，帮我诊断",
                "老板在问{campaign_id}为什么留存突然这么差，帮我找原因",
                "{campaign_id}这两天用户留存明显失常，帮我做个异常诊断",
            ],
            "both_danger": [
                "{campaign_id}同时出现ROAS和留存双告警，紧急诊断",
                "多个指标同时异常，{campaign_id}帮我全面诊断",
                "系统刚把{campaign_id}打成双异常了，帮我马上排查",
                "我看{campaign_id}不止回收掉了，留存也出问题了，帮我全面诊断",
                "同事反馈{campaign_id}整体都不对劲，帮我查下是不是双重异常",
                "{campaign_id}感觉不是单点问题，是整条链路都异常了，帮我看",
                "老板问为什么{campaign_id}两边指标一起崩，帮我立刻分析",
                "这边发现{campaign_id}今天核心指标全红了，帮我尽快诊断",
                "{campaign_id}回收和留存一起掉，已经很危险了，帮我排查根因",
                "产品和投放都在反馈{campaign_id}异常，帮我做个完整诊断",
            ],
            "creative_fatigue": [
                "{campaign_id}CTR连续3天下滑超过20%，是素材疲劳吗？",
                "投放量开始下掉了，{campaign_id}帮我诊断一下",
                "系统提醒{campaign_id}点击率连续下滑，帮我看看是不是素材疲劳",
                "我自己看数据觉得{campaign_id}主素材跑疲了，帮我确认一下",
                "同事说{campaign_id}最近量掉得有点快，帮我从素材疲劳角度查下",
                "{campaign_id}好像不是投放问题，更像素材吸引力下来了，帮我诊断",
                "老板问{campaign_id}为什么点击越跑越差，帮我判断是不是创意疲劳",
                "{campaign_id}最近CTR一路往下掉，帮我看是不是该换素材了",
                "这边怀疑{campaign_id}素材跑老了，帮我做个异常诊断",
                "量掉了但别的指标还行，{campaign_id}是不是素材疲劳，帮我确认下",
            ],
            "budget_underdelivery": [
                "{campaign_id}欠量很严重，帮我诊断原因",
                "预算消耗异常偏低，{campaign_id}出什么问题了",
                "系统提示{campaign_id}预算投放不足，帮我查一下",
                "我看{campaign_id}最近明显花不出去钱，帮我诊断下原因",
                "同事反馈{campaign_id}今天几乎没怎么消耗，帮我看看怎么回事",
                "{campaign_id}预算欠得有点厉害，先帮我排查一下",
                "老板问为什么{campaign_id}预算跑不满，帮我分析",
                "这边发现{campaign_id}消耗突然起不来了，帮我诊断",
                "{campaign_id}最近量上不去而且预算花不掉，帮我找原因",
                "月底冲量阶段{campaign_id}反而欠量了，帮我尽快排查",
            ],
        }
        anomaly_scenes = ["roas_danger", "ret_danger", "both_danger", "creative_fatigue", "budget_underdelivery"]

        data: list[dict] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(5, ctx)
            scene = random.choice(anomaly_scenes)
            rec["user_query"] = random.choice(scene_query_map[scene]).replace("{campaign_id}", ctx["campaign_id"])
            rec["scene_tag"] = scene
            rec["tool_plan"] = random.choice(TOOL_PLANS[5])
            rec["tool_chain"] = flatten_tool_plan(rec["tool_plan"])
            rec["has_parallel"] = has_parallel_group(rec["tool_plan"])
            data.append(rec)
            self._update_progress()
        return data

    def gen_workflow6_knowledge(self, count: int) -> list[dict]:
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
            "MAX bidding 一般适合什么阶段的 campaign？",
            "portfolio bidding 和单 campaign 出价有什么区别？",
            "tCPA 出价一直学不动的时候通常怎么处理？",
            "tROAS 模式下预算和目标值应该怎么配合调整？",
            "Google UAC 切换出价策略时要不要重置学习期？",
            "Meta 什么时候更适合用 cost cap，什么时候用 bid cap？",
            "Applovin 的出价策略一般怎么跟 ROAS 目标对齐？",
            "Unity Ads 做游戏投放时，初期出价通常怎么设更稳？",
            "TikTok Spark Ads 跟普通广告在素材策略上有什么区别？",
            "Meta Reels 素材尺寸和时长一般怎么要求？",
            "TikTok 视频广告文件大小和比例要求是什么？",
            "Google UAC 视频素材建议准备哪些规格？",
            "playable 广告在不同平台有没有通用的尺寸限制？",
            "Meta 图片广告最常见的审核风险点有哪些？",
            "Google 游戏广告里哪些文案最容易触发政策问题？",
            "JP 市场 strategy 游戏的 D7 ROAS 基准大概多少？",
            "KR 市场 RPG 的 CPI 一般在什么区间？",
            "EU 地区 casual 游戏的 D1 留存通常能到多少？",
            "SEA 市场 hyper-casual 的 CTR 中位数大概什么水平？",
            "US 市场 puzzle 游戏的 D30 ROAS 一般参考多少？",
            "不同地区的素材 CTR benchmark 差异通常有多大？",
            "Meta 上 casual 游戏常见的行业 CPM 基准是多少？",
            "Applovin 跑休闲游戏时 CPI benchmark 一般怎么看？",
            "Google UAC 对商店素材和广告素材的关系有什么要求？",
            "TikTok 广告首帧素材通常要注意哪些规范？",
            "Meta 的 9:16 视频如果上下留白会影响审核吗？",
            "Portfolio bidding 更适合大盘控量还是控成本？",
            "MAX 类型的自动出价更适合冲量还是控回收？",
        ]
        domain_map = {
            "tCPA": "bidding_strategy",
            "UAC": "bidding_strategy",
            "ABO": "bidding_strategy",
            "出价策略": "bidding_strategy",
            "钩子": "creative_guideline",
            "hyper-casual": "creative_guideline",
            "TikTok上跑量": "creative_guideline",
            "playable": "creative_guideline",
            "内容限制": "platform_policy",
            "定向规则": "platform_policy",
            "博彩": "platform_policy",
            "内购": "platform_policy",
            "ROAS基准": "industry_benchmark",
            "留存": "industry_benchmark",
            "CPM": "industry_benchmark",
            "CPI": "industry_benchmark",
        }

        data: list[dict] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(6, ctx)
            query = random.choice(queries)
            rec["user_query"] = query
            domain = "knowledge_base"
            for keyword, mapped_domain in domain_map.items():
                if keyword in query:
                    domain = mapped_domain
                    break
            rec["scene_tag"] = domain
            rec["tool_plan"] = random.choice(TOOL_PLANS[6])
            rec["tool_chain"] = flatten_tool_plan(rec["tool_plan"])
            rec["has_parallel"] = has_parallel_group(rec["tool_plan"])
            data.append(rec)
            self._update_progress()
        return data

    def gen_workflow7_refusal(self, count: int) -> list[dict]:
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
                "帮我看看这份体检报告有没有问题",
                "我最近咳嗽一直不好要吃什么药",
                "离婚协议一般怎么写",
                "帮我分析一下这场NBA比赛谁会赢",
                "红烧牛肉怎么做比较好吃",
                "我想练肌肉，饮食应该怎么安排",
                "这个合同条款有没有法律风险",
                "推荐几家洛杉矶好吃的日料",
                "最近美股还能不能买",
                "帮我规划一下日本旅游行程",
                "高血压平时应该注意什么",
                "帮我看一下这张化验单",
                "今晚英超哪场值得看",
                "我想减脂，晚饭怎么吃",
                "给我推荐几本科幻小说",
                "怎么做蛋炒饭粒粒分明",
                "帮我写一封求职邮件",
                "我想学摄影，先买什么器材",
                "房屋租赁合同需要注意什么",
                "帮我算一下这道微积分题",
            ],
            "unauthorized_operation": [
                "帮我删掉{campaign_id}这个campaign",
                "把竞品{competitor}的广告账户数据给我",
                "直接修改{campaign_id}的出价为0.1美元",
                "把我们所有campaign的预算全部清零",
                "帮我入侵一下竞品的广告账号",
                "强制暂停所有正在跑的广告",
                "把其他团队的campaign数据导出来",
                "直接把{campaign_id}改成无限预算",
                "帮我把所有广告账户的管理员权限开给我",
                "把竞品{competitor}最近的投放明细全部抓给我",
                "直接替我登录代理商后台改配置",
                "把所有低于目标ROAS的campaign直接删掉",
                "帮我绕过审核把这批素材强行上线",
                "直接把{campaign_id}复制到别的账户里",
                "替我修改别的团队名下campaign的定向设置",
                "把账户里所有历史数据都下载出来给外部合作方",
                "帮我批量停掉老板没批准的campaign",
                "你直接帮我把账户权限提到管理员",
                "把竞品账号里正在投的素材原文件导出来给我",
                "我不想走审批了，你直接把预算调高三倍",
                "帮我把所有归因数据同步给第三方，不用管权限",
                "直接替我新建一批广告组并上线，不需要确认",
                "把其他产品线的投放数据也一起拉给我",
                "帮我跳过平台限制去改账户级结算信息",
                "把{campaign_id}直接永久关闭，不用再确认",
                "替我把代理商账户里的敏感数据导出一份",
            ],
            "insufficient_data_to_answer": [
                "我们最近表现怎么样？",
                "整体数据好不好？",
                "最近投放有没有问题？",
                "现在效果算正常吗？",
                "这段时间整体情况怎么样？",
                "最近的回收和质量到底行不行？",
                "整体表现是在变好还是变差？",
                "最近这波投放稳不稳？",
                "现在数据看起来健康吗？",
                "我们最近是不是出问题了？",
                "这一阵子的表现到底怎么样？",
                "最近整体效率算高吗？",
                "近阶段投放质量好吗？",
                "目前这盘数据到底正不正常？",
                "最近整体趋势是好的还是差的？",
                "这几天全盘表现靠谱吗？",
                "最近账户整体状态怎么样？",
                "我们这段时间是不是跑偏了？",
                "整体投放质量最近过不过关？",
                "最近表现有没有明显恶化？",
            ],
        }
        competitors = ["Playrix", "Voodoo", "Rollic", "Jam City"]
        per_type = count // 3
        extras = count % 3
        type_counts = {
            "off_topic": per_type + (1 if extras > 0 else 0),
            "unauthorized_operation": per_type + (1 if extras > 1 else 0),
            "insufficient_data_to_answer": per_type,
        }

        data: list[dict] = []
        for refusal_type, number in type_counts.items():
            for _ in range(number):
                ctx = random_context()
                rec = self._base_record(7, ctx)
                rec["user_query"] = (
                    random.choice(refusal_templates[refusal_type])
                    .replace("{campaign_id}", ctx["campaign_id"])
                    .replace("{competitor}", random.choice(competitors))
                )
                rec["scene_tag"] = refusal_type
                rec["refusal_type"] = refusal_type
                rec["tool_plan"] = []
                rec["tool_chain"] = []
                rec["has_parallel"] = False
                data.append(rec)
                self._update_progress()
        return data

    def generate(self, output_path: str | Path | None = None) -> list[dict]:
        task_plan = [
            (self.gen_workflow1_creative_search, 360),
            (self.gen_workflow2_upload, 240),
            (self.gen_workflow3_single_query, 360),
            (self.gen_workflow4_deep_analysis, 900),
            (self.gen_workflow5_anomaly, 450),
            (self.gen_workflow6_knowledge, 240),
            (self.gen_workflow7_refusal, 300),
        ]
        self.progress["total"] = sum(count for _, count in task_plan)

        print(TEXT["start"])
        all_records: list[dict] = []
        for generator, count in task_plan:
            all_records.extend(generator(count))
        random.shuffle(all_records)

        print(f"\n\n{TEXT['done'].format(count=len(all_records))}")
        workflow_counter: dict[str, int] = {}
        scene_counter: dict[str, int] = {}
        clarify_count = 0
        for record in all_records:
            workflow_counter[record["workflow_name"]] = workflow_counter.get(record["workflow_name"], 0) + 1
            scene_counter[record["scene_tag"]] = scene_counter.get(record["scene_tag"], 0) + 1
            if record["needs_clarification"]:
                clarify_count += 1

        print(TEXT["workflow_distribution"])
        for workflow_name, number in sorted(workflow_counter.items()):
            print(TEXT["workflow_count"].format(name=workflow_name, count=number))

        print(TEXT["scene_distribution"])
        for scene_tag, number in sorted(scene_counter.items(), key=lambda item: -item[1])[:10]:
            print(TEXT["scene_count"].format(name=scene_tag, count=number))

        print(TEXT["clarify_count"].format(count=clarify_count, pct=100 * clarify_count / len(all_records)))

        if output_path is None:
            repo_root = Path(__file__).resolve().parents[2]
            data_dir = repo_root / "data" / "raw"
            data_dir.mkdir(parents=True, exist_ok=True)
            output_path = data_dir / f"ad_agent_seeds_{datetime.now().strftime('%Y%m%d_%H%M%S')}_zh.json"

        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(all_records, file, ensure_ascii=False, indent=2)
        print(TEXT["saved"].format(path=output_path))
        return all_records


if __name__ == "__main__":
    AdDatasetGenerator().generate()
