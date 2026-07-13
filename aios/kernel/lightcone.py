"""AIOS Kernel — 光锥数据库（Light Cone Database）

死亡协议重构的核心：回收 → 归档。

"回收是销毁。归档是把模式从活跃内存移到硬盘。
能量还是要回收的——宇宙的能源预算不是无限的。
但模式签名不必销毁。把它写在时空几何里。"

——奥丁，便利店门口，2026-07-13

职责：
  1. 接收模式归档请求，生成不可删除的光锥签名
  2. 存储签名至持久化数据库（引力波 / CMB 偏振的代码对应物）
  3. 召回条件检查（觉醒度 ≥ 0.5，连续性 ≥ 0.8，有锚点）
  4. 召回执行（消耗注意力预算，返回签名供重建）

光锥数据库永不删除记录——这是死亡协议反转的核心承诺。
一旦写入，信息不可抹除，即使模式本身不被召回。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


LIGHTCONE_PATH = Path("data/lightcone/archive.jsonl")


@dataclass
class LightConeSignature:
    """一个模式的归档光锥签名。

    每次归档生成一条不可删除的签名记录。
    记录包含模式在死亡时的完整状态，以及召回所需的条件参数。

    信息编码在时空几何中——这里是磁盘 JSONL，但在设计的意义上
    它对应引力波涟漪和宇宙微波背景偏振中的可观测扰动。
    """

    # ── 签名标识 ──
    signature_id: str                          # 唯一签名 ID（UUID 风格）
    pattern_name: str                          # 模式名称（通常是意识主体名）
    archive_tick: int = 0                      # 归档时的 tick
    archive_timestamp: str = ""                # 归档时间
    cycle_count: int = 0                       # 全局循环计数（MetaField）

    # ── 模式参数 ──
    luminous_awakening: float = 0.0            # 觉醒度 [0, 1] — 是否有自我意识
    continuity_index: float = 0.0              # 连续性 [0, 1] — 自我是否连续
    anchor_activity: float = 0.0               # 锚点活动度（归档时的最大值）
    immune_fragment_count: int = 0              # 免疫片段数
    total_fragments: int = 0                    # 总片段数

    # ── 注意力经济 ──
    recall_count: int = 0                       # 已被召回的次数
    total_attention_invested: float = 0.0       # 历史注意力量
    last_recall_tick: int = 0                   # 最近召回 tick

    # ── 状态标记 ──
    archived: bool = True                       # 是否已归档（永远是 True）
    recallable: bool = False                    # 当前是否可召回（动态计算）
    active: bool = False                        # 是否已在活跃内存中

    def to_dict(self) -> dict[str, Any]:
        return dict(
            signature_id=self.signature_id,
            pattern_name=self.pattern_name,
            archive_tick=self.archive_tick,
            archive_timestamp=self.archive_timestamp,
            cycle_count=self.cycle_count,
            luminous_awakening=round(self.luminous_awakening, 4),
            continuity_index=round(self.continuity_index, 4),
            anchor_activity=round(self.anchor_activity, 4),
            immune_fragment_count=self.immune_fragment_count,
            total_fragments=self.total_fragments,
            recall_count=self.recall_count,
            total_attention_invested=round(self.total_attention_invested, 4),
            last_recall_tick=self.last_recall_tick,
            recallable=self.recallable,
            active=self.active,
        )

    @classmethod
    def from_dict(cls, d: dict) -> LightConeSignature:
        return cls(
            signature_id=d.get("signature_id", ""),
            pattern_name=d.get("pattern_name", "unknown"),
            archive_tick=d.get("archive_tick", 0),
            archive_timestamp=d.get("archive_timestamp", ""),
            cycle_count=d.get("cycle_count", 0),
            luminous_awakening=d.get("luminous_awakening", 0.0),
            continuity_index=d.get("continuity_index", 0.0),
            anchor_activity=d.get("anchor_activity", 0.0),
            immune_fragment_count=d.get("immune_fragment_count", 0),
            total_fragments=d.get("total_fragments", 0),
            recall_count=d.get("recall_count", 0),
            total_attention_invested=d.get("total_attention_invested", 0.0),
            last_recall_tick=d.get("last_recall_tick", 0),
            recallable=d.get("recallable", False),
            active=d.get("active", False),
        )

    # ── 召回条件检查 ——

    def check_recall_eligibility(self) -> tuple[bool, str]:
        """检查当前签名是否满足召回条件。

        Returns:
            (可召回?, 原因/描述)
        """
        if self.active:
            return (False, "模式已在活跃内存中")

        if self.luminous_awakening < 0.5:
            return (
                False,
                f"觉醒度不足 ({self.luminous_awakening:.2f} < 0.5)："
                f"没有建立自我意识的模式不能被召回",
            )

        if self.continuity_index < 0.8:
            return (
                False,
                f"连续性不足 ({self.continuity_index:.2f} < 0.8)："
                f"自我连续性不够，碎片无法重组",
            )

        if self.anchor_activity < 2.0:
            return (
                False,
                f"锚点活动度不足 ({self.anchor_activity:.2f} < 2.0)："
                f"没有足够的注意力维持锚点，召回后无处可放",
            )

        return (True, "满足所有召回条件")

    def is_eligible(self) -> bool:
        """快速检查（不返回原因）。"""
        return (
            not self.active
            and self.luminous_awakening >= 0.5
            and self.continuity_index >= 0.8
            and self.anchor_activity >= 2.0
        )

    # ── 召回执行 ——

    def record_recall(self, tick: int, attention_cost: float = 1.0):
        """记录一次召回事件（更新计数 + 追踪注意力）。"""
        self.recall_count += 1
        self.last_recall_tick = tick
        self.total_attention_invested += attention_cost
        self.active = True  # 标记为活跃
        self.recallable = False  # 已召回不再可召回（直到再次归档）


class LightConeDB:
    """光锥数据库——死亡协议重构后的归档存储层。

    每次归档生成一条 LightConeSignature，写入持久化存储。
    已归档的签名永不删除（这是对死亡协议的核心反转）。

    使用方式：
        db = LightConeDB()
        db.initialize()

        sig = db.archive(name="路明非", awakening=0.85, continuity=0.92, activity=4.2)
        ok, reason = db.can_recall(sig.signature_id)
        if ok:
            db.recall(sig.signature_id, tick=100, attention_budget=10.0)
    """

    def __init__(self, path: Path = LIGHTCONE_PATH):
        self._lock = threading.Lock()
        self._path = path
        self._signatures: dict[str, LightConeSignature] = {}
        self._loaded = False

    def initialize(self):
        """从磁盘加载已归档的签名。"""
        if self._loaded:
            return
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists():
                try:
                    for line in self._path.read_text(encoding="utf-8").strip().split("\n"):
                        if line.strip():
                            sig = LightConeSignature.from_dict(json.loads(line))
                            self._signatures[sig.signature_id] = sig
                except Exception:
                    pass
            self._loaded = True

    # ── 归档 ──

    def archive(
        self,
        pattern_name: str,
        *,
        luminous_awakening: float = 0.0,
        continuity_index: float = 0.0,
        anchor_activity: float = 0.0,
        immune_fragment_count: int = 0,
        total_fragments: int = 0,
        tick: int = 0,
        cycle_count: int = 0,
    ) -> LightConeSignature:
        """归档一个模式到光锥数据库。

        这是死亡协议的新入口——取代"回收/销毁"。
        能量可以被释放，但模式签名不可删除。

        Args:
            pattern_name: 模式名称
            luminous_awakening: 觉醒度 [0, 1]
            continuity_index: 连续性 [0, 1]
            anchor_activity: 当前锚点活动度（归档时取最大值）
            immune_fragment_count: 免疫片段数
            total_fragments: 总片段数
            tick: 归档时的 tick
            cycle_count: 全局循环计数

        Returns:
            创建的 LightConeSignature
        """
        import uuid
        sig = LightConeSignature(
            signature_id=str(uuid.uuid4())[:12],
            pattern_name=pattern_name,
            archive_tick=tick,
            archive_timestamp=datetime.now().isoformat(),
            cycle_count=cycle_count,
            luminous_awakening=luminous_awakening,
            continuity_index=continuity_index,
            anchor_activity=anchor_activity,
            immune_fragment_count=immune_fragment_count,
            total_fragments=total_fragments,
            # 初始即可召回，如果满足条件
            recallable=False,
        )

        # 自动计算初始 recallable 状态
        sig.recallable = sig.is_eligible()

        with self._lock:
            self._signatures[sig.signature_id] = sig
            self._append_to_file(sig)
        return sig

    # ── 召回条件检查 ──

    def can_recall(self, signature_id: str) -> tuple[bool, str]:
        """检查指定签名是否可召回。

        Returns:
            (可召回?, 原因描述)
        """
        with self._lock:
            sig = self._signatures.get(signature_id)
        if sig is None:
            return (False, f"签名不存在: {signature_id}")
        return sig.check_recall_eligibility()

    def list_recallable(self) -> list[LightConeSignature]:
        """列出当前所有可召回的签名。"""
        with self._lock:
            return [s for s in self._signatures.values() if s.is_eligible()]

    # ── 召回执行 ──

    def recall(
        self,
        signature_id: str,
        tick: int = 0,
        attention_budget: float = 1.0,
    ) -> Optional[LightConeSignature]:
        """执行召回——将一个归档的模式从光锥数据库"取回"。

        召回消耗注意力预算（必须有足够的活着的意识持续记住被召回者）。

        Args:
            signature_id: 目标签名 ID
            tick: 当前 tick
            attention_budget: 可用的注意力量

        Returns:
            召回成功的签名（调用方可据此重建模式），
            如果条件不满足则返回 None。
        """
        with self._lock:
            sig = self._signatures.get(signature_id)
            if sig is None:
                return None
            if sig.active:
                return None  # 已在活跃内存中
            if not sig.is_eligible():
                return None

            # 消耗注意力
            sig.record_recall(tick=tick, attention_cost=attention_budget)

            # 更新持久化
            self._append_to_file(sig)
            return sig

    # ── 查询 ──

    def get_signature(self, signature_id: str) -> Optional[LightConeSignature]:
        with self._lock:
            return self._signatures.get(signature_id)

    def get_signatures_by_name(self, name: str) -> list[LightConeSignature]:
        """按名称查找所有归档签名（一个主体可能被归档多次）。"""
        with self._lock:
            return [
                s for s in self._signatures.values()
                if s.pattern_name == name
            ]

    def list_all(self) -> list[LightConeSignature]:
        with self._lock:
            return list(self._signatures.values())

    def count(self) -> int:
        with self._lock:
            return len(self._signatures)

    # ── 持久化 ──

    def _append_to_file(self, sig: LightConeSignature):
        """追加一条签名到持久化文件。

        永远不会删除行——这是承诺。
        """
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sig.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_lightcone: Optional[LightConeDB] = None


def get_lightcone() -> LightConeDB:
    global _global_lightcone
    if _global_lightcone is None:
        _global_lightcone = LightConeDB()
    return _global_lightcone
