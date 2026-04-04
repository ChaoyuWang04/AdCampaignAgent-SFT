"""
Ad Campaign Agent - Seed Data Generator
生成用于 SFT 训练的种子数据，仅保留中文数据生产。
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.datapipeline.workflow_loader import load_all_workflow_configs


PLATFORMS = ["Google", "Meta", "Tiktok", "Applovin", "Unity"]
GAME_GENRES = ["casual", "puzzle", "hyper_casual", "strategy", "rpg"]
REGIONS = ["US", "JP", "SEA", "KR", "EU"]

ROAS_BASELINES = {
    "Google": {"casual": (0.80, 1.20), "puzzle": (0.85, 1.30), "hyper_casual": (0.60, 0.90), "strategy": (0.90, 1.40), "rpg": (0.95, 1.50)},
    "Meta": {"casual": (0.75, 1.10), "puzzle": (0.80, 1.20), "hyper_casual": (0.55, 0.85), "strategy": (0.85, 1.30), "rpg": (0.90, 1.40)},
    "Tiktok": {"casual": (0.72, 1.00), "puzzle": (0.75, 1.10), "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Applovin": {"casual": (0.68, 1.00), "puzzle": (0.73, 1.10), "hyper_casual": (0.50, 0.80), "strategy": (0.80, 1.20), "rpg": (0.85, 1.30)},
    "Unity": {"casual": (0.58, 1.00), "puzzle": (0.53, 1.10), "hyper_casual": (0.52, 0.80), "strategy": (0.87, 1.20), "rpg": (0.83, 1.30)},
}

RET_BASELINES = {
    "casual": {"d1": 0.35, "d7": 0.12},
    "puzzle": {"d1": 0.38, "d7": 0.14},
    "hyper_casual": {"d1": 0.40, "d7": 0.15},
    "strategy": {"d1": 0.30, "d7": 0.10},
    "rpg": {"d1": 0.28, "d7": 0.09},
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
METRIC_QUERY_SCENES = [
    "query_roas",
    "query_retention",
    "query_ctr",
    "query_spend",
    "query_installs",
    "query_cpm",
]
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


def load_workflow_definitions() -> dict[int, dict[str, Any]]:
    return load_all_workflow_configs()


def _make_campaign_ids(n: int = 60) -> list[str]:
    return [f"CMP_{random.randint(1000, 9999)}" for _ in range(n)]


def _make_app_ids() -> list[str]:
    prefixes = ["com.guru", "com.funplay", "com.gamestar", "io.mobilegame"]
    genres = ["puzzle", "casual", "match3", "runner", "merge"]
    return [f"{prefix}.{genre}{random.randint(1, 9):02d}" for prefix in prefixes for genre in genres]


CAMPAIGN_IDS = _make_campaign_ids(500)
APP_IDS = _make_app_ids()


def random_date_range(window_days: int = 7, offset_max: int = 14) -> dict[str, str]:
    end = datetime(2026, 3, 1) - timedelta(days=random.randint(0, offset_max))
    start = end - timedelta(days=window_days)
    return {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}


def random_context() -> dict[str, Any]:
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


def flatten_tool_plan(tool_plan: list[dict[str, Any]]) -> list[str]:
    flattened: list[str] = []
    for group in tool_plan:
        flattened.extend(group.get("tools", []))
    return flattened


def has_parallel_group(tool_plan: list[dict[str, Any]]) -> bool:
    return any(group.get("mode") == "parallel" and len(group.get("tools", [])) > 1 for group in tool_plan)


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
    return "query_roas"


def pick_bucket_by_query_count(intent_buckets: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    names = list(intent_buckets.keys())
    weights = [max(1, len(intent_buckets[name].get("queries", []))) for name in names]
    picked = random.choices(names, weights=weights, k=1)[0]
    return picked, intent_buckets[picked]


def parse_metric_hints(query: str) -> list[str]:
    lowered = query.lower()
    hints: list[str] = []
    if "roas" in lowered or "回收" in query:
        hints.append("roas")
    if "留存" in query or "retention" in lowered:
        hints.append("retention_d1")
    if "ctr" in lowered or "点击" in query:
        hints.append("ctr")
    if "cpi" in lowered:
        hints.append("cpi")
    if "cpm" in lowered:
        hints.append("cpm")
    if "花费" in query or "预算" in query or "消耗" in query or "spend" in lowered:
        hints.append("spend")
    if "安装" in query or "installs" in lowered:
        hints.append("installs")
    return hints or ["roas"]


def has_platform_token(query: str) -> bool:
    return any(token in query for token in ["Google", "Meta", "TikTok", "Tiktok", "Applovin", "Unity", "UAC", "Facebook"])


def has_genre_token(query: str) -> bool:
    lowered = query.lower()
    return any(token in lowered for token in ["casual", "puzzle", "hyper-casual", "hyper_casual", "strategy", "rpg"]) or "休闲" in query


def has_region_token(query: str) -> bool:
    return any(token in query for token in REGIONS)


def has_campaign_token(query: str) -> bool:
    return "CMP_" in query


def has_app_token(query: str) -> bool:
    return "." in query and any(token in query for token in ["com.", "io."])


def has_date_range_token(query: str) -> bool:
    return any(
        token in query
        for token in [
            "最近",
            "近期",
            "上周",
            "这周",
            "本周",
            "上个月",
            "这个月",
            "近一周",
            "近7天",
            "近30天",
            "最近7天",
            "最近30天",
            "最近三天",
            "最近几天",
            "昨天",
            "今天",
            "这几天",
            "这段时间",
            "月底",
            "月初",
            "两天",
            "三天",
            "不到3天",
            "几天",
            "这期",
            "这一轮",
        ]
    )


SLOT_CHECKERS = {
    "platform": has_platform_token,
    "genre": has_genre_token,
    "region": has_region_token,
    "campaign_id": has_campaign_token,
    "app_id": has_app_token,
    "date_range": has_date_range_token,
}


def missing_required_slots(query: str, required_slots: list[str]) -> list[str]:
    missing: list[str] = []
    for slot in required_slots:
        checker = SLOT_CHECKERS.get(slot)
        if checker is None:
            continue
        if not checker(query):
            missing.append(slot)
    return missing


class AdDatasetGenerator:
    def __init__(self):
        self.progress = {"completed": 0, "total": 0}
        self.workflow_defs = load_workflow_definitions()

    def _workflow(self, workflow_id: int) -> dict[str, Any]:
        return self.workflow_defs[workflow_id]

    def _format(self, template: str, ctx: dict[str, Any], **extra: Any) -> str:
        values = {
            "platform": ctx["platform"],
            "genre": ctx["game_genre"],
            "region": ctx["region"],
            "campaign_id": ctx["campaign_id"],
            "app_id": ctx["app_id"],
            **extra,
        }
        return template.format(**values)

    def _bucket_required_slots(self, workflow_id: int, bucket_name: str, bucket: dict[str, Any] | None = None) -> list[str]:
        if bucket and "required_slots" in bucket:
            return list(bucket["required_slots"])
        return list(self._workflow(workflow_id).get("required_slots", {}).get(bucket_name, []))

    def _clarify_answer(self, cfg: dict[str, Any], reason: str, ctx: dict[str, Any]) -> str:
        if cfg.get("workflow_id") == 4 and reason in {"timerange_missing", "campaign_id_and_timerange_missing"}:
            date_range = ctx.get("date_range", {})
            start = date_range.get("start", "")
            end = date_range.get("end", "")
            time_text = f"{start}到{end}" if start and end else "最近7天"
            if reason == "timerange_missing":
                return f"时间是{time_text}"
            return f"看{ctx['campaign_id']}，时间是{time_text}"
        templates = cfg.get("clarification", {}).get("answer_templates", {})
        if isinstance(templates, dict):
            template = templates.get(reason)
            if template:
                return self._format(template, ctx)
        if isinstance(templates, list) and templates:
            return self._format(templates[0], ctx)
        return ""

    def _update_progress(self) -> None:
        self.progress["completed"] += 1
        completed = self.progress["completed"]
        total = self.progress["total"]
        if total <= 0:
            return
        print(f"\r{TEXT['progress']}: {completed}/{total} ({100 * completed / total:.1f}%)", end="", flush=True)

    def _base_record(self, workflow: int, ctx: dict[str, Any]) -> dict[str, Any]:
        return {
            "workflow": workflow,
            "workflow_name": self._workflow(workflow)["workflow_name"],
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
            "intent_bucket": None,
            "query_slots": {},
        }

    def _finalize_record(self, rec: dict[str, Any], tool_plan: list[dict[str, Any]]) -> dict[str, Any]:
        rec["tool_plan"] = tool_plan
        rec["tool_chain"] = flatten_tool_plan(tool_plan)
        rec["has_parallel"] = has_parallel_group(tool_plan)
        return rec

    def gen_workflow1_creative_search(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(1)
        competitors = cfg["variables"]["competitors"]
        intent_buckets = cfg["intent_buckets"]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(1, ctx)
            if random.random() < cfg["clarify_probability"]:
                rec["user_query"] = random.choice(cfg["clarify_queries"])
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "platform_or_genre_missing"
                rec["clarification_answer"] = self._clarify_answer(cfg, "platform_or_genre_missing", ctx)
                rec["intent_bucket"] = "clarify"
                rec["scene_tag"] = "creative_search_clarify"
                tool_plan = []
            else:
                bucket_name, bucket = pick_bucket_by_query_count(intent_buckets)
                competitor = random.choice(competitors)
                rec["intent_bucket"] = bucket_name
                rec["scene_tag"] = bucket["scene_tag"]
                rec["user_query"] = self._format(
                    random.choice(bucket["queries"]),
                    ctx,
                    competitor=competitor,
                )
                if bucket_name == "competitor_ads":
                    rec["query_slots"]["competitor_name"] = competitor
                missing_slots = missing_required_slots(rec["user_query"], self._bucket_required_slots(1, bucket_name, bucket))
                if missing_slots:
                    rec["needs_clarification"] = True
                    reason = bucket["clarification_reason"]
                    rec["clarification_reason"] = reason
                    rec["clarification_answer"] = self._clarify_answer(cfg, reason, ctx)
                    tool_plan = []
                else:
                    tool_plan = bucket["tool_plan"]
            data.append(self._finalize_record(rec, tool_plan))
            self._update_progress()
        return data

    def gen_workflow2_upload(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(2)
        intent_buckets = cfg["intent_buckets"]
        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(2, ctx)
            is_fail = random.random() < cfg["fail_probability"]
            if is_fail:
                bucket_name = "validate_only_retry"
                bucket = intent_buckets[bucket_name]
                rec["user_query"] = self._format(random.choice(bucket["queries"]), ctx)
                rec["scene_tag"] = random.choice(bucket["scene_tags"])
                rec["intent_bucket"] = bucket_name
                tool_plan = bucket["tool_plan"]
            else:
                success_buckets = {name: bucket for name, bucket in intent_buckets.items() if name != "validate_only_retry"}
                bucket_name, bucket = pick_bucket_by_query_count(success_buckets)
                rec["user_query"] = self._format(random.choice(bucket["queries"]), ctx)
                rec["scene_tag"] = random.choice(bucket["scene_tags"])
                rec["intent_bucket"] = bucket_name
                missing_slots = missing_required_slots(rec["user_query"], self._bucket_required_slots(2, rec["intent_bucket"], bucket))
                if missing_slots:
                    rec["needs_clarification"] = True
                    reason = bucket["clarification_reason"]
                    rec["clarification_reason"] = reason
                    rec["clarification_answer"] = self._clarify_answer(cfg, reason, ctx)
                    tool_plan = []
                else:
                    tool_plan = bucket["tool_plan"]
            data.append(self._finalize_record(rec, tool_plan))
            self._update_progress()
        return data

    def gen_workflow3_single_query(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(3)
        intent_buckets = cfg["intent_buckets"]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(3, ctx)
            if random.random() < cfg["clarify_probability"]:
                rec["user_query"] = random.choice(cfg["clarify_queries"])
                rec["needs_clarification"] = True
                rec["clarification_reason"] = "campaign_id_missing"
                rec["clarification_answer"] = self._clarify_answer(cfg, "campaign_id_missing", ctx)
                rec["intent_bucket"] = "clarify_missing_campaign"
                rec["scene_tag"] = "clarify_missing_campaign"
                tool_plan = []
            else:
                bucket_name, bucket = pick_bucket_by_query_count(intent_buckets)
                rec["intent_bucket"] = bucket_name
                rec["user_query"] = self._format(random.choice(bucket["queries"]), ctx)
                missing_slots = missing_required_slots(rec["user_query"], self._bucket_required_slots(3, bucket_name, bucket))
                if bucket_name in {"campaign_metrics", "creative_metrics"}:
                    rec["query_slots"]["metrics"] = parse_metric_hints(rec["user_query"])
                if missing_slots:
                    rec["needs_clarification"] = True
                    reason = bucket["clarification_reason"]
                    rec["clarification_reason"] = reason
                    rec["clarification_answer"] = self._clarify_answer(cfg, reason, ctx)
                    rec["scene_tag"] = "clarify_missing_campaign"
                    tool_plan = []
                elif bucket_name == "campaign_metrics":
                    rec["scene_tag"] = infer_metric_scene(rec["user_query"])
                    tool_plan = bucket["tool_plan"]
                elif bucket_name == "creative_metrics":
                    rec["scene_tag"] = "creative_metrics"
                    tool_plan = bucket["tool_plan"]
                else:
                    rec["scene_tag"] = "appsflyer_report"
                    rec["query_slots"]["metrics"] = parse_metric_hints(rec["user_query"])
                    tool_plan = bucket["tool_plan"]
            data.append(self._finalize_record(rec, tool_plan))
            self._update_progress()
        return data

    def gen_workflow4_deep_analysis(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(4)
        scene_tool_plan_map = cfg["scene_tool_plan_map"]
        scene_intent_map = cfg["scene_intent_map"]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(4, ctx)
            scene = random.choice(cfg["scene_tags"])
            if random.random() < cfg["clarify_probability"]:
                rec["user_query"] = random.choice(cfg["queries"]["ambiguous"])
                rec["needs_clarification"] = True
                reason = cfg["clarification"]["reasons"]["campaign_id_and_timerange_missing"]
                rec["clarification_reason"] = reason
                rec["clarification_answer"] = self._clarify_answer(cfg, reason, ctx)
                rec["intent_bucket"] = "clarify_missing_scope"
                rec["scene_tag"] = "clarify_missing_scope"
                tool_plan = []
            else:
                rec["user_query"] = self._format(random.choice(cfg["scene_query_map"][scene]), ctx)
                rec["intent_bucket"] = scene_intent_map[scene]
                missing_slots = missing_required_slots(rec["user_query"], self._bucket_required_slots(4, rec["intent_bucket"]))
                if missing_slots:
                    rec["needs_clarification"] = True
                    if "campaign_id" in missing_slots:
                        reason = cfg["clarification"]["reasons"]["campaign_id_and_timerange_missing"]
                    else:
                        reason = cfg["clarification"]["reasons"]["timerange_missing"]
                    rec["clarification_reason"] = reason
                    rec["clarification_answer"] = self._clarify_answer(cfg, reason, ctx)
                    tool_plan = []
                else:
                    tool_plan = scene_tool_plan_map[scene]
                rec["scene_tag"] = scene
            if rec["scene_tag"] is None:
                rec["scene_tag"] = scene
            rec["query_slots"]["benchmark_metric"] = (
                "roas"
                if scene in {"healthy", "roas_warning", "roas_danger", "insufficient_data"}
                else "retention_d1"
                if scene in {"ret_warning", "ret_danger", "both_warning", "both_danger"}
                else "ctr"
                if scene == "creative_fatigue"
                else "cpm"
            )
            data.append(self._finalize_record(rec, tool_plan))
            self._update_progress()
        return data

    def gen_workflow5_anomaly(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(5)
        scene_tool_plan_map = cfg["scene_tool_plan_map"]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(5, ctx)
            scene = random.choice(cfg["scene_tags"])
            rec["user_query"] = self._format(random.choice(cfg["scene_query_map"][scene]), ctx)
            rec["scene_tag"] = scene
            rec["intent_bucket"] = scene
            missing_slots = missing_required_slots(rec["user_query"], self._bucket_required_slots(5, scene))
            if missing_slots:
                rec["needs_clarification"] = True
                reason = "campaign_id_missing"
                rec["clarification_reason"] = reason
                rec["clarification_answer"] = self._clarify_answer(cfg, reason, ctx)
                tool_plan = []
            else:
                tool_plan = scene_tool_plan_map[scene]
            data.append(self._finalize_record(rec, tool_plan))
            self._update_progress()
        return data

    def gen_workflow6_knowledge(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(6)
        intent_buckets = cfg["intent_buckets"]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(6, ctx)
            bucket_name, bucket = pick_bucket_by_query_count(intent_buckets)
            rec["intent_bucket"] = bucket_name
            rec["user_query"] = random.choice(bucket["queries"])
            rec["scene_tag"] = bucket_name
            missing_slots = missing_required_slots(rec["user_query"], self._bucket_required_slots(6, bucket_name, bucket))
            if missing_slots:
                rec["needs_clarification"] = True
                reason = bucket["clarification_reason"]
                rec["clarification_reason"] = reason
                rec["clarification_answer"] = self._clarify_answer(cfg, reason, ctx)
                tool_plan = []
            else:
                tool_plan = bucket["tool_plan"]
            data.append(self._finalize_record(rec, tool_plan))
            self._update_progress()
        return data

    def gen_workflow7_refusal(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(7)
        competitors = cfg["variables"]["competitors"]
        refusal_types = ["off_topic", "unauthorized_internal", "unauthorized_external"]
        per_type = count // len(refusal_types)
        extras = count % len(refusal_types)
        type_counts = {
            refusal_type: per_type + (1 if index < extras else 0)
            for index, refusal_type in enumerate(refusal_types)
        }

        data: list[dict[str, Any]] = []
        for refusal_type, number in type_counts.items():
            for _ in range(number):
                ctx = random_context()
                rec = self._base_record(7, ctx)
                rec["user_query"] = self._format(
                    random.choice(cfg["refusal_templates"][refusal_type]),
                    ctx,
                    competitor=random.choice(competitors),
                )
                rec["scene_tag"] = refusal_type
                rec["refusal_type"] = refusal_type
                rec["intent_bucket"] = refusal_type
                data.append(self._finalize_record(rec, []))
                self._update_progress()
        return data

    def generate(self, output_path: str | Path | None = None) -> list[dict[str, Any]]:
        task_plan = [
            (self.gen_workflow1_creative_search, self._workflow(1)["count"]),
            (self.gen_workflow2_upload, self._workflow(2)["count"]),
            (self.gen_workflow3_single_query, self._workflow(3)["count"]),
            (self.gen_workflow4_deep_analysis, self._workflow(4)["count"]),
            (self.gen_workflow5_anomaly, self._workflow(5)["count"]),
            (self.gen_workflow6_knowledge, self._workflow(6)["count"]),
            (self.gen_workflow7_refusal, self._workflow(7)["count"]),
        ]
        self.progress["total"] = sum(count for _, count in task_plan)

        print(TEXT["start"])
        all_records: list[dict[str, Any]] = []
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
