import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    )

from src.datapipeline import conversation_splitter


def test_resolve_input_path_uses_ready2train_message(monkeypatch, tmp_path):
    message_dir = tmp_path / "data" / "ready2train" / "message"
    message_dir.mkdir(parents=True)
    target_file = message_dir / "sample_message.json"
    target_file.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(conversation_splitter, "DEFAULT_DATASET_DIR", message_dir)

    resolved = conversation_splitter.resolve_input_path("sample_message.json")

    assert resolved == target_file


def test_derive_output_path_appends_multiturn_suffix():
    input_path = Path("data/ready2train/message/ad_agent_sft_demo_en_message.json")

    output_path = conversation_splitter.derive_output_path(input_path)

    assert output_path == Path(
        "data/ready2train/message/ad_agent_sft_demo_en_message_multiturn.json"
    )


def test_main_prompts_for_filename_and_uses_same_directory(monkeypatch, tmp_path):
    input_path = tmp_path / "data" / "ready2train" / "message" / "picked.json"
    expected_output = tmp_path / "data" / "ready2train" / "message" / "picked_multiturn.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        conversation_splitter, "DEFAULT_DATASET_DIR", input_path.parent
    )
    monkeypatch.setattr("builtins.input", lambda _: "picked.json")

    captured = {}

    def fake_split_conversations(actual_input, actual_output):
        captured["input"] = actual_input
        captured["output"] = actual_output

    monkeypatch.setattr(
        conversation_splitter, "split_conversations", fake_split_conversations
    )

    conversation_splitter.main()

    assert captured["input"] == input_path
    assert captured["output"] == expected_output


def test_split_conversations_does_not_print_per_conversation_logs(tmp_path, capsys):
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        """
[
  {
    "messages": [
      {"role": "system", "content": "s"},
      {"role": "user", "content": "u"},
      {"role": "assistant", "content": "a1"},
      {"role": "tool", "content": "t1"},
      {"role": "assistant", "content": "a2"}
    ]
  }
]
""".strip(),
        encoding="utf-8",
    )

    conversation_splitter.split_conversations(input_path, output_path)

    stdout = capsys.readouterr().out
    assert "处理第" not in stdout
    assert "额外复制了2份" not in stdout
