"""Data Collector — 世界数据收集器。

自动记录所有世界的状态变更、事件、对话到结构化 JSONL。
每一行是独立的、自包含的，可直接用作训练数据。

用法:
    collector = DataCollector()
    collector.record_state(world_id, name, tick, state, phase)
    collector.record_event(world_id, name, event_type, description, state)
    collector.record_dialogue(world_id, name, speaker, text, state)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("aios.data_collector")

DEFAULT_DATA_DIR = Path("data/collected")


class DataCollector:
    """世界数据收集器。

    线程安全。每次记录立即落盘（append 模式，不缓冲）。
    每行 JSON 自包含：时间戳、世界、状态、事件、对话都在一行内。
    """

    def __init__(self, data_dir: str | Path = DEFAULT_DATA_DIR):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # 按世界分文件: data/collected/{world_name}.jsonl
        # 也维护一个全量: data/collected/_all.jsonl
        self._all_path = self._data_dir / "_all.jsonl"

        # 缓存世界名 → world_id 映射（只需存一次）
        self._name_map: dict[str, str] = {}

    def register_world(self, world_id: str, world_name: str):
        """注册一个世界（首次 state.publish 时自动调用）。"""
        with self._lock:
            self._name_map[world_name] = world_id
        logger.debug("DataCollector: 注册世界 %s (%s)", world_name, world_id)

    # ── 核心记录方法 ──

    def record_state(self, world_id: str, world_name: str,
                     tick: int, state: dict[str, Any],
                     phase: str = "", day: int = 0, hour: float = 0):
        """记录世界状态变更。"""
        entry = self._build_entry(world_id, world_name, tick, state,
                                  phase=phase, day=day, hour=hour)
        self._append(entry, world_name)

    def record_event(self, world_id: str, world_name: str,
                     tick: int, state: dict[str, Any],
                     event_type: str, event_desc: str,
                     phase: str = "", day: int = 0, hour: float = 0):
        """记录世界事件。"""
        entry = self._build_entry(world_id, world_name, tick, state,
                                  phase=phase, day=day, hour=hour)
        entry["event"] = {"type": event_type, "description": event_desc}
        self._append(entry, world_name)

    def record_dialogue(self, world_id: str, world_name: str,
                        tick: int, state: dict[str, Any],
                        speaker: str, text: str,
                        phase: str = "", day: int = 0, hour: float = 0,
                        context: str = ""):
        """记录角色对话。

        Args:
            speaker: 说话者（角色名）
            text: 说话内容
            context: 对话上下文（如前一句、当前场景等，可选）
        """
        entry = self._build_entry(world_id, world_name, tick, state,
                                  phase=phase, day=day, hour=hour)
        entry["dialogue"] = {"speaker": speaker, "text": text}
        if context:
            entry["context"] = context
        self._append(entry, world_name)

    # ── 内部方法 ──

    def _build_entry(self, world_id: str, world_name: str,
                     tick: int, state: dict[str, Any],
                     phase: str = "", day: int = 0, hour: float = 0) -> dict:
        """构建一条通用数据条目。"""
        entry: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "world": world_name,
            "world_id": world_id,
            "tick": tick,
            "state": dict(state),
        }
        if phase:
            entry["phase"] = phase
        if day:
            entry["day"] = day
        if hour is not None and hour > 0:
            entry["hour"] = hour
        return entry

    def _append(self, entry: dict, world_name: str):
        """线程安全地追加一行到对应文件。"""
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            # 全量文件
            try:
                with open(self._all_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError as e:
                logger.warning("写入全量日志失败: %s", e)
            # 按世界分文件
            world_path = self._data_dir / f"{world_name}.jsonl"
            try:
                with open(world_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError as e:
                logger.warning("写入世界日志失败 (%s): %s", world_name, e)

    def get_world_path(self, world_name: str) -> Path:
        """获取指定世界的数据文件路径。"""
        return self._data_dir / f"{world_name}.jsonl"

    @property
    def all_path(self) -> Path:
        return self._all_path

    def count_lines(self, world_name: str | None = None) -> int:
        """统计行数。"""
        path = self.get_world_path(world_name) if world_name else self._all_path
        try:
            with open(path, encoding="utf-8") as f:
                return sum(1 for _ in f)
        except (OSError, FileNotFoundError):
            return 0


# ════════════════════════════════════════════════════════════
# Kernel Server 集成接口
# ════════════════════════════════════════════════════════════

# 全局单例
_collector: Optional[DataCollector] = None


def get_collector(data_dir: str | Path | None = None) -> DataCollector:
    """获取 DataCollector 全局单例。"""
    global _collector
    if _collector is None:
        _collector = DataCollector(data_dir or DEFAULT_DATA_DIR)
    return _collector


def reset_collector():
    """重置单例（用于测试）。"""
    global _collector
    _collector = None
