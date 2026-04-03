from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def src_dir() -> Path:
    return repo_root() / "src"


def data_dir() -> Path:
    return repo_root() / "data"


def outputs_dir() -> Path:
    return repo_root() / "outputs"


def models_dir() -> Path:
    return repo_root() / "models"


def scripts_dir() -> Path:
    return repo_root() / "scripts"


def tests_dir() -> Path:
    return repo_root() / "tests"


def raw_data_dir() -> Path:
    return data_dir() / "raw"


def intermediate_data_dir() -> Path:
    return data_dir() / "intermediate"


def processed_data_dir() -> Path:
    return data_dir() / "processed"


def default_model_dir() -> Path:
    return models_dir() / "qwen3-0_6b"


def tools_schema_path() -> Path:
    return src_dir() / "tools" / "all_tools.json"
