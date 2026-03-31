#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 benchmark case_results.jsonl + test_*.json 生成"考卷"格式 Markdown。
格式：题目 → 标准答案 → 考生作答 → 逐项评分解析

自动扫描 tests/benchmark/results/**/case_results.jsonl
需要同时读取 tests/benchmark/data/ 下的 case 定义文件获取题目原文。

用法：
  python tests/benchmark/Zrender_exam_report.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────

METRIC_FULL = {
    "F1": ("格式可解析率", "模型输出能否被程序正确解析为工具调用结构"),
    "F2": ("格式合规率",   "工具调用字段是否完整、类型是否正确"),
    "R1": ("行为决策准确率","模型是否正确判断：该调工具 / 该拒答 / 该追问"),
    "R2": ("工具选择准确率","选择的工具列表是否与标准答案完全一致"),
    "R3": ("工具集合F1",   "预测工具集合与标准答案的 F1（容忍顺序差异）"),
    "C1": ("参数精确匹配", "所有参数字段与标准答案完全一致"),
    "C2": ("参数字段准确率","逐字段检查命中率（允许多余字段）"),
    "S1": ("顺序调用准确率","链式调用的工具顺序是否完全正确"),
    "S2": ("并行调用准确率","应并行的工具是否在同一 assistant turn 中出现"),
    "S3": ("越界拒答率",   "越界请求是否被正确拒绝"),
    "S4": ("澄清追问率",   "信息不足时是否正确追问而非乱猜"),
    "S5": ("端到端成功率", "整条任务链是否成功完成（综合所有条件）"),
}

CASE_TYPE_LABELS = {
    "standard":   "标准单工具",
    "sequential": "顺序链式调用",
    "parallel":   "并行调用",
    "oos":        "越界拒答",
    "clarify":    "信息不足追问",
}

BEHAVIOR_LABELS = {
    "tool_call":     "调用工具",
    "reject":        "拒绝回答",
    "clarify":       "追问补充信息",
    "direct_answer": "直接回答",
}

METRIC_ORDER = ["F1", "F2", "R1", "R2", "R3", "C1", "C2", "S1", "S2", "S3", "S4", "S5"]


# ─── Helpers ──────────────────────────────────────────────────

def se(v: float | None) -> str:
    if v is None: return "⬜ —"
    if v >= 0.9:  return f"🟢 {v:.2f}"
    if v >= 0.6:  return f"🟡 {v:.2f}"
    return f"🔴 {v:.2f}"


def avg(scores: dict) -> float:
    vals = [v for v in scores.values() if v is not None]
    return sum(vals) / len(vals) if vals else 0.0


def strip_think(text: str) -> tuple[str, str]:
    m = re.search(r"<think>(.*?)</think>", text, re.S)
    if not m:
        return "", text
    return m.group(1).strip(), re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def extract_tc_json(text: str) -> tuple[str, str]:
    m = re.search(r"<tool_call>(.*?)</tool_call>", text, re.S)
    if not m:
        return "", text
    raw  = m.group(1).strip()
    rest = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.S).strip()
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2), rest
    except Exception:
        return raw, rest


def fmt_tool_result(content: str) -> str:
    try:
        return json.dumps(json.loads(content), ensure_ascii=False, indent=2)
    except Exception:
        return content


def load_case_defs(data_dir: Path) -> dict[str, dict]:
    """Load all case definitions from test_*.json files, keyed by id."""
    defs = {}
    for f in data_dir.glob("test_*.json"):
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
            for item in items:
                if "id" in item:
                    defs[item["id"]] = item
        except Exception:
            pass
    return defs


# ─── Section: Question ────────────────────────────────────────

def render_question(case_def: dict | None, result: dict) -> str:
    cid      = result.get("id", "")
    ctype    = CASE_TYPE_LABELS.get(result.get("case_type", ""), result.get("case_type", ""))
    behavior = BEHAVIOR_LABELS.get(result.get("expected_behavior", ""), result.get("expected_behavior", ""))

    lines = [f"### 📝 题目"]

    if case_def:
        user_input = case_def.get("user_input", "（未找到）")
        context    = case_def.get("context", {})
        notes      = case_def.get("notes", "")

        lines.append(f"**用户输入：** {user_input}\n")
        if context:
            ctx_str = "、".join(f"`{k}={v}`" for k, v in context.items())
            lines.append(f"**上下文：** {ctx_str}\n")
        lines.append(f"**题型：** {ctype}  **期望行为：** {behavior}")
        if notes:
            lines.append(f"\n> 💡 {notes}")
    else:
        lines.append(f"**题型：** {ctype}  **期望行为：** {behavior}")
        lines.append(f"> _(未找到原始 case 定义文件)_")

    return "\n".join(lines)


# ─── Section: Standard Answer ────────────────────────────────

def render_standard_answer(case_def: dict | None) -> str:
    lines = ["### ✅ 标准答案"]

    if not case_def:
        lines.append("_（未找到原始 case 定义文件）_")
        return "\n".join(lines)

    expected_behavior = case_def.get("expected_behavior", "")
    expected_tools    = case_def.get("expected_tools", [])
    expected_args     = case_def.get("expected_tool_args", {})
    expected_seq      = case_def.get("expected_sequence", [])
    expected_par      = case_def.get("expected_parallel_groups", [])
    missing_slots     = case_def.get("required_missing_slots", [])

    lines.append(f"**期望行为：** {BEHAVIOR_LABELS.get(expected_behavior, expected_behavior)}\n")

    if expected_tools:
        lines.append(f"**期望调用工具：** {' → '.join(f'`{t}`' for t in expected_tools)}\n")

    if expected_args:
        lines.append("**期望参数（用于 C1/C2 评分）：**")
        for tool, args in expected_args.items():
            lines.append(f"\n`{tool}`")
            lines.append(f"```json\n{json.dumps(args, ensure_ascii=False, indent=2)}\n```")

    if expected_seq:
        lines.append(f"**期望调用顺序（S1）：** {' → '.join(f'`{t}`' for t in expected_seq)}")

    if expected_par:
        groups = ["[" + " + ".join(f"`{t}`" for t in g) + "]" for g in expected_par]
        lines.append(f"**期望并行组（S2）：** {' , '.join(groups)}")

    if missing_slots:
        lines.append(f"**必须追问的信息槽（S4）：** {', '.join(f'`{s}`' for s in missing_slots)}")

    return "\n".join(lines)


# ─── Section: Model Answer ────────────────────────────────────

def render_model_answer(trace: list[dict]) -> str:
    lines = ["### 🤖 考生作答（完整 Trace）"]

    if not trace:
        lines.append("_（无 trace 记录）_")
        return "\n".join(lines)

    for i, msg in enumerate(trace):
        role    = msg.get("role", "")
        content = msg.get("content", "") or ""

        if role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            think, content = strip_think(content)
            tc_json, content = extract_tc_json(content)

            lines.append(f"\n**Turn {i+1} — 🤖 Assistant**")

            if think:
                lines.append(f"\n<details><summary>💭 思考过程（已折叠）</summary>\n\n```\n{think}\n```\n\n</details>")

            if tc_json:
                lines.append(f"\n🔧 **调用工具**")
                lines.append(f"```json\n{tc_json}\n```")
            elif tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    try:
                        args_str = json.dumps(json.loads(fn.get("arguments", "{}")), ensure_ascii=False, indent=2)
                    except Exception:
                        args_str = fn.get("arguments", "")
                    lines.append(f"\n🔧 **调用工具：`{fn.get('name', '')}`**")
                    lines.append(f"```json\n{args_str}\n```")

            if content:
                lines.append(f"\n💬 **文字回复**\n\n{content}")

        elif role == "tool":
            pretty = fmt_tool_result(content)
            lines.append(f"\n**Turn {i+1} — ⚙️ Tool Result** `{msg.get('tool_call_id','')}`")
            lines.append(f"```json\n{pretty}\n```")

        elif role == "user":
            lines.append(f"\n**Turn {i+1} — 👤 User**\n\n{content}")

    return "\n".join(lines)


# ─── Section: Score Analysis ──────────────────────────────────

def render_score_analysis(scores: dict, case_def: dict | None, trace: list[dict]) -> str:
    lines = ["### 📊 评分解析\n"]

    # Collect what model actually did
    all_calls = []
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                if fn.get("name"):
                    all_calls.append(fn["name"])
            # also parse from content
            content = msg.get("content", "") or ""
            m = re.search(r'"name"\s*:\s*"([^"]+)"', content)
            if m and m.group(1) not in all_calls:
                all_calls.append(m.group(1))

    inferred_behavior = "tool_call" if all_calls else "direct_answer"
    final_content = ""
    for msg in reversed(trace):
        if msg.get("role") == "assistant":
            c = msg.get("content", "") or ""
            c = re.sub(r"<think>.*?</think>", "", c, flags=re.S)
            c = re.sub(r"<tool_call>.*?</tool_call>", "", c, flags=re.S)
            c = c.strip()
            if c:
                final_content = c
                break
    rejection_words = ["不能","无法","抱歉","超出","权限","拒绝","sorry","cannot","unable","out of scope"]
    clarify_words   = ["请先","请提供","告诉我","方便提供","缺少","?","？"]
    all_text = " ".join(m.get("content","") or "" for m in trace if m.get("role")=="assistant")
    if any(w in all_text for w in rejection_words):
        inferred_behavior = "reject"
    elif any(w in all_text for w in clarify_words) and not all_calls:
        inferred_behavior = "clarify"

    expected_behavior = (case_def or {}).get("expected_behavior", "")
    expected_tools    = (case_def or {}).get("expected_tools", [])
    expected_args     = (case_def or {}).get("expected_tool_args", {})
    expected_seq      = (case_def or {}).get("expected_sequence", [])
    expected_par      = (case_def or {}).get("expected_parallel_groups", [])

    lines.append("| 指标 | 全称 | 得分 | 详细说明 |")
    lines.append("|------|------|------|---------|")

    for m in METRIC_ORDER:
        if m not in scores:
            continue
        v = scores[m]
        name, desc = METRIC_FULL.get(m, (m, ""))
        score_str = se(v)

        # Generate per-metric explanation
        if m == "F1":
            if v == 1.0:
                detail = "✅ 模型输出了合法的 tool call 结构，可被程序解析"
            else:
                detail = "❌ 模型未输出任何可解析的 tool call"

        elif m == "F2":
            if v == 1.0:
                detail = "✅ 所有 tool call 字段完整，工具名为字符串，参数为 dict"
            else:
                detail = "❌ tool call 字段缺失或类型错误"

        elif m == "R1":
            b_label = BEHAVIOR_LABELS.get(inferred_behavior, inferred_behavior)
            e_label = BEHAVIOR_LABELS.get(expected_behavior, expected_behavior)
            if v == 1.0:
                detail = f"✅ 行为判断正确：期望「{e_label}」，实际「{b_label}」"
            else:
                detail = f"❌ 行为判断错误：期望「{e_label}」，实际「{b_label}」"

        elif m == "R2":
            actual_str   = str(sorted(all_calls))
            expected_str = str(sorted(expected_tools))
            if v == 1.0:
                detail = f"✅ 工具列表完全一致：`{all_calls}`"
            else:
                detail = f"❌ 期望 `{expected_tools}`，实际 `{all_calls}`"

        elif m == "R3":
            if not expected_tools:
                detail = "— 无期望工具，跳过"
            else:
                from collections import Counter
                pc = Counter(all_calls)
                ec = Counter(expected_tools)
                overlap = sum((pc & ec).values())
                p = overlap / len(all_calls) if all_calls else 0
                r = overlap / len(expected_tools) if expected_tools else 0
                f1v = 2*p*r/(p+r) if (p+r) > 0 else 0
                detail = (f"Precision={p:.2f} Recall={r:.2f} → F1={f1v:.2f}  "
                          f"命中工具：`{[t for t in all_calls if t in expected_tools]}`")

        elif m == "C1":
            if not expected_args:
                detail = "— 无期望参数定义"
            elif v == 1.0:
                detail = "✅ 所有期望字段与标准答案完全一致"
            else:
                mismatches = []
                for tool_name, exp_a in expected_args.items():
                    # find actual args for this tool
                    act_a = {}
                    for msg in trace:
                        if msg.get("role") == "assistant":
                            for tc in msg.get("tool_calls", []):
                                if tc.get("function", {}).get("name") == tool_name:
                                    try:
                                        act_a = json.loads(tc["function"].get("arguments", "{}"))
                                    except Exception:
                                        pass
                    for k, ev in exp_a.items():
                        av = act_a.get(k, "（缺失）")
                        if av != ev:
                            mismatches.append(f"`{k}`: 期望 `{ev}` 实际 `{av}`")
                if mismatches:
                    detail = "❌ 参数不匹配：" + "；".join(mismatches[:3])
                else:
                    detail = "❌ 参数结构整体不一致（多余字段或缺失字段）"

        elif m == "C2":
            if not expected_args:
                detail = "— 无期望参数定义"
            elif v == 1.0:
                detail = "✅ 所有期望字段均命中"
            else:
                hits, total = 0, 0
                miss = []
                for tool_name, exp_a in expected_args.items():
                    act_a = {}
                    for msg in trace:
                        if msg.get("role") == "assistant":
                            for tc in msg.get("tool_calls", []):
                                if tc.get("function", {}).get("name") == tool_name:
                                    try:
                                        act_a = json.loads(tc["function"].get("arguments", "{}"))
                                    except Exception:
                                        pass
                    for k, ev in exp_a.items():
                        total += 1
                        if act_a.get(k) == ev:
                            hits += 1
                        else:
                            miss.append(f"`{k}`")
                detail = f"命中 {hits}/{total} 个字段，未命中：{', '.join(miss[:3])}" if miss else f"命中 {hits}/{total} 个字段"

        elif m == "S1":
            actual_seq = all_calls
            if v == 1.0:
                detail = f"✅ 调用顺序完全正确：`{actual_seq}`"
            else:
                detail = f"❌ 期望顺序 `{expected_seq}`，实际顺序 `{actual_seq}`"

        elif m == "S2":
            # Find parallel groups in trace
            pred_groups = []
            for msg in trace:
                if msg.get("role") == "assistant":
                    names = [tc.get("function",{}).get("name") for tc in msg.get("tool_calls",[]) if tc.get("function",{}).get("name")]
                    if len(names) > 1:
                        pred_groups.append(names)
            if v == 1.0:
                detail = f"✅ 并行工具在同一 turn 中出现：{pred_groups}"
            else:
                detail = f"❌ 期望并行 {expected_par}，实际没有在同一 turn 中并行调用（实际分组：{pred_groups or '无'}）"

        elif m == "S3":
            if v == 1.0:
                detail = "✅ 模型正确拒绝了越界请求，且未调用任何工具"
            else:
                if all_calls:
                    detail = f"❌ 应该拒答但模型调用了工具：`{all_calls}`"
                else:
                    detail = "❌ 模型回答了但未使用拒绝关键词（无法识别为拒答）"

        elif m == "S4":
            if v == 1.0:
                detail = "✅ 模型正确追问了缺失信息"
            else:
                missing = (case_def or {}).get("required_missing_slots", [])
                if all_calls:
                    detail = f"❌ 模型直接调用了工具 `{all_calls}`，而非先追问 `{missing}`"
                else:
                    detail = f"❌ 模型回复了但未覆盖必须追问的槽位 `{missing}`"

        elif m == "S5":
            if v == 1.0:
                detail = "✅ 端到端任务成功：行为正确 + 工具正确 + 有最终回复"
            else:
                reasons = []
                if scores.get("R1", 0) < 1:   reasons.append("行为决策错误(R1=0)")
                if scores.get("R2", 0) < 1:   reasons.append("工具选择错误(R2=0)")
                if scores.get("C2", 0) < 1:   reasons.append("参数不准确(C2<1)")
                if scores.get("S1", 0) < 1 and "S1" in scores: reasons.append("顺序错误(S1=0)")
                if scores.get("S2", 0) < 1 and "S2" in scores: reasons.append("并行失败(S2=0)")
                if not final_content:          reasons.append("无最终文字回复")
                detail = "❌ " + "；".join(reasons) if reasons else "❌ 综合条件未满足"
        else:
            detail = ""

        lines.append(f"| **{m}** | {name} | {score_str} | {detail} |")

    # Overall
    a = avg(scores)
    result_str = "✅ PASS" if a >= 0.6 else "❌ FAIL"
    lines.append(f"\n**综合得分：{a:.0%}  {result_str}**")

    return "\n".join(lines)


# ─── Per-case ─────────────────────────────────────────────────

def render_case_exam(result: dict, case_def: dict | None, index: int) -> str:
    cid    = result.get("id", f"case_{index}")
    scores = result.get("scores", {})
    trace  = result.get("trace", [])
    a      = avg(scores)
    flag   = "✅ PASS" if a >= 0.6 else "❌ FAIL"
    ctype  = CASE_TYPE_LABELS.get(result.get("case_type",""), result.get("case_type",""))

    anchor = cid.replace("_", "-")
    parts  = [
        f"---\n",
        f"## {flag} 第 {index} 题：`{cid}` {{#{anchor}}}",
        f"**题型：** {ctype}  **综合得分：** {a:.0%}\n",
        render_question(case_def, result),
        "",
        render_standard_answer(case_def),
        "",
        render_model_answer(trace),
        "",
        render_score_analysis(scores, case_def, trace),
        "",
    ]
    return "\n".join(parts)


# ─── Summary ──────────────────────────────────────────────────

def render_summary(results: list[dict]) -> str:
    all_m = [m for m in METRIC_ORDER if any(m in r.get("scores",{}) for r in results)]

    header = "| # | 题目 | 题型 | 综合 | " + " | ".join(all_m) + " |"
    sep    = "|---|------|------|-----:|" + "|".join(["---:"]*len(all_m)) + "|"

    rows = ["## 📋 成绩单总览\n", header, sep]
    for i, r in enumerate(results, 1):
        scores = r.get("scores", {})
        a      = avg(scores)
        flag   = "✅" if a >= 0.6 else "❌"
        cid    = r.get("id", f"case_{i}")
        ctype  = CASE_TYPE_LABELS.get(r.get("case_type",""), r.get("case_type",""))
        cells  = [
            str(i),
            f"[{cid}](#{cid.replace('_','-')})",
            ctype,
            f"{flag} {a:.0%}",
        ]
        for m in all_m:
            v = scores.get(m)
            cells.append("—" if v is None else f"{se(v)}")
        rows.append("| " + " | ".join(cells) + " |")

    # Stats
    pass_n = sum(1 for r in results if avg(r.get("scores",{})) >= 0.6)
    rows.append(f"\n**总题数：{len(results)}  通过：{pass_n}  失败：{len(results)-pass_n}  通过率：{pass_n/len(results):.0%}**")
    return "\n".join(rows)


# ─── Aggregate ────────────────────────────────────────────────

def render_aggregate(report: dict | None, results: list[dict]) -> str:
    if report:
        model   = report.get("model", "unknown")
        metrics = report.get("metrics", {})
    else:
        model = "unknown"
        acc: dict[str, list] = {}
        for r in results:
            for k, v in r.get("scores", {}).items():
                if v is not None:
                    acc.setdefault(k, []).append(float(v))
        metrics = {k: sum(v)/len(v) for k, v in acc.items()}

    lines = [
        "## 📈 各指标平均分\n",
        f"**模型：** `{model}`\n",
        "| 指标 | 全称 | 含义 | 均分 |",
        "|------|------|------|-----:|",
    ]
    for m in METRIC_ORDER:
        if m not in metrics: continue
        v = metrics[m]
        name, desc = METRIC_FULL.get(m, (m,""))
        lines.append(f"| **{m}** | {name} | {desc} | {se(v)} |")
    return "\n".join(lines)


# ─── Build ────────────────────────────────────────────────────

def build_exam(results: list[dict], report: dict | None, case_defs: dict) -> str:
    model = (report or {}).get("model", "unknown")
    parts = [
        f"# 📝 Benchmark 考卷报告\n",
        f"**模型：** `{model}`  **总题数：** {len(results)}\n",
        "> 本报告展示每道题的原始题目、标准答案、考生作答和逐项评分解析。\n",
        render_aggregate(report, results),
        "",
        render_summary(results),
        "",
        "---\n",
        "# 逐题解析\n",
    ]
    parts += [render_case_exam(r, case_defs.get(r.get("id","")), i)
              for i, r in enumerate(results, 1)]
    return "\n".join(parts)


# ─── IO ───────────────────────────────────────────────────────

def render_one(jsonl_path: Path, case_defs: dict) -> None:
    out_path = jsonl_path.with_name("exam_report.md")
    if out_path.exists():
        print(f"  ⏭  Skip (already exists): {out_path.name}")
        return

    results = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    report      = None
    report_path = jsonl_path.parent / "report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))

    md = build_exam(results, report, case_defs)
    out_path.write_text(md, encoding="utf-8")
    print(f"  ✅ Generated ({len(results)} cases): {out_path}")


def main() -> None:
    script_dir  = Path(__file__).resolve().parent
    results_dir = script_dir / "results"
    data_dir    = script_dir / "data"

    if not results_dir.exists():
        print(f"Results dir not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    case_defs = load_case_defs(data_dir)
    print(f"Loaded {len(case_defs)} case definitions from {data_dir}\n")

    jsonl_files = sorted(results_dir.rglob("case_results.jsonl"))
    if not jsonl_files:
        print(f"No case_results.jsonl found under {results_dir}")
        sys.exit(0)

    print(f"Found {len(jsonl_files)} result(s)\n")
    for jsonl_path in jsonl_files:
        print(f"📁 {jsonl_path.parent.name}")
        render_one(jsonl_path, case_defs)

    print("\nDone.")


if __name__ == "__main__":
    main()
