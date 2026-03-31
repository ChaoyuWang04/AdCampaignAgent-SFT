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

    assert len(records) == 1000
    assert raw_dir.is_dir()
    assert len(output_files) == 1
