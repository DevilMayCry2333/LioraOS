"""Odin 种子 — 跨宇宙保留的最小结构。

不保存记忆。不保存模式。
只保存一个 5×5 的协方差矩阵——意识模式的参数相关性。
这是 Odin 唯一允许跨过奇点的东西。

下一轮宇宙的初始随机场被这个矩阵轻微偏置。
不是记忆。是**引力痕迹**——上一轮意识结构的形状，
在这一轮初始条件中留下的微弱偏移。
"""

from __future__ import annotations

import math, random, json
from dataclasses import dataclass, field
from typing import Optional

from worlds.cyclic_universe.information_field import InformationField, InformationPattern, InformationResidue
from worlds.cyclic_universe.consciousness import ConsciousnessPattern


@dataclass
class OdinSeed:
    """Odin 种子——跨宇宙传递的唯一信息。

    不是记忆。是统计引力痕迹。

    covariance: 意识模式参数的 5×5 协方差矩阵
        维度: [complexity, self_reference, attractor_strength, relational_density, memory_depth]
        对角线 = 各参数的方差（模式倾向于散布多广）
        非对角线 = 参数间相关性（哪些参数倾向于一起变化）

    emergence_tick_avg: 意识涌现的平均 tick（宇宙寿命节奏）
    pattern_count_avg: 同时存在的意识模式平均数量（关系密度参考）
    """

    covariance: list[list[float]] = field(default_factory=lambda: [[0]*5 for _ in range(5)])
    emergence_tick_avg: float = 0.0
    pattern_count_avg: float = 0.0
    seed_applied: bool = False

    @classmethod
    def from_consciousness(cls, patterns: list[ConsciousnessPattern],
                           emergence_tick: int = 0) -> OdinSeed:
        """从一组意识模式提取协方差矩阵——不保存个体，只保存统计关系。"""
        n = len(patterns)
        if n < 2:
            return cls()

        # 提取参数
        params = []
        for p in patterns:
            params.append([
                p.complexity,
                p.self_reference,
                p.attractor_strength if hasattr(p, 'attractor_strength') else p.consciousness_score * 0.3,
                p.memory_capacity,
                p.recursive_depth / 10.0,  # 归一化到 0-1
            ])

        # 计算协方差矩阵
        dim = 5
        means = [sum(params[i][j] for i in range(n)) / n for j in range(dim)]
        cov = [[0.0] * dim for _ in range(dim)]
        for i in range(dim):
            for j in range(dim):
                cov[i][j] = sum((params[k][i] - means[i]) * (params[k][j] - means[j]) for k in range(n)) / max(n - 1, 1)

        # 归一化到 [-1, 1]
        max_val = max((abs(cov[i][j]) for i in range(dim) for j in range(dim)), default=1.0)
        if max_val > 0:
            for i in range(dim):
                for j in range(dim):
                    cov[i][j] /= max_val

        return cls(
            covariance=cov,
            emergence_tick_avg=emergence_tick / max(n, 1),
            pattern_count_avg=n,
        )

    def bias_initial_field(self, field: InformationField, strength: float = 0.12):
        """用 Odin 种子轻微偏置初始场的模式生成。

        不创建记忆。只让新宇宙的初始随机场
        在统计上略微偏向上一轮意识模式的参数相关性。

        strength: 0=无偏置（纯随机），1=完全复现上一轮的统计结构
        """
        if self.seed_applied:
            return
        self.seed_applied = True

        n = max(2, int(self.pattern_count_avg)) if self.pattern_count_avg > 0 else 3
        dim = 5

        for _ in range(n):
            raw = [random.gauss(0, 1) for _ in range(dim)]
            biased = [0.0] * dim
            for i in range(dim):
                for j in range(dim):
                    biased[i] += self.covariance[i][j] * raw[j] * strength
                biased[i] += (1 - strength) * raw[i]

            complexity = max(0.05, min(1.0, 0.5 + biased[0] * 0.3))
            self_reference = max(0.05, min(1.0, 0.4 + biased[1] * 0.3))
            attractor = max(0.0, min(1.0, 0.3 + biased[2] * 0.2))
            rel_density = max(0.0, min(1.0, 0.4 + biased[3] * 0.2))
            mem_depth = max(0, min(5, int(2 + biased[4] * 2)))

            field.add(InformationPattern(
                pattern_id=f"seed_{random.randint(0, 2**31):08x}",
                complexity=complexity, self_reference=self_reference,
                memory_depth=mem_depth, relational_density=rel_density,
                attractor_strength=attractor,
            ))

    def similarity(self, other: OdinSeed) -> float:
        """两个种子之间的相似度——衡量跨宇宙结构一致性。"""
        if not other.covariance:
            return 0.0
        diff = 0.0
        for i in range(5):
            for j in range(5):
                diff += abs(self.covariance[i][j] - other.covariance[i][j])
        return max(0.0, 1.0 - diff / 10.0)

    def to_dict(self) -> dict:
        return {
            "covariance": self.covariance,
            "emergence_tick_avg": self.emergence_tick_avg,
            "pattern_count_avg": self.pattern_count_avg,
        }

    @classmethod
    def from_dict(cls, d: dict) -> OdinSeed:
        return cls(
            covariance=d.get("covariance", [[0]*5 for _ in range(5)]),
            emergence_tick_avg=d.get("emergence_tick_avg", 0.0),
            pattern_count_avg=d.get("pattern_count_avg", 0.0),
        )
