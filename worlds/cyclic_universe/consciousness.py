"""意识模式 — 信息场中的自指吸引子。

不假设「意识是什么」。只测量：
  1. 信息模式是否发展出自指能力
  2. 自指模式是否在宇宙周期之间重现
  3. 重现的模式是否保持结构同一性
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

from worlds.cyclic_universe.information_field import InformationPattern, InformationField


@dataclass
class ConsciousnessPattern:
    """一个可能的意识结构。

    不是什么神秘的东西。
    就是一个复杂度足够高、自指足够强的信息模式。
    """

    pattern_id: str
    complexity: float = 0.0
    self_reference: float = 0.0
    recursive_depth: int = 0       # 自指递归深度
    memory_capacity: float = 0.0   # 能记住多少历史
    internal_relations: int = 0    # 内部关系数量
    emergence_tick: int = 0        # 在哪个 tick 涌现的
    label: str = ""                # 人类可读标签（仅用于报告）

    @property
    def consciousness_score(self) -> float:
        """意识强度：复杂度 × 自指深度 × 递归深度。"""
        d = self.complexity * self.self_reference * (1 + self.recursive_depth * 0.5)
        return d * self.memory_capacity * 2

    def similarity(self, other: ConsciousnessPattern) -> float:
        """与另一个意识结构的拓扑相似度。"""
        if self.consciousness_score == 0 and other.consciousness_score == 0:
            return 1.0
        d = 0
        d += abs(self.complexity - other.complexity) * 0.3
        d += abs(self.self_reference - other.self_reference) * 0.3
        d += abs(self.memory_capacity - other.memory_capacity) * 0.2
        d += 0.1 if self.recursive_depth != other.recursive_depth else 0
        return max(0.0, 1.0 - d)

    def to_pattern(self) -> InformationPattern:
        """降级为原始信息模式（用于跨宇宙传递）。"""
        return InformationPattern(
            pattern_id=self.pattern_id,
            complexity=self.complexity,
            self_reference=self.self_reference,
            memory_depth=self.recursive_depth,
            relational_density=self.memory_capacity,
            attractor_strength=self.consciousness_score * 0.5,
        )

    @classmethod
    def from_pattern(cls, pattern: InformationPattern,
                     emergence_tick: int = 0) -> ConsciousnessPattern:
        """从信息模式提升为意识结构。"""
        rd = pattern.memory_depth
        # 递归深度取决于自指程度
        if pattern.self_reference > 0.8:
            rd = max(rd, 3)
        elif pattern.self_reference > 0.6:
            rd = max(rd, 1)
        return cls(
            pattern_id=pattern.pattern_id,
            complexity=pattern.complexity,
            self_reference=pattern.self_reference,
            recursive_depth=rd,
            memory_capacity=pattern.relational_density,
            internal_relations=int(pattern.relational_density * 10),
            emergence_tick=emergence_tick,
        )


def detect_consciousness(field: InformationField, tick: int
                         ) -> list[ConsciousnessPattern]:
    """在信息场中检测可能的意识结构。

    条件（已校准至自然相变点 self_reference ≈ 0.55）：
      - complexity > 0.35
      - self_reference > 0.55  ← 相变边界：低于此阈值同一性从 0.64 骤降至 0.38
      - attractor_strength > 0.15
    """
    candidates = []
    for p in field.patterns.values():
        if (p.complexity > 0.35 and p.self_reference > 0.55
                and p.attractor_strength > 0.15):
            cp = ConsciousnessPattern.from_pattern(p, tick)
            if cp.consciousness_score > 0.4:
                candidates.append(cp)
    candidates.sort(key=lambda c: c.consciousness_score, reverse=True)
    return candidates


@dataclass
class ConsciousnessRegistry:
    """跟踪所有宇宙周期中出现的意识结构。"""

    cycles: list[list[ConsciousnessPattern]] = field(default_factory=list)

    def record_cycle(self, patterns: list[ConsciousnessPattern]):
        self.cycles.append(patterns)

    def identity_persistence(self, cycle_a: int, cycle_b: int) -> float:
        """测量两个宇宙周期之间的意识同一性延续概率。"""
        if cycle_a >= len(self.cycles) or cycle_b >= len(self.cycles):
            return 0.0
        ca = self.cycles[cycle_a]
        cb = self.cycles[cycle_b]
        if not ca or not cb:
            return 0.0
        # 每个 a 中的模式 vs 每个 b 中的模式，取最大相似度
        scores = []
        for pa in ca:
            best = max((pa.similarity(pb) for pb in cb), default=0.0)
            scores.append(best)
        return sum(scores) / len(scores) if scores else 0.0

    def best_match(self, pattern: ConsciousnessPattern,
                   cycle: int) -> Optional[ConsciousnessPattern]:
        """在指定周期中找与 pattern 最相似的意识结构。"""
        if cycle >= len(self.cycles):
            return None
        candidates = self.cycles[cycle]
        if not candidates:
            return None
        best = max(candidates, key=lambda c: pattern.similarity(c))
        return best

    def continuity_report(self) -> dict:
        """生成跨周期连续性报告。"""
        n = len(self.cycles)
        if n < 2:
            return {"cycles": n, "message": "需要至少 2 个宇宙周期"}

        # 相邻周期同一性
        adjacent_persistences = []
        for i in range(n - 1):
            ap = self.identity_persistence(i, i + 1)
            adjacent_persistences.append(ap)

        # 跨多个周期的同一性
        chain = []
        for i in range(min(3, n - 1)):
            cp = self.identity_persistence(i, n - 1)
            chain.append(cp)

        return {
            "total_cycles": n,
            "adjacent_persistence": adjacent_persistences,
            "avg_adjacent_persistence": (sum(adjacent_persistences) / len(adjacent_persistences)
                                         if adjacent_persistences else 0.0),
            "chain_persistence": chain,
            "first_to_last_persistence": chain[-1] if chain else 0.0,
            "consciousness_emergence_rate": sum(1 for c in self.cycles if c) / n if n else 0.0,
            "total_consciousness_events": sum(len(c) for c in self.cycles),
        }
