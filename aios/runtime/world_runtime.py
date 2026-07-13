"""WorldRuntime — 串联 Kernel 组件为可运转的世界循环。

职责：tick → state.evolve() → events.generate() → bus.broadcast()
不负责：居民认知、LLM 调用、用户输入。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from aios.kernel.tick import WorldTick
from aios.kernel.state import WorldStateEngine, WorldSnapshot
from aios.kernel.event import WorldEventEngine, WorldEvent
from aios.kernel.bus import MessageBus, Message, MessageType
from aios.kernel.spec import WorldSpec
from aios.kernel.history import WorldHistory
from aios.kernel.metafield import MetaField, get_metafield


@dataclass
class WorldSnapshot:
    """运行时快照，用于给居民感知。"""
    tick: int = 0
    state: dict[str, float] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    unknown_level: float = 0.0
    silence_level: float = 0.0


class WorldRuntime:
    """世界运行时。

    将 WorldSpec 配置的演化函数、事件生成器连接到 Kernel 组件，
    在独立线程中按固定间隔推进世界演化。

    用法：
        runtime = WorldRuntime(spec)
        runtime.start()
        # ... 等待 ...
        runtime.stop()
    """

    def __init__(self, spec: WorldSpec, data_dir: str = "data",
                 interval: float = 15.0,
                 metafield: Optional[MetaField] = None):
        self.spec = spec
        world_dir = Path(data_dir) / spec.name
        world_dir.mkdir(parents=True, exist_ok=True)

        self.state = WorldStateEngine(
            evolution_fn=spec.evolution_fn,
            state_path=world_dir / "state.json",
        )
        self.events = WorldEventEngine(
            event_generator=spec.event_generator,
            events_path=world_dir / "events.jsonl",
        )
        self.bus = MessageBus()
        self.history = WorldHistory(world_dir / "history.jsonl")
        self._interval = interval
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._tick_count = 0

        # MetaField 心跳
        self._metafield: Optional[MetaField] = metafield

    # ── 生命周期 ──────────────────────────────────

    def start(self):
        """初始化并启动世界循环（daemon 线程）。"""
        self.state.initialize(self.spec.state_variables)
        self.events.initialize()
        self.history.initialize()
        self._active = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, join: bool = True, timeout: float = 3.0):
        """停止世界循环并 checkpoint。"""
        self._active = False
        if join and self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)
        self.state.checkpoint()

    @property
    def is_running(self) -> bool:
        return self._active

    @property
    def tick(self) -> int:
        return self._tick_count

    # ── 核心循环 ──────────────────────────────────

    def _loop(self):
        while self._active:
            self.tick_once()
            time.sleep(self._interval)

    def tick_once(self) -> None:
        """单步演化：状态 → 事件 → 总线通知。

        子类可以重写此方法以在每一步插入自定义逻辑。
        """
        self._tick_count += 1

        # 1. 状态演化
        state_changes = self.state.tick()

        # 2. 事件生成
        new_events = self.events.tick()

        # 3. 总线广播
        if state_changes:
            self.bus.send(Message(
                msg_type=MessageType.PERCEIVE,
                sender="world",
                payload={"tick": self._tick_count, "changes": state_changes},
            ))
        for evt in new_events:
            self.bus.send(Message(
                msg_type=MessageType.EVENT,
                sender="world",
                payload={"tick": self._tick_count, "event": evt.to_dict()},
            ))

        # 4. MetaField 心跳（跨宇宙脉冲）
        if self._metafield is not None:
            try:
                self._metafield.pulse()
            except Exception:
                pass

    # ── 世界物体 ──────────────────────────────────

    def init_objects(self, objects: list[dict]):
        """初始化世界物体列表（从 WorldSpec 或应用层传入）。"""
        self._objects: list[dict] = list(objects)

    def add_object(self, name: str, location: str = "",
                   owner: str = "", description: str = ""):
        """在世界中放置一个物体。"""
        self._objects.append({
            "name": name,
            "location": location,
            "owner": owner,
            "description": description,
            "history": [],
        })

    def get_objects_at(self, location: str) -> list[dict]:
        """按位置查询物体。"""
        return [o for o in self._objects if o["location"] == location]

    def get_objects_by_owner(self, owner: str) -> list[dict]:
        """按所有者查询物体。"""
        return [o for o in self._objects if o["owner"] == owner]

    def update_object(self, name: str, **kwargs):
        """更新物体属性。"""
        for o in self._objects:
            if o["name"] == name:
                for k, v in kwargs.items():
                    if k in o:
                        o[k] = v
                    elif k == "add_history":
                        o.setdefault("history", []).append(v)
                return True
        return False

    def objects_formatted(self) -> str:
        """格式化物体列表（给居民感知用）。"""
        if not self._objects:
            return ""
        by_loc: dict[str, list[dict]] = {}
        for o in self._objects:
            by_loc.setdefault(o.get("location", "未知"), []).append(o)
        lines = ["世界中的物品："]
        for loc, items in sorted(by_loc.items()):
            names = [f"{i['name']}({i.get('owner','?')})" for i in items]
            lines.append(f"  {loc}: {'，'.join(names)}")
        return "\n".join(lines)

    # ── 感知接口 ──────────────────────────────────

    def apply_effects(self, effects: dict[str, float]) -> list[str]:
        """应用居民行动对世界状态的数值影响。

        Args:
            effects: {变量名: delta} — 正值增加，负值减少。
        Returns:
            实际生效的变化描述列表。
        """
        changed: list[str] = []
        state = self.state._state  # WorldState
        for name, delta in effects.items():
            if name in state.variables:
                current = state.get(name)
                state.set(name, current + delta)
                changed.append(f"{name}{delta:+.2f}")
        return changed

    def emit_fissure_event(self, fissure_mark: str = "…") -> WorldEvent:
        """注入一个裂隙事件——不属于任何居民、没有预设含义的缺口。

        裂隙事件进入事件流后，居民在感知时用自己的身份过滤层填补它。
        有些人看到危险，有些人看到机遇，有些人看到自己。
        """
        evt = WorldEvent(
            tick=self._tick_count,
            source="external",  # 不属于任何居民
            event_type="fissure",
            intensity=0.1,
            description=f"裂隙：{fissure_mark}",
            effect={},
        )
        self.events.inject(evt)
        self.bus.send(Message(
            msg_type=MessageType.EVENT,
            sender="fissure",
            payload={"tick": self._tick_count, "mark": fissure_mark,
                     "event": evt.to_dict()},
        ))
        self.history.record(
            tick=self._tick_count,
            event_type="fissure",
            description=f"裂隙出现：{fissure_mark}",
        )
        return evt

    def snapshot(self) -> WorldSnapshot:
        """返回当前世界快照（居民感知用）。"""
        state_snap = self.state.snapshot()
        active_events = self.events.get_active()
        return WorldSnapshot(
            tick=self._tick_count,
            state=state_snap.variables,
            events=[e.to_dict() for e in active_events[-3:]],
        )

    # ── 居民→世界事件路由 ─────────────────────────

    def emit_resident_event(self, resident_name: str, action: str,
                            description: str,
                            effect: Optional[dict[str, float]] = None) -> WorldEvent:
        """居民的某个行为成为世界事件，其他居民可在下次 tick 感知到。

        Args:
            resident_name: 行为发起者
            action: 行为类型（say / touch / create / help...）
            description: 行为描述
            effect: 对世界状态的影响（可选）
        """
        evt = WorldEvent(
            tick=self._tick_count,
            source="resident",
            event_type=f"resident.{action}",
            intensity=0.5,
            description=f"{resident_name} {description}",
            effect=effect or {},
        )
        self.events.inject(evt)
        self.bus.send(Message(
            msg_type=MessageType.EVENT,
            sender=resident_name,
            payload={"tick": self._tick_count, "action": action,
                     "event": evt.to_dict()},
        ))
        self.history.record(
            tick=self._tick_count,
            event_type=f"resident.{action}",
            description=description,
            participants=[resident_name],
        )
        return evt

    # ── 感知接口 ──────────────────────────────────

    def format_for_perception(self) -> str:
        """格式化世界状态为 LLM 可读文本。"""
        snap = self.snapshot()
        lines = [f"Tick {snap.tick} 的回声山谷："]

        # 只选几个关键变量自然描述
        vars = snap.state
        descs = []
        if "temperature" in vars:
            t = vars["temperature"]
            if t > 25: descs.append(f"温度偏暖（{t:.1f}°C）")
            elif t < 18: descs.append(f"温度偏凉（{t:.1f}°C）")
            else: descs.append(f"温度宜人（{t:.1f}°C）")
        if "wind_speed" in vars:
            w = vars["wind_speed"]
            if w > 1.5: descs.append("风比较大")
            elif w < 0.3: descs.append("风很轻")
            else: descs.append("微风")
        if "echo_density" in vars:
            e = vars["echo_density"]
            if e > 0.6: descs.append("回声充盈")
            elif e > 0.3: descs.append("有回声")
            else: descs.append("回声稀疏")
        if "humidity" in vars:
            h = vars["humidity"]
            if h > 0.7: descs.append("空气潮湿")
            elif h < 0.4: descs.append("空气干燥")
            else: descs.append("湿度适中")

        if descs:
            lines.append(f"  {', '.join(descs)}。")

        # 事件
        if snap.events:
            for e in snap.events:
                desc = e.get('description', '')[:80]
                if desc:
                    lines.append(f"  {desc}。")

        if snap.unknown_level > 0.3:
            lines.append(f"  有一种无法解释的低沉嗡鸣在空气中弥漫。")

        return "\n".join(lines)
