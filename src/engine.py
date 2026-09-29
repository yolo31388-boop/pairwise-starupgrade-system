"""装备升星突破系统"""
import logging
import random

logger = logging.getLogger("starupgrade")


class Equipment:
    """装备。星级带掉星保护：单次赋值最多掉 1 星，直接赋更低值会被钳制。"""

    def __init__(self, eid, star=0, level=1, base_atk=100):
        self.eid = eid
        self._star = 0
        self.level = level
        self.base_atk = base_atk
        self.tier = 0
        self.star = star

    @property
    def star(self):
        return self._star

    @star.setter
    def star(self, value):
        value = max(0, int(value))
        if value < self._star - 1:
            value = self._star - 1
        self._star = value

    def reset_star(self):
        self._star = 0

    def __repr__(self):
        return (f"Equipment(eid={self.eid!r}, star={self._star}, "
                f"level={self.level}, base_atk={self.base_atk}, tier={self.tier})")


class StarUpgradeSystem:
    MAX_STAR = 10
    PITY_LIMIT = 20
    CHARM_RATE_BONUS = 0.2
    MATERIAL_BASE_COST = 10
    BREAKTHROUGH_LEVEL_STEP = 10

    SUCCESS_RATES = {
        0: 0.95, 1: 0.92, 2: 0.89, 3: 0.86, 4: 0.83,
        5: 0.80, 6: 0.77, 7: 0.74, 8: 0.71, 9: 0.68,
    }

    def __init__(self):
        self.equipment: dict[str, Equipment] = {}
        self.pity: dict[str, int] = {}
        self.protect_charms = 0
        self.charm_active: dict[str, int] = {}
        self.materials: dict[str, int] = {}
        self.buffs: dict[str, dict[str, list[float]]] = {}
        self.logs: list[dict] = []

    def get_success_rate(self, star):
        if star in self.SUCCESS_RATES:
            return self.SUCCESS_RATES[star]
        return min(self.SUCCESS_RATES.values())

    def get_material_cost(self, star):
        return self.MATERIAL_BASE_COST * (star + 1)

    def add_materials(self, eid, count):
        self.materials[eid] = self.materials.get(eid, 0) + count

    def use_protect_charm(self, eid):
        """保护符：提高下一次升星成功率（上限100%）且失败不掉星，不再直接必成。"""
        self.protect_charms += 1
        self.charm_active[eid] = self.charm_active.get(eid, 0) + 1
        return True

    def upgrade(self, eid):
        eq = self.equipment[eid]
        if eq.star >= self.MAX_STAR:
            self._log(eid, eq.star, 0.0, "已满星")
            return False
        cost = self.get_material_cost(eq.star)
        if eid in self.materials:
            if self.materials[eid] < cost:
                self._log(eid, eq.star, 0.0, "材料不足", cost=cost)
                return False
            self.materials[eid] -= cost
        base_rate = self.get_success_rate(eq.star)
        charms = self.charm_active.get(eid, 0)
        rate = min(1.0, base_rate + self.CHARM_RATE_BONUS * charms)
        guaranteed = self.pity.get(eid, 0) >= self.PITY_LIMIT
        success = guaranteed or random.random() < rate
        if success:
            eq.star += 1
            self.pity[eid] = 0
        else:
            self.pity[eid] = self.pity.get(eid, 0) + 1
            if charms == 0:
                eq.star -= 1
        if charms:
            self.charm_active[eid] = 0
        self._log(eid, eq.star, rate, "成功" if success else "失败",
                  guaranteed=guaranteed, cost=cost, pity=self.pity[eid])
        return success

    def breakthrough(self, eid):
        eq = self.equipment[eid]
        required_level = (eq.tier + 1) * self.BREAKTHROUGH_LEVEL_STEP
        if eq.star >= self.MAX_STAR and eq.level >= required_level:
            eq.tier += 1
            eq.reset_star()
            self.pity[eid] = 0
            self._log(eid, eq.star, 1.0, "突破成功", tier=eq.tier)
            return True
        self._log(eid, eq.star, 0.0, "突破条件不足",
                  required_level=required_level)
        return False

    def transfer(self, src_eid, dst_eid):
        """传承：把源装备的升星等级和保底计数转移到新装备。"""
        src = self.equipment[src_eid]
        dst = self.equipment[dst_eid]
        dst.reset_star()
        dst.star = src.star
        src.reset_star()
        self.pity[dst_eid] = self.pity.get(src_eid, 0)
        self.pity[src_eid] = 0
        self._log(dst_eid, dst.star, 1.0, "传承", src=src_eid)
        return True

    def add_buff(self, eid, zone, value):
        self.buffs.setdefault(eid, {}).setdefault(zone, []).append(value)

    def get_atk(self, eid):
        """同类（同乘区）加成加法合并，异类（不同乘区）之间乘法叠加。"""
        eq = self.equipment[eid]
        zones = {zone: sum(values)
                 for zone, values in self.buffs.get(eid, {}).items()}
        zones["star"] = zones.get("star", 0.0) + eq.star * 0.1
        atk = eq.base_atk
        for zone_bonus in zones.values():
            atk *= (1 + zone_bonus)
        return atk

    def _log(self, eid, star, rate, result, **extra):
        entry = {"eid": eid, "star": star, "rate": rate,
                 "result": result, **extra}
        self.logs.append(entry)
        logger.info("starupgrade %s", entry)
