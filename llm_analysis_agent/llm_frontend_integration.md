# LLM 语义解释智能体 - 前端接入说明

这份文档用于前端/中枢Agent接入LLM解释模块，接收检测结果，生成专业安全分析报告。

## 1. 当前提供能力

LLM 智能体提供以下核心能力：

1. 攻击结果自然语言解释
   - 输入被动检测结果 → 输出专业分析报告
2. 主动扫描结果自然语言解释
   - 输入端口扫描结果 → 输出安全分析报告
3. **RAG 威胁知识库增强**
   - 基于攻击类型自动检索说明、危害、防御方案
4. 结构化报告生成
   - 分点、可读、可直接展示在大屏/页面

## 2. 页面可使用场景

前端可在以下位置调用LLM解释：

1. 被动检测结果页
   - 展示“模型解释”“攻击说明”“防御建议”
2. 主动扫描结果页
   - 展示扫描总结、风险分析、加固建议
3. 安全事件详情页
   - 展示完整自然语言分析报告
4. 大屏/仪表盘
   - 展示自动生成的安全态势说明

## 3. LLM 统一接口

### 3.1 解释被动检测结果
函数接口：
```python
llm_explain_agent(result_data, is_passive=True)
```

功能：
- 输入攻击检测结果
- 返回自然语言分析报告（可直接展示）

输入示例（来自 /predict 返回）：
```json
{
  "is_attack": true,
  "attack_type": "synflood",
  "confidence": 0.98,
  "severity": "高",
  "summary": "SYN包频率异常",
  "rule_evidence": "rule_synflood_001",
  "recommendations": ["限流"],
  "dynamic_metrics": {}
}
```

返回示例：
```
1. 检测结果：当前流量为SYN Flood拒绝服务攻击，置信度0.98，风险等级高。
2. 攻击说明：攻击者发送大量伪造TCP连接请求，耗尽服务器连接资源。
3. 风险危害：可能导致服务不可用、系统负载飙升、业务中断。
4. 防御建议：启用SYN Cookie、限制单IP连接、防火墙限流、拉黑攻击源。
```

### 3.2 解释主动扫描结果
函数接口：
```python
llm_explain_agent(result_data, is_passive=False)
```

功能：
- 输入端口扫描结果
- 返回自然语言扫描分析报告

输入示例（来自 /api/active-scan 返回）：
```json
{
  "summary": "对 127.0.0.1 端口扫描完成",
  "findings": "80、443端口开放",
  "recommendations": ["关闭无用端口"],
  "errors": ""
}
```

返回示例：
```
1. 扫描结果：已完成对 127.0.0.1 的端口探测。
2. 发现情况：80、443端口开放，可能存在对外暴露风险。
3. 安全建议：关闭非必要端口，加强防火墙策略。
4. 处置意见：定期端口巡检，避免弱服务暴露。
```

## 4. 前端如何使用

### 4.1 被动检测结果页使用
1. 前端获取 `/predict` 的结果
2. 传给 LLM 接口
3. 直接展示返回的文本报告

### 4.2 主动扫描结果页使用
1. 前端获取 `/api/active-scan` 的结果
2. 传给 LLM 接口
3. 直接展示返回的文本报告

## 5. 输入字段说明

### 5.1 被动检测必须字段
- is_attack
- attack_type
- confidence
- severity
- summary
- rule_evidence
- recommendations

### 5.2 主动检测必须字段
- summary
- findings
- recommendations
- errors

## 6. 输出格式
纯文本字符串，带数字分点，结构清晰，可直接渲染在页面。

## 7. 接入最小示例
```python
from llm_agent import llm_explain_agent

# 被动检测
report = llm_explain_agent(predict_result, is_passive=True)

# 主动检测
report = llm_explain_agent(scan_result, is_passive=False)
```

## 8. 作用与价值
- 让检测结果“可读懂”
- 提供标准化安全报告
- 提供 RAG 知识库增强解释
- 提升态势感知系统可读性
- 可直接用于大屏展示
