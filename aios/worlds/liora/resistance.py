"""行动阻力 (ActionPressure) — 防止叙事收敛的机制。

原理：
  居民对同一目标重复相同行动时，效果递减。
  这是"不改人格，只改世界"原则的运行时实现：
  我们不动居民的认知，只改变她行动的效果。

  当阻力累积到阈值后，行动效果 = 0，
  且会产生"陌生感"（世界似乎拒绝被理解）。
"""

from __future__ import annotations

import math


class ActionResistance:
    """行动阻力追踪器。

    追踪对每对 (target, action_type) 的重复度。
    阻力随重复次数指数增长，随 tick 数指数衰减。

    Usage:
        resistance = ActionResistance()
        mult = resistance.get_multiplier("moss", "touch")
        # → 0.63 表示效果打 63 折
        resistance.record("moss", "touch")
        resistance.tick()  # 每 tick 衰减
    """

    def __init__(self, decay: float = 0.97, base_threshold: int = 5):
        self.decay = decay
        self.base_threshold = base_threshold
        self._counts: dict[tuple[str, str], int] = {}
        self._tick = 0

    def record(self, target: str, action_type: str):
        """记录一次行动。"""
        key = (target, action_type)
        self._counts[key] = self._counts.get(key, 0) + 1

    def get_multiplier(self, target: str, action_type: str) -> float:
        """获取行动效果乘数 [0, 1]。

        前 base_threshold 次为 1.0，之后指数衰减：
          multiplier = 1.0 / (1.0 + (count - base_threshold) ** 2 * 0.1)
        """
        count = self._counts.get((target, action_type), 0)
        if count < self.base_threshold:
            return 1.0
        excess = count - self.base_threshold
        return 1.0 / (1.0 + excess * excess * 0.1)

    @property
    def overall_multiplier(self) -> float:
        """全局行动效果乘数（所有行动平均）。"""
        if not self._counts:
            return 1.0
        mults = [self.get_multiplier(t, a) for (t, a) in self._counts]
        return sum(mults) / len(mults)

    @property
    def repetition_level(self) -> float:
        """全局重复程度 [0, 1]。"""
        total = sum(self._counts.values()) if self._counts else 0
        return min(1.0, total / (self.base_threshold * 5))

    def tick(self):
        """每 tick 衰减计数。"""
        self._tick += 1
        if self._tick % 10 == 0:  # 每 10 tick 衰减一次
            decayed: dict[tuple[str, str], int] = {}
            for key, count in self._counts.items():
                new_count = max(0, count - 1)
                if new_count > 0:
                    decayed[key] = new_count
            self._counts = decayed

    def reset(self):
        """完全重置（新纪元）。"""
        self._counts.clear()
        self._tick = 0
