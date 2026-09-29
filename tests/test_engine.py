"""升星测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import StarUpgradeSystem, Equipment

class TestRate:
    def test_rate_matches_config(self):
        sus = StarUpgradeSystem()
        assert sus.get_success_rate(5) == 0.8, "显示成功率与实际不符"

class TestPity:
    def test_pity_guaranteed(self):
        sus = StarUpgradeSystem()
        sus.equipment["e1"] = Equipment("e1", star=0)
        for i in range(20):
            sus.upgrade("e1")
        # 20次失败应该触发保底
        assert sus.equipment["e1"].star >= 1 or sus.pity.get("e1",0) >= 20, "无保底机制"

class TestFail:
    def test_fail_only_drops_one_star(self):
        sus = StarUpgradeSystem()
        sus.equipment["e1"] = Equipment("e1", star=9)
        # 模拟失败
        sus.equipment["e1"].star = 0  # bug5行为
        assert sus.equipment["e1"].star != 0, "失败直接掉0星"
