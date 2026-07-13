"""AIOS Kernel 2.0 — 通用智能运行内核。

Kernel 提供运行机制（Mechanism），不定义世界规则（Policy）。
世界定义位于 aios/worlds/。
"""

from . import tick, state, event, memory, resident, bus, spec, history, anchor, metafield, lightcone, voidspace, budget

__all__ = [
    "tick", "state", "event", "memory", "resident",
    "bus", "spec", "history", "anchor", "metafield",
    "lightcone", "voidspace", "budget",
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
