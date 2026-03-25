import os
import sys

if __package__ in {None, ""}:
    sys.path.append(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    )

from src.datapipeline.generate_base_dataset import AdDatasetGenerator


def test_generate_defaults_to_data_raw(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    script_path = repo_root / "src" / "datapipeline" / "generate_base_dataset.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("# test stub\n", encoding="utf-8")

    monkeypatch.setattr(
        "src.datapipeline.generate_base_dataset.Path.resolve",
        lambda self: script_path,
    )

    generator = AdDatasetGenerator("en")
    records = generator.generate()

    raw_dir = repo_root / "data" / "raw"
    output_files = list(raw_dir.glob("ad_agent_seeds_*_en.json"))

    assert len(records) == 1000
    assert raw_dir.is_dir()
    assert len(output_files) == 1
