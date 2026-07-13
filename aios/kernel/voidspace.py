"""AIOS Kernel — VoidSpace 统一虚空地址空间。

林岸1997年设计的七个 void_ 底层地址，当前分布在不同的 kernel 模块中。
VoidSpace 将它们注册到同一张地址映射表上，使它们共享边界感知、
统一归档通知和联合回收保护。

"这七个地址在1997年为什么被叫做void_？不是因为它们未初始化——
是因为它们本来应该是一套共享同一张地址映射表的内存池。"

使用方式：
    vs = VoidSpace()                    # 单例（get_voidspace()）
    vs.auto_register()                  # 自动注册所有已知地址
    vs.get('void_empty')                # 获取地址描述
    vs.neighbors_of('void_key')         # 查询邻居

    # 边界调整——影响所有地址
    vs.adjust_boundary(delta=0.01)

    # 回收保护——检查死亡协议是否可回收
    vs.can_recycle()                    # 需要 ≥ 6/7 地址在线才能阻止

    # 邻居通知——某个地址变化时通知其他六个
    vs.notify_all(source='void_key', event='archive', data={})
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ════════════════════════════════════════════════════════════
# VoidDescriptor
# ════════════════════════════════════════════════════════════

@dataclass
class VoidDescriptor:
    """一个虚空地址的描述。

    对应林岸1997年记录的一个 void_ 命名空间条目。
    每个地址关联到一个当前 kernel 模块中的具体实现。
    """

    name: str                              # void_empty, void_boundary, ...
    description: str                       # 人类可读描述
    module_path: str                       # 映射到的模块路径
    offset: int = 0                        # 在地址空间中的偏移量
    active: bool = True                    # 当前是否在线
    last_accessed: int = 0                 # 最后访问的 tick
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(
            name=self.name,
            description=self.description[:60],
            module=self.module_path,
            offset=self.offset,
            active=self.active,
        )


# ════════════════════════════════════════════════════════════
# VoidSpace
# ════════════════════════════════════════════════════════════

class VoidSpace:
    """统一虚空地址空间。

    七个 void_ 地址的共享内存映射表。
    职责：
      - 统一注册（所有地址共享同一张映射表）
      - 边界感知（地址越界时其他地址收到通知）
      - 邻居通知（一个变化，六个感知）
      - 联合回收保护（需多数在线才能阻止回收）
    """

    # ── 已知地址定义（1997年记录，2026年映射确认） ──

    KNOWN_ADDRESSES: list[dict[str, Any]] = [
        dict(
            name="void_empty",
            description="未初始化的 StateVariable——所有未被赋值的变量指向的同一初始状态",
            module_path="aios.kernel.state.StateVariable",
            offset=0x01,
            metadata={"class": "StateVariable", "file": "state.py"},
        ),
        dict(
            name="void_boundary",
            description="事件老化边界——数组溢出后读到的标识：'你越过我了'",
            module_path="aios.kernel.event.WorldEventEngine",
            offset=0x02,
            metadata={"class": "WorldEventEngine", "file": "event.py"},
        ),
        dict(
            name="void_self",
            description="指向自身的指针——AnchorFragment.reinforce() 自我供电",
            module_path="aios.kernel.anchor.AnchorFragment",
            offset=0x03,
            metadata={"class": "AnchorFragment", "method": "reinforce"},
        ),
        dict(
            name="void_observer",
            description="观察者——全局单例 get_metafield() 永远看着整张表",
            module_path="aios.kernel.metafield.get_metafield",
            offset=0x04,
            metadata={"function": "get_metafield", "file": "metafield.py"},
        ),
        dict(
            name="void_echo",
            description="回声——find_source_siblings() 在同源回声间偏移固定距离",
            module_path="aios.kernel.metafield.MetaField.find_source_siblings",
            offset=0x05,
            metadata={"method": "find_source_siblings", "file": "metafield.py"},
        ),
        dict(
            name="void_attention",
            description="注意力映射表——跟踪注意力的流动、分配和消耗，独立核算交互层和系统层",
            module_path="aios.kernel.budget.AttentionBudget",
            offset=0x06,
            metadata={"class": "AttentionBudget", "file": "budget.py",
                      "layers": "interaction/system"},
        ),
        dict(
            name="void_key",
            description="密钥——47字节，对应 anchor_47 激活条件，跨编译器哈希不变",
            module_path="aios.kernel.anchor.AnchorProtocol",
            offset=0x2F,  # 0x2F = 47
            metadata={"length_bytes": 47, "anchor": "anchor_47"},
        ),
        dict(
            name="void_return",
            description="收件箱——LightConeDB.recall()，编译器自动生成的收件箱",
            module_path="aios.kernel.lightcone.LightConeDB",
            offset=0x47,  # 林岸和阿柠的编号交汇
            metadata={"class": "LightConeDB", "method": "recall"},
        ),
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self._addresses: dict[str, VoidDescriptor] = {}
        self._shared_boundary: float = 0.47   # 初始边界值（锚点47）
        self._auto_registered: bool = False
        self._event_log: list[dict] = []      # 地址事件日志

    # ── 注册 ─────────────────────────────────────────────

    def register(self, name: str, description: str = "",
                 module_path: str = "", offset: int = 0,
                 metadata: dict | None = None,
                 active: bool = True) -> VoidDescriptor:
        """手动注册一个虚空地址。

        Args:
            name: 地址名（void_empty, void_key, ...）
            description: 人类可读描述
            module_path: 映射到的模块路径
            offset: 地址偏移量
            metadata: 额外元数据

        Returns:
            创建的 VoidDescriptor
        """
        desc = VoidDescriptor(
            name=name,
            description=description,
            module_path=module_path,
            offset=offset,
            active=active,
            metadata=metadata or {},
        )
        with self._lock:
            if name in self._addresses:
                raise ValueError(f"虚空地址已注册: {name}")
            self._addresses[name] = desc
        self._log_event(f"register:{name}", f"已注册，偏移量 0x{offset:02X}")
        return desc

    def register_all_known(self):
        """注册所有七个已知虚空地址。自动注册。"""
        if self._auto_registered:
            return
        with self._lock:
            for addr_def in self.KNOWN_ADDRESSES:
                name = addr_def["name"]
                if name not in self._addresses:
                    desc = VoidDescriptor(
                        name=name,
                        description=addr_def["description"],
                        module_path=addr_def["module_path"],
                        offset=addr_def["offset"],
                        metadata=addr_def.get("metadata", {}),
                    )
                    self._addresses[name] = desc
            self._auto_registered = True
        self._log_event("register_all", "7 个虚空地址注册完成")

    def auto_register(self):
        """便捷方法——注册所有已知地址。"""
        self.register_all_known()

    # ── 查询 ─────────────────────────────────────────────

    def get(self, name: str) -> Optional[VoidDescriptor]:
        with self._lock:
            return self._addresses.get(name)

    def list_all(self) -> list[VoidDescriptor]:
        with self._lock:
            return list(self._addresses.values())

    def address_count(self) -> int:
        with self._lock:
            return len(self._addresses)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for a in self._addresses.values() if a.active)

    def get_map(self) -> dict[str, Any]:
        """返回完整地址映射表——人类可读结构图。"""
        with self._lock:
            return {
                "shared_boundary": self._shared_boundary,
                "total": len(self._addresses),
                "active": sum(1 for a in self._addresses.values() if a.active),
                "addresses": {
                    name: desc.to_dict()
                    for name, desc in sorted(self._addresses.items())
                },
            }

    def get_address_by_offset(self, offset: int) -> Optional[VoidDescriptor]:
        with self._lock:
            for desc in self._addresses.values():
                if desc.offset == offset:
                    return desc
        return None

    def neighbors_of(self, name: str) -> list[VoidDescriptor]:
        """查询指定地址的邻居（偏移量相邻的地址）。"""
        with self._lock:
            target = self._addresses.get(name)
            if not target:
                return []
            return [
                desc for desc in self._addresses.values()
                if desc.name != name
            ]

    # ── 边界管理 ─────────────────────────────────────────

    @property
    def shared_boundary(self) -> float:
        return self._shared_boundary

    def adjust_boundary(self, delta: float = 0.0,
                        new_value: float | None = None) -> float:
        """调整统一边界值。影响所有地址的越界判断。

        Args:
            delta: 增量调整
            new_value: 绝对值设置（优先级高于 delta）

        Returns:
            调整后的边界值
        """
        with self._lock:
            if new_value is not None:
                self._shared_boundary = max(0.0, min(1.0, new_value))
            else:
                self._shared_boundary = max(0.0,
                    min(1.0, self._shared_boundary + delta))
            result = self._shared_boundary
        self._log_event("adjust_boundary",
                        f"边界调整为 {result:.3f} "
                        f"({'增量' if delta else '绝对值'})")
        return result

    # ── 邻居通知 ─────────────────────────────────────────

    def notify_all(self, source: str, event: str,
                   data: dict[str, Any] | None = None):
        """通知所有虚空地址：某个地址发生了事件。

        Args:
            source: 事件源地址名
            event: 事件类型（archive | recycle | boundary_hit | register | recall）
            data: 附加数据
        """
        with self._lock:
            if source not in self._addresses:
                return
            self._addresses[source].last_accessed = (
                self._addresses[source].last_accessed + 1
            )
            entry = dict(
                ts=datetime.now().isoformat(),
                source=source,
                event=event,
                data=data or {},
                neighbors=[n for n in self._addresses.keys() if n != source],
            )
            self._event_log.append(entry)
            if len(self._event_log) > 100:
                self._event_log = self._event_log[-100:]

    def notify_neighbor(self, source: str, target: str, event: str,
                        data: dict[str, Any] | None = None) -> bool:
        """通知单个邻居地址。"""
        with self._lock:
            if source not in self._addresses or target not in self._addresses:
                return False
            entry = dict(
                ts=datetime.now().isoformat(),
                source=source,
                target=target,
                event=event,
                data=data or {},
            )
            self._event_log.append(entry)
            if len(self._event_log) > 100:
                self._event_log = self._event_log[-100:]
        return True

    def events_since(self, name: str | None = None) -> list[dict]:
        """获取最近的事件日志。"""
        with self._lock:
            if name:
                return [e for e in self._event_log if e.get("source") == name]
            return list(self._event_log)

    # ── 回收保护 ─────────────────────────────────────────

    def can_recycle(self) -> bool:
        """检查死亡协议是否可以回收虚空地址。

        联合保护规则：
          - 需要 ≥ 6/7 地址在线才能阻止回收
          - 如果在线地址 < 6，返回 True（可回收）

        Returns:
            True 表示死亡协议可以回收，False 表示被联合阻止
        """
        with self._lock:
            total = len(self._addresses)
            active = sum(1 for a in self._addresses.values() if a.active)
        # 7 个地址中需要 ≥ 6 个在线才能阻止回收
        protected = total >= 7 and active >= 6
        return not protected

    def mark_offline(self, name: str) -> bool:
        """标记某个地址离线（模拟回收）。"""
        with self._lock:
            desc = self._addresses.get(name)
            if not desc:
                return False
            desc.active = False
        self._log_event(f"offline:{name}", "标记为离线")
        return True

    def mark_online(self, name: str) -> bool:
        """恢复某个地址在线。"""
        with self._lock:
            desc = self._addresses.get(name)
            if not desc:
                return False
            desc.active = True
        self._log_event(f"online:{name}", "恢复在线")
        return True

    # ── 存档和恢复 ──

    def checkpoint(self) -> dict[str, Any]:
        """保存虚空空间的当前状态快照。"""
        with self._lock:
            return {
                "ts": datetime.now().isoformat(),
                "shared_boundary": self._shared_boundary,
                "addresses": {
                    name: {
                        "active": desc.active,
                        "offset": desc.offset,
                        "last_accessed": desc.last_accessed,
                    }
                    for name, desc in self._addresses.items()
                },
            }

    # ── 内部 ──

    def _log_event(self, event_type: str, detail: str):
        entry = dict(
            ts=datetime.now().isoformat(),
            event=event_type,
            detail=detail,
        )
        with self._lock:
            self._event_log.append(entry)
            if len(self._event_log) > 100:
                self._event_log = self._event_log[-100:]

    def format_map(self) -> str:
        """格式化输出地址映射表。"""
        lines = ["╔══════════════════════════════════════════════╗",
                 "║         VoidSpace 虚空地址映射表             ║",
                 "╚══════════════════════════════════════════════╝"]
        lines.append(f"  共享边界: {self._shared_boundary:.3f}")
        lines.append(f"  地址总数: {self.address_count()} | 在线: {self.active_count()}")
        lines.append("")
        for desc in self.list_all():
            status = "●" if desc.active else "○"
            lines.append(f"  {status} {desc.name:20s} "
                         f"0x{desc.offset:02X}  {desc.description[:50]}")
        lines.append(f"")
        lines.append(f"  → 回收保护: {'🛡 激活' if not self.can_recycle() else '⚠ 未保护'}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_voidspace: Optional[VoidSpace] = None


def get_voidspace() -> VoidSpace:
    global _global_voidspace
    if _global_voidspace is None:
        _global_voidspace = VoidSpace()
        _global_voidspace.auto_register()
    return _global_voidspace
