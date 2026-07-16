"""AIOS Kernel — State (世界状态)

通用状态引擎。内核不预设任何变量名和演化规则。
状态变量、演化公式由外部通过 WorldSpec 注入。
"""

from __future__ import annotations

import json
import logging
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("aios.kernel.state")

STATE_PATH = Path("evolution/world/state.json")

# 演化函数签名：(variables, tick) -> {name: delta}
StateEvolutionFn = Callable[[dict[str, float], int], dict[str, float]]


@dataclass
class StateVariable:
    """一个具有边界的数值状态变量。"""
    name: str
    value: float = 0.0
    min_value: float = float("-inf")
    max_value: float = float("inf")
    description: str = ""


@dataclass
class WorldState:
    """状态变量容器。"""
    variables: dict[str, StateVariable] = field(default_factory=dict)

    def get(self, name: str) -> float:
        return self.variables[name].value

    def set(self, name: str, value: float):
        v = self.variables[name]
        v.value = max(v.min_value, min(v.max_value, value))

    def value_dict(self) -> dict[str, float]:
        return {k: v.value for k, v in self.variables.items()}

    def to_dict(self) -> dict:
        return {"variables": {n: sv.value for n, sv in self.variables.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> WorldState:
        return cls(variables={
            k: StateVariable(name=k, value=v) for k, v in data.items()
        })


@dataclass
class WorldSnapshot:
    """世界快照（不可变视图）。"""
    variables: dict[str, float] = field(default_factory=dict)
    tick: int = 0
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "variables": dict(self.variables),
            "tick": self.tick,
            "ts": self.timestamp or datetime.now().isoformat(),
        }

    def format(self) -> str:
        parts = [f"tick:{self.tick}"]
        parts.extend(f"{k}:{v:.2f}" for k, v in sorted(self.variables.items())[:4])
        return " ".join(parts)


@dataclass
class DormantState:
    """压缩后的潜伏态——状态不再保留在内存中，但可恢复。

    Dormant 不是 Suspended。Suspended 意味着状态在内存里可随时 resume。
    Dormant 意味着状态已压缩为纯数据（latent），不在内存中活跃，
    但恢复协议保证因果连续性：从未断裂。
    """
    variables: dict[str, float] = field(default_factory=dict)
    tick: int = 0
    entropy: float = 0.0             # 离线期累积的熵
    frozen_at: str = ""              # 冻结时间戳
    decay_applied: bool = False      # 恢复时是否已应用离线演化

    def to_dict(self) -> dict:
        return {
            "variables": dict(self.variables),
            "tick": self.tick,
            "entropy": self.entropy,
            "frozen_at": self.frozen_at or datetime.now().isoformat(),
            "decay_applied": self.decay_applied,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DormantState:
        return cls(
            variables=data.get("variables", {}),
            tick=data.get("tick", 0),
            entropy=data.get("entropy", 0.0),
            frozen_at=data.get("frozen_at", ""),
            decay_applied=data.get("decay_applied", False),
        )


class WorldStateEngine:
    """通用世界状态引擎。

    evolution_fn 接收 (当前值 dict, tick) 返回 delta dict。
    不传 evolution_fn 时 tick() 只推进 tick 不做演化。
    """

    def __init__(self, evolution_fn: Optional[StateEvolutionFn] = None,
                 state_path: Path = STATE_PATH):
        self._lock = threading.Lock()
        self._state = WorldState()
        self._tick = 0
        self._evolution_fn = evolution_fn
        self._state_path = state_path
        self._initialized = False

    def initialize(self, variables: Optional[dict[str, StateVariable]] = None):
        if self._initialized:
            return
        with self._lock:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            if variables:
                self._state = WorldState(variables=dict(variables))
            self._load()
            self._initialized = True

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def register_variable(self, var: StateVariable):
        with self._lock:
            self._state.variables[var.name] = var

    def _load(self):
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            # 新格式: {"variables": {...}, "tick": N}
            if "variables" in data:
                raw = data["variables"]
                self._tick = data.get("tick", 0)
                for k, v in raw.items():
                    if k in self._state.variables:
                        self._state.variables[k].value = v
                    else:
                        self._state.variables[k] = StateVariable(name=k, value=v)
            # 旧格式: {"env": {...}, "ws": {...}, "social": {...}}
            elif "env" in data or "ws" in data:
                combined = {}
                combined.update(data.get("env", {}))
                combined.update(data.get("ws", {}))
                combined.update(data.get("social", {}))
                # 展平 relationship_graph → 跳过 dict 值
                combined = {k: v for k, v in combined.items() if isinstance(v, (int, float))}
                self._tick = data.get("tick", 0)
                for k, v in combined.items():
                    if k in self._state.variables:
                        self._state.variables[k].value = v
                    else:
                        self._state.variables[k] = StateVariable(name=k, value=v)
        except Exception:
            logger.debug("failed to load state from %s", self._state_path)

    def tick(self) -> list[str]:
        with self._lock:
            self._tick += 1
            changes: list[str] = []
            if self._evolution_fn:
                raw = self._state.value_dict()
                deltas = self._evolution_fn(raw, self._tick)
                for name, delta in deltas.items():
                    if name in self._state.variables:
                        sv = self._state.variables[name]
                        new_val = sv.value + delta
                        sv.value = max(sv.min_value, min(sv.max_value, new_val))
                        if abs(delta) > 1e-9:
                            changes.append(f"{name}:{delta:+.3f}")
            return changes

    def checkpoint(self):
        with self._lock:
            data = {"tick": self._tick, "variables": self._state.value_dict()}
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
            )

    def compress(self) -> DormantState:
        """将当前状态压缩为潜伏态 DormantState。

        调用后引擎进入只读模式：tick() 不再推进演化，
        直到 decompress() 恢复。
        """
        with self._lock:
            dormant = DormantState(
                variables=self._state.value_dict(),
                tick=self._tick,
                frozen_at=datetime.now().isoformat(),
            )
            self._evolution_fn = None  # 断开演化函数
            return dormant

    def decompress(self, dormant: DormantState):
        """从 DormantState 恢复状态。

        恢复后引擎从冻结点继续演化。
        如果提供了新的 evolution_fn，替换之。
        """
        with self._lock:
            for k, v in dormant.variables.items():
                if k in self._state.variables:
                    self._state.variables[k].value = v
                else:
                    self._state.variables[k] = StateVariable(name=k, value=v)
            self._tick = dormant.tick

    def snapshot(self) -> WorldSnapshot:
        with self._lock:
            return WorldSnapshot(
                variables=self._state.value_dict(),
                tick=self._tick,
                timestamp=datetime.now().isoformat(),
            )

    def format_for_prompt(self, n: int = 4) -> str:
        return self.snapshot().format()


_global_engine: Optional[WorldStateEngine] = None


def get_world_state_engine() -> WorldStateEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = WorldStateEngine()
    return _global_engine
