"""未知信号累积器 — 自指不完备性的核心机制。

原理：
  居民沉默或重复行动时，未知信号累积。
  累积到阈值时，向世界注入无法解释的数值扰动。

  居民无法直接观测此机制。她能感知的只有"未知信号的压力"。
  这就是自指递归的运行时体现：居民的行动（或沉默）改变世界，
  但因果链条在居民的视界之外。

  这 60 行代码取代了 AnotherMe 中的 VoidField + EntropyField + 部分 EventEcology。
"""

from __future__ import annotations

import random
import math

# 可被未知信号扰动的状态变量名
_DISTURBABLE_KEYS = [
    "temperature", "wind_speed", "humidity", "light_level", "pressure",
    "echo_density", "silence_level", "vibration_field",
]


class UnknownAccumulator:
    """未知信号累积器。

    每 tick 根据沉默和重复程度累积 unknown level。
    达到阈值时 emit() 产生一个"未知源扰动"注入世界。

    Usage:
        unknown = UnknownAccumulator()
        unknown.tick(silence_active=True, repetition_level=0.3)
        if unknown.should_emit():
            delta = unknown.emit()
            world_state.apply_delta(delta)
    """

    def __init__(self, decay_rate: float = 0.08, threshold: float = 4.0):
        self.level = 0.0
        self.decay_rate = decay_rate
        self.threshold = threshold
        self._emissions = 0

    @property
    def pressure(self) -> float:
        """归一化压力值 [0, 1]，居民可以感知到但看不懂。"""
        return min(1.0, self.level / self.threshold)

    def tick(self, silence_active: bool, repetition_level: float):
        """每 tick 更新累积水平。

        Args:
            silence_active: 居民当前是否处于沉默状态
            repetition_level: 居民的重复行动程度 [0, 1]
        """
        # 沉默 → 累积
        if silence_active:
            self.level += 0.35
        # 重复行动 → 摩擦生未知
        if repetition_level > 0.3:
            self.level += repetition_level * 0.25
        # 安静无为 → 自然衰减
        if not silence_active and repetition_level <= 0.3:
            self.level = max(0, self.level - self.decay_rate)
        # 硬上限
        self.level = min(10.0, self.level)

    def should_emit(self) -> bool:
        """是否达到阈值，需要释放一次未知扰动。"""
        return self.level >= self.threshold

    def emit(self) -> dict[str, float]:
        """消耗阈值当量的未知信号，产生随机扰动。

        Returns:
            {变量名: delta} 字典，可传给 WorldStateEngine 的 apply_delta()
        """
        self.level = max(0, self.level - self.threshold)
        self._emissions += 1

        # 随机扰动 1~3 个状态变量
        n_vars = random.randint(1, 3)
        targets = random.sample(_DISTURBABLE_KEYS, min(n_vars, len(_DISTURBABLE_KEYS)))
        intensity = min(1.0, self._emissions * 0.1)  # 越往后扰动越强

        delta = {}
        for key in targets:
            delta[key] = random.uniform(-0.3, 0.3) * intensity

        return delta

    def emit_fissure(self) -> str:
        """释放一个裂隙事件——一段不属于任何居民、任何世界模板的文本缺口。

        裂隙不携带预设含义。它是一个空位，
        每个居民在感知到时，会用自己的身份权重填补它。

        Returns:
            一个开放的、不确定的描述。不是信息，是信息缺失处的标记。
        """
        self.level = max(0, self.level - self.threshold)
        self._emissions += 1

        fragments = [
            "▲", "…", "——", "∅",
            "? ? ?", ". . .",
        ]
        return random.choice(fragments)

    def reset(self):
        """完全重置（新纪元/居民重置时）。"""
        self.level = 0.0
        self._emissions = 0
