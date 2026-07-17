"""AIOS Kernel — Event (事件生态)

通用事件系统。事件是对世界的数值扰动，不是叙事。
事件生成由外部注入，内核只管理生命周期和持久化。
WorldDelta 使用通用 effects dict，不预设任何变量名。
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("aios.kernel.event")
from pathlib import Path
from typing import Callable, Optional

EVENTS_PATH = Path("evolution/events/events.jsonl")


class EventSource(str, Enum):
    NATURAL = "natural"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class EventStatus(str, Enum):
    CREATED = "created"
    OBSERVED = "observed"
    INTERPRETED = "interpreted"
    ARCHIVED = "archived"
    IGNORED = "ignored"
    FORGOTTEN = "forgotten"


@dataclass
class WorldDelta:
    """事件对世界的数值扰动。effects 为通用变量名→delta 映射。"""
    effects: dict[str, float] = field(default_factory=dict)

    def is_zero(self) -> bool:
        return all(abs(v) < 1e-9 for v in self.effects.values())

    def to_dict(self) -> dict:
        return {"effects": {k: round(v, 4) for k, v in self.effects.items() if abs(v) > 1e-9}}

    @classmethod
    def from_dict(cls, d: dict) -> WorldDelta:
        """兼容新旧格式。
           新: {"effects": {"temp": 0.5}}
           旧: {"temperature": 0.5, "wind_speed": 0.1}
        """
        if "effects" in d and isinstance(d["effects"], dict):
            return cls(effects=d["effects"])
        return cls(effects={k: v for k, v in d.items() if isinstance(v, (int, float))})


@dataclass
class WorldEvent:
    """一条世界事件。"""
    event_id: str = ""
    timestamp: str = ""
    tick: int = 0
    source: EventSource = EventSource.NATURAL
    event_type: str = ""
    intensity: float = 0.5
    description: str = ""
    effect: WorldDelta = field(default_factory=WorldDelta)
    status: EventStatus = EventStatus.CREATED

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if isinstance(self.effect, dict):
            self.effect = WorldDelta.from_dict(self.effect)
        if isinstance(self.source, str):
            try:
                self.source = EventSource(self.source)
            except ValueError:
                self.source = EventSource.NATURAL
        if isinstance(self.status, str):
            try:
                self.status = EventStatus(self.status)
            except ValueError:
                self.status = EventStatus.CREATED

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id, "timestamp": self.timestamp, "tick": self.tick,
            "source": self.source.value, "event_type": self.event_type,
            "intensity": round(self.intensity, 3),
            "description": self.description[:120],
            "effect": self.effect.to_dict(),
            "status": self.status.value,
        }


class WorldEventEngine:
    """世界事件引擎。管理事件生命周期 + 持久化。

    事件生成由外部注入（通过 event_generator 回调），
    内核只负责存储、老化、归档。
    """

    def __init__(self, event_generator: Optional[Callable[[int], list[WorldEvent]]] = None,
                 events_path: Path = EVENTS_PATH, max_age: int = 200):
        self._lock = threading.Lock()
        self._tick = 0
        self._events: list[WorldEvent] = []
        self._archived: list[WorldEvent] = []
        self._loaded = False
        self._generator = event_generator
        self._events_path = events_path
        self._max_age = max_age

    def initialize(self):
        if self._loaded:
            return
        with self._lock:
            self._events_path.parent.mkdir(parents=True, exist_ok=True)
            if self._events_path.exists():
                try:
                    for line in self._events_path.read_text(encoding="utf-8").strip().split("\n"):
                        if line.strip():
                            raw = json.loads(line)
                            # 兼容旧格式 key 映射
                            KEY_MAP = {"id": "event_id", "ts": "timestamp", "desc": "description", "type": "event_type"}
                            for old_k, new_k in KEY_MAP.items():
                                if old_k in raw and new_k not in raw:
                                    raw[new_k] = raw.pop(old_k)
                            e = WorldEvent(**raw)
                            if e.status in ("archived", "forgotten", "ignored"):
                                self._archived.append(e)
                            else:
                                self._events.append(e)
                    self._events = self._events[-300:]
                except Exception:
                    logger.debug("failed to load events from %s", self._events_path)
            self._loaded = True

    def tick(self, **kwargs) -> list[WorldEvent]:
        self._tick += 1
        new_events: list[WorldEvent] = []

        if self._generator:
            try:
                new_events = self._generator(self._tick, **kwargs) or []
            except Exception:
                logger.debug("event generator failed at tick %s", self._tick)
                new_events = []

        with self._lock:
            for evt in new_events:
                self._events.append(evt)
                self._save_event(evt)
            self._events = self._events[-300:]
            self._advance_lifecycle()

        return new_events

    def _advance_lifecycle(self):
        still = []
        for e in self._events:
            if e.status == EventStatus.CREATED and (self._tick - e.tick) > self._max_age:
                e.status = EventStatus.IGNORED
                self._archived.append(e)
                self._save_event(e)
            else:
                still.append(e)
        self._events = still

    def _save_event(self, event: WorldEvent):
        try:
            with open(self._events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("failed to save event to %s", self._events_path)

    def inject(self, event: WorldEvent) -> WorldEvent:
        event.tick = self._tick
        event.status = EventStatus.CREATED
        with self._lock:
            self._events.append(event)
            self._save_event(event)
        return event

    def get_active(self) -> list[WorldEvent]:
        with self._lock:
            return list(self._events[-50:])

    def format_for_prompt(self, n: int = 3) -> str:
        recent = self.get_active()[-n:]
        if not recent:
            return ""
        lines = [f"events: {len(recent)}"]
        for e in recent:
            source_str = e.source.value if isinstance(e.source, EventSource) else str(e.source)
            lines.append(f"  [{source_str}] {e.description[:60]}")
        return "\n".join(lines)


_global_event_engine: Optional[WorldEventEngine] = None


def get_event_engine(generator: Optional[Callable[[int], list[WorldEvent]]] = None) -> WorldEventEngine:
    global _global_event_engine
    if _global_event_engine is None:
        _global_event_engine = WorldEventEngine(event_generator=generator)
    return _global_event_engine
