"""WorldHistory — 世界历史日志。

持久化的重大事件记录，不设过期时间。
居民和系统可以通过它了解"过去发生了什么"。
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("aios.kernel.history")
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
                    logger.debug("failed to load history from %s", self._path)
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
            logger.warning("failed to append to history file %s", self._path)

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

    def load_history_fragments(self, n: int = 10, for_persona: bool = True) -> list[str]:
        """加载最近 N 条历史记录作为"残留记忆"文本片段。

        用于新循环初始化：居民在创建时调用此方法，将上一循环的历史
        片段注入 persona，模拟"残留意念"。

        Args:
            n: 要返回的最近记录数
            for_persona: True 时返回格式化的可读文本（可直接追加到 system persona）

        Returns:
            文本片段列表，按时间从新到旧排列
        """
        entries = self.recent(n)
        if not entries:
            return []
        if for_persona:
            return [
                f"世界记录：tick {e.tick} — {e.description[:120]}"
                for e in reversed(entries)
            ]
        return [e.description for e in entries]

    # ── Checkpoint / Replay 协议 ──────────────────────────

    def create_checkpoint(self, resident_id: str, compressed_state: dict[str, Any],
                          tick: int = 0) -> HistoryEntry:
        """创建一个检查点——将 Resident 的压缩状态写入历史日志。

        检查点是恢复的起点：恢复时只需找最近的 checkpoint，
        然后重放之后的增量事件，无需 O(n) 全量扫描。

        存储格式：event_type="checkpoint"，description=JSON 编码的压缩状态。
        """
        import json as json_mod
        payload = {
            "resident_id": resident_id,
            "state": compressed_state,
            "tick": tick or self._entries[-1].tick if self._entries else 0,
        }
        entry = HistoryEntry(
            tick=tick or (self._entries[-1].tick if self._entries else 0),
            event_type="checkpoint",
            description=f"checkpoint:{resident_id}:{json_mod.dumps(payload, ensure_ascii=False)}",
            participants=[resident_id],
        )
        with self._lock:
            self._entries.append(entry)
            self._append_to_file(entry)
        return entry

    def find_last_checkpoint(self, resident_id: str) -> Optional[HistoryEntry]:
        """找到某个 Resident 最近的一个检查点。

        如果没有检查点，返回 None（需要全量重放）。
        """
        with self._lock:
            for entry in reversed(self._entries):
                if (entry.event_type == "checkpoint"
                        and resident_id in entry.participants):
                    return entry
        return None

    def replay_since(self, resident_id: str, from_tick: int = 0) -> list[HistoryEntry]:
        """重放某个 Resident 在指定 tick 之后的所有事件。

        通常配合 find_last_checkpoint() 使用：
          checkpoint = history.find_last_checkpoint("res_xxx")
          if checkpoint:
              events = history.replay_since("res_xxx", from_tick=checkpoint.tick)
          else:
              events = history.replay_since("res_xxx", from_tick=0)  # 全量

        Returns:
            按时间顺序排列的事件列表（从从新到旧）。
        """
        with self._lock:
            events = [
                e for e in self._entries
                if e.tick >= from_tick
                and (not resident_id or resident_id in e.participants)
                and e.event_type != "checkpoint"
            ]
        return list(events)

    def extract_checkpoint_state(self, entry: HistoryEntry) -> Optional[dict[str, Any]]:
        """从检查点条目中提取压缩状态。"""
        if entry.event_type != "checkpoint":
            return None
        import json as json_mod
        try:
            prefix = f"checkpoint:{entry.participants[0]}:" if entry.participants else "checkpoint:"
            payload_str = entry.description[len(prefix):]
            return json_mod.loads(payload_str).get("state")
        except Exception:
            return None

    def clear(self):
        with self._lock:
            self._entries.clear()


_global_history: Optional[WorldHistory] = None


def get_world_history(path: Path = HISTORY_PATH) -> WorldHistory:
    global _global_history
    if _global_history is None:
        _global_history = WorldHistory(path=path)
    return _global_history
