# LLM 语义解释智能体
## 项目：多智能体协同网络安全态势感知系统
## 功能说明
接收**被动攻击检测**与**主动端口扫描**结果，
通过 RAG 威胁知识库 + DeepSeek 大模型，
**自动生成专业、分点、可直接展示的安全分析报告**。

---

## 对外接口（中枢Agent直接调用）
```python
from llm_agent import llm_explain_agent

# 被动检测
report = llm_explain_agent(detection_result, is_passive=True)

# 主动检测
report = llm_explain_agent(scan_result, is_passive=False)