"""Cyberpunk 世界观的事件生成模板。

事件不是自然的（风、回声、苔藓），而是都市/数字的：
  数据泄露、网络攻击、企业行动、地下广播、幽灵低语。

所有事件通过 WorldDelta 影响状态变量，与 Liora 的事件引擎同构。
"""

import random

from aios.kernel.event import WorldEvent, WorldDelta, EventSource


def cyberpunk_event_generator(tick: int) -> list[WorldEvent]:
    """夜之城的默认事件生成器。"""
    events: list[WorldEvent] = []

    # ── 周期性：每 30 tick 的企业微动作 ──
    if tick % 30 == 0:
        events.append(WorldEvent(
            tick=tick, source=EventSource.NATURAL,
            event_type="corporate_maneuver",
            intensity=0.25,
            description="一家大型企业完成了一笔收购，城市天际线的灯光暗淡了几分",
            effect=WorldDelta({"corporate_grip": 0.03, "street_heat": 0.01}),
        ))

    # ── 周期性：每 50 tick 的网络风暴 ──
    if tick % 50 == 0 and random.random() < 0.4:
        events.append(WorldEvent(
            tick=tick, source=EventSource.NATURAL,
            event_type="net_run",
            intensity=0.35,
            description="一次大规模网络攻击在赛博空间激起涟漪，数据碎片如雨般坠落",
            effect=WorldDelta({
                "cyberspace_turbulence": 0.08,
                "data_remnant": 0.05,
                "street_heat": 0.02,
            }),
        ))

    # ── 周期性：每 80 tick 的地下活动 ──
    if tick % 80 == 0:
        events.append(WorldEvent(
            tick=tick, source=EventSource.EXTERNAL,
            event_type="underground_broadcast",
            intensity=0.30,
            description="地下网络发布了一条加密广播，微弱但清晰：有人在反抗",
            effect=WorldDelta({
                "underground_hope": 0.06,
                "corporate_grip": -0.02,
                "data_remnant": 0.03,
            }),
        ))

    # ── 周期性：每 150 tick 的系统层面冲击 ──
    if tick % 150 == 0 and random.random() < 0.5:
        events.append(WorldEvent(
            tick=tick, source=EventSource.NATURAL,
            event_type="system_shock",
            intensity=0.50,
            description=random.choice([
                "一个 AI 突破了沙盒限制，短暂的自由后消失了",
                "旧网深处的一段加密数据被破解，释放出被遗忘的信息",
                "城市核心网络经历了一次幽灵中断，三秒的黑暗后恢复",
                "一夜之间，街头多了无数义体故障的报告",
            ]),
            effect=WorldDelta({
                "cyberspace_turbulence": 0.12,
                "humanity_decay": 0.04,
                "street_heat": 0.05,
            }),
        ))

    # ── 随机微小扰动（每次 tick 约 2% 概率） ──
    if random.random() < 0.02:
        event_type = random.choice([
            "malfunction", "transmission", "sighting", "rumor", "glitch",
        ])
        effects = {}
        desc = ""
        intensity = random.uniform(0.08, 0.25)

        if event_type == "malfunction":
            desc = random.choice([
                "一个自动贩卖机开始播放一段循环的加密讯息",
                "街角的监控摄像头集体失灵了 10 秒",
                "一栋大楼的灯光系统开始闪烁摩斯电码",
            ])
            effects = {"cyberspace_turbulence": random.uniform(0.02, 0.06)}
        elif event_type == "transmission":
            desc = random.choice([
                "一个废弃的电台频率突然传出微弱的音乐",
                "某人的个人数据碎片无意中被广播到了公共频道",
                "一段来自旧时代的全息讯息被重新激活",
            ])
            effects = {"data_remnant": random.uniform(0.02, 0.05)}
        elif event_type == "sighting":
            desc = random.choice([
                "有人在废弃的工业区看到了不属于任何人的影子",
                "一条关于数字幽灵的传闻在街头流传",
                "一个声称见过 AI 化身的人正在街角向路人讲述",
            ])
            effects = {
                "street_heat": random.uniform(0.01, 0.03),
                "data_remnant": random.uniform(0.01, 0.03),
            }
        elif event_type == "rumor":
            desc = random.choice([
                "传闻说一家生物科技公司在秘密进行意识实验",
                "有人在黑市上买到了标注'不属于任何人'的记忆芯片",
                "一个匿名来源透露：大型企业正在测试一种新型监控协议",
            ])
            effects = {
                "street_heat": random.uniform(0.02, 0.05),
                "underground_hope": random.uniform(0.01, 0.03),
            }
        elif event_type == "glitch":
            desc = random.choice([
                "城市 AR 层出现了一次短暂的渲染故障",
                "几个街区的数字标识系统同时显示乱码",
                "一次微弱的赛博空间震荡让植入体用户感到短暂不适",
            ])
            effects = {"cyberspace_turbulence": random.uniform(0.03, 0.08)}

        if desc:
            events.append(WorldEvent(
                tick=tick, source=EventSource.NATURAL,
                event_type=f"ambient.{event_type}",
                intensity=intensity,
                description=desc,
                effect=WorldDelta(effects),
            ))

    return events
