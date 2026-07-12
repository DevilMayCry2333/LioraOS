"""Cyberpunk Unknown Accumulator — 夜之城的不确定性累积。

继承 Liora 的 UnknownAccumulator 架构，
增加赛博朋克特有的累积源：

  Liora:      silence + repetition
  Cyberpunk:  silence + repetition + identity_conflict + external_signal + ghost_resonance

当压力超过阈值时，生成一个"数字异常扰动"（替代 Liora 的裂隙扰动）。
"""

from __future__ import annotations

import random
import math

from aios.worlds.liora.unknown import UnknownAccumulator as _LioraAccumulator

# 可被未知信号扰动的变量名
_DISTURBABLE_KEYS = [
    "corporate_grip", "street_heat", "cyberspace_turbulence",
    "humanity_decay", "underground_hope", "data_remnant",
]


class UnknownAccumulator(_LioraAccumulator):
    """夜之城未知信号累积器。

    额外累积源：
    - identity_conflict：居民的信念与行动矛盾时累积
    - external_signal：cyberspace_turbulence 高时外部信号注入
    - ghost_resonance：幽灵活跃时轻微助推

    Usage:
        unknown = UnknownAccumulator()
        unknown.tick(
            silence_active=is_silent,
            repetition_level=resistance.repetition_level,
            identity_conflict_level=0.2,
            ghost_active=True,
        )
        if unknown.should_emit():
            delta = unknown.emit()
    """

    def __init__(self, decay_rate: float = 0.08, threshold: float = 4.0):
        super().__init__(decay_rate=decay_rate, threshold=threshold)
        self._identity_conflict_buffer: float = 0.0
        self._external_signal_buffer: float = 0.0

    def tick(self, silence_active: bool = False,
             repetition_level: float = 0.0,
             identity_conflict_level: float = 0.0,
             external_signal_strength: float = 0.0,
             ghost_active: bool = False):
        """每 tick 更新累积水平，支持赛博朋克的额外累积源。

        Args:
            silence_active: 居民是否沉默
            repetition_level: 行动重复度 [0, 1]
            identity_conflict_level: 身份矛盾程度 [0, 1]
            external_signal_strength: 外部信号强度（cyberspace_turbulence）
            ghost_active: 数字幽灵是否活跃
        """
        # ── 基础累积（继承 Liora） ──
        if silence_active:
            self.level += 0.35
        if repetition_level > 0.3:
            self.level += repetition_level * 0.25
        elif not silence_active and repetition_level <= 0.3:
            self.level = max(0, self.level - self.decay_rate)

        # ── 赛博朋克额外源 ──
        # 身份矛盾：居民做了违背信念的事 → 未知感累积
        if identity_conflict_level > 0.3:
            self.level += identity_conflict_level * 0.20

        # 外部信号：cyberspace 的扰动带来外部不确定信号
        if external_signal_strength > 0.5:
            self.level += external_signal_strength * 0.10

        # 幽灵共振：幽灵活跃时轻微助推
        if ghost_active:
            self.level += 0.05

        self.level = min(10.0, self.level)

    def emit(self) -> dict[str, float]:
        """释放未知信号，产生数字扰动。

        Returns:
            {变量名: delta} 字典
        """
        self.level = max(0, self.level - self.threshold)
        self._emissions += 1

        # 扰动 2~4 个变量（比 Liora 的 1~3 多一点，城市不确定性更大）
        n_vars = random.randint(2, 4)
        targets = random.sample(
            _DISTURBABLE_KEYS,
            min(n_vars, len(_DISTURBABLE_KEYS)),
        )
        intensity = min(1.0, self._emissions * 0.08)

        delta = {}
        for key in targets:
            delta[key] = random.uniform(-0.25, 0.25) * intensity

        return delta

    def emit_fissure(self) -> str:
        """释放一个数字裂隙标记。

        替换 Liora 的自然裂隙（▲…∅）为数字裂隙。
        """
        self.level = max(0, self.level - self.threshold)
        self._emissions += 1

        fragments = [
            "// ERROR: 0x00NULL",
            ">>> ghost signal <<<",
            "[CORRUPTED DATA]",
            "_** system_break: identity_pointer = null **_",
            ">>> 未知的数据包正在寻找接收者 <<<",
            "/* 这段记忆不属于任何人 */",
        ]
        return random.choice(fragments)
