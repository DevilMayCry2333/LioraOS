"""AIOS Kernel — 通用运行机制层。

提供所有世界共享的基础设施（时钟、状态、事件、居民、总线、规约、历史）。
不包含特定叙事绑定的模块（那些在 aios/narrative/）。
"""

from . import tick, state, event, memory, resident, bus, spec, history, budget

__all__ = [
    "tick", "state", "event", "memory", "resident",
    "bus", "spec", "history", "budget",
]


def shutdown():
    """优雅关闭所有内核子系统。

    在进程退出前调用，确保：
    - tick 线程安全停止
    - 世界状态 checkpoint 到磁盘
    """
    tick.get_world_tick().stop(join=True, timeout=2.0)
    try:
        state.get_world_state_engine().checkpoint()
    except Exception:
        pass
