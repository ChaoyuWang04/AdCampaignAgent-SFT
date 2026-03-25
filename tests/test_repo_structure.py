import importlib
import pathlib
import sys
import types
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def install_dependency_stubs() -> None:
    if "openai" not in sys.modules:
        openai = types.ModuleType("openai")

        class OpenAI:  # pragma: no cover - stub
            def __init__(self, *args, **kwargs):
                pass

        openai.OpenAI = OpenAI
        sys.modules["openai"] = openai

    if "torch" not in sys.modules:
        torch = types.ModuleType("torch")
        torch.bool = bool
        torch.long = int
        torch.float16 = "float16"
        torch.bfloat16 = "bfloat16"
        torch.float32 = "float32"

        class _DummyTensor:
            def __init__(self, value=None, dtype=None):
                self.value = value
                self.dtype = dtype

            def clone(self):
                return _DummyTensor(self.value, self.dtype)

            def __invert__(self):
                return self

            def __getitem__(self, key):
                return False

            def __setitem__(self, key, value):
                return None

            def numel(self):
                return 0

            def tolist(self):
                return []

        torch.Tensor = _DummyTensor
        torch.tensor = lambda *args, **kwargs: _DummyTensor()
        torch.zeros = lambda *args, **kwargs: _DummyTensor()
        torch.ones_like = lambda *args, **kwargs: _DummyTensor()

        nn = types.ModuleType("torch.nn")
        utils_mod = types.ModuleType("torch.nn.utils")
        rnn_mod = types.ModuleType("torch.nn.utils.rnn")
        rnn_mod.pad_sequence = lambda *args, **kwargs: _DummyTensor()
        utils_mod.rnn = rnn_mod
        nn.utils = utils_mod
        torch.nn = nn

        cuda = types.ModuleType("torch.cuda")
        cuda.is_available = lambda: False
        cuda.get_device_capability = lambda *_args, **_kwargs: (0, 0)
        torch.cuda = cuda

        utils = types.ModuleType("torch.utils")
        data = types.ModuleType("torch.utils.data")

        class Dataset:  # pragma: no cover - stub
            pass

        data.Dataset = Dataset
        utils.data = data
        torch.utils = utils

        sys.modules["torch"] = torch
        sys.modules["torch.nn"] = nn
        sys.modules["torch.nn.utils"] = utils_mod
        sys.modules["torch.nn.utils.rnn"] = rnn_mod
        sys.modules["torch.cuda"] = cuda
        sys.modules["torch.utils"] = utils
        sys.modules["torch.utils.data"] = data

    if "transformers" not in sys.modules:
        transformers = types.ModuleType("transformers")

        class _Base:  # pragma: no cover - stub
            def __init__(self, *args, **kwargs):
                pass

            @classmethod
            def from_pretrained(cls, *args, **kwargs):
                return cls()

        class AutoTokenizer(_Base):
            pad_token = "<pad>"
            eos_token = "<eos>"
            pad_token_id = 0

            def apply_chat_template(self, *args, **kwargs):
                return []

            def add_special_tokens(self, *args, **kwargs):
                return None

        class AutoModelForCausalLM(_Base):
            def parameters(self):
                return []

            def gradient_checkpointing_enable(self):
                return None

        class Trainer:  # pragma: no cover - stub
            def __init__(self, *args, **kwargs):
                pass

        class TrainingArguments:  # pragma: no cover - stub
            def __init__(self, *args, **kwargs):
                pass

        class TrainerCallback:  # pragma: no cover - stub
            pass

        class BitsAndBytesConfig:  # pragma: no cover - stub
            def __init__(self, *args, **kwargs):
                pass

        transformers.AutoTokenizer = AutoTokenizer
        transformers.AutoModelForCausalLM = AutoModelForCausalLM
        transformers.Trainer = Trainer
        transformers.TrainingArguments = TrainingArguments
        transformers.TrainerCallback = TrainerCallback
        transformers.BitsAndBytesConfig = BitsAndBytesConfig
        transformers.set_seed = lambda *_args, **_kwargs: None
        sys.modules["transformers"] = transformers


install_dependency_stubs()


class RepoStructureTests(unittest.TestCase):
    def test_core_packages_are_importable(self) -> None:
        modules = [
            "src.common.project_paths",
            "src.common.llm",
            "src.datapipeline.generate_dataset",
            "src.datapipeline.convert_dataset",
            "src.train.inspect_qwen_dataset",
            "src.inference.travel_assistant_funcall",
            "src.inference.travel_assistant_funcall_fixed",
            "src.tools.get_hotel",
            "src.tools.get_route",
            "src.tools.get_weather",
        ]

        for module_name in modules:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)

    def test_project_paths_resolve_repo_assets(self) -> None:
        project_paths = importlib.import_module("src.common.project_paths")

        self.assertEqual(project_paths.repo_root(), REPO_ROOT)
        self.assertEqual(project_paths.data_dir(), REPO_ROOT / "data")
        self.assertEqual(project_paths.models_dir(), REPO_ROOT / "models")
        self.assertEqual(project_paths.src_dir(), REPO_ROOT / "src")
        self.assertEqual(project_paths.tools_schema_path(), REPO_ROOT / "src" / "tools" / "all_tools.json")


if __name__ == "__main__":
    unittest.main()
