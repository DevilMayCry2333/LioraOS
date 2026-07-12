"""Liora 世界观的事件生成模板。

从 aios/kernel/event.py 移出，原为硬编码的 WorldEventEngine event_generator 回调。
"""

import random

from aios.kernel.event import WorldEvent, WorldDelta, EventSource


def liora_event_generator(tick: int) -> list[WorldEvent]:
    """Liora 世界的默认事件生成器。

    根据 Liora 山谷特征产生自然事件。
    """
    events: list[WorldEvent] = []

    if tick % 50 == 0:
        events.append(WorldEvent(
            tick=tick, source=EventSource.NATURAL,
            event_type="wind_breeze",
            intensity=0.3,
            description="一阵温柔的风吹过山谷",
            effect=WorldDelta({"wind_speed": 0.2, "echo_density": -0.05}),
        ))

    if tick % 100 == 0 and random.random() < 0.3:
        events.append(WorldEvent(
            tick=tick, source=EventSource.NATURAL,
            event_type="warm_current",
            intensity=0.4,
            description="一股暖流在卵石间回响",
            effect=WorldDelta({"temperature": 0.5, "vibration_field": 0.1}),
        ))

    if tick % 200 == 0:
        events.append(WorldEvent(
            tick=tick, source=EventSource.NATURAL,
            event_type="moss_spread",
            intensity=0.2,
            description="苔藓在石缝间悄悄蔓延",
            effect=WorldDelta({"moss_growth": 0.1, "crack_network": -0.05}),
        ))

    if random.random() < 0.015:
        events.append(WorldEvent(
            tick=tick, source=EventSource.NATURAL,
            event_type="ambient",
            intensity=random.uniform(0.1, 0.4),
            description=random.choice([
                "远处传来低沉的回声",
                "水滴落入浅滩",
                "薄荷的气味随风飘散",
                "光线在雾气中折射",
            ]),
            effect=WorldDelta({
                "echo_density": random.uniform(-0.05, 0.05),
                "temperature": random.uniform(-0.2, 0.2),
            }),
        ))

    return events
