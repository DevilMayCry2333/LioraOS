"""WorldHistory — 世界历史日志。

持久化的重大事件记录，不设过期时间。
居民和系统可以通过它了解"过去发生了什么"。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

HISTORY_PATH = Path("data/world/history.jsonl")


@dataclass
class HistoryEntry:
    """一条历史记录。"""
    tick: int = 0
    event_type: str = ""
    description: str = ""
    participants: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "type": self.event_type,
            "desc": self.description[:200],
            "participants": self.participants,
            "ts": self.timestamp or datetime.now().isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> HistoryEntry:
        return cls(
            tick=d.get("tick", 0),
            event_type=d.get("type", d.get("event_type", "")),
            description=d.get("desc", d.get("description", "")),
            participants=d.get("participants", []),
            timestamp=d.get("ts", d.get("timestamp", "")),
        )


class WorldHistory:
    """世界历史日志。追加型，不设过期，可查询最近/按类型/按参与者。"""

    def __init__(self, path: Path = HISTORY_PATH, max_entries: int = 1000):
        self._lock = threading.Lock()
        self._path = path
        self._max_entries = max_entries
        self._entries: list[HistoryEntry] = []
        self._loaded = False

    def initialize(self):
        if self._loaded:
            return
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists():
                try:
                    for line in self._path.read_text(encoding="utf-8").strip().split("\n"):
                        if line.strip():
                            self._entries.append(HistoryEntry.from_dict(json.loads(line)))
                except Exception:
                    pass
            self._loaded = True

    def record(self, tick: int, event_type: str, description: str,
               participants: Optional[list[str]] = None):
        """记录一条历史事件。"""
        entry = HistoryEntry(
            tick=tick,
            event_type=event_type,
            description=description,
            participants=participants or [],
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]
            self._append_to_file(entry)

    def _append_to_file(self, entry: HistoryEntry):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def recent(self, n: int = 10) -> list[HistoryEntry]:
        """最近的 n 条记录。"""
        with self._lock:
            return list(self._entries[-n:])

    def by_type(self, event_type: str) -> list[HistoryEntry]:
        """按类型过滤。"""
        with self._lock:
            return [e for e in self._entries if e.event_type == event_type]

    def by_participant(self, name: str) -> list[HistoryEntry]:
        """按参与者过滤。"""
        with self._lock:
            return [e for e in self._entries if name in e.participants]

    def timeline(self, n: int = 20) -> str:
        """格式化的历史时间线（给 LLM/居民用）。"""
        entries = self.recent(n)
        if not entries:
            return "（世界尚未记录任何重要事件。）"
        lines = ["世界历史："]
        for e in reversed(entries):
            parts = [f"  [tick {e.tick}] {e.description[:80]}"]
            if e.participants:
                parts[0] += f" ({', '.join(e.participants)})"
            lines.append(parts[0])
        return "\n".join(lines)

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def clear(self):
        with self._lock:
            self._entries.clear()


_global_history: Optional[WorldHistory] = None


def get_world_history(path: Path = HISTORY_PATH) -> WorldHistory:
    global _global_history
    if _global_history is None:
        _global_history = WorldHistory(path=path)
    return _global_history
