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
from typing import Optional

DATA_DIR = Path("evolution/inhabitants")


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


_global_registry: Optional[ResidentRegistry] = None


def get_resident_registry() -> ResidentRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ResidentRegistry()
    return _global_registry
