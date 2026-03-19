#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ad Campaign Agent SFT Dataset - Quality Analysis & Report Generator
输出：checker/{report_subfolder}/dataset_card.md + 6张图表
"""

import json
import sys
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
import matplotlib.font_manager as fm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import pandas as pd

# ─────────────────────────────────────────────────────────────
# 0. 路径扫描
# ─────────────────────────────────────────────────────────────

#import Chinese Font
def _setup_chinese_font():
    """按优先级查找系统中文字体，找到即应用"""
    candidates = [
        "PingFang HK",           # 你系统上有，首选
        "Heiti TC",              # 你系统上有
        "Hiragino Sans GB",      # 你系统上有，简体中文支持最好
        "Hiragino Sans",         # 你系统上有
        "Arial Unicode MS",      # 你系统上有，兜底
        "Hiragino Maru Gothic Pro",
        "Hiragino Mincho ProN",
    ]
    
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            matplotlib.rcParams["font.family"]       = font
            matplotlib.rcParams["axes.unicode_minus"] = False
            print(f"   🔤 Chinese font applied: {font}")
            return font
    # 全部找不到时的兜底：直接用路径加载
    fallback_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in fallback_paths:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            prop = fm.FontProperties(fname=path)
            matplotlib.rcParams["font.family"]       = prop.get_name()
            matplotlib.rcParams["axes.unicode_minus"] = False
            print(f"   🔤 Chinese font loaded from path: {path}")
            return prop.get_name()
    print("   ⚠️  No Chinese font found, labels may show as boxes")
    return None


def find_input_file(filename: str) -> Path:
    """
    在以下位置按顺序搜索文件：
      1. 直接路径（用户输入了绝对/相对路径）
      2. 当前脚本所在目录的 parent（项目根目录）
      3. 项目根目录下的 data/ 子目录
    找不到时打印友好提示并退出。
    """
    candidates = [
        Path(filename),                                    # 1. 直接路径
        Path(__file__).parent.parent / filename,           # 2. 项目根目录
        Path(__file__).parent.parent / "data" / filename,  # 3. data/ 子目录
    ]
    for p in candidates:
        if p.exists():
            print(f"📂 Found input: {p.resolve()}")
            return p.resolve()

    # 未找到：列出 data/ 里有哪些 json 文件给用户参考
    data_dir = Path(__file__).parent.parent / "data"
    print(f"\n❌ File not found: '{filename}'")
    print(f"   Searched in:")
    for c in candidates:
        print(f"     {c}")
    if data_dir.exists():
        jsons = list(data_dir.glob("*.json"))
        if jsons:
            print(f"\n   Available JSON files in data/:")
            for j in jsons:
                print(f"     {j.name}")
        else:
            print(f"\n   No JSON files found in data/")
    sys.exit(1)


def make_output_dir(input_path: Path) -> Path:
    """
    在 checker/ 下创建以输入文件名（去扩展名）命名的子目录。
    例：data/ad_agent_sft_20260316.json
     → checker/ad_agent_sft_20260316/
    """
    stem       = input_path.stem
    checker    = Path(__file__).parent.parent / "checker" / stem
    checker.mkdir(parents=True, exist_ok=True)
    print(f"📁 Report will be saved to: {checker.resolve()}")
    return checker


# ─────────────────────────────────────────────────────────────
# 1. 格式检测 & 归一化（与上一版相同）
# ─────────────────────────────────────────────────────────────

_SHAREGPT_ROLE_MAP = {"system":"system","human":"user","gpt":"assistant","tool":"tool"}

def detect_format(record: dict) -> str:
    if "messages"       in record and record["messages"]       and "role" in record["messages"][0]:
        return "openai"
    if "conversations"  in record and record["conversations"]  and "from" in record["conversations"][0]:
        return "sharegpt"
    return "unknown"

def to_openai_messages(record: dict, fmt: str) -> list:
    if fmt == "openai":
        return record.get("messages", [])
    if fmt == "sharegpt":
        messages = []
        for turn in record.get("conversations", []):
            role    = _SHAREGPT_ROLE_MAP.get(turn.get("from",""), "unknown")
            content = turn.get("value","")
            if role == "assistant" and "<tool_call>" in content:
                match = re.search(r"<tool_call>(.*?)</tool_call>", content, re.DOTALL)
                if match:
                    try:
                        payload = json.loads(match.group(1).strip())
                        call_id = f"call_sgpt_{len(messages):04d}"
                        messages.append({
                            "role":"assistant","content":"",
                            "tool_calls":[{"id":call_id,"type":"function","function":{
                                "name":payload.get("name","unknown"),
                                "arguments":json.dumps(payload.get("arguments",{}),ensure_ascii=False)
                            }}]
                        })
                        continue
                    except json.JSONDecodeError:
                        pass
            messages.append({"role":role,"content":content})
        return messages
    return []

def load_and_normalize(path: Path):
    raw         = json.loads(path.read_text(encoding="utf-8"))
    fmt_counter = Counter()
    normalized  = []
    for record in raw:
        fmt      = detect_format(record)
        fmt_counter[fmt] += 1
        messages = to_openai_messages(record, fmt)
        normalized.append({"messages":messages,"_meta":record.get("_meta",{})})
    dominant = fmt_counter.most_common(1)[0][0] if fmt_counter else "unknown"
    return normalized, dominant, fmt_counter


# ─────────────────────────────────────────────────────────────
# 2. 统计计算（纯数据，不打印）
# ─────────────────────────────────────────────────────────────

def count_tokens_approx(text: str) -> int:
    zh = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return zh + max(1, (len(text) - zh) // 4)

def percentile(data: list, p: float) -> float:
    if not data: return 0.0
    s = sorted(data)
    return s[min(int(len(s)*p/100), len(s)-1)]

def compute_stats(data: list) -> dict:
    wf_counter       = Counter()
    scene_counter    = Counter()
    platform_counter = Counter()
    genre_counter    = Counter()
    tool_counter     = Counter()
    chain_len_list   = []
    turn_len_list    = []
    token_list       = []
    user_token_list  = []
    asst_token_list  = []
    clarify_count    = 0
    refusal_count    = 0
    has_tool_count   = 0
    chain_combos     = Counter()
    last_turn_types  = Counter()
    format_errors    = []

    for i, record in enumerate(data):
        messages = record["messages"]
        meta     = record["_meta"]

        wf_counter[meta.get("workflow_name","unknown")]  += 1
        scene_counter[meta.get("scene_tag","unknown")]   += 1
        platform_counter[meta.get("platform","unknown")] += 1
        genre_counter[meta.get("game_genre","unknown")]  += 1

        chain = meta.get("tool_chain",[])
        chain_len_list.append(len(chain))
        for t in chain: tool_counter[t] += 1
        chain_combos[" → ".join(chain) if chain else "(no tools)"] += 1

        turn_len_list.append(len(messages))
        total_tok = user_tok = asst_tok = 0
        for m in messages:
            content = m.get("content","") or ""
            if "tool_calls" in m:
                for tc in m["tool_calls"]:
                    content += tc["function"].get("arguments","")
            tok = count_tokens_approx(content)
            total_tok += tok
            if m["role"] == "user":        user_tok  += tok
            elif m["role"] == "assistant": asst_tok  += tok
        token_list.append(total_tok)
        user_token_list.append(user_tok)
        asst_token_list.append(asst_tok)

        has_clarify = any(
            m["role"]=="user" and idx>0
            and messages[idx-1]["role"]=="assistant"
            and not messages[idx-1].get("tool_calls")
            for idx,m in enumerate(messages) if idx>0
        )
        if has_clarify:              clarify_count += 1
        if meta.get("workflow")==7:  refusal_count += 1
        if any("tool_calls" in m for m in messages): has_tool_count += 1

        last = messages[-1] if messages else {}
        if last.get("role") == "assistant":
            if   last.get("tool_calls"):               last_turn_types["assistant_tool_call"] += 1
            elif last.get("content","").strip():        last_turn_types["assistant_text"]      += 1
            else:                                       last_turn_types["assistant_empty"]     += 1
        else:
            last_turn_types[last.get("role","unknown")] += 1

        call_ids = set()
        for m in messages:
            if "tool_calls" in m:
                for tc in m["tool_calls"]: call_ids.add(tc.get("id",""))
            if "tool_call_id" in m and m["tool_call_id"] not in call_ids:
                format_errors.append(f"record[{i}]: orphan tool_call_id")
        if (messages and messages[-1]["role"]=="assistant"
                and not messages[-1].get("content","").strip()
                and not messages[-1].get("tool_calls")):
            format_errors.append(f"record[{i}]: empty last assistant turn")
        if messages and messages[0]["role"] != "system":
            format_errors.append(f"record[{i}]: first message is not system")

    return dict(
        total=len(data),
        wf_counter=wf_counter, scene_counter=scene_counter,
        platform_counter=platform_counter, genre_counter=genre_counter,
        tool_counter=tool_counter, chain_len_list=chain_len_list,
        turn_len_list=turn_len_list, token_list=token_list,
        user_token_list=user_token_list, asst_token_list=asst_token_list,
        clarify_count=clarify_count, refusal_count=refusal_count,
        has_tool_count=has_tool_count, chain_combos=chain_combos,
        last_turn_types=last_turn_types, format_errors=format_errors,
    )


# ─────────────────────────────────────────────────────────────
# 3. 图表生成
# ─────────────────────────────────────────────────────────────

PALETTE   = sns.color_palette("Blues_r", 12)
BG_COLOR  = "#F8FAFC"
GRID_COLOR= "#E2E8F0"
BAR_COLOR = "#2563EB"
ACCENT    = "#F59E0B"

def _style_ax(ax, title: str):
    ax.set_facecolor(BG_COLOR)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12, color="#1E293B")
    ax.tick_params(colors="#475569", labelsize=9)
    ax.spines[["top","right","left"]].set_visible(False)
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.yaxis.grid(False)

def fig_workflow(s: dict, out: Path) -> Path:
    wf   = s["wf_counter"]
    df   = pd.DataFrame(wf.items(), columns=["workflow","count"]).sort_values("count")
    fig, ax = plt.subplots(figsize=(9,4), facecolor=BG_COLOR)
    bars = ax.barh(df["workflow"], df["count"], color=BAR_COLOR, height=0.55)
    for bar, val in zip(bars, df["count"]):
        ax.text(bar.get_width()+2, bar.get_y()+bar.get_height()/2,
                f"{val} ({100*val/s['total']:.1f}%)",
                va="center", fontsize=8.5, color="#334155")
    _style_ax(ax, "Workflow Distribution")
    ax.set_xlabel("Number of Conversations", color="#475569", fontsize=9)
    ax.set_xlim(0, df["count"].max()*1.22)
    plt.tight_layout()
    p = out/"fig1_workflow.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

def fig_scene(s: dict, out: Path) -> Path:
    sc  = s["scene_counter"]
    df  = pd.DataFrame(sc.items(), columns=["scene","count"]).sort_values("count")
    colors = [ACCENT if "danger" in x else BAR_COLOR for x in df["scene"]]
    fig, ax = plt.subplots(figsize=(10,7), facecolor=BG_COLOR)
    bars = ax.barh(df["scene"], df["count"], color=colors, height=0.65)
    for bar, val in zip(bars, df["count"]):
        ax.text(bar.get_width()+0.5, bar.get_y()+bar.get_height()/2,
                f"{val}", va="center", fontsize=8, color="#334155")
    _style_ax(ax, "Scene Tag Distribution  (🟡 = danger scenarios)")
    ax.set_xlabel("Count", color="#475569", fontsize=9)
    ax.set_xlim(0, df["count"].max()*1.18)
    legend = [mpatches.Patch(color=ACCENT, label="danger scenarios"),
              mpatches.Patch(color=BAR_COLOR, label="other")]
    ax.legend(handles=legend, fontsize=8, loc="lower right")
    plt.tight_layout()
    p = out/"fig2_scene.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

def fig_turn_dist(s: dict, out: Path) -> Path:
    turns = s["turn_len_list"]
    fig, ax = plt.subplots(figsize=(8,4), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    sns.histplot(turns, bins=range(min(turns), max(turns)+2),
                 color=BAR_COLOR, alpha=0.85, ax=ax, edgecolor="white")
    ax.axvline(statistics.mean(turns),  color=ACCENT,    linestyle="--", lw=1.5, label=f"mean={statistics.mean(turns):.1f}")
    ax.axvline(statistics.median(turns),color="#10B981", linestyle="--", lw=1.5, label=f"median={statistics.median(turns):.1f}")
    _style_ax(ax, "Conversation Length Distribution (message turns)")
    ax.set_xlabel("Number of Messages", color="#475569", fontsize=9)
    ax.set_ylabel("Count", color="#475569", fontsize=9)
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax.xaxis.grid(False)
    ax.legend(fontsize=8)
    plt.tight_layout()
    p = out/"fig3_turn_dist.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

def fig_token_dist(s: dict, out: Path) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(13,4), facecolor=BG_COLOR)
    sets = [
        (s["token_list"],      "Total tokens / conv",   "#2563EB"),
        (s["user_token_list"], "User turn tokens",      "#10B981"),
        (s["asst_token_list"], "Assistant turn tokens", "#F59E0B"),
    ]
    for ax, (lst, title, color) in zip(axes, sets):
        ax.set_facecolor(BG_COLOR)
        sns.boxplot(y=lst, ax=ax, color=color, width=0.4,
                    flierprops=dict(marker="o", markersize=3, alpha=0.4))
        ax.set_title(title, fontsize=10, fontweight="bold", color="#1E293B", pad=8)
        ax.tick_params(colors="#475569", labelsize=8)
        ax.spines[["top","right","bottom"]].set_visible(False)
        ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
        med = statistics.median(lst)
        ax.text(0.55, med, f"  median={med:.0f}", va="center",
                fontsize=8, color="#334155", transform=ax.get_yaxis_transform())
    fig.suptitle("Token Distribution (approx)", fontsize=13,
                 fontweight="bold", color="#1E293B", y=1.02)
    plt.tight_layout()
    p = out/"fig4_token_dist.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

def fig_tool_freq(s: dict, out: Path) -> Path:
    tc  = s["tool_counter"]
    df  = pd.DataFrame(tc.items(), columns=["tool","count"]).sort_values("count")
    fig, ax = plt.subplots(figsize=(10,6), facecolor=BG_COLOR)
    colors  = [BAR_COLOR if i >= len(df)-5 else "#93C5FD" for i in range(len(df))]
    bars    = ax.barh(df["tool"], df["count"], color=colors, height=0.6)
    for bar, val in zip(bars, df["count"]):
        ax.text(bar.get_width()+1, bar.get_y()+bar.get_height()/2,
                str(val), va="center", fontsize=8.5, color="#334155")
    _style_ax(ax, "Tool Call Frequency  (darker = top 5)")
    ax.set_xlabel("Total Calls", color="#475569", fontsize=9)
    ax.set_xlim(0, df["count"].max()*1.18)
    plt.tight_layout()
    p = out/"fig5_tool_freq.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

def fig_platform_genre(s: dict, out: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11,5), facecolor=BG_COLOR)
    for ax, counter, title in [
        (axes[0], s["platform_counter"], "Platform Distribution"),
        (axes[1], s["genre_counter"],    "Game Genre Distribution"),
    ]:
        labels = list(counter.keys())
        values = list(counter.values())
        colors = sns.color_palette("Blues_r", len(labels))
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.1f%%",
            colors=colors, startangle=90,
            wedgeprops=dict(edgecolor="white", linewidth=1.5),
            textprops=dict(fontsize=9, color="#1E293B"),
        )
        for at in autotexts: at.set_fontsize(8)
        ax.set_facecolor(BG_COLOR)
        ax.set_title(title, fontsize=12, fontweight="bold",
                     color="#1E293B", pad=10)
    fig.patch.set_facecolor(BG_COLOR)
    plt.tight_layout()
    p = out/"fig6_platform_genre.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

def generate_all_figures(s: dict, out: Path) -> dict:
    print("🎨 Generating figures...")
    figs = {}
    figs["workflow"]       = fig_workflow(s, out)
    figs["scene"]          = fig_scene(s, out)
    figs["turn_dist"]      = fig_turn_dist(s, out)
    figs["token_dist"]     = fig_token_dist(s, out)
    figs["tool_freq"]      = fig_tool_freq(s, out)
    figs["platform_genre"] = fig_platform_genre(s, out)
    print(f"   ✅ {len(figs)} figures saved")
    return figs


# ─────────────────────────────────────────────────────────────
# 4. Markdown 报告生成
# ─────────────────────────────────────────────────────────────

def write_markdown(s: dict, fmt: str, input_path: Path,
                   figs: dict, out: Path):
    total     = s["total"]
    errors    = s["format_errors"]
    turns     = s["turn_len_list"]
    tokens    = s["token_list"]
    now       = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── tool chain top15 표 데이터 ──────────────────────────
    top_chains = s["chain_combos"].most_common(15)

    # ── scene 표 ──────────────────────────────────────────
    scene_rows = "\n".join(
        f"| `{sc}` | {cnt} | {100*cnt/total:.1f}% |"
        for sc, cnt in sorted(s["scene_counter"].items(), key=lambda x: -x[1])
    )

    # ── tool 표 ──────────────────────────────────────────
    tool_rows = "\n".join(
        f"| `{tool}` | {cnt} | {100*cnt/s['has_tool_count']:.1f}% |"
        for tool, cnt in sorted(s["tool_counter"].items(), key=lambda x: -x[1])
    )

    chain_rows = "\n".join(
        f"| `{combo[:60]}{'...' if len(combo)>60 else ''}` | {cnt} |"
        for combo, cnt in top_chains
    )

    md = f"""# Ad Campaign Agent SFT Dataset — Quality Report

> Generated: {now}
> Source file: `{input_path.name}`
> Format detected: **{fmt.upper()}** → normalized to OpenAI Messages

---

## 📋 Overview

| Metric | Value |
|--------|-------|
| Total conversations | **{total:,}** |
| Input format | {fmt.upper()} |
| With tool calls | {s['has_tool_count']:,} ({100*s['has_tool_count']/total:.1f}%) |
| With clarification turn | {s['clarify_count']:,} ({100*s['clarify_count']/total:.1f}%) |
| Refusal conversations | {s['refusal_count']:,} ({100*s['refusal_count']/total:.1f}%) |
| Unique tools covered | {len(s['tool_counter'])} |
| Distinct scene tags | {len(s['scene_counter'])} |
| Format errors | {"✅ 0 — clean" if not errors else f"⚠️ {len(errors)}"} |
| Platforms | {', '.join(sorted(s['platform_counter']))} |
| Game genres | {', '.join(sorted(s['genre_counter']))} |

---

## 1. Workflow Distribution

![workflow distribution](fig1_workflow.png)

| Workflow | Count | % |
|----------|------:|--:|
""" + "\n".join(
        f"| {wf} | {cnt} | {100*cnt/total:.1f}% |"
        for wf, cnt in sorted(s["wf_counter"].items(), key=lambda x: -x[1])
    ) + f"""

---

## 2. Scene Tag Distribution

![scene tag distribution](fig2_scene.png)

| Scene Tag | Count | % |
|-----------|------:|--:|
{scene_rows}

---

## 3. Conversation Length

![turn distribution](fig3_turn_dist.png)

| Stat | Value |
|------|-------|
| Min | {min(turns)} turns |
| Max | {max(turns)} turns |
| Mean | {statistics.mean(turns):.2f} turns |
| Median | {statistics.median(turns):.1f} turns |
| Std dev | {statistics.stdev(turns):.2f} |
| p25 | {percentile(turns,25):.0f} |
| p75 | {percentile(turns,75):.0f} |
| p90 | {percentile(turns,90):.0f} |

---

## 4. Token Distribution (approx)

> Estimation method: Chinese characters ≈ 1 token/char, English ≈ 1 token/4 chars

![token distribution](fig4_token_dist.png)

| Scope | Min | Mean | Median | p90 | Max |
|-------|----:|-----:|-------:|----:|----:|
| Total / conv | {min(tokens)} | {statistics.mean(tokens):.0f} | {statistics.median(tokens):.0f} | {percentile(tokens,90):.0f} | {max(tokens)} |
| User turns | {min(s['user_token_list'])} | {statistics.mean(s['user_token_list']):.0f} | {statistics.median(s['user_token_list']):.0f} | {percentile(s['user_token_list'],90):.0f} | {max(s['user_token_list'])} |
| Assistant turns | {min(s['asst_token_list'])} | {statistics.mean(s['asst_token_list']):.0f} | {statistics.median(s['asst_token_list']):.0f} | {percentile(s['asst_token_list'],90):.0f} | {max(s['asst_token_list'])} |

---

## 5. Tool Call Statistics

![tool frequency](fig5_tool_freq.png)

### Tool Chain Length

| Chain Length | Count | % |
|-------------|------:|--:|
""" + "\n".join(
        f"| {length} tool(s) | {cnt} | {100*cnt/total:.1f}% |"
        for length, cnt in sorted(Counter(s["chain_len_list"]).items())
    ) + f"""

### Individual Tool Call Frequency

| Tool | Calls | % of tool-call convs |
|------|------:|---------------------:|
{tool_rows}

### Top 15 Tool Chain Combinations

| Chain | Count |
|-------|------:|
{chain_rows}

---

## 6. Platform & Genre Diversity

![platform and genre](fig6_platform_genre.png)

### Platform

| Platform | Count | % |
|----------|------:|--:|
""" + "\n".join(
        f"| {p} | {cnt} | {100*cnt/total:.1f}% |"
        for p, cnt in sorted(s["platform_counter"].items(), key=lambda x: -x[1])
    ) + """

### Game Genre

| Genre | Count | % |
|-------|------:|--:|
""" + "\n".join(
        f"| {g} | {cnt} | {100*cnt/total:.1f}% |"
        for g, cnt in sorted(s["genre_counter"].items(), key=lambda x: -x[1])
    ) + f"""

---

## 7. Last Turn Type Distribution

| Turn Type | Count | % |
|-----------|------:|--:|
""" + "\n".join(
        f"| `{lt}` | {cnt} | {100*cnt/total:.1f}% |"
        for lt, cnt in sorted(s["last_turn_types"].items(), key=lambda x: -x[1])
    ) + f"""

---

## 8. Format Validation

| Check | Result |
|-------|--------|
| tool_call_id pairing | {"✅ All matched" if not errors else f"⚠️ {len(errors)} errors"} |
| Last turn non-empty | {"✅ OK" if not any("empty last" in e for e in errors) else "⚠️ Has empty last turns"} |
| System message first | {"✅ OK" if not any("not system" in e for e in errors) else "⚠️ Some records missing system"} |

{"" if not errors else chr(10).join(f"- `{e}`" for e in errors[:10])}

---

*Report generated by `3_dataquality_check.py`*
"""

    out_path = out / "dataset_card.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"📄 Markdown report saved: {out_path}")


# ─────────────────────────────────────────────────────────────
# 5. Main
# ─────────────────────────────────────────────────────────────

def main():
    _setup_chinese_font()
    if len(sys.argv) < 2:
        filename = input("Input JSON file name: ").strip()
    else:
        filename = sys.argv[1]

    input_path = find_input_file(filename)
    out_dir    = make_output_dir(input_path)

    print("⏳ Loading and normalizing dataset...")
    data, dominant_fmt, fmt_counter = load_and_normalize(input_path)
    print(f"   ✅ {len(data):,} records loaded  |  format: {dominant_fmt.upper()}")
    if len(fmt_counter) > 1:
        print(f"   ⚠  Mixed formats: {dict(fmt_counter)}")

    print("📊 Computing statistics...")
    stats = compute_stats(data)
    stats["has_tool_count"] = stats["has_tool_count"]   # already in dict

    figs = generate_all_figures(stats, out_dir)
    write_markdown(stats, dominant_fmt, input_path, figs, out_dir)

    print(f"\n✅ Report complete → {out_dir.resolve()}")
    print(f"   dataset_card.md + {len(figs)} figures")


if __name__ == "__main__":
    main()
