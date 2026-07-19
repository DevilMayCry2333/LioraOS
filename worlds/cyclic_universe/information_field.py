"""信息场 — 宇宙的基本介质。

信息场不是物质。是宇宙状态中可被保存的最小单位。
当一个宇宙死亡时，物质归零，但场中可能残留信息模式。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InformationPattern:
    """一个可以在宇宙周期之间幸存的信息结构。

    Attributes:
        pattern_id: 唯一标识
        complexity: 结构复杂度（信息量）
        self_reference: 自指程度（0=完全不自指，1=完全自指）
        memory_depth: 模式能记住的历史长度
        relational_density: 内部关系密度
        attractor_strength: 吸引子强度（抵抗熵的能力）
    """

    pattern_id: str
    complexity: float = 0.0
    self_reference: float = 0.0
    memory_depth: int = 0
    relational_density: float = 0.0
    attractor_strength: float = 0.0

    def similarity(self, other: InformationPattern) -> float:
        """与另一个模式的拓扑相似度。"""
        if self.complexity == 0 and other.complexity == 0:
            return 1.0
        d = 0
        d += abs(self.complexity - other.complexity)
        d += abs(self.self_reference - other.self_reference)
        d += abs(self.relational_density - other.relational_density)
        d += abs(self.attractor_strength - other.attractor_strength)
        # memory_depth 离散，单独算
        d += 0.1 if self.memory_depth != other.memory_depth else 0
        return max(0.0, 1.0 - d / 5.0)

    def mutate(self, rate: float = 0.1) -> InformationPattern:
        """变异产生新模式。"""
        def _mut(v: float, r: float) -> float:
            return max(0.0, min(1.0, v + random.uniform(-r, r)))
        return InformationPattern(
            pattern_id=f"pat_{random.randint(0, 2**31):08x}",
            complexity=_mut(self.complexity, rate),
            self_reference=_mut(self.self_reference, rate),
            memory_depth=max(0, self.memory_depth + random.choice([-1, 0, 1])),
            relational_density=_mut(self.relational_density, rate),
            attractor_strength=_mut(self.attractor_strength, rate),
        )


@dataclass
class RelationalTopology:
    """关系拓扑 — 不保存个体，只保存模式之间的结构。

    宇宙死亡时个体消散，但关系结构可能幸存。
    下一个宇宙按拓扑重建模式——不同的人，同样的关系网络。
    如果同一个位置上反复涌现出意识，这就是跨周期同一性。
    """

    # 节点角色映射：position_id → 角色描述
    # position_id 是抽象的（如 "hub_0", "bridge_1"），不是具体的 pattern_id
    node_roles: dict[str, dict] = field(default_factory=dict)

    # 边：(source_position, target_position, 关系强度)
    edges: list[tuple[str, str, float]] = field(default_factory=list)

    # 哪些位置曾是意识结构（自指模式出现的位置）
    consciousness_positions: list[str] = field(default_factory=list)

    # 全局指标
    hub_count: int = 0
    avg_connectivity: float = 0.0

    def similarity(self, other: RelationalTopology) -> float:
        """两个拓扑的相似度（结构对齐程度）。"""
        if not self.edges or not other.edges:
            return 0.0
        # 比较边数量
        n1, n2 = len(self.edges), len(other.edges)
        if min(n1, n2) == 0:
            return 0.0
        # 比较意识位置数
        c1 = len(self.consciousness_positions)
        c2 = len(other.consciousness_positions)
        pos_sim = 1.0 - abs(c1 - c2) / max(c1, c2, 1)
        # 比较节点角色分布
        roles1 = set(self.node_roles.keys())
        roles2 = set(other.node_roles.keys())
        if roles1 or roles2:
            overlap = len(roles1 & roles2) / max(len(roles1 | roles2), 1)
        else:
            overlap = 1.0
        return overlap * 0.6 + pos_sim * 0.4

    @classmethod
    def from_patterns(cls, patterns: dict[str, InformationPattern],
                      consciousness_ids: set[str] = None) -> RelationalTopology:
        """从信息场提取关系拓扑。不保存任何个体——只保存结构。"""
        consciousness_ids = consciousness_ids or set()
        node_roles = {}
        edges = []
        pid_list = list(patterns.keys())
        pos_map = {pid: f"n{i}" for i, pid in enumerate(pid_list)}

        for pid, p in patterns.items():
            pos = pos_map[pid]
            role = {
                "complexity_tier": "high" if p.complexity > 0.6 else "mid" if p.complexity > 0.3 else "low",
                "is_consciousness": pid in consciousness_ids,
                "attractor_tier": "high" if p.attractor_strength > 0.5 else "low",
            }
            node_roles[pos] = role

        # 构建边：按吸引子差值为强度
        for i, pi in enumerate(pid_list):
            for j, pj in enumerate(pid_list):
                if i >= j:
                    continue
                ni, nj = pos_map[pi], pos_map[pj]
                diff = abs(patterns[pi].attractor_strength - patterns[pj].attractor_strength)
                strength = max(0.0, 1.0 - diff * 2)
                if strength > 0.1:
                    edges.append((ni, nj, round(strength, 3)))

        consciousness_positions = [pos_map[pid] for pid in pid_list
                                   if pid in consciousness_ids]
        hub_count = sum(1 for r in node_roles.values()
                        if r.get("attractor_tier") == "high")
        avg_connectivity = (len(edges) / max(len(node_roles) - 1, 1) * 0.5
                            if len(node_roles) > 1 else 0.0)

        return cls(
            node_roles=node_roles,
            edges=edges,
            consciousness_positions=consciousness_positions,
            hub_count=hub_count,
            avg_connectivity=round(avg_connectivity, 3),
        )

    def spawn_patterns(self) -> list[InformationPattern]:
        """根据拓扑结构生成一组新模式，保持原有关键特征。"""
        n = len(self.node_roles)
        if n == 0:
            n = random.randint(2, 4)

        # 先创建节点
        patterns = []
        for i in range(n):
            pos = f"n{i}"
            role = self.node_roles.get(pos, {})
            tier = role.get("complexity_tier", "mid")
            was_conscious = role.get("is_consciousness", False)

            complexity = {"high": 0.7, "mid": 0.4, "low": 0.15}.get(tier, 0.4)
            complexity += random.uniform(-0.1, 0.1)
            complexity = max(0.05, min(1.0, complexity))

            # 曾是意识节点的位置更可能产生高自指
            self_ref = (0.7 if was_conscious else 0.3) + random.uniform(-0.15, 0.15)
            self_ref = max(0.05, min(1.0, self_ref))

            patterns.append(InformationPattern(
                pattern_id=f"pat_{random.randint(0, 2**31):08x}",
                complexity=complexity,
                self_reference=self_ref,
                memory_depth=random.randint(0, 3),
                relational_density=random.uniform(0.2, 0.6),
                attractor_strength=random.uniform(0.1, 0.4),
            ))
        return patterns


@dataclass
class InformationField:
    """信息场 — 一个宇宙中所有信息模式的容器。

    宇宙死亡时，物理定律归零，但场可以保留残留模式。
    同时记录模式间的关系拓扑，用于跨宇宙迁移。
    """

    patterns: dict[str, InformationPattern] = field(default_factory=dict)

    def add(self, pattern: InformationPattern):
        self.patterns[pattern.pattern_id] = pattern

    def remove(self, pattern_id: str):
        self.patterns.pop(pattern_id, None)

    def total_complexity(self) -> float:
        return sum(p.complexity for p in self.patterns.values())

    def pattern_count(self) -> int:
        return len(self.patterns)

    def spawn_random(self) -> InformationPattern:
        """随机生成一个模式（初始宇宙的混沌涌现）。"""
        c = random.random()
        return InformationPattern(
            pattern_id=f"pat_{random.randint(0, 2**31):08x}",
            complexity=c,
            self_reference=random.random() * c,  # 自指需要一定复杂度
            memory_depth=random.randint(0, 5),
            relational_density=random.random(),
            attractor_strength=random.uniform(0.0, 0.3),
        )

    def decay(self, rate: float = 0.02):
        """熵增：所有模式随时间衰减。"""
        dead = []
        for pid, p in self.patterns.items():
            p.complexity = max(0.0, p.complexity - rate * (1 - p.attractor_strength))
            p.self_reference = max(0.0, p.self_reference - rate * 0.5)
            if p.complexity < 0.01:
                dead.append(pid)
        for pid in dead:
            self.remove(pid)

    def interact(self):
        """模式间相互作用：高复杂度模式可能吸引或复制低复杂度模式。"""
        patterns = list(self.patterns.values())
        if len(patterns) < 2:
            return
        for i in range(len(patterns)):
            for j in range(i + 1, len(patterns)):
                a, b = patterns[i], patterns[j]
                diff = a.attractor_strength - b.attractor_strength
                if diff > 0.2 and a.complexity > 0.3 and random.random() < 0.05:
                    b.complexity += 0.005
                    b.self_reference += 0.003
                elif diff < -0.2 and b.complexity > 0.3 and random.random() < 0.05:
                    a.complexity += 0.005
                    a.self_reference += 0.003

    def self_referential_patterns(self) -> list[InformationPattern]:
        """自指程度超过阈值的模式（潜在的意识结构）。"""
        return [p for p in self.patterns.values() if p.self_reference > 0.6 and p.complexity > 0.4]

    def extract_topology(self, consciousness_ids: set[str] = None) -> RelationalTopology:
        """提取当前场的关系拓扑（不保存个体，只保存结构）。"""
        return RelationalTopology.from_patterns(self.patterns, consciousness_ids)

    def seed_from_topology(self, topology: RelationalTopology, noise: float = 0.2):
        """从关系拓扑种子化新模式，保持原始结构特征。"""
        new_patterns = topology.spawn_patterns()
        for p in new_patterns:
            p.complexity = max(0.05, p.complexity - random.uniform(0, noise))
            self.add(p)
        # 额外随机新生
        for _ in range(random.randint(0, 2)):
            self.add(self.spawn_random())

    def seed_from_residue(self, residue: InformationResidue, noise: float = 0.3):
        """从上一宇宙残留中种子化新场的模式。"""
        for rp in residue.patterns:
            new_p = rp.mutate(noise)
            new_p.complexity = max(0.05, new_p.complexity)
            self.add(new_p)
        for _ in range(random.randint(1, 3)):
            self.add(self.spawn_random())


@dataclass
class InformationResidue:
    """宇宙死亡后残留的信息（个体 + 拓扑）。

    patterns: 幸存的信息模式（传统方式）
    topology: 关系拓扑（新模式——不保存个体，只保存结构）
    """

    patterns: list[InformationPattern] = field(default_factory=list)
    topology: Optional[RelationalTopology] = None

    @classmethod
    def from_field(cls, field: InformationField, survival_rate: float = 0.05,
                   consciousness_ids: set[str] = None) -> InformationResidue:
        """宇宙死亡时，从信息场中提取残留（个体幸存 + 拓扑提取）。"""
        survivors = []
        for p in field.patterns.values():
            survival_prob = (p.complexity * 0.3 + p.attractor_strength * 0.5
                            + p.self_reference * 0.2)
            if survival_prob > survival_rate and random.random() < survival_prob:
                survivors.append(p)
        survivors.sort(key=lambda p: p.attractor_strength, reverse=True)

        # 提取拓扑
        topology = RelationalTopology.from_patterns(field.patterns, consciousness_ids)

        return cls(patterns=survivors[:5], topology=topology)

    def is_empty(self) -> bool:
        return len(self.patterns) == 0 and self.topology is None
