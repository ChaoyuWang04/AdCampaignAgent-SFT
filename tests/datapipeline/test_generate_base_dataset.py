import importlib.util
from pathlib import Path


GENERATOR_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "0_generate_base_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_base_dataset", GENERATOR_PATH)
generate_base_dataset = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generate_base_dataset)


def test_generate_defaults_to_data_raw(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "0_generate_base_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")

    monkeypatch.setattr(generate_base_dataset.Path, "resolve", lambda self: script_path)

    generator = generate_base_dataset.AdDatasetGenerator()
    records = generator.generate()

    raw_dir = repo_root / "data" / "raw"
    output_files = list(raw_dir.glob("ad_agent_seeds_*_zh.json"))

    assert len(records) == sum(workflow["count"] for workflow in generate_base_dataset.load_workflow_definitions().values())
    assert raw_dir.is_dir()
    assert len(output_files) == 1


def test_generate_record_keeps_seed_contract():
    generator = generate_base_dataset.AdDatasetGenerator()

    record = generator.gen_workflow1_creative_search(1)[0]

    expected_keys = {
        "workflow",
        "workflow_name",
        "user_role",
        "platform",
        "game_genre",
        "region",
        "campaign_id",
        "app_id",
        "date_range",
        "roas_baseline_d7",
        "roas_baseline_d30",
        "ret_baseline_d1",
        "ret_baseline_d7",
        "user_query",
        "needs_clarification",
        "clarification_reason",
        "clarification_answer",
        "scene_tag",
        "tool_plan",
        "tool_chain",
        "has_parallel",
        "refusal_type",
    }

    assert expected_keys.issubset(record.keys())
    assert record["workflow"] == 1
    assert record["workflow_name"] == "素材搜寻"
    assert isinstance(record["tool_plan"], list)
    assert isinstance(record["tool_chain"], list)


def test_workflow_definitions_load_from_yaml():
    workflows = generate_base_dataset.load_workflow_definitions()

    assert set(workflows) == {1, 2, 3, 4, 5, 6, 7}
    assert workflows[1]["workflow_name"] == "素材搜寻"
    assert workflows[1]["count"] == 360
    assert workflows[1]["tool_plans"]
