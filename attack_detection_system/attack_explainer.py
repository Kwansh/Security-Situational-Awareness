import pandas as pd
import numpy as np

class AttackExplainer:
    def __init__(self):
        self.rule_descriptions = {
            "SYN_FLOOD": "检测到SYN Flood攻击：每秒SYN包数量超过{}个，可能为DDoS攻击。",
            "UDP_FLOOD": "检测到UDP Flood攻击：每分钟UDP包数量超过{}个，占用大量带宽。",
            "DNS_FLOOD": "检测到DNS Flood攻击：DNS查询次数超过{}次/秒，试图耗尽DNS服务器资源。",
            "SQL_INJECTION": "检测到SQL注入攻击：数据包中包含SQL注入关键字，试图操纵数据库。",
            "NORMAL": "正常流量，无明显攻击特征。"
        }

    def explain_rule(self, row):
        """生成规则检测的解释"""
        attack_type = row.get("rule_attack_type", "NORMAL")
        if attack_type == "SYN_FLOOD":
            return self.rule_descriptions["SYN_FLOOD"].format(row.get("syn_count_per_sec", "?"))
        elif attack_type == "UDP_FLOOD":
            return self.rule_descriptions["UDP_FLOOD"].format(row.get("udp_count_per_min", "?"))
        elif attack_type == "DNS_FLOOD":
            return self.rule_descriptions["DNS_FLOOD"].format(row.get("dns_query_count", "?"))
        elif attack_type == "SQL_INJECTION":
            return self.rule_descriptions["SQL_INJECTION"]
        else:
            return self.rule_descriptions["NORMAL"]

    def explain_ml(self, row):
        """生成机器学习检测的解释"""
        pred = row.get("ml_prediction", 0)
        anomaly = row.get("anomaly_score", 1)
        if pred == 1:
            return "机器学习模型识别为攻击流量（逻辑回归预测为攻击）。"
        else:
            if anomaly == -1:
                return "孤立森林检测为异常，但逻辑回归判定为正常，可能为未知攻击。"
            else:
                return "机器学习模型判定为正常流量。"

    def generate_explanation(self, df):
        """为每条记录生成综合解释"""
        df["rule_explanation"] = df.apply(self.explain_rule, axis=1)
        df["ml_explanation"] = df.apply(self.explain_ml, axis=1)
        df["final_explanation"] = df["rule_explanation"] + " " + df["ml_explanation"]
        return df