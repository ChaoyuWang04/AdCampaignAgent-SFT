#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 benchmark case_results.jsonl 转换为 Markdown 报告。
自动扫描 tests/benchmark/results/**/case_results.jsonl
有 .md 的跳过，没有的自动生成。

用法：
  python tests/benchmark/render_benchmark_report.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

METRIC_ORDER = ["F1", "F2", "R1", "R2", "R3", "C1", "C2", "S1", "S2", "S3", "S4", "S5"]

METRIC_DESCRIPTIONS = {
    "F1": "格式可解析",
    "F2": "格式合规",
    "R1": "行为决策",
    "R2": "工具选择",
    "R3": "工具集合F1",
    "C1": "参数精确匹配",
    "C2": "参数字段准确",
    "S1": "顺序调用",
    "S2": "并行调用",
    "S3": "拒答",
    "S4": "追问",
    "S5": "端到端成功",
}

CASE_TYPE_LABELS = {
    "standard":   "标准",
    "sequential": "顺序",
    "parallel":   "并行",
    "oos":        "越界",
    "clarify":    "追问",
}

BEHAVIOR_LABELS = {
    "tool_call":     "工具调用",
    "reject":        "拒答",
    "clarify":       "追问",
    "direct_answer": "直接回答",
}


# ─── Score helpers ────────────────────────────────────────────

def score_emoji(v: float | None) -> str:
    if v is None:
        return "⬜"
    if v >= 0.9:
        return "🟢"
    if v >= 0.6:
        return "🟡"
    return "🔴"


def fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def avg_scores(scores: dict) -> float:
    vals = [v for v in scores.values() if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


# ─── Aggregate section ────────────────────────────────────────

def render_aggregate(report: dict | None, cases: list[dict]) -> str:
    if report:
        model   = report.get("model", "unknown")
        count   = report.get("case_count", len(cases))
        metrics = report.get("metrics", {})
    else:
        model = "unknown"
        count = len(cases)
        acc: dict[str, list[float]] = {}
        for c in cases:
            for k, v in c.get("scores", {}).items():
                if v is not None:
                    acc.setdefault(k, []).append(float(v))
        metrics = {k: sum(v) / len(v) for k, v in acc.items()}

    lines = [
        f"## 📈 聚合指标\n",
        f"**模型:** `{model}`  ",
        f"**Cases:** {count}\n",
        "| 指标 | 说明 | 分数 | 等级 |",
        "|------|------|-----:|------|",
    ]
    for m in METRIC_ORDER:
        if m not in metrics:
            continue
        v    = metrics[m]
        desc = METRIC_DESCRIPTIONS.get(m, m)
        bar  = score_emoji(v)
        lines.append(f"| **{m}** | {desc} | {v:.1%} | {bar} |")

    return "\n".join(lines)


# ─── Summary table ────────────────────────────────────────────

def render_summary(cases: list[dict]) -> str:
    all_m = []
    seen  = set()
    for m in METRIC_ORDER:
        if any(m in c.get("scores", {}) for c in cases) and m not in seen:
            all_m.append(m)
            seen.add(m)

    header = "| # | ID | 类型 | 期望行为 | 综合 | " + " | ".join(all_m) + " |"
    sep    = "|---|----|----|--------|-----:|" + "|".join(["-----:"] * len(all_m)) + "|"

    rows = [f"## 📋 Case 总览\n", header, sep]
    for i, c in enumerate(cases, 1):
        scores   = c.get("scores", {})
        avg      = avg_scores(scores)
        result   = "✅" if avg >= 0.6 else "❌"
        ctype    = CASE_TYPE_LABELS.get(c.get("case_type", ""), c.get("case_type", ""))
        behavior = BEHAVIOR_LABELS.get(c.get("expected_behavior", ""), c.get("expected_behavior", ""))
        cid      = c.get("id", f"case_{i}")
        cells    = [
            str(i),
            f"[{cid}](#{cid.replace('_', '-')})",
            ctype,
            behavior,
            f"{result} {avg:.0%}",
        ]
        for m in all_m:
            v = scores.get(m)
            cells.append(f"{score_emoji(v)} {fmt(v)}")
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join(rows)


# ─── Trace rendering ──────────────────────────────────────────

def strip_think(text: str) -> tuple[str, str]:
    m = re.search(r"<think>(.*?)</think>", text, re.S)
    if not m:
        return "", text
    think = m.group(1).strip()
    rest  = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    return think, rest


def extract_tool_call_json(text: str) -> tuple[str, str]:
    m = re.search(r"<tool_call>(.*?)</tool_call>", text, re.S)
    if not m:
        return "", text
    raw  = m.group(1).strip()
    rest = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.S).strip()
    try:
        obj = json.loads(raw)
        return json.dumps(obj, ensure_ascii=False, indent=2), rest
    except Exception:
        return raw, rest


def render_trace(trace: list[dict]) -> str:
    if not trace:
        return "> _(无 trace)_\n"

    lines = []
    for msg in trace:
        role    = msg.get("role", "")
        content = msg.get("content", "") or ""

        if role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            think, content = strip_think(content)
            tc_json, content = extract_tool_call_json(content)

            lines.append("**🤖 Assistant**\n")

            if think:
                lines.append("<details><summary>💭 思考过程</summary>\n")
                lines.append(f"```\n{think}\n```\n")
                lines.append("</details>\n")

            if tc_json:
                lines.append("🔧 **Tool Call**")
                lines.append(f"```json\n{tc_json}\n```")

            if tool_calls and not tc_json:
                for tc in tool_calls:
                    fn   = tc.get("function", {})
                    name = fn.get("name", "")
                    try:
                        args     = json.loads(fn.get("arguments", "{}"))
                        args_str = json.dumps(args, ensure_ascii=False, indent=2)
                    except Exception:
                        args_str = fn.get("arguments", "")
                    lines.append(f"🔧 **Tool Call: `{name}`**")
                    lines.append(f"```json\n{args_str}\n```")

            if content:
                lines.append(content)

        elif role == "tool":
            tool_id = msg.get("tool_call_id", "")
            try:
                data   = json.loads(content)
                pretty = json.dumps(data, ensure_ascii=False, indent=2)
            except Exception:
                pretty = content
            lines.append(f"**⚙️ Tool Result** `{tool_id}`")
            lines.append(f"```json\n{pretty}\n```")

        elif role == "user":
            lines.append(f"**👤 User**\n\n{content}")

        lines.append("\n---\n")

    return "\n".join(lines)


# ─── Per-case section ─────────────────────────────────────────

def render_case(case: dict, index: int) -> str:
    cid      = case.get("id", f"case_{index}")
    ctype    = CASE_TYPE_LABELS.get(case.get("case_type", ""), case.get("case_type", ""))
    behavior = BEHAVIOR_LABELS.get(case.get("expected_behavior", ""), case.get("expected_behavior", ""))
    scores   = case.get("scores", {})
    trace    = case.get("trace", [])
    avg      = avg_scores(scores)
    result   = "✅ PASS" if avg >= 0.6 else "❌ FAIL"

    score_parts = []
    for m in METRIC_ORDER:
        if m in scores:
            v = scores[m]
            score_parts.append(f"`{m}` {score_emoji(v)} {fmt(v)}")
    score_line = "  ".join(score_parts)

    anchor = cid.replace("_", "-")
    lines = [
        f"---\n",
        f"### {result} `{cid}` {{#{anchor}}}",
        f"**类型:** {ctype}  |  **期望行为:** {behavior}  |  **综合得分:** {avg:.0%}\n",
        score_line,
        "",
        "<details>",
        f"<summary>📋 查看 Trace（{len(trace)} 条消息）</summary>\n",
        render_trace(trace),
        "</details>",
        "",
    ]
    return "\n".join(lines)


# ─── Build full markdown ──────────────────────────────────────

def build_md(cases: list[dict], report: dict | None) -> str:
    model = (report or {}).get("model", "unknown")
    parts = [
        f"# 📊 Benchmark Report\n",
        f"**模型:** `{model}`  **Cases:** {len(cases)}\n",
        render_aggregate(report, cases),
        "",
        render_summary(cases),
        "",
        "## 🔍 Case 详情\n",
    ]
    parts += [render_case(c, i) for i, c in enumerate(cases, 1)]
    return "\n".join(parts)


# ─── IO ───────────────────────────────────────────────────────

def render_one(jsonl_path: Path) -> None:
    out_path = jsonl_path.with_suffix(".md")
    if out_path.exists():
        print(f"  ⏭  Skip (already exists): {out_path.name}")
        return

    cases = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    report      = None
    report_path = jsonl_path.parent / "report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))

    md = build_md(cases, report)
    out_path.write_text(md, encoding="utf-8")
    print(f"  ✅ Generated ({len(cases)} cases): {out_path}")


def main() -> None:
    script_dir  = Path(__file__).resolve().parent
    results_dir = script_dir / "results"

    if not results_dir.exists():
        print(f"Results dir not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    jsonl_files = sorted(results_dir.rglob("case_results.jsonl"))
    if not jsonl_files:
        print(f"No case_results.jsonl found under {results_dir}")
        sys.exit(0)

    print(f"Found {len(jsonl_files)} result(s) under {results_dir}\n")
    for jsonl_path in jsonl_files:
        print(f"📁 {jsonl_path.parent.name}")
        render_one(jsonl_path)

    print("\nDone.")


if __name__ == "__main__":
    main()