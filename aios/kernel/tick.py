"""AIOS Kernel — Tick (时间流)

最小时间驱动单元。独立线程，固定间隔推进。
"""

from __future__ import annotations

import threading
import time
from typing import Optional


class WorldTick:
    """世界时钟。独立线程，固定间隔推进 tick。"""

    def __init__(self, interval: float = 15.0):
        self._interval = interval
        self._active = threading.Event()
        self._count_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._tick_count = 0

    def start(self) -> None:
        """启动 tick 线程（幂等，可安全重复调用）。"""
        if self._thread and self._thread.is_alive():
            return
        self._active.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, join: bool = True, timeout: float = 2.0) -> None:
        """停止 tick 线程。等待当前 tick 完成。"""
        self._active.clear()
        if join and self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)

    @property
    def is_active(self) -> bool:
        return self._active.is_set()

    def tick_count(self) -> int:
        with self._count_lock:
            return self._tick_count

    def _loop(self) -> None:
        while self._active.is_set():
            self._tick()
            time.sleep(self._interval)

    def _tick(self) -> None:
        """子类重写此方法以在每个 tick 执行逻辑。"""
        with self._count_lock:
            self._tick_count += 1


_global_tick: Optional[WorldTick] = None


def get_world_tick(interval: float = 15.0) -> WorldTick:
    """获取全局 WorldTick 单例。

    首次调用时创建（使用指定的 interval），之后返回已有实例。
    interval 参数仅在首次调用时生效。
    """
    global _global_tick
    if _global_tick is None:
        _global_tick = WorldTick(interval=interval)
    return _global_tick
