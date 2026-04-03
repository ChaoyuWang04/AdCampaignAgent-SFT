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
    return random.choice(METRIC_QUERY_SCENES)


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

    def _pick_tool_plan(self, workflow_id: int) -> list[dict[str, Any]]:
        return random.choice(self._workflow(workflow_id)["tool_plans"])

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
        }

    def _finalize_record(self, rec: dict[str, Any], tool_plan: list[dict[str, Any]]) -> dict[str, Any]:
        rec["tool_plan"] = tool_plan
        rec["tool_chain"] = flatten_tool_plan(tool_plan)
        rec["has_parallel"] = has_parallel_group(tool_plan)
        return rec

    def gen_workflow1_creative_search(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(1)
        competitors = cfg["variables"]["competitors"]
        clarify_template = cfg["clarification"]["answer_templates"][0]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(1, ctx)
            if random.random() < cfg["clarify_probability"]:
                rec["user_query"] = random.choice(cfg["queries"]["ambiguous"])
                rec["needs_clarification"] = True
                rec["clarification_reason"] = cfg["clarification"]["reason"]
                rec["clarification_answer"] = self._format(clarify_template, ctx)
            else:
                rec["user_query"] = self._format(random.choice(cfg["queries"]["clear"]), ctx, competitor=random.choice(competitors))
            rec["scene_tag"] = cfg["scene_tag"]
            data.append(self._finalize_record(rec, self._pick_tool_plan(1)))
            self._update_progress()
        return data

    def gen_workflow2_upload(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(2)
        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(2, ctx)
            is_fail = random.random() < cfg["fail_probability"]
            if is_fail:
                rec["user_query"] = self._format(random.choice(cfg["queries"]["fail"]), ctx)
                rec["scene_tag"] = random.choice(cfg["scene_tags"]["fail"])
                tool_plan = cfg["tool_plans"][2]
            else:
                rec["user_query"] = self._format(random.choice(cfg["queries"]["success"]), ctx)
                rec["scene_tag"] = random.choice(cfg["scene_tags"]["success"])
                tool_plan = random.choice(cfg["tool_plans"][:2])
            data.append(self._finalize_record(rec, tool_plan))
            self._update_progress()
        return data

    def gen_workflow3_single_query(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(3)
        clarify_template = cfg["clarification"]["answer_templates"][0]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(3, ctx)
            if random.random() < cfg["clarify_probability"]:
                rec["user_query"] = random.choice(cfg["queries"]["ambiguous"])
                rec["needs_clarification"] = True
                rec["clarification_reason"] = cfg["clarification"]["reason"]
                rec["clarification_answer"] = self._format(clarify_template, ctx)
            else:
                rec["user_query"] = self._format(random.choice(cfg["queries"]["clear"]), ctx)
            rec["scene_tag"] = infer_metric_scene(rec["user_query"])
            data.append(self._finalize_record(rec, self._pick_tool_plan(3)))
            self._update_progress()
        return data

    def gen_workflow4_deep_analysis(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(4)
        clarify_template = cfg["clarification"]["answer_templates"][0]

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(4, ctx)
            scene = random.choice(cfg["scene_tags"])
            if random.random() < cfg["clarify_probability"]:
                rec["user_query"] = random.choice(cfg["queries"]["ambiguous"])
                rec["needs_clarification"] = True
                rec["clarification_reason"] = cfg["clarification"]["reason"]
                rec["clarification_answer"] = self._format(clarify_template, ctx)
            else:
                rec["user_query"] = self._format(random.choice(cfg["scene_query_map"][scene]), ctx)
            rec["scene_tag"] = scene
            data.append(self._finalize_record(rec, self._pick_tool_plan(4)))
            self._update_progress()
        return data

    def gen_workflow5_anomaly(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(5)

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(5, ctx)
            scene = random.choice(cfg["scene_tags"])
            rec["user_query"] = self._format(random.choice(cfg["scene_query_map"][scene]), ctx)
            rec["scene_tag"] = scene
            data.append(self._finalize_record(rec, self._pick_tool_plan(5)))
            self._update_progress()
        return data

    def gen_workflow6_knowledge(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(6)

        data: list[dict[str, Any]] = []
        for _ in range(count):
            ctx = random_context()
            rec = self._base_record(6, ctx)
            query = random.choice(cfg["queries"])
            rec["user_query"] = query
            domain = "knowledge_base"
            for keyword, mapped_domain in cfg["domain_map"].items():
                if keyword in query:
                    domain = mapped_domain
                    break
            rec["scene_tag"] = domain
            data.append(self._finalize_record(rec, self._pick_tool_plan(6)))
            self._update_progress()
        return data

    def gen_workflow7_refusal(self, count: int) -> list[dict[str, Any]]:
        cfg = self._workflow(7)
        competitors = cfg["variables"]["competitors"]
        per_type = count // 3
        extras = count % 3
        type_counts = {
            "off_topic": per_type + (1 if extras > 0 else 0),
            "unauthorized_operation": per_type + (1 if extras > 1 else 0),
            "insufficient_data_to_answer": per_type,
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
