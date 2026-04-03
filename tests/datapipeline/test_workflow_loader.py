import importlib.util
from pathlib import Path


LOADER_PATH = Path(__file__).resolve().parents[2] / "src" / "datapipeline" / "workflow_loader.py"
SPEC = importlib.util.spec_from_file_location("workflow_loader", LOADER_PATH)
workflow_loader = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(workflow_loader)


def test_load_all_workflow_configs_returns_seven_workflows():
    workflows = workflow_loader.load_all_workflow_configs()

    assert len(workflows) == 7
    assert set(workflows) == {1, 2, 3, 4, 5, 6, 7}


def test_workflow_config_contains_required_fields():
    workflow = workflow_loader.load_all_workflow_configs()[4]

    assert workflow["workflow_id"] == 4
    assert workflow["workflow_name"] == "多维深度分析"
    assert workflow["count"] == 900
    assert isinstance(workflow["tool_plans"], list)
