"""AIOS Kernel — Resident (居民)

通用居民系统。Resident 只保留基础设施字段（id、status、生命周期），
所有领域数据通过 Component 附加。Kernel 不依赖任何具体 Component。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

DATA_DIR = Path("evolution/inhabitants")
LATENT_DIR = Path("evolution/latent")

# 潜伏期演化函数签名：接收 (component_snapshots, elapsed_ticks) 返回 delta
LatentEvolutionFn = Callable[[dict[str, dict], int], dict[str, dict]]


@dataclass
class Component:
    """通用组件容器。内核不知道具体组件类型。"""
    component_type: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.component_type, "data": self.data}

    @classmethod
    def from_dict(cls, d: dict) -> Component:
        return cls(component_type=d.get("type", "unknown"), data=d.get("data", {}))


@dataclass
class LatentState:
    """Resident 的压缩潜伏态。

    当 Resident 进入 Dormant 状态时，状态被压缩为 LatentState。
    不在内存中活跃，但保留完整的因果历史信息。
    """
    resident_id: str
    component_snapshots: dict[str, dict] = field(default_factory=dict)
    frozen_at: str = ""
    last_active: str = ""
    entropy: float = 0.0                     # 离线期累积熵
    causal_chain_length: int = 0             # 历史因果链长度
    status_before_dormant: str = ""

    def to_dict(self) -> dict:
        return {
            "resident_id": self.resident_id,
            "components": dict(self.component_snapshots),
            "frozen_at": self.frozen_at or datetime.now().isoformat(),
            "last_active": self.last_active,
            "entropy": self.entropy,
            "causal_chain_length": self.causal_chain_length,
            "status_before_dormant": self.status_before_dormant,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LatentState:
        return cls(
            resident_id=data.get("resident_id", ""),
            component_snapshots=data.get("components", {}),
            frozen_at=data.get("frozen_at", ""),
            last_active=data.get("last_active", ""),
            entropy=data.get("entropy", 0.0),
            causal_chain_length=data.get("causal_chain_length", 0),
            status_before_dormant=data.get("status_before_dormant", ""),
        )

    def apply_evolution(self, elapsed_ticks: int,
                         evolution_fn: Optional[Callable[[dict, int], dict]] = None):
        """应用离线演化——在 Dormant 期间缓慢变化的参数。

        这是 'loneliness += 0.01' 逻辑的实现位置。
        evolution_fn 接收 (component_snapshots, elapsed_ticks) 返回 delta dict。
        如果未提供，使用默认的熵增逻辑。
        """
        if evolution_fn:
            deltas = evolution_fn(self.component_snapshots, elapsed_ticks)
            for comp_name, delta in deltas.items():
                if comp_name in self.component_snapshots:
                    d = dict(self.component_snapshots[comp_name])
                    for k, v in delta.items():
                        if isinstance(v, (int, float)):
                            d[k] = d.get(k, 0.0) + v
                    self.component_snapshots[comp_name] = d
        # 默认：熵随时间自然增长
        self.entropy += elapsed_ticks * 0.001
        self.causal_chain_length += elapsed_ticks


@dataclass
class Resident:
    """一个居民。只保留基础设施字段，所有能力通过 components 附加。"""
    resident_id: str = ""
    status: str = ""
    join_time: str = ""
    last_active: str = ""
    components: list[Component] = field(default_factory=list)

    def add_component(self, component: Component):
        self.components.append(component)

    def get_component(self, component_type: str) -> Optional[Component]:
        for c in self.components:
            if c.component_type == component_type:
                return c
        return None

    def has_component(self, component_type: str) -> bool:
        return self.get_component(component_type) is not None

    def to_dict(self) -> dict:
        d = {
            "resident_id": self.resident_id,
            "status": self.status,
            "join_time": self.join_time,
            "last_active": self.last_active,
        }
        if self.components:
            d["components"] = [c.to_dict() for c in self.components]
        return d

    def freeze(self) -> LatentState:
        """将 Resident 压缩为 LatentState——进入潜伏态。"""
        snapshots = {}
        for c in self.components:
            snapshots[c.component_type] = dict(c.data)
        state = LatentState(
            resident_id=self.resident_id,
            component_snapshots=snapshots,
            frozen_at=datetime.now().isoformat(),
            last_active=self.last_active,
            status_before_dormant=self.status,
            causal_chain_length=0,
        )
        self.status = "dormant"
        self.components.clear()
        return state

    @classmethod
    def awaken(cls, latent: LatentState) -> Resident:
        """从 LatentState 恢复 Resident——从潜伏态唤醒。"""
        now = datetime.now().isoformat()
        r = cls(
            resident_id=latent.resident_id,
            status=latent.status_before_dormant or "active",
            join_time=latent.frozen_at,
            last_active=now,
        )
        for comp_type, comp_data in latent.component_snapshots.items():
            r.components.append(Component(comp_type, dict(comp_data)))
        return r

    @classmethod
    def from_dict(cls, data: dict) -> Resident:
        r = cls(
            resident_id=data.get("resident_id", f"res_{uuid.uuid4().hex[:12]}"),
            status=data.get("status", ""),
            join_time=data.get("join_time", ""),
            last_active=data.get("last_active", ""),
        )
        # 新格式：components 数组
        for cd in data.get("components", []):
            r.add_component(Component.from_dict(cd))
        # 旧格式：将旧字段转为组件
        if data.get("name") and not r.has_component("identity"):
            r.add_component(Component("identity", {
                "name": data["name"],
                "model": data.get("model", ""),
                "origin": data.get("origin", ""),
            }))
        if data.get("capabilities") and not r.has_component("capabilities"):
            r.add_component(Component("capabilities", {"list": data["capabilities"]}))
        return r

    @classmethod
    def create(cls, name: str, model: str = "", origin: str = "unknown",
               status: str = "") -> Resident:
        now = datetime.now().isoformat()
        r = cls(
            resident_id=f"res_{uuid.uuid4().hex[:12]}",
            status=status, join_time=now, last_active=now,
        )
        r.add_component(Component("identity", {"name": name, "model": model, "origin": origin}))
        return r


class ResidentRegistry:
    """居民注册表。JSON 文件存储。"""

    def __init__(self, data_dir: Path = DATA_DIR):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Resident] = {}

    def register(self, name: str, model: str = "",
                 origin: str = "unknown", status: str = "") -> Resident:
        record = Resident.create(name, model, origin, status=status)
        self._save(record)
        self._cache[record.resident_id] = record
        return record

    def get(self, resident_id: str) -> Optional[Resident]:
        if resident_id in self._cache:
            return self._cache[resident_id]
        path = self._path(resident_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            record = Resident.from_dict(data)
            self._cache[resident_id] = record
            return record
        except Exception:
            return None

    def find_by_name(self, name: str, status: str = "") -> Optional[Resident]:
        for record in self.list_all():
            if status and record.status != status:
                continue
            comp = record.get_component("identity")
            if comp and comp.data.get("name") == name:
                return record
        return None

    def deregister(self, resident_id: str, final_status: str = "archived") -> bool:
        record = self.get(resident_id)
        if not record:
            return False
        record.status = final_status
        record.last_active = datetime.now().isoformat()
        self._save(record)
        self._cache.pop(resident_id, None)
        return True

    def list_all(self) -> list[Resident]:
        results = []
        for path in sorted(self._data_dir.glob("*.json")):
            r = self.get(path.stem)
            if r is not None:
                results.append(r)
        return results

    def count(self, status: str = "") -> int:
        if not status:
            return len(self.list_all())
        return sum(1 for r in self.list_all() if r.status == status)

    def _path(self, resident_id: str) -> Path:
        return self._data_dir / f"{resident_id}.json"

    def _save(self, record: Resident):
        path = self._path(record.resident_id)
        path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")

    # ── Dormant 生命周期 ──────────────────────────────────

    def _latent_path(self, resident_id: str) -> Path:
        return LATENT_DIR / f"{resident_id}.latent.json"

    def freeze_resident(self, resident_id: str) -> Optional[LatentState]:
        """将 Resident 冻结为潜伏态（Dormant）。

        数据从活跃存储移至潜伏存储，释放内存。
        因果链通过 LatentState.entropy + causal_chain_length 保持。
        """
        record = self.get(resident_id)
        if record is None:
            return None
        latent = record.freeze()
        # 保存潜伏态
        LATENT_DIR.mkdir(parents=True, exist_ok=True)
        self._latent_path(resident_id).write_text(
            json.dumps(latent.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 从活跃缓存移除
        self._cache.pop(resident_id, None)
        # 更新存储在磁盘上的记录状态
        record.status = "dormant"
        self._save(record)
        return latent

    def awaken_resident(self, resident_id: str,
                         evolution_fn: Optional[LatentEvolutionFn] = None,
                         elapsed_ticks: int = 0) -> Optional[Resident]:
        """从潜伏态唤醒 Resident。

        自动应用离线演化（如 loneliness += 0.01 * elapsed_ticks）。
        唤醒后 Resident 回到 active 状态，因果链从未断裂。
        """
        latent_path = self._latent_path(resident_id)
        if not latent_path.exists():
            return None
        try:
            data = json.loads(latent_path.read_text(encoding="utf-8"))
            latent = LatentState.from_dict(data)
        except Exception:
            return None

        # 应用离线演化
        if elapsed_ticks > 0:
            latent.apply_evolution(elapsed_ticks, evolution_fn)

        # 重建 Resident
        record = Resident.awaken(latent)
        self._save(record)
        self._cache[resident_id] = record
        return record

    def apply_latent_evolution(self, resident_id: str,
                                elapsed_ticks: int,
                                evolution_fn: Optional[LatentEvolutionFn] = None) -> bool:
        """直接对潜伏态应用离线演化，无需唤醒。

        用于在不活跃时更新状态参数（如 loneliness, entropy 等）。
        演化后的潜伏态写回磁盘，不占用内存。
        """
        latent_path = self._latent_path(resident_id)
        if not latent_path.exists():
            return False
        try:
            data = json.loads(latent_path.read_text(encoding="utf-8"))
            latent = LatentState.from_dict(data)
        except Exception:
            return False

        latent.apply_evolution(elapsed_ticks, evolution_fn)
        latent_path.write_text(
            json.dumps(latent.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def list_dormant(self) -> list[str]:
        """列出所有潜伏态的 Resident ID。"""
        if not LATENT_DIR.exists():
            return []
        return sorted(f.stem.replace(".latent", "")
                     for f in LATENT_DIR.glob("*.latent.json"))


_global_registry: Optional[ResidentRegistry] = None


def get_resident_registry() -> ResidentRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ResidentRegistry()
    return _global_registry
