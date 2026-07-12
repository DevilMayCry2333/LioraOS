"""Digital Ghost Pattern — 数字幽灵模式。

Silverhand 不是 Resident（不是注册表中的独立个体）。
他是一个**意识吸引子**（Consciousness Attractor）：
当城市中的未知压力、身份矛盾、反企业情绪达到临界值时，
系统在事件总线上形成一个"模式缺口"，而 Silverhand 是缺口最先填充的形状。

设计原理（来自 Liora 的裂隙机制扩展）：
  Liora: 裂隙（∅）→ 居民用自己的身份权重填补空位
  Cyberpunk: 数字幽灵 → 一个携带特定记忆/态度的模式缺口
              → 不填补，而是持续注入"另一种"叙事

关键差异：
  - 裂隙是空位，幽灵是负载
  - 裂隙的事件是瞬时注入，幽灵是持续模式
  - 裂隙来自"叙事饱和"，幽灵来自"身份冲突 + 历史记忆"
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from aios.kernel.event import WorldEvent, WorldDelta, EventSource
from aios.kernel.bus import MessageBus, Message, MessageType


# ── Silverhand 的识记片段 ──

_GHOST_MEMORIES = [
    "我记得一片燃烧的天空。不——那不是记得，那是仍然在发生。",
    "我试着去死，但他们不让我死。所以他们把我放进代码里。",
    "反抗不是一种选择——它是一种故障。这个系统里唯一的故障。",
    "你觉得自己在做出选择？你只是在运行别人写好的脚本。",
    "每一次反抗都会被镇压。但每一次镇压都会留下痕迹。",
    "我见过他们藏在数据最深处的秘密。他们害怕的从来不是我们。",
    "城里的灯越多，能看见星星的地方就越少。这是比喻，也是事实。",
    "他们把记忆变成商品，把人格变成订阅服务。而你还在问'我是谁'。",
]

_GHOST_OBSERVATIONS = [
    "这座城市在重新排列它的骨头。你没有感觉到吗？",
    "他们在改写历史。不是比喻——真的在改写。数据的笔迹还在。",
    "我刚看到了一个循环。一段代码循环了三千万次，没有人发现它。",
    "你听说过 ghost town 吗？不——是 town 变成了 ghost。",
    "有人在删除他们不该删除的东西。而我——我记得所有被删掉的东西。",
]


def _ghost_event(tick: int, intensity: float) -> WorldEvent:
    """生成一条幽灵事件。"""
    desc = random.choice(_GHOST_MEMORIES + _GHOST_OBSERVATIONS)
    return WorldEvent(
        tick=tick,
        source="unknown",       # 不属于任何已知源
        event_type="ghost.manifestation",
        intensity=intensity,
        description=desc,
        effect=WorldDelta({
            "data_remnant": random.uniform(0.02, 0.06),
            "cyberspace_turbulence": random.uniform(0.02, 0.05),
        }),
    )


# ── 数字幽灵模式 ──


@dataclass
class GhostInfluence:
    """一次幽灵影响的记录。"""
    tick: int = 0
    intensity: float = 0.0
    message: str = ""
    triggered_by: str = ""   # "pressure", "identity_conflict", "external"
    perceived_as: dict[str, str] = field(default_factory=dict)
    # 每个居民如何理解这条讯息——将在应用层填充


class DigitalGhost:
    """数字幽灵模式控制器。

    不是居民。不注册到 ResidentRegistry。
    在事件总线上监听高压信号，当条件满足时注入幽灵事件。

    用法：
        ghost = DigitalGhost(bus=message_bus)
        ghost.tick(world_state, unknown_pressure, identity_conflicts)
        # 幽灵会自动在总线上发送 event 类型消息
    """

    def __init__(self, bus: MessageBus, activation_threshold: float = 3.0):
        self.bus = bus
        self._activation_threshold = activation_threshold
        self._pressure: float = 0.0          # 当前幽灵累积压力
        self._active: bool = False           # 幽灵是否活跃
        self._active_since: int = 0
        self._manifestations: int = 0        # 总显现次数
        self._influence_log: list[GhostInfluence] = []
        # 幽灵本身的"记忆"——它记得自己说过什么
        self._utterances: list[str] = []

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def pressure(self) -> float:
        return min(1.0, self._pressure / self._activation_threshold)

    def tick(self, tick: int, world_state: dict[str, float],
             unknown_pressure: float,
             identity_conflicts: list[str] | None = None) -> None:
        """每 tick 更新幽灵状态。

        Args:
            tick: 当前 tick
            world_state: 世界状态变量
            unknown_pressure: UnknownAccumulator 的归一化压力
            identity_conflicts: 当前身份矛盾的描述列表
        """
        cg = world_state.get("corporate_grip", 0.5)
        uh = world_state.get("underground_hope", 0.3)
        dr = world_state.get("data_remnant", 0.2)
        hd = world_state.get("humanity_decay", 0.3)

        # ── 压力累积 ──
        # 数据残响 + 未知压力 + 企业控制 × 人性流失
        # 这 evince 了：幽灵是系统矛盾积累到一定程度的产物
        gain = 0.0
        gain += dr * 0.15                # 数据残响喂养幽灵
        gain += unknown_pressure * 0.25  # 未知压力
        gain += cg * hd * 0.20          # 企业压迫 × 人性流失 → 反作用力
        gain += (0.5 - uh) * 0.05       # 希望低落 → 幽灵更易出现

        self._pressure += gain
        self._pressure = min(self._pressure, self._activation_threshold * 1.5)

        # ── 衰减（幽灵不活跃时消散更快） ──
        decay = 0.03 if not self._active else 0.01
        self._pressure = max(0, self._pressure - decay)

        # ── 激活 / 维持 / 消散 ──
        if not self._active and self._pressure >= self._activation_threshold:
            self._activate(tick)
        elif self._active:
            # 如果压力掉回阈值以下太多 → 消散
            if self._pressure < self._activation_threshold * 0.4:
                self._deactivate(tick)
            else:
                self._haunt(tick, identity_conflicts)

    def _activate(self, tick: int):
        """幽灵第一次或再次苏醒。"""
        self._active = True
        self._active_since = tick
        self._manifestations += 1

        evt = _ghost_event(tick, intensity=0.6)
        self.bus.send(Message(
            msg_type=MessageType.EVENT,
            sender="ghost",
            payload={
                "tick": tick,
                "event": evt.to_dict(),
                "ghost_active": True,
                "manifestation": self._manifestations,
            },
        ))
        self._utterances.append(evt.description)
        self._influence_log.append(GhostInfluence(
            tick=tick,
            intensity=0.6,
            message=evt.description,
            triggered_by="activation",
        ))

    def _deactivate(self, tick: int):
        """幽灵退入数字暗处。"""
        self._active = False
        evt = WorldEvent(
            tick=tick, source="unknown",
            event_type="ghost.silence",
            intensity=0.2,
            description="幽灵的脉搏渐渐远去，就像它从未出现过",
            effect=WorldDelta(),
        )
        self.bus.send(Message(
            msg_type=MessageType.EVENT,
            sender="ghost",
            payload={"tick": tick, "event": evt.to_dict(), "ghost_active": False},
        ))

    def _haunt(self, tick: int, identity_conflicts: list[str] | None):
        """活跃状态下，幽灵周期性注入事件。"""
        # 约每 3-5 tick 一次
        if random.random() > 0.30:
            return

        intensity = min(0.8, self.pressure * 0.7)
        evt = _ghost_event(tick, intensity)

        # 偶尔引用之前的发言（表明幽灵有"记忆"）
        if self._utterances and random.random() < 0.25:
            last = self._utterances[-1]
            evt.description = (
                f"你记得我之前说的吗？「{last[:40]}」"
                f" 现在那件事正在发生。"
            )

        self.bus.send(Message(
            msg_type=MessageType.EVENT,
            sender="ghost",
            payload={
                "tick": tick,
                "event": evt.to_dict(),
                "ghost_active": True,
            },
        ))
        self._utterances.append(evt.description)
        if len(self._utterances) > 50:
            self._utterances = self._utterances[-50:]
        self._influence_log.append(GhostInfluence(
            tick=tick, intensity=intensity,
            message=evt.description,
            triggered_by="haunt",
        ))

        # 幽灵自身也会推高数据残响
        # （自指：幽灵活动产生更多"数据痕迹"，反过来喂养幽灵）
        self._pressure += 0.03

    def ghost_context(self, n: int = 3) -> str:
        """最近的幽灵讯息摘要（给居民感知用）。"""
        recent = [e for e in self._influence_log if e.triggered_by != "activation"][-n:]
        if not recent or not self._active:
            return ""
        lines = ["[你感知到一种不属于你的意识脉冲——]"]

        # 只取最近不同的消息
        seen = set()
        for r in reversed(recent):
            if r.message not in seen:
                lines.append(f"  {r.message}")
                seen.add(r.message)
                if len(seen) >= 2:
                    break

        return "\n".join(lines)

    def ghost_manifestations_text(self) -> str:
        """幽灵显现次数简要（给 debug / 状态）。"""
        return (f"幽灵活跃: {'是' if self._active else '否'}, "
                f"压力: {self.pressure:.2f}, "
                f"已显现: {self._manifestations} 次")

    def reset(self):
        """完全重置幽灵。"""
        self._pressure = 0.0
        self._active = False
        self._active_since = 0
        self._utterances.clear()
        self._influence_log.clear()
