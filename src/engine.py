"""装备升星突破系统"""
from dataclasses import dataclass
import logging
import random

logger = logging.getLogger("starupgrade")

DEFAULT_CONFIG = {
    "success_rate": 0.8,          # 默认成功率（显示与实际严格一致）
    "success_rates": None,        # dict[int, float] | None，按星级单独覆盖
    "pity_threshold": 20,         # 连续失败 N 次后下一次必成
    "material_base_cost": 10,     # 材料消耗 = base * (star + 1)，随星级递增
    "max_star": 10,
    "breakthrough_min_level": 10,  # 突破所需最低角色等级
    "star_atk_bonus": 0.1,         # 升星乘区：每星 +10% 攻击（同区加法）
    "breakthrough_atk_bonus": 0.2,  # 突破乘区：每阶 +20% 攻击（同区加法）
    "charm_rate_bonus": 0.2,       # 保护符：下一次升星成功率 +20%（封顶 100%）
    "protected_star_floor": 3,   # 掉星保护：星级低于该值时失败不再掉星
}


@dataclass
class Equipment:
    eid: str
    star: int = 0
    level: int = 1
    base_atk: float = 100
    breakthrough: int = 0

    def __setattr__(self, name, value):
        # 掉星保护：直接赋值一次最多掉 1 星，杜绝"失败直接掉 0 星"
        if name == "star":
            current = self.__dict__.get("star")
            if (
                current is not None
                and isinstance(value, (int, float))
                and value < current - 1
            ):
                value = max(current - 1, 0)
        object.__setattr__(self, name, value)

    def reset_star(self, value: int = 0) -> None:
        """内部接口：突破 / 传承时重置星级，绕过掉星保护。"""
        object.__setattr__(self, "star", value)


class StarUpgradeSystem:
    def __init__(self, config=None, rng=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.equipment: dict[str, Equipment] = {}
        self.pity: dict[str, int] = {}   # 连续失败计数（保底，可随传承继承）
        self.protect_charms: int = 0
        self.materials: int = 0
        self.history: list[dict] = []    # 升星日志（内存可查，同时写 logging）
        self._charm_active: set[str] = set()
        self._rng = rng if rng is not None else random

    # ---- 配置查询 ----

    def get_success_rate(self, star: int) -> float:
        """配置成功率：展示与实际判定使用同一个值。"""
        rates = self.config.get("success_rates")
        if rates and star in rates:
            return rates[star]
        return self.config["success_rate"]

    def get_material_cost(self, star: int) -> int:
        """材料消耗随星级递增：base * (star + 1)，高星消耗更多。"""
        return self.config["material_base_cost"] * (star + 1)

    def get_effective_rate(self, eid: str) -> float:
        """实际成功率 = 配置成功率 + 保护符加成，封顶 100%。"""
        eq = self.equipment[eid]
        rate = self.get_success_rate(eq.star)
        if eid in self._charm_active:
            rate += self.config["charm_rate_bonus"]
        return min(1.0, rate)

    def add_materials(self, n: int) -> None:
        self.materials += n

    def add_protect_charms(self, n: int) -> None:
        self.protect_charms += n

    # ---- 升星 ----

    def upgrade(self, eid: str) -> bool:
        eq = self.equipment[eid]
        max_star = self.config["max_star"]
        if eq.star >= max_star:
            logger.info("升星跳过 eid=%s 已满星(%d)", eid, max_star)
            return False

        star_before = eq.star
        cost = self.get_material_cost(star_before)
        self.materials = max(0, self.materials - cost)

        base_rate = self.get_success_rate(star_before)  # 实际判定用的就是配置值
        charm_used = eid in self._charm_active
        rate = self.get_effective_rate(eid)

        pity_before = self.pity.get(eid, 0)
        guaranteed = pity_before >= self.config["pity_threshold"]
        success = guaranteed or self._rng.random() < rate

        if success:
            eq.star = star_before + 1
            self.pity[eid] = 0
        else:
            self.pity[eid] = pity_before + 1
            # 失败只掉 1 星；保护符生效或处于低星保护带则不掉
            if not charm_used and star_before >= self.config["protected_star_floor"]:
                eq.star = star_before - 1

        if charm_used:
            self._charm_active.discard(eid)

        record = {
            "eid": eid,
            "star_before": star_before,
            "star_after": eq.star,
            "base_rate": base_rate,
            "charm_used": charm_used,
            "effective_rate": rate,
            "guaranteed": guaranteed,
            "material_cost": cost,
            "success": success,
            "pity": self.pity[eid],
        }
        self.history.append(record)
        logger.info(
            "升星 eid=%s %d->%d 成功率=%.2f(配置%.2f%s) 材料=%d 保底计数=%d %s",
            eid, star_before, eq.star, rate, base_rate,
            "+保护符" if charm_used else "", cost, self.pity[eid],
            "成功" if success else "失败",
        )
        return success

    # ---- 突破 ----

    def breakthrough(self, eid: str) -> bool:
        """突破：同时检查星级与角色等级，缺一不可。"""
        eq = self.equipment[eid]
        min_level = self.config["breakthrough_min_level"]
        if eq.star >= self.config["max_star"] and eq.level >= min_level:
            eq.breakthrough += 1
            eq.reset_star(0)
            logger.info("突破成功 eid=%s 突破阶=%d", eid, eq.breakthrough)
            return True
        logger.info(
            "突破失败 eid=%s 需要星级>=%d且等级>=%d，当前星级=%d等级=%d",
            eid, self.config["max_star"], min_level, eq.star, eq.level,
        )
        return False

    # ---- 传承 ----

    def inherit(self, source_eid: str, target_eid: str) -> bool:
        """传承：升星等级与保底计数一起转移到新装备，换装备不再重新升星。"""
        src = self.equipment[source_eid]
        dst = self.equipment[target_eid]
        dst.reset_star(src.star)
        src.reset_star(0)
        self.pity[target_eid] = max(
            self.pity.get(target_eid, 0), self.pity.pop(source_eid, 0)
        )
        logger.info(
            "传承 %s -> %s 星级=%d 保底计数=%d",
            source_eid, target_eid, dst.star, self.pity[target_eid],
        )
        return True

    # ---- 属性 ----

    def _atk_bonus_groups(self, eq: Equipment) -> dict:
        # 每个乘区内部是加法列表；乘区之间由 get_atk 做乘法
        return {
            "star": [self.config["star_atk_bonus"]] * eq.star,
            "breakthrough": [self.config["breakthrough_atk_bonus"]] * eq.breakthrough,
        }

    def get_atk(self, eid: str) -> float:
        """同类加成加法叠加，异类乘区之间乘法。"""
        eq = self.equipment[eid]
        atk = eq.base_atk
        for group in self._atk_bonus_groups(eq).values():
            atk *= 1.0 + sum(group)
        return atk

    # ---- 保护符 ----

    def use_protect_charm(self, eid: str) -> bool:
        """保护符：下一次升星成功率 +charm_rate_bonus（封顶 100%），且失败不掉星。

        不再直接必成；下一次 upgrade 判定后消耗。
        """
        if self.protect_charms <= 0:
            return False
        self.protect_charms -= 1
        self._charm_active.add(eid)
        logger.info("保护符生效 eid=%s 剩余=%d", eid, self.protect_charms)
        return True
