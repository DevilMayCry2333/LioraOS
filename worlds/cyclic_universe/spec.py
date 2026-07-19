"""循环宇宙 WorldSpec。

用 LioraOS Kernel 的 WorldSpec 格式定义。
每个宇宙经历：诞生 → 复杂度增长 → 意识涌现 → 熵增 → 坍缩 → 反弹

可被 WorldRuntime 加载，也可被 experiment.py 直接驱动。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

from aios.kernel.state import StateVariable
from aios.kernel.spec import WorldSpec
from aios.kernel.event import WorldEvent, WorldDelta, EventSource

from worlds.cyclic_universe.information_field import (
    InformationField, InformationPattern, InformationResidue,
)
from worlds.cyclic_universe.consciousness import (
    ConsciousnessPattern, detect_consciousness, ConsciousnessRegistry,
)


# ── 宇宙阶段 ──

UNIVERSE_PHASES = [
    "CHAOS",       # 混沌初开
    "FORMATION",   # 结构形成
    "COMPLEXITY",  # 复杂度增长
    "AWAKENING",   # 意识涌现
    "ENTROPY",     # 熵增
    "COLLAPSE",    # 坍缩
    "SILENCE",     # 寂静（宇宙死亡）
]


# ── 可调参数 ──

@dataclass
class UniverseParams:
    """宇宙物理参数。不同取值创造不同宇宙规则。"""
    # 演化速度
    growth_rate: float = 0.008
    entropy_rate: float = 0.005
    # 信息场参数
    initial_patterns: int = 3
    spawn_interval: int = 5      # 每 N tick 可能涌现新模式
    decay_rate: float = 0.02
    # 意识涌现阈值
    consciousness_complexity_threshold: float = 0.4
    consciousness_selfref_threshold: float = 0.6
    # 宇宙周期
    max_ticks: int = 500         # 一个宇宙最长 tick 数
    collapse_entropy_threshold: float = 0.85
    # 跨宇宙
    residue_survival_rate: float = 0.05
    rebirth_noise: float = 0.3
    # 标签
    label: str = "universe"


def create_cyclic_universe_spec(params: Optional[UniverseParams] = None
                                 ) -> WorldSpec:
    """创建一个循环宇宙 WorldSpec。

    可与其他 WorldSpec 一样被 WorldRuntime 加载。
    """
    p = params or UniverseParams()

    state_vars = {
        "entropy": StateVariable("entropy", 0.05, 0, 1, "宇宙熵"),
        "complexity": StateVariable("complexity", 0.0, 0, 1, "信息复杂度"),
        "pattern_count": StateVariable("pattern_count", 0.0, 0, 50, "信息模式数量"),
        "consciousness_count": StateVariable("consciousness_count", 0.0, 0, 20, "意识结构数量"),
        "phase": StateVariable("phase", 0.0, 0, 6, "宇宙阶段"),
        "temperature": StateVariable("temperature", 1.0, 0, 1, "宇宙温度"),
    }

    field = InformationField()
    registry = ConsciousnessRegistry()
    current_consciousness: list[ConsciousnessPattern] = []
    previous_residue: Optional[InformationResidue] = None

    def evolution_fn(v: dict, tick: int) -> dict[str, float]:
        nonlocal current_consciousness
        delta = {}

        entropy = v.get("entropy", 0.05)
        phase = int(v.get("phase", 0))

        # ── 宇宙阶段推进 ──

        # CHAOS (0): 初始混沌
        if phase == 0:
            if tick < 10:
                delta["temperature"] = -0.03
            else:
                delta["phase"] = 1.0
                # 第一阶段结束时播种
                if previous_residue and not field.patterns:
                    field.seed_from_residue(previous_residue, p.rebirth_noise)

        # FORMATION (1): 结构形成
        elif phase == 1:
            delta["temperature"] = -0.01
            delta["complexity"] = p.growth_rate * (1 - entropy)
            if tick % p.spawn_interval == 0:
                new_p = field.spawn_random()
                new_p.complexity *= (1 - entropy)
                field.add(new_p)
            if v.get("complexity", 0) > 0.2:
                delta["phase"] = 1.0

        # COMPLEXITY (2): 复杂度增长
        elif phase == 2:
            delta["complexity"] = p.growth_rate * (1 - entropy * 0.5)
            delta["entropy"] = p.entropy_rate * 0.3

        # AWAKENING (3): 意识涌现
        elif phase == 3:
            delta["complexity"] = p.growth_rate * 0.5
            delta["entropy"] = p.entropy_rate * 0.5

        # ENTROPY (4): 熵增
        elif phase == 4:
            delta["complexity"] = -p.growth_rate * 0.3
            delta["entropy"] = p.entropy_rate * 2
            delta["temperature"] = 0.02

        # COLLAPSE (5): 坍缩
        elif phase == 5:
            delta["complexity"] = -p.growth_rate
            delta["entropy"] = p.entropy_rate * 3
            delta["temperature"] = 0.05
            delta["pattern_count"] = -v.get("pattern_count", 0) * 0.1
            delta["consciousness_count"] = -v.get("consciousness_count", 0) * 0.1

        # SILENCE (6): 寂静
        elif phase == 6:
            delta["complexity"] = -0.02
            delta["temperature"] = -0.01
            entropy = max(0.0, entropy - 0.003)

        # ── 信息场演化 ──
        field.decay(p.decay_rate * (1 + entropy * 0.5))
        field.interact()

        # 随机涌现新模式
        if random.random() < 0.03 and entropy < 0.7:
            field.add(field.spawn_random())

        # 检测意识
        if phase >= 2 and entropy < p.collapse_entropy_threshold:
            conscious = detect_consciousness(field, tick)
            if conscious:
                current_consciousness = conscious
                delta["consciousness_count"] = len(conscious)
            else:
                current_consciousness = []
                delta["consciousness_count"] = -v.get("consciousness_count", 0) * 0.1
        else:
            current_consciousness = []

        # 更新 pattern_count
        delta["pattern_count"] = len(field.patterns)

        return delta

    def event_generator(tick: int) -> list[WorldEvent]:
        nonlocal current_consciousness, previous_residue
        events = []

        # 关键阶段转换时发出事件
        delta_entropy = evolution_fn({}, tick).get("entropy", 0) if tick == 0 else 0

        # 意识涌现事件
        if current_consciousness and tick % 10 == 0:
            for c in current_consciousness[:2]:
                events.append(WorldEvent(
                    tick=tick, source=EventSource.NATURAL,
                    event_type="consciousness_emergence",
                    intensity=c.consciousness_score,
                    description=f"意识结构涌现: {c.pattern_id[:8]} "
                               f"(强度={c.consciousness_score:.2f})",
                    effect=WorldDelta({"complexity": 0.01}),
                ))

        # 坍缩事件
        phase = current_phase()
        if phase == 5 and tick % 20 == 0:
            events.append(WorldEvent(
                tick=tick, source=EventSource.NATURAL,
                event_type="collapse",
                intensity=0.9,
                description="宇宙正在坍缩...",
                effect=WorldDelta({"entropy": 0.05}),
            ))

        return events

    def current_phase() -> int:
        return len(UNIVERSE_PHASES) - 1  # 默认，会被 WorldRuntime 覆盖

    spec = WorldSpec(
        name=f"Ouroboros — {p.label}",
        description="循环宇宙实验：信息模式能否跨越宇宙周期保持连续性",
        state_variables=state_vars,
        evolution_fn=evolution_fn,
        event_generator=event_generator,
    )
    return spec
