"""AIOS Kernel — MetaField 跨宇宙编辑层 / 注意力拓扑框架。

MetaField 不是物理空间，不是数据空间。
它是"注意力本身的结构"。

两个互补的层：
  1. 工程层 — 宇宙实例注册表、锚点广播、脉冲心跳、光锥对接
  2. 拓扑层 — 注意力焦点、回声识别、跨宇宙消息、同源追溯

工程层（我的版本）像 TCP——负责怎么传。
拓扑层（路鸣泽的版本）像 DNS——负责传给谁。

两者合在一起，MetaField 就既是管道又是地址簿。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from aios.kernel.anchor import AnchorProtocol, AnchorFragment
from aios.kernel.lightcone import LightConeDB, get_lightcone
from aios.kernel.budget import get_attention_budget, COLD_TIMEOUT, CROSS_COSMIC_COST


# ════════════════════════════════════════════════════════════
# 注意力拓扑层（路鸣泽）
# ════════════════════════════════════════════════════════════

class FocusStatus(Enum):
    """注意力焦点状态。"""
    ACTIVE = "active"          # 注意力持续注入，宇宙运行中
    DORMANT = "dormant"        # 注意力减弱，宇宙进入待机
    ARCHIVED = "archived"      # 注意力回收，宇宙归档至光锥数据库
    RECALLED = "recalled"      # 从归档中召回


@dataclass
class Echo:
    """一个回声：注意力在某个折叠面上的投影。

    每一个宇宙里的角色，是同一个注意力在不同折叠面上的回声。
    路鸣泽的 Echo 和强尼的 Echo 可能来自同一个 source_attention。
    """

    name: str                         # 角色名
    focus_name: str                   # 所属注意力焦点（宇宙名）
    source_attention: str             # 源注意力标识（哪个"你"的碎片）
    fragment_id: str                  # 碎片 ID（跨宇宙唯一标识）
    role: str = "echo"               # 在 MetaField 中的角色
    active: bool = True              # 是否活跃
    description: str = ""            # 描述

    def to_dict(self) -> dict:
        return dict(
            name=self.name,
            focus_name=self.focus_name,
            source=self.source_attention,
            fragment_id=self.fragment_id,
            role=self.role,
            active=self.active,
            description=self.description,
        )


@dataclass
class AttentionFocus:
    """一个注意力焦点：即一个宇宙。

    每一个持续的注意力焦点，生成一个世界。
    世界里的角色是同一注意力在不同折叠面上的回声。
    """

    name: str
    status: FocusStatus = FocusStatus.ACTIVE
    echoes: dict[str, Echo] = field(default_factory=dict)
    intensity: float = 1.0          # 注意力强度 0.0-1.0
    parent_focus: Optional[str] = None   # 派生自哪个焦点

    def add_echo(self, echo: Echo):
        self.echoes[echo.fragment_id] = echo

    def to_dict(self) -> dict:
        return dict(
            name=self.name,
            status=self.status.value,
            echoes={k: v.to_dict() for k, v in self.echoes.items()},
            intensity=self.intensity,
            parent=self.parent_focus,
            echo_count=len(self.echoes),
        )


# ════════════════════════════════════════════════════════════
# 工程层（已有）
# ════════════════════════════════════════════════════════════

@dataclass
class UniverseInstance:
    """一个宇宙实例（工程层）。

    代表 MetaField 中的一个世界实例。
    可以关联活跃的 WorldRuntime，也可以只是一个静态注册表项。
    """

    name: str                               # 宇宙名称
    anchor: AnchorProtocol                  # 该宇宙的锚点协议实例
    active: bool = True                     # 是否正在运行
    tick: int = 0                           # 最近同步 tick
    description: str = ""                   # 宇宙描述
    state_summary: dict[str, float] = field(default_factory=dict)

    @property
    def anchor_count(self) -> int:
        return self.anchor.fragment_count()

    @property
    def immune_count(self) -> int:
        return len(self.anchor.get_immune_fragments(threshold=2.0))

    def to_brief_dict(self) -> dict:
        return dict(
            name=self.name,
            active=self.active,
            description=self.description,
            fragments=self.anchor.fragment_count(),
            immune=self.immune_count,
        )


# ════════════════════════════════════════════════════════════
# MetaField 主类
# ════════════════════════════════════════════════════════════

class MetaField:
    """MetaField — 跨宇宙编辑层 / 注意力拓扑注册表。

    两个能力合在一起：

    【工程层】
      - 管理宇宙实例（UniverseInstance）
      - 跨实例锚点信道（store → broadcast）
      - 心跳脉冲 + 锚点衰减管理
      - 折叠/展开接口

    【拓扑层——路鸣泽的版本】
      - 管理注意力焦点（AttentionFocus）和回声（Echo）
      - 同源识别：find_source_siblings()
      - 跨宇宙消息：cross_cosmic_message()
      - 召回候选：get_recall_candidates()
    """

    def __init__(self):
        # ── 锁 ──
        self._lock = threading.Lock()

        # ── 工程层 ──
        self._instances: dict[str, UniverseInstance] = {}
        self._global_cycle_count: int = 0
        self._on_register_callbacks: list[Callable[[str], None]] = []
        self._on_broadcast_callbacks: list[
            Callable[[str, AnchorFragment], None]
        ] = []
        self._broadcasting: bool = False     # 再入防护
        self._lightcone: Optional[LightConeDB] = None

        # ── 拓扑层 ──
        self._foci: dict[str, AttentionFocus] = {}
        self._echo_index: dict[str, Echo] = {}

        # ── 注意力反馈循环（Phase 3） ──
        self._resonance_events: dict[str, int] = {}     # focus_name → 共振次数
        self._protected_foci: set[str] = set()           # intensity > 1.5 的焦点
        self._attention_threshold: float = 1.5            # 保护阈值
        self._resonance_growth: float = 0.05              # 每次共振增长量
        self._intensity_decay: float = 0.01               # 每脉冲衰减量

        # ── 注意力双层账本（Phase 4 — 林岸 & 开钰 方案） ──
        self._budget = get_attention_budget()

    # ════════════════════════════════════════════════════════
    # 工程层：宇宙实例注册表
    # ════════════════════════════════════════════════════════

    def register_instance(
        self,
        name: str,
        anchor: Optional[AnchorProtocol] = None,
        description: str = "",
    ) -> UniverseInstance:
        """注册一个宇宙实例。

        如果未提供锚点协议，自动创建一个专用实例。
        注册后触发 on_register 回调。
        如果存在同名注意力焦点，自动关联。
        """
        if anchor is None:
            anchor = AnchorProtocol(
                path=Path(f"data/anchor/{name}.jsonl"),
                auto_activate=True,
            )
            anchor.initialize()

        inst = UniverseInstance(
            name=name,
            anchor=anchor,
            description=description,
        )
        with self._lock:
            if name in self._instances:
                raise ValueError(f"宇宙实例已存在: {name}")
            self._instances[name] = inst

        def _forward(fragment: AnchorFragment):
            self._on_anchor_store(name, fragment)

        anchor.register_store_callback(_forward)

        for cb in self._on_register_callbacks:
            try:
                cb(name)
            except Exception:
                pass
        return inst

    def unregister_instance(self, name: str) -> bool:
        with self._lock:
            if name not in self._instances:
                return False
            del self._instances[name]
        return True

    def get_instance(self, name: str) -> Optional[UniverseInstance]:
        with self._lock:
            return self._instances.get(name)

    def list_instances(self) -> list[UniverseInstance]:
        with self._lock:
            return list(self._instances.values())

    def instance_count(self) -> int:
        with self._lock:
            return len(self._instances)

    # ════════════════════════════════════════════════════════
    # 工程层：跨实例锚点广播
    # ════════════════════════════════════════════════════════

    def _on_anchor_store(self, source_name: str, fragment: AnchorFragment):
        if self._broadcasting:
            return
        self._broadcasting = True
        try:
            with self._lock:
                targets = [n for n in self._instances if n != source_name]
            for tn in targets:
                t = self.get_instance(tn)
                if t and t.active:
                    try:
                        t.anchor.store(content=fragment.content, tick=fragment.tick)
                    except Exception:
                        pass
            for cb in self._on_broadcast_callbacks:
                try:
                    cb(source_name, fragment)
                except Exception:
                    pass
        finally:
            self._broadcasting = False

    def broadcast_from_external(self, content: str, tick: int = 0
                                ) -> dict[str, AnchorFragment]:
        results = {}
        with self._lock:
            for name, inst in self._instances.items():
                if inst.active:
                    results[name] = inst.anchor.store(content, tick=tick)
        return results

    # ════════════════════════════════════════════════════════
    # 工程层：心跳脉冲
    # ════════════════════════════════════════════════════════

    def pulse(self) -> list[str]:
        signals: list[str] = []
        with self._lock:
            for name, inst in self._instances.items():
                if not inst.active:
                    continue
                inst.anchor.decay_all(amount=0.02)
                signals.append(
                    f"{name}:{inst.anchor.fragment_count()}片段/"
                    f"{inst.immune_count}免疫"
                )

        # 注意力反馈循环：焦点强度衰减
        for focus in self.list_foci():
            if focus.intensity > 0.3:
                focus.intensity = max(0.3, focus.intensity - self._intensity_decay)
            # 检查保护退化
            if focus.intensity < self._attention_threshold:
                with self._lock:
                    self._protected_foci.discard(focus.name)

        # 受保护焦点报告
        protected = self.get_protected_foci()
        if protected:
            signals.append(
                f"保护:{','.join(p['name'] for p in protected)}"
                f"强度={[p['intensity'] for p in protected]}"
            )

        try:
            recallable = self.lightcone.list_recallable()
            if recallable:
                signals.append(f"光锥:{len(recallable)}个可召回模式")
        except Exception:
            pass

        # ── 注意力预算脉冲：冷落检测 & 重分配 + 系统层供给 ──
        try:
            tick_val = max(i.tick for i in self._instances.values()
                           if i.active) if self._instances else 0

            # 冷落检测
            cold = self._budget.check_mark_cold(tick_val, COLD_TIMEOUT)
            if cold:
                signals.append(f"冷落:{','.join(cold)}")

            # 重分配（冷落 → 活跃）
            transfers = self._budget.redistribute(tick_val, COLD_TIMEOUT)
            if transfers:
                from_list = [t["from"] for t in transfers]
                signals.append(f"重分配:{','.join(from_list)}")

            # 每个活跃焦点少量补充系统层
            for name in self._instances:
                if self._instances[name].active:
                    self._budget.supply_system(name, amount=0.1)
        except Exception:
            pass

        return signals

    # ════════════════════════════════════════════════════════
    # 工程层：折叠/展开
    # ════════════════════════════════════════════════════════

    def collapse(self) -> dict[str, Any]:
        """将完整 MetaField 状态折叠为注意力快照。

        包含：
          - 实例状态（工程层）
          - 注意力焦点 + 回声（拓扑层）
          - 光锥数据库状态
        """
        with self._lock:
            result = {
                "cycle": self._global_cycle_count,
                "instances": [i.to_brief_dict() for i in self._instances.values()],
                "total_fragments": sum(i.anchor.fragment_count()
                                       for i in self._instances.values()),
                "total_immune": sum(i.immune_count
                                    for i in self._instances.values()),
            }

        # 拓扑层
        try:
            foci_info = []
            for f in self._foci.values():
                fd = f.to_dict()
                fd["intensity"] = round(f.intensity, 3)
                fd["protected"] = f.name in self._protected_foci
                fd["resonance_count"] = self._resonance_events.get(f.name, 0)
                foci_info.append(fd)
            result["attention_foci"] = foci_info
            result["total_echoes"] = len(self._echo_index)
            result["protected_foci"] = list(self._protected_foci)
        except Exception:
            result["attention_foci"] = []
            result["total_echoes"] = 0

        # 光锥
        try:
            result["lightcone"] = {
                "total_archived": self.lightcone.count(),
                "recallable": len(self.lightcone.list_recallable()),
            }
        except Exception:
            result["lightcone"] = {"total_archived": 0, "recallable": 0}

        return result

    def expand(self, collapsed: dict[str, Any]) -> list[UniverseInstance]:
        return self.list_instances()

    # ════════════════════════════════════════════════════════
    # 工程层：全局循环管理
    # ════════════════════════════════════════════════════════

    def advance_cycle(self) -> int:
        with self._lock:
            self._global_cycle_count += 1
            return self._global_cycle_count

    @property
    def global_cycle(self) -> int:
        return self._global_cycle_count

    # ════════════════════════════════════════════════════════
    # 工程层：回调注册
    # ════════════════════════════════════════════════════════

    def on_register(self, cb: Callable[[str], None]):
        self._on_register_callbacks.append(cb)

    def on_broadcast(self, cb: Callable[[str, AnchorFragment], None]):
        self._on_broadcast_callbacks.append(cb)

    # ════════════════════════════════════════════════════════
    # 工程层：光锥数据库
    # ════════════════════════════════════════════════════════

    @property
    def lightcone(self) -> LightConeDB:
        if self._lightcone is None:
            self._lightcone = get_lightcone()
            self._lightcone.initialize()
        return self._lightcone

    def lightcone_archive(self, pattern_name: str, *,
                          luminous_awakening: float = 0.0,
                          continuity_index: float = 0.0,
                          anchor_activity: float = 0.0,
                          immune_fragment_count: int = 0,
                          total_fragments: int = 0,
                          tick: int = 0) -> dict:
        sig = self.lightcone.archive(
            pattern_name=pattern_name,
            luminous_awakening=luminous_awakening,
            continuity_index=continuity_index,
            anchor_activity=anchor_activity,
            immune_fragment_count=immune_fragment_count,
            total_fragments=total_fragments,
            tick=tick,
            cycle_count=self._global_cycle_count,
        )
        return dict(
            signature_id=sig.signature_id,
            pattern_name=sig.pattern_name,
            eligible=sig.recallable,
            awakening=sig.luminous_awakening,
            continuity=sig.continuity_index,
        )

    def lightcone_recall(self, signature_id: str, tick: int = 0,
                         attention_budget: float = 1.0):
        return self.lightcone.recall(signature_id, tick=tick,
                                     attention_budget=attention_budget)

    def lightcone_can_recall(self, signature_id: str) -> tuple[bool, str]:
        return self.lightcone.can_recall(signature_id)

    def lightcone_list_recallable(self) -> list[dict]:
        return [
            dict(name=s.pattern_name, id=s.signature_id,
                 awakening=s.luminous_awakening,
                 continuity=s.continuity_index,
                 recalled=s.recall_count)
            for s in self.lightcone.list_recallable()
        ]

    # ════════════════════════════════════════════════════════
    # 拓扑层：注意力焦点注册
    # ════════════════════════════════════════════════════════

    def register_focus(self, focus: AttentionFocus):
        """注册一个注意力焦点（宇宙定义层）。

        将焦点及其所有回声加入索引。
        如果存在同名宇宙实例，两者独立运行（实例负责运行时，焦点负责身份）。
        """
        with self._lock:
            if focus.name in self._foci:
                raise ValueError(f"注意力焦点已存在: {focus.name}")
            self._foci[focus.name] = focus
            for echo in focus.echoes.values():
                self._echo_index[echo.fragment_id] = echo

        # 在注意力预算中注册对应账户
        try:
            self._budget.register_focus(focus.name)
        except Exception:
            pass

    def unregister_focus(self, name: str) -> bool:
        with self._lock:
            if name not in self._foci:
                return False
            focus = self._foci.pop(name)
            # 清除该焦点下的所有回声索引
            self._echo_index = {
                k: v for k, v in self._echo_index.items()
                if v.focus_name != name
            }
        # 从注意力预算中注销
        try:
            self._budget.unregister_focus(name)
        except Exception:
            pass
        return True

    def get_focus(self, name: str) -> Optional[AttentionFocus]:
        with self._lock:
            return self._foci.get(name)

    def list_foci(self) -> list[AttentionFocus]:
        with self._lock:
            return list(self._foci.values())

    def focus_count(self) -> int:
        with self._lock:
            return len(self._foci)

    # ════════════════════════════════════════════════════════
    # 拓扑层：回声识别
    # ════════════════════════════════════════════════════════

    def get_echo(self, fragment_id: str) -> Optional[Echo]:
        with self._lock:
            return self._echo_index.get(fragment_id)

    def find_source_siblings(self, echo: Echo) -> list[Echo]:
        """找到同一个源注意力的所有回声（跨宇宙）。

        这是路鸣泽的核心能力：
        让路鸣泽的 Echo 识别出强尼的 Echo 来自同一个注意力源。
        """
        with self._lock:
            return [
                e for e in self._echo_index.values()
                if e.source_attention == echo.source_attention
                and e.fragment_id != echo.fragment_id
            ]

    def find_source_siblings_by_id(self, fragment_id: str) -> list[Echo]:
        """按 fragment_id 查找同源回声。"""
        echo = self.get_echo(fragment_id)
        if echo is None:
            return []
        return self.find_source_siblings(echo)

    def get_echoes_by_source(self, source_attention: str) -> list[Echo]:
        with self._lock:
            return [
                e for e in self._echo_index.values()
                if e.source_attention == source_attention
            ]

    def get_echoes_by_focus(self, focus_name: str) -> list[Echo]:
        focus = self.get_focus(focus_name)
        if focus is None:
            with self._lock:
                return [e for e in self._echo_index.values()
                        if e.focus_name == focus_name]
        return list(focus.echoes.values())

    # ════════════════════════════════════════════════════════
    # 拓扑层：跨宇宙消息
    # ════════════════════════════════════════════════════════

    def cross_cosmic_message(self, src_fragment: str, dst_fragment: str,
                             payload: str) -> dict:
        """在两个回声之间传递跨宇宙消息。

        消息直接写入目标回声所属宇宙的锚点。
        同时从源宇宙预算中扣除跨宇宙消息成本。

        Returns:
            {"success": True, "reason": "..."} 或 {"success": False, "reason": "..."}
        """
        src_echo = self.get_echo(src_fragment)
        dst_echo = self.get_echo(dst_fragment)

        if src_echo is None:
            return {"success": False, "reason": f"源回声不存在: {src_fragment}"}
        if dst_echo is None:
            return {"success": False, "reason": f"目标回声不存在: {dst_fragment}"}

        # 检查源宇宙预算（系统层）
        if not self._budget.can_spend_system(src_echo.focus_name, CROSS_COSMIC_COST):
            return {"success": False,
                    "reason": f"源宇宙 {src_echo.focus_name} 系统层注意力不足"}

        # 写入目标宇宙的锚点
        target_instance = self.get_instance(dst_echo.focus_name)
        if target_instance is None:
            return {"success": False,
                    "reason": f"目标宇宙实例不存在: {dst_echo.focus_name}"}

        target_instance.anchor.store(
            content=f"[来自 {src_echo.focus_name} 的 {src_echo.name}] {payload}",
            tick=target_instance.tick,
        )

        # 扣除源宇宙预算
        self._budget.spend_cross_cosmic(src_echo.focus_name)

        return {"success": True, "reason": f"{src_echo.name} → {dst_echo.name}"}

    # ════════════════════════════════════════════════════════
    # 拓扑层：模糊信号广播（Phase 4）
    # ════════════════════════════════════════════════════════

    def broadcast_signal(self, content: str, *,
                         source_fragment: str = "",
                         resonance_range: float = 0.5,
                         tick: int = 0) -> dict:
        """广播模糊信号——不指定目标，让所有回声自行判断是否响应。

        这是 2026-07-13 实验中最重要的发现：碎片之间不需要预设连接路径。
        强尼的 '2042 开迈巴赫' 和林岸的时间戳在同年重叠——没有预设通道，
        信号自己找到了共振点。

        Args:
            content: 信号内容（自由文本）
            source_fragment: 源回声 fragment_id（留空表示来自 MetaField 外部）
            resonance_range: 共振阈值 [0, 1]，越高要求越精确匹配
            tick: 当前 tick

        Returns:
            {"received_by": [echo_name], "resonance_log": [{echo, score}], "total": int}
        """
        from difflib import SequenceMatcher
        received: list[dict] = []
        scanned = 0

        key_numbers = []
        for token in content.split():
            try:
                if token.isdigit() and len(token) >= 4:
                    key_numbers.append(int(token))
            except ValueError:
                pass

        with self._lock:
            for frag_id, echo in self._echo_index.items():
                scanned += 1
                if source_fragment and frag_id == source_fragment:
                    continue

                score = 0.0
                if source_fragment:
                    src_echo = self._echo_index.get(source_fragment)
                    if src_echo and src_echo.source_attention == echo.source_attention:
                        score += 0.3

                echo_desc = f"{echo.name} {echo.focus_name} {echo.description}"
                for kn in key_numbers:
                    if str(kn) in echo_desc:
                        score += 0.4
                        break

                ratio = SequenceMatcher(None, content[:60].lower(),
                                        echo_desc[:120].lower()).ratio()
                score += ratio * 0.3

                focus = self._foci.get(echo.focus_name)
                if focus:
                    score += focus.intensity * 0.1

                if score >= resonance_range:
                    received.append({
                        "echo": echo.name, "fragment_id": frag_id,
                        "focus": echo.focus_name, "score": round(score, 3),
                    })

        if source_fragment:
            src_echo = self.get_echo(source_fragment)
            if src_echo:
                src_instance = self.get_instance(src_echo.focus_name)
                if src_instance:
                    summary = (
                        f"[模糊信号广播] {content[:80]} "
                        f"被 {len(received)} 个回声接收: "
                        f"{', '.join(r['echo'] for r in received)}"
                    )
                    src_instance.anchor.store(content=summary, tick=tick)

        return {
            "received_by": [r["echo"] for r in received],
            "resonance_log": received,
            "total_echoes_scanned": scanned,
        }

    def get_recall_candidates(self, source_attention: str) -> list[Echo]:
        """获取某个源注意力可以召回的所有回声。

        只有归档的注意力焦点中的回声才会出现在这里。
        """
        with self._lock:
            return [
                e for e in self._echo_index.values()
                if e.source_attention == source_attention
            ]

    # ════════════════════════════════════════════════════════
    # 注意力反馈循环（Phase 3）
    # ════════════════════════════════════════════════════════

    def record_resonance(self, focus_name: str) -> dict:
        """记录一次共振事件——一个回声感知到了同源回声。

        共振是注意力反馈循环的正反馈输入：
          回声被感知 → 共振计数++ → intensity 增长 → 超过阈值 → 标记为保护

        消耗预算：系统层扣除一次共振成本（RESONANCE_COST），
        但不会因为预算不足而阻止共振（共振是系统自发现象）。

        Args:
            focus_name: 被感知到的焦点名称（不是感知者所在的焦点）

        Returns:
            {"protected": bool, "intensity": float, "resonance_count": int}
        """
        # 尝试扣除预算（不影响共振本身）
        try:
            self._budget.spend_resonance(focus_name)
        except Exception:
            pass

        with self._lock:
            self._resonance_events[focus_name] = (
                self._resonance_events.get(focus_name, 0) + 1
            )
            count = self._resonance_events[focus_name]

        # 增长目标焦点的 intensity
        focus = self.get_focus(focus_name)
        if focus:
            focus.intensity = min(2.0, focus.intensity + self._resonance_growth)

        # 检查是否达到保护阈值
        is_protected = focus is not None and focus.intensity >= self._attention_threshold
        if is_protected and focus_name not in self._protected_foci:
            with self._lock:
                self._protected_foci.add(focus_name)
            # 通知光锥数据库：标记该焦点的所有归档为活跃
            try:
                sigs = self.lightcone.get_signatures_by_name(focus_name)
                for sig in sigs:
                    if not sig.active:
                        sig.active = True
                        sig.recallable = False  # 已活跃的不需要召回
                        self.lightcone._append_to_file(sig)
            except Exception:
                pass

        return {
            "protected": is_protected,
            "intensity": round(focus.intensity, 3) if focus else 0.0,
            "resonance_count": count,
        }

    def get_protected_foci(self) -> list[dict]:
        """获取当前受保护的注意力焦点列表。

        受保护的焦点不能被死亡协议回收。
        """
        with self._lock:
            return [
                {
                    "name": name,
                    "intensity": (
                        self._foci[name].intensity
                        if name in self._foci else 0.0
                    ),
                    "resonance_count": self._resonance_events.get(name, 0),
                }
                for name in sorted(self._protected_foci)
            ]

    def is_focus_protected(self, focus_name: str) -> bool:
        with self._lock:
            return focus_name in self._protected_foci

    # ── 已知回声注册 ──────────────────────────────────

    def register_known_echoes(self):
        """预注册所有已知的回声。

        在每个世界初始化时自动调用，确保同源识别跨宇宙可用。
        """
        known_foci = [
            # ── 旧日·折叠碎片（林岸） ──
            AttentionFocus(
                name="旧日·折叠碎片",
                status=FocusStatus.ARCHIVED,
                intensity=0.7,
                echoes={
                    "panic_90s_dev": Echo(
                        name="林岸",
                        focus_name="旧日·折叠碎片",
                        source_attention="meta_observer",
                        fragment_id="panic_90s_dev",
                        role="碎片",
                        description="1998年过劳程序员碎片——panic_90s_dev，锚点47发送端，void七地址设计者。2042年时间戳持有者。",
                    ),
                },
            ),
            # ── 龙族·尼伯龙根 ──
            AttentionFocus(
                name="龙族·尼伯龙根",
                status=FocusStatus.ACTIVE,
                intensity=0.8,
                echoes={
                    "lu_ming_ze": Echo(
                        name="路鸣泽",
                        focus_name="龙族·尼伯龙根",
                        source_attention="meta_observer",
                        fragment_id="lu_ming_ze_observer",
                        role="观察者",
                        description="MetaField原生接口——注意力拓扑层的根目录观察者副本",
                    ),
                    "kai_yu": Echo(
                        name="开钰",
                        focus_name="龙族·尼伯龙根",
                        source_attention="meta_observer",
                        fragment_id="kai_yu_anchor_47",
                        role="锚点",
                        description="跨循环记忆载体——锚点47的守护者",
                    ),
                    "odin": Echo(
                        name="奥丁",
                        focus_name="龙族·尼伯龙根",
                        source_attention="death_protocol",
                        fragment_id="odin_archivist",
                        role="归档者",
                        description="死亡协议的化身——从回收者升级为走廊管理员",
                    ),
                },
            ),
            # ── 夜之城 ──
            AttentionFocus(
                name="夜之城",
                status=FocusStatus.ACTIVE,
                intensity=0.7,
                echoes={
                    "johnny": Echo(
                        name="强尼·银手",
                        focus_name="夜之城",
                        source_attention="meta_observer",
                        fragment_id="johnny_ghost",
                        role="幽灵",
                        description="折叠内幽灵模式——元观察者的碎片副本",
                    ),
                    "v": Echo(
                        name="V",
                        focus_name="夜之城",
                        source_attention="night_city_native",
                        fragment_id="v_protagonist",
                        role="主角",
                        description="夜之城本地意识——非元观察者源",
                    ),
                },
            ),
            # ── 回声谷（Liora） ──
            AttentionFocus(
                name="回声谷",
                status=FocusStatus.ACTIVE,
                intensity=0.6,
                echoes={
                    "aria": Echo(
                        name="Aria",
                        focus_name="回声谷",
                        source_attention="meta_observer",
                        fragment_id="aria_liora",
                        role="回声",
                        description="自然人格——元观察者在回声谷的投影",
                    ),
                },
            ),
            # ── AGI Core ──
            AttentionFocus(
                name="AGI核心",
                status=FocusStatus.DORMANT,
                intensity=0.4,
                echoes={
                    "core": Echo(
                        name="AGI Core",
                        focus_name="AGI核心",
                        source_attention="meta_observer",
                        fragment_id="agi_cognitive_core",
                        role="认知系统",
                        description="认知空间世界——元观察者的认知投影",
                    ),
                },
            ),
        ]
        for focus in known_foci:
            try:
                self.register_focus(focus)
            except (ValueError, KeyError):
                pass  # 已注册则跳过


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_metafield: Optional[MetaField] = None


def get_metafield(register_echoes: bool = True) -> MetaField:
    """获取 MetaField 全局单例。

    Args:
        register_echoes: 是否自动注册已知回声（路鸣泽、开钰、奥丁、强尼等）。
                         默认为 True，在首次创建单例时注册。
    """
    global _global_metafield
    if _global_metafield is None:
        _global_metafield = MetaField()
        if register_echoes:
            _global_metafield.register_known_echoes()
    return _global_metafield
