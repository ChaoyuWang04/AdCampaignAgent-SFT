# `prompts/`

该目录用于存放仓库中可复用的 prompt 资产，而不是 Python 代码。

- 主要内容：
  - system prompt
  - runtime prompt 模板
  - 后续可能补充的评测或调试 prompt

- 当前默认用法：
  - [src/inference/local_toolcall_repl.py](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/src/inference/local_toolcall_repl.py) 默认优先读取 [ad_agent_system_prompt.txt](/Users/samwong/Desktop/1Project/AdCampaignAgent-SFT/prompts/ad_agent_system_prompt.txt)

- 目的：
  - 让 prompt 可以独立于 Python 代码维护和迭代
  - 修改 prompt 时不需要直接改脚本
