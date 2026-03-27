#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""测试 inspect_qwen_dataset 的输出格式。"""

import os
import sys

if __package__ in {None, ""}:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.train.inspect_qwen_dataset import format_section, format_segment_lines


def test_format_segment_lines_inserts_blank_lines_between_segments() -> None:
    """多个 segment 之间应插入空行，便于阅读。"""
    rendered = format_segment_lines(
        [
            (10, 20, "segment_a"),
            (30, 40, "segment_b"),
        ]
    )

    assert rendered[0] == "  [10:20] -> 'segment_a'"
    assert rendered[1] == ""
    assert rendered[2] == "  [30:40] -> 'segment_b'"


def test_format_section_wraps_content_with_clear_title() -> None:
    """每个输出块都应有明确标题和内容边界。"""
    rendered = format_section(
        "Loss Segments",
        [
            "说明: 当前展示参与 loss 的片段",
            "实际输出:",
            "  [10:20] -> 'segment_a'",
        ],
    )

    assert rendered[0] == "-" * 80
    assert rendered[1] == "[Loss Segments]"
    assert rendered[2] == "-" * 80
    assert rendered[3] == "说明: 当前展示参与 loss 的片段"
    assert rendered[4] == "实际输出:"
