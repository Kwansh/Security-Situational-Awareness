import os
import json
from openai import OpenAI

# ============================ 知识库加载 ============================
def load_knowledge_base():
    # 🔥 修复 1：改为绝对路径，确保 FastAPI 导入时不会报找不到文件的错
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "attack_knowledge.json")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_attack_info(attack_type):
    kb = load_knowledge_base()
    return kb.get(attack_type, kb["unknown"])

# ============================ LLM 配置 ============================
API_KEY = "sk-767d063d79bf4248ada8754fa8fb06f8"
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

# ============================ 被动检测报告 ============================
def generate_passive_report(result_data):
    attack_type = result_data.get("attack_type", "unknown")
    info = get_attack_info(attack_type)

    # 🔥 修复 2：安全处理置信度，防止传参为 None 或字符串时导致格式化崩溃
    confidence = result_data.get('confidence')
    try:
        confidence_val = float(confidence) if confidence is not None else 0.0
    except ValueError:
        confidence_val = 0.0

    prompt = f"""
你是专业网络安全分析师，请根据攻击检测结果生成正式安全报告。
规则：
1. 仅使用 1、2、3、4 数字分点，纯文本，不要加粗、不要斜体、不要任何特殊格式。
2. 语言简洁专业，可直接在页面展示。
3. 严格按照以下结构输出。

检测信息：
是否攻击：{result_data.get('is_attack')}
攻击类型：{info['name']}
置信度：{confidence_val:.2f}
风险等级：{result_data.get('severity')}
系统摘要：{result_data.get('summary')}
规则证据：{result_data.get('rule_evidence')}
当前流量实际指标：{result_data.get('dynamic_metrics')}

攻击知识：
典型技术特征：{info.get('technical_indicators', '暂无特定技术指标')}
{info['description']}
危害：{info['harm']}
防御：{info['defense']}

输出结构：
1. 检测结果：说明是否攻击、类型、置信度、风险等级与系统摘要
2. 攻击说明：简要说明攻击原理
3. 风险危害：说明可能造成的影响
4. 防御建议：给出可落地的防御措施
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-flash", # 如果官方接口报错，请改成 "deepseek-chat"
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            stream=False,
            timeout=15.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM API Error: {e}")
        return "1. 系统提示：AI 分析引擎网络连接异常。\n2. 当前状态：无法调用大模型生成深度报告，请直接参考上方基础检测结果。"

# ============================ 主动扫描报告 ============================
def generate_active_report(result_data):
    prompt = f"""
你是网络安全分析师，请根据端口扫描结果生成简洁正式的安全报告。
规则：
1. 仅使用 1、2、3、4 数字分点，纯文本，不要加粗、不要斜体、不要任何格式。
2. 重点说明开放端口风险与加固建议。
3. 可直接用于前端页面展示。

扫描信息：
扫描摘要：{result_data.get('summary')}
发现结果：{result_data.get('findings')}
安全建议：{result_data.get('recommendations')}
错误信息：{result_data.get('errors')}

输出结构：
1. 扫描结果：说明扫描目标、完成状态与开放端口情况
2. 风险分析：分析开放端口带来的潜在风险
3. 安全建议：给出具体可落地的加固措施
4. 注意事项：扫描相关说明
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # 如果官方接口报错，请改成 "deepseek-chat"
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            stream=False,
            timeout=15.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM API Error: {e}")
        return "1. 系统提示：AI 分析引擎网络连接异常。\n2. 当前状态：无法调用大模型生成深度报告，请直接参考上方基础检测结果。"

# ============================ 对外统一接口（对接关关 + 后端） ============================
def llm_explain_agent(result_data, is_passive=True):
    if is_passive:
        return generate_passive_report(result_data)
    else:
        return generate_active_report(result_data)

# ============================ 测试 ============================
if __name__ == "__main__":
    passive_data = {
        "is_attack": True,
        "attack_type": "synflood",
        "confidence": 0.98,
        "severity": "高",
        "summary": "SYN包速率异常，半连接数过高",
        "recommendations": ["限流", "拉黑IP"],
        "dynamic_metrics": {"syn_count": 1200, "pkt_len": 64},
        "rule_evidence": "rule_synflood_001"
    }

    print("===== 被动检测报告 =====")
    print(llm_explain_agent(passive_data, is_passive=True))