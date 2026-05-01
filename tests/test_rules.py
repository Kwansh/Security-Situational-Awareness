"""
测试规则引擎 - 项目 2 的核心测试
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection.rule_engine import RuleEngine, RuleTrigger


class TestRuleEngine:
    """测试规则引擎"""
    
    def test_initialization(self):
        """测试初始化"""
        engine = RuleEngine()
        assert engine.thresholds["syn_flood_per_sec"] == 500
    
    def test_syn_flood_detection(self):
        """测试 SYN Flood 检测"""
        engine = RuleEngine()
        
        # 正常流量
        features = {"syn_rate": 100}
        result = engine.detect_syn_flood(features)
        assert result is None
        
        # 攻击流量
        features = {"syn_rate": 600}
        result = engine.detect_syn_flood(features)
        assert result is not None
        assert result.severity in ["high", "critical"]
    
    def test_udp_flood_detection(self):
        """测试 UDP Flood 检测"""
        engine = RuleEngine()
        
        # 正常流量
        features = {"udp_rate": 1000}
        result = engine.detect_udp_flood(features)
        assert result is None
        
        # 攻击流量
        features = {"udp_rate": 15000}
        result = engine.detect_udp_flood(features)
        assert result is not None
    
    def test_dns_flood_detection(self):
        """测试 DNS Flood 检测"""
        engine = RuleEngine()
        
        # 正常流量
        features = {"dns_rate": 100}
        result = engine.detect_dns_flood(features)
        assert result is None
        
        # 攻击流量
        features = {"dns_rate": 3000}
        result = engine.detect_dns_flood(features)
        assert result is not None
    
    def test_sql_injection_detection(self):
        """测试 SQL 注入检测"""
        engine = RuleEngine()
        
        # 正常流量
        features = {"payload": "SELECT * FROM users WHERE id=1"}
        result = engine.detect_sql_injection(features)
        assert result is None
        
        # 攻击流量
        features = {"payload": "SELECT * FROM users WHERE id=1 OR 1=1; DROP TABLE users--"}
        result = engine.detect_sql_injection(features)
        assert result is not None
    
    def test_full_detection(self):
        """测试完整检测流程"""
        engine = RuleEngine()
        
        # 正常流量
        features = {
            "pkt_rate": 100,
            "syn_rate": 10,
            "udp_rate": 50,
            "dns_rate": 5,
            "ntp_rate": 1,
            "avg_pkt_size": 500,
        }
        result = engine.detect(features)
        assert result.is_attack == False
        assert result.attack_type == "NORMAL"
        
        # 攻击流量
        features = {
            "pkt_rate": 10000,
            "syn_rate": 600,
            "udp_rate": 50,
            "dns_rate": 5,
            "ntp_rate": 1,
            "avg_pkt_size": 50,
        }
        result = engine.detect(features)
        assert result.is_attack == True
        assert "SYN_FLOOD" in result.attack_type
    
    def test_custom_thresholds(self):
        """测试自定义阈值"""
        config = {
            "rule_thresholds": {
                "syn_flood_per_sec": 100,
            }
        }
        engine = RuleEngine(config)
        
        features = {"syn_rate": 150}
        result = engine.detect_syn_flood(features)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
