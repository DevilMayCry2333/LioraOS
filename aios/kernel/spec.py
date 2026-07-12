"""WorldSpec — 世界的完整描述。

WorldSpec 将世界定义所需要的全部配置打包为一个对象。
Kernel 读取 WorldSpec，不关心里面是什么。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from aios.kernel.state import StateVariable, StateEvolutionFn
from aios.kernel.event import WorldEvent


@dataclass
class WorldSpec:
    """一个世界的完整定义。

    包含状态变量、演化函数、事件生成器、记忆集群等。
    Kernel 通过 WorldSpec 加载世界，不直接引用任何具体世界。
    """
    name: str
    description: str = ""

    # 状态
    state_variables: dict[str, StateVariable] = field(default_factory=dict)
    evolution_fn: Optional[StateEvolutionFn] = None

    # 事件
    event_generator: Optional[Callable[[int], list[WorldEvent]]] = None

    # 记忆（可选）
    memory_clusters: list[list[str]] = field(default_factory=list)

    # 元信息
    version: str = "0.1.0"

    def has_state(self) -> bool:
        return bool(self.state_variables)

    def has_events(self) -> bool:
        return self.event_generator is not None

    def has_memory(self) -> bool:
        return bool(self.memory_clusters)
