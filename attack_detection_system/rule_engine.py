import pandas as pd
import re

class RuleEngine:
    def __init__(self):
        self.syn_threshold = 500
        self.udp_threshold = 10000
        self.dns_threshold = 2000

    def detect_syn_flood(self, df):
        condition = df["syn_count_per_sec"] > self.syn_threshold
        df.loc[condition, "rule_attack_type"] = "SYN_FLOOD"
        return df

    def detect_udp_flood(self, df):
        condition = df["udp_count_per_min"] > self.udp_threshold
        df.loc[condition, "rule_attack_type"] = "UDP_FLOOD"
        return df

    def detect_dns_flood(self, df):
        condition = df["dns_query_count"] > self.dns_threshold
        df.loc[condition, "rule_attack_type"] = "DNS_FLOOD"
        return df

    def detect_sql_injection(self, df):
        keywords = r"(union|select|or 1=1|drop|insert|update)"
        df["sql_flag"] = df["payload"].astype(str).apply(
            lambda x: 1 if re.search(keywords, x, re.IGNORECASE) else 0
        )
        df.loc[df["sql_flag"] == 1, "rule_attack_type"] = "SQL_INJECTION"
        return df

    def run_rules(self, df):
        df["rule_attack_type"] = "NORMAL"
        df = self.detect_syn_flood(df)
        df = self.detect_udp_flood(df)
        df = self.detect_dns_flood(df)
        df = self.detect_sql_injection(df)
        return df