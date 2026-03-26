# AdCampaignAgent SFT → arXiv 论文提升指南

> 当前状态：1.7B LoRA SFT 训练完成，loss=0.4，pipeline 跑通
> 目标状态：可投 arXiv 的技术报告，可放入 PhD 申请作品集

---

## 一、论文结构（对照 ACL/EMNLP 格式）

```
1. Abstract          （150词，最后写）
2. Introduction      （问题 + 贡献 + 论文结构）
3. Related Work      （Agent、Tool Calling、SFT 相关工作）
4. Method            （数据构建 + 模型选择 + 训练方案）
5. Experiments       （数据集、基线、指标、结果）
6. Analysis          （消融实验、错误分析）
7. Conclusion
```

---

## 二、当前缺口 Checklist

### 🔴 必须补充（没有这些无法投稿）

- [ ] **推理验证脚本**：证明模型输出正确，不只是 loss 低
- [ ] **定量评估指标**：tool call accuracy、parameter accuracy
- [ ] **Baseline 对比**：至少和未微调的 base model 对比
- [ ] **数据集说明**：来源、规模、构建方法、质量分析

### 🟡 强烈建议补充（显著提升论文质量）

- [ ] **eval 集接入训练**：train/eval loss 双曲线，证明没有过拟合
- [ ] **消融实验**：不同 epoch、不同 LoRA rank 的效果对比
- [ ] **错误分析**：模型在哪类样本上失败，为什么
- [ ] **Human evaluation**：至少 50 条人工评分

### 🟢 加分项（有余力再做）

- [ ] **Case study**：展示 3-5 个典型的好/坏输出对比
- [ ] **多模型对比**：0.6B vs 1.7B vs 7B
- [ ] **HuggingFace 发布**：model card + 数据集上传

---

## 三、Step-by-Step 执行路径

### Step 1：推理验证（1-2天）

写一个推理测试脚本，验证模型能否正确调用工具：

```python
# src/eval/inference_test.py
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("models/Qwen3-1.7B-Base")
model = PeftModel.from_pretrained(model, "models/Qwen3-1.7B-Base_lora_last_assistant")
tokenizer = AutoTokenizer.from_pretrained("models/Qwen3-1.7B-Base")

# 给几个测试 prompt，看输出是否包含正确的工具调用
test_prompts = [
    "帮我创建一个针对18-25岁游戏用户的广告活动",
    "分析这个广告活动的投放效果",
]
```

**判断标准：**
- 模型输出中包含正确的工具名称？
- 工具参数填写合理？
- 输出格式符合预期（JSON/函数调用格式）？

---

### Step 2：定量评估指标（3-5天）

这是论文的核心贡献，需要写评估脚本：

```python
# src/eval/evaluate.py

def tool_call_accuracy(predictions, ground_truths):
    """
    指标1：工具选择准确率
    预测的工具名称 == 真实工具名称
    """
    correct = 0
    for pred, gt in zip(predictions, ground_truths):
        if extract_tool_name(pred) == extract_tool_name(gt):
            correct += 1
    return correct / len(predictions)

def parameter_accuracy(predictions, ground_truths):
    """
    指标2：参数填写准确率
    预测参数中正确填写的比例
    """
    pass

def format_accuracy(predictions):
    """
    指标3：格式正确率
    输出是否符合 JSON/函数调用格式，能否被解析
    """
    pass
```

**结果表格格式（论文里长这样）：**

| Model | Tool Acc | Param Acc | Format Acc |
|-------|----------|-----------|------------|
| Qwen3-1.7B-Base (no FT) | 12.3% | 8.1% | 45.2% |
| + LoRA SFT (ours) | **78.5%** | **71.2%** | **95.3%** |

---

### Step 3：数据集分析（1-2天）

补充数据章节，让 reviewer 信任你的数据质量：

```python
# src/analysis/dataset_analysis.py
import json
import matplotlib.pyplot as plt

# 需要展示的图表：
# 1. 对话轮数分布（histogram）
# 2. 序列长度分布（histogram）
# 3. 工具调用频率分布（bar chart）
# 4. 数据集 split 统计（train/eval 比例）

data = json.load(open("data/ready2train/..."))

lengths = [len(sample["messages"]) for sample in data]
plt.hist(lengths, bins=20)
plt.xlabel("Number of turns")
plt.ylabel("Count")
plt.title("Conversation Length Distribution")
plt.savefig("figures/data_distribution.png")
```

**数据章节需要回答的问题：**
- 数据从哪来？（rule-based 生成？GPT-4 生成？人工标注？）
- 如何保证质量？（过滤规则、人工审核比例）
- 数据多样性如何？（覆盖了哪些广告场景和工具）

---

### Step 4：Baseline 对比（1天）

最低要求：和未微调的 base model 跑同样的 eval：

```bash
# 在 run_eval.sh 里加 baseline 评估
# 不加载 LoRA adapter，直接用 base model 推理
python3 src/eval/evaluate.py \
  --model_path models/Qwen3-1.7B-Base \
  --eval_file data/test/... \
  --output baseline_results.json

# 加载 LoRA adapter 评估
python3 src/eval/evaluate.py \
  --model_path models/Qwen3-1.7B-Base \
  --lora_path models/Qwen3-1.7B-Base_lora_last_assistant \
  --eval_file data/test/... \
  --output sft_results.json
```

---

### Step 5：消融实验（2-3天，可选但加分）

用 wandb Sweeps 或手动跑，对比关键超参：

```yaml
# 消融1：LoRA rank 的影响
实验A: lora_r=16  → tool_acc=?
实验B: lora_r=32  → tool_acc=?  ← 当前
实验C: lora_r=64  → tool_acc=?

# 消融2：训练轮数的影响
实验A: epoch=1  → tool_acc=?  ← 当前
实验B: epoch=2  → tool_acc=?
实验C: epoch=3  → tool_acc=?

# 消融3：loss masking 策略
实验A: only_last_assistant=True   ← 当前
实验B: only_last_assistant=False  （所有 assistant 都计算 loss）
```

---

### Step 6：写作（1周）

#### Abstract 模板
```
We present [项目名], a supervised fine-tuning approach for 
mobile game advertising agents based on [数据集规模] 
multi-turn conversation samples. Using LoRA fine-tuning on 
Qwen3-1.7B-Base, our model achieves [X]% tool call accuracy 
on held-out test data, compared to [Y]% for the untuned 
baseline. We release our training pipeline and dataset at 
[HuggingFace URL].
```

#### Introduction 结构
1. 背景：移动广告 + Agent 的需求
2. 挑战：通用 LLM 不会正确调用广告工具
3. 我们的方案：构建数据集 + SFT 微调
4. 贡献列表（3条，bullet points）
5. 论文结构（"The rest of the paper is organized as..."）

---

## 四、数据质量提升（如果想更进一步）

当前数据是 rule-based 生成，reviewer 可能质疑真实性。
提升方案按成本排序：

| 方案 | 成本 | 效果 |
|------|------|------|
| 增加数据多样性（更多广告场景） | 低 | 中 |
| 用 GPT-4 重写低质量样本 | 中 | 高 |
| 招募标注员人工标注 100 条 | 中 | 高 |
| 真实广告平台数据（需合规）| 高 | 很高 |

最低成本的提升：**写清楚数据构建的每一步**，让读者能复现，这比数据规模更重要。

---

## 五、发布 Checklist（投稿前）

```
HuggingFace
- [ ] 上传模型 adapter 到 HuggingFace Hub
- [ ] 写 model card（包含：用途、限制、训练细节、示例输出）
- [ ] 上传数据集（如果允许公开）

代码
- [ ] GitHub README 完善（安装、使用、复现步骤）
- [ ] requirements.txt / pyproject.toml 完整
- [ ] 添加 LICENSE

论文
- [ ] 用 LaTeX 写（overleaf.com，免费）
- [ ] 图表分辨率 >= 300 DPI
- [ ] 投稿前用 grammarly 检查英文
- [ ] arXiv 分类选：cs.CL 或 cs.AI
```

---

## 六、时间估算

| 任务 | 预计时间 | 优先级 |
|------|----------|--------|
| 推理验证脚本 | 1天 | 🔴 必须 |
| 定量评估指标 | 3天 | 🔴 必须 |
| 数据集分析图表 | 1天 | 🔴 必须 |
| Baseline 对比 | 1天 | 🔴 必须 |
| eval 集接入训练 | 0.5天 | 🟡 建议 |
| 消融实验 | 2天 | 🟡 建议 |
| 论文写作 | 5天 | — |
| **总计** | **~2周** | — |

---

## 七、最低可发布版本（MVP）

如果时间紧，至少做到这四件事就能发 arXiv technical report：

1. ✅ 推理脚本，展示 3-5 个输出样例
2. ✅ Tool call accuracy vs baseline 的对比数字
3. ✅ wandb loss 曲线截图
4. ✅ HuggingFace model card

这个版本足够放进 PhD 申请作品集，证明你有完整的 end-to-end ML 项目经验。
