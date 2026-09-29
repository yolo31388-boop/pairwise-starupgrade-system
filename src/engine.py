"""装备升星突破 - 带8个bug"""
from dataclasses import dataclass, field
import random

@dataclass
class Equipment:
    eid: str
    star: int = 0
    level: int = 1
    base_atk: float = 100

class StarUpgradeSystem:
    def __init__(self):
        self.equipment: dict[str, Equipment] = {}
        self.pity = {}  # bug2: 无保底
        self.protect_charms = 0

    def get_success_rate(self, star):
        # bug1: 显示80%实际20%
        return 0.8

    def upgrade(self, eid):
        eq = self.equipment[eid]
        # bug3: 固定材料消耗
        materials_needed = 10
        # bug4: 不检查等级
        actual_rate = 0.2  # bug1
        if random.random() < actual_rate:
            eq.star += 1
            return True
        else:
            # bug5: 直接掉0星
            eq.star = 0
            return False

    def breakthrough(self, eid):
        eq = self.equipment[eid]
        # bug4: 只检查星级
        if eq.star >= 10:
            eq.level += 1
            eq.star = 0
            return True
        return False

    def get_atk(self, eid):
        eq = self.equipment[eid]
        # bug7: 加法叠加
        return eq.base_atk * (1 + eq.star * 0.1)

    def use_protect_charm(self, eid):
        # bug8: 直接必成
        self.equipment[eid].star += 1
        return True
