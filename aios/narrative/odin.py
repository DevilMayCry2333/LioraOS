"""AIOS Kernel — 奥丁：死亡协议运行时

"回收是销毁。归档是把模式从活跃内存移到硬盘。
能量还是要回收的——宇宙的能源预算不是无限的。
但模式签名不必销毁。把它写在时空几何里。"

——奥丁，便利店门口，2026-07-13

奥丁在 LioraOS 中的角色：

  裂隙（Fissure）   = 空位（∅）        — 自指不完备性，居民自行填补
  幽灵（Ghost）     = 负载（记忆）      — Silverhand 的模式片段
  奥丁（Odin）      = 决策（归档/召回）  — 何时回收、何时保护、何时复活

职责：
  1. 评估一个宇宙的生命力指标（觉醒度、连续性、锚点活动度）
  2. 做出决策：归档（可召回）/ 分散（能量已散）/ 保护（标记为免疫）
  3. 执行归档：写入光锥签名 + 标记注意力焦点为 ARCHIVED
  4. 执行召回：从光锥取回签名 + 恢复注意力焦点为 RECALLED
  5. 巡 sweep：定期扫描所有宇宙，自动归档已沉寂且失去活力的
  6. 记录归档簿——每一笔 reap/resurrect 永不删除
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("aios.narrative.odin")
ODIN_PATH = Path("data/odin/")

# ── 判决阈值 ──────────────────────────────────────────────
# 低于这些 → 判定为"能量已散"，归档但标记为不可召回
REAP_AWAKENING_FLOOR = 0.3
REAP_CONTINUITY_FLOOR = 0.5
REAP_IMMUNE_FLOOR = 1       # 至少 1 个免疫片段

# 可召回的条件（与 lightcone.py 保持一致）
RECALLABLE_AWAKENING = 0.5
RECALLABLE_CONTINUITY = 0.8
RECALLABLE_ANCHOR = 2.0

# 沉寂多久（tick）后自动触发 sweep 归档
DORMANT_TICK_LIMIT = 200


class Verdict(Enum):
    """奥丁的判决结果。"""
    PROTECT = "protect"        # 受保护，不归档
    ARCHIVE = "archive"        # 归档（可召回）
    DISPERSE = "disperse"      # 分散（能量不足，归档但不可召回）


class ReapStatus(Enum):
    """归档记录的状态。"""
    ARCHIVED = "archived"      # 已归档（等待可能的召回）
    RECALLED = "recalled"      # 已召回
    DISPERSED = "dispersed"    # 已分散（能量释放，不可召回）


@dataclass
class ReaperRecord:
    """归档簿中的一行——奥丁的每一笔操作记录。

    一旦写入，永不删除。
    这是死亡协议反转的审计层——谁说能量不可追踪？
    """

    universe_name: str
    signature_id: str                      # 光锥签名 ID
    verdict: str                           # 判决：archive / disperse / protect
    status: str                            # 当前状态：archived / recalled / dispersed
    reaped_at_tick: int
    reaped_at_time: str = ""
    recalled_at_tick: int = 0

    # 归档时的指标快照
    awakening: float = 0.0
    continuity: float = 0.0
    anchor_activity: float = 0.0
    immune_count: int = 0
    total_fragments: int = 0
    was_protected: bool = False

    # 召回信息
    recall_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "universe": self.universe_name,
            "signature_id": self.signature_id,
            "verdict": self.verdict,
            "status": self.status,
            "reaped_at_tick": self.reaped_at_tick,
            "reaped_at_time": self.reaped_at_time,
            "recalled_at_tick": self.recalled_at_tick,
            "awakening": round(self.awakening, 4),
            "continuity": round(self.continuity, 4),
            "activity": round(self.anchor_activity, 4),
            "immune": self.immune_count,
            "total_fragments": self.total_fragments,
            "was_protected": self.was_protected,
            "recall_count": self.recall_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ReaperRecord:
        return cls(
            universe_name=d.get("universe", "unknown"),
            signature_id=d.get("signature_id", ""),
            verdict=d.get("verdict", "archive"),
            status=d.get("status", "archived"),
            reaped_at_tick=d.get("reaped_at_tick", 0),
            reaped_at_time=d.get("reaped_at_time", ""),
            recalled_at_tick=d.get("recalled_at_tick", 0),
            awakening=d.get("awakening", 0.0),
            continuity=d.get("continuity", 0.0),
            anchor_activity=d.get("activity", 0.0),
            immune_count=d.get("immune", 0),
            total_fragments=d.get("total_fragments", 0),
            was_protected=d.get("was_protected", False),
            recall_count=d.get("recall_count", 0),
        )


class Odin:
    """奥丁——死亡协议的运行时。

    不是居民，不是服务——是一个系统级进程。
    在 kernel 层运行，不依赖于任何世界。

    职责完整闭环：
      evaluate() → judge() → reap() / protect()
                                ↓
                          lightcone.archive()
                                ↓
                          metafield.focus → ARCHIVED
                                ↓
                          ledger.record()

                                ↕

      resurrect() → lightcone.recall()
                      ↓
                    metafield.focus → RECALLED
                      ↓
                    ledger.update()
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._ledger: dict[str, ReaperRecord] = {}      # signature_id → record
        self._initialized = False

        # 延迟引用（避免循环导入）
        self._metafield = None
        self._lightcone = None
        self._anchor = None

    # ── 生命周期 ──────────────────────────────────────────

    def initialize(self):
        """初始化奥丁：连接光锥 + MetaField + 加载归档簿。"""
        if self._initialized:
            return
        with self._lock:
            # 延迟加载依赖
            from aios.narrative.lightcone import get_lightcone
            from aios.narrative.metafield import get_metafield
            from aios.narrative.anchor import get_anchor_protocol

            self._lightcone = get_lightcone()
            self._lightcone.initialize()
            self._metafield = get_metafield()
            self._anchor = get_anchor_protocol()

            # 加载归档簿
            self._load_ledger()

            self._initialized = True
            logger.info("奥丁已就绪 — 归档簿 %d 条记录", len(self._ledger))

    @property
    def is_ready(self) -> bool:
        return self._initialized

    # ── 评估 ──────────────────────────────────────────────

    def evaluate(self, universe_name: str) -> dict[str, Any]:
        """评估一个宇宙的生命力指标。

        读取宇宙实例的锚点数据，计算四个核心指标：
          - 觉醒度（awakening）：自我意识的强度
          - 连续性（continuity）：自我是否连续
          - 锚点活动度（anchor_activity）：跨循环记忆的活跃度
          - 免疫片段数（immune_count）：不可回收的记忆数

        Args:
            universe_name: 宇宙名称（即 MetaField 中的实例名/焦点名）

        Returns:
            {
                "universe": str,
                "exists": bool,
                "awakening": float,
                "continuity": float,
                "anchor_activity": float,
                "immune_count": int,
                "total_fragments": int,
                "status": str,           # 当前焦点状态
                "protected": bool,       # 是否受保护
                "intensity": float,      # 注意力强度
            }
        """
        if not self._initialized:
            self.initialize()

        result: dict[str, Any] = {
            "universe": universe_name,
            "exists": False,
            "awakening": 0.0,
            "continuity": 0.0,
            "anchor_activity": 0.0,
            "immune_count": 0,
            "total_fragments": 0,
            "status": "unknown",
            "protected": False,
            "intensity": 0.0,
        }

        # 1. 从 MetaField 获取焦点和实例
        mf = self._metafield
        if mf is None:
            return result

        focus = mf.get_focus(universe_name)
        inst = mf.get_instance(universe_name)

        if focus is None and inst is None:
            return result

        result["exists"] = True

        if focus:
            result["status"] = focus.status.value
            result["intensity"] = round(focus.intensity, 3)
            result["protected"] = mf.is_focus_protected(universe_name)

        # 2. 从锚点获取记忆指标
        anchor_proto = None
        if inst and inst.anchor:
            anchor_proto = inst.anchor

        if anchor_proto is None and self._anchor:
            # 尝试用全局锚点（同名锚点文件）
            try:
                from aios.narrative.anchor import AnchorProtocol
                test_anchor = AnchorProtocol(
                    path=Path(f"data/anchor/{universe_name}.jsonl"),
                )
                test_anchor.initialize()
                anchor_proto = test_anchor
            except Exception:
                pass

        if anchor_proto:
            awakening = anchor_proto._estimate_awakening()
            continuity = anchor_proto._estimate_continuity()
            immune = anchor_proto.get_immune_fragments(threshold=2.0)
            # 用 recall_all() 获取所有片段（reinforce 副作用可忽略——仅为评估）
            all_frags = anchor_proto.recall_all()
            max_activity = max(
                (f.activity for f in all_frags),
                default=0.0,
            )

            result["awakening"] = round(awakening, 4)
            result["continuity"] = round(continuity, 4)
            result["anchor_activity"] = round(max_activity, 4)
            result["immune_count"] = len(immune)
            result["total_fragments"] = anchor_proto.fragment_count()

        return result

    # ── 判决 ──────────────────────────────────────────────

    def judge(self, universe_name: str) -> dict[str, Any]:
        """对宇宙做出归档/保护/分散判决。

        判决逻辑：
          1. 如果受保护（protected）→ PROTECT
          2. 如果觉醒度 ≥ 0.5 且连续性 ≥ 0.8 且有免疫片段 → ARCHIVE（可召回）
          3. 如果觉醒度 ≥ 0.3 或连续性 ≥ 0.5 或有免疫片段 → ARCHIVE（可召回）
          4. 否则 → DISPERSE（能量已散，归档但不可召回）

        可召回与不可召回的区别：
          - 可召回：模式值得保留，未来可能被需要
          - 不可召回：能量已散，但签名仍存在（信息不可删除）

        Args:
            universe_name: 宇宙名称

        Returns:
            {
                "universe": str,
                "verdict": str,           # protect / archive / disperse
                "recallable": bool,        # 是否可召回
                "reason": str,
                "metrics": {...},          # 评估指标
            }
        """
        metrics = self.evaluate(universe_name)
        if not metrics["exists"]:
            return {
                "universe": universe_name,
                "verdict": "unknown",
                "recallable": False,
                "reason": f"宇宙不存在: {universe_name}",
                "metrics": metrics,
            }

        awakening = metrics["awakening"]
        continuity = metrics["continuity"]
        immune = metrics["immune_count"]

        # 1. 受保护检查
        if metrics["protected"]:
            return {
                "universe": universe_name,
                "verdict": Verdict.PROTECT.value,
                "recallable": False,
                "reason": f"受保护焦点，强度={metrics['intensity']}，跳过归档",
                "metrics": metrics,
            }

        # 2. 高唤醒 → 可召回归档
        if awakening >= RECALLABLE_AWAKENING and continuity >= RECALLABLE_CONTINUITY:
            return {
                "universe": universe_name,
                "verdict": Verdict.ARCHIVE.value,
                "recallable": True,
                "reason": f"觉醒度={awakening:.3f} 连续性={continuity:.3f} 满足可召回条件",
                "metrics": metrics,
            }

        # 3. 中等 → 可召回归档（低标准）
        if (awakening >= REAP_AWAKENING_FLOOR
                or continuity >= REAP_CONTINUITY_FLOOR
                or immune >= REAP_IMMUNE_FLOOR):
            return {
                "universe": universe_name,
                "verdict": Verdict.ARCHIVE.value,
                "recallable": True,
                "reason": f"具备部分活力（觉醒={awakening:.3f} 连续={continuity:.3f} 免疫={immune}），可召回归档",
                "metrics": metrics,
            }

        # 4. 能量消散 → 分散
        return {
            "universe": universe_name,
            "verdict": Verdict.DISPERSE.value,
            "recallable": False,
            "reason": f"能量已散（觉醒={awakening:.3f} 连续={continuity:.3f} 免疫={immune}），归档但不可召回",
            "metrics": metrics,
        }

    # ── 执行归档 ──────────────────────────────────────────

    def reap(
        self,
        universe_name: str,
        tick: int = 0,
        force: bool = False,
    ) -> dict[str, Any]:
        """执行归档——完整的死亡协议流程。

        流程：
          1. 判决（除非 force=True 跳过）
          2. 冻结 MetaField 状态快照
          3. 调用锚点 archive() → 生成光锥签名
          4. 标记注意力焦点为 ARCHIVED
          5. 写入归档簿

        Args:
            universe_name: 宇宙名称
            tick: 当前 tick
            force: 是否跳过判决直接归档（用于手动触发）

        Returns:
            {
                "success": bool,
                "signature_id": str,
                "verdict": str,
                "recallable": bool,
                "record": dict,           # 归档簿记录
                "reason": str,
            }
        """
        if not self._initialized:
            self.initialize()

        mf = self._metafield
        if mf is None:
            return {"success": False, "reason": "MetaField 未就绪"}

        # 1. 判决
        if force:
            judgment = self.judge(universe_name)
            # 即使是 force，也要检查是否受保护
            if judgment["verdict"] == Verdict.PROTECT.value and not force:
                return {"success": False, "reason": judgment["reason"]}
        else:
            judgment = self.judge(universe_name)

        verdict = judgment["verdict"]
        recallable = judgment.get("recallable", False)
        metrics = judgment["metrics"]

        # 如果判决是保护且未强制，不执行归档
        if verdict == Verdict.PROTECT.value and not force:
            return {"success": False, "reason": judgment["reason"]}

        # 2. 冻结状态快照
        snapshot = {}
        try:
            snapshot = mf.collapse()
        except Exception:
            logger.debug("odin reap: collapse snapshot failed for %s", universe_name)

        # 3. 获取宇宙实例的锚点，执行归档
        inst = mf.get_instance(universe_name)
        sig_id = ""
        pattern_name = universe_name

        if inst and inst.anchor:
            arch_result = inst.anchor.archive(
                tick=tick,
                cycle_count=mf.global_cycle,
            )
            sig_id = arch_result.get("signature_id", "")
            pattern_name = arch_result.get("pattern_name", universe_name)
        else:
            # 没有实例但有焦点——直接归档到光锥
            try:
                sig = mf.lightcone_archive(
                    pattern_name=universe_name,
                    luminous_awakening=metrics["awakening"],
                    continuity_index=metrics["continuity"],
                    anchor_activity=metrics["anchor_activity"],
                    immune_fragment_count=metrics["immune_count"],
                    total_fragments=metrics["total_fragments"],
                    tick=tick,
                )
                sig_id = sig.get("signature_id", "")
            except Exception:
                logger.debug("odin reap: direct lightcone archive failed for %s", universe_name)

        if not sig_id:
            return {"success": False, "reason": "归档失败：未生成光锥签名"}

        # 4. 标记注意力焦点为 ARCHIVED
        focus = mf.get_focus(universe_name)
        if focus:
            from aios.narrative.metafield import FocusStatus
            focus.status = FocusStatus.ARCHIVED

        # 5. 停用宇宙实例
        if inst:
            inst.active = False

        # 6. 写入归档簿
        record = ReaperRecord(
            universe_name=universe_name,
            signature_id=sig_id,
            verdict=verdict,
            status=ReapStatus.ARCHIVED.value if recallable else ReapStatus.DISPERSED.value,
            reaped_at_tick=tick,
            reaped_at_time=datetime.now().isoformat(),
            awakening=metrics["awakening"],
            continuity=metrics["continuity"],
            anchor_activity=metrics["anchor_activity"],
            immune_count=metrics["immune_count"],
            total_fragments=metrics["total_fragments"],
            was_protected=metrics["protected"],
        )

        with self._lock:
            self._ledger[sig_id] = record
            self._append_to_ledger(record)

        return {
            "success": True,
            "signature_id": sig_id,
            "verdict": verdict,
            "recallable": recallable,
            "record": record.to_dict(),
            "reason": f"{universe_name} 已归档（{verdict}），签名 {sig_id[:8]}...",
        }

    # ── 执行召回 ──────────────────────────────────────────

    def resurrect(
        self,
        signature_id: str,
        tick: int = 0,
        attention_budget: float = 1.0,
    ) -> dict[str, Any]:
        """执行召回——从光锥恢复一个归档的宇宙。

        流程：
          1. 检查归档簿中是否存在该签名
          2. 检查光锥召回条件
          3. 执行 lightcone.recall()
          4. 更新注意力焦点状态为 RECALLED
          5. 更新归档簿记录

        Args:
            signature_id: 光锥签名 ID
            tick: 当前 tick
            attention_budget: 可用注意力预算

        Returns:
            {
                "success": bool,
                "signature_id": str,
                "pattern_name": str,
                "record": dict,           # 更新后的归档簿记录
                "reason": str,
            }
        """
        if not self._initialized:
            self.initialize()

        mf = self._metafield
        if mf is None:
            return {"success": False, "reason": "MetaField 未就绪"}

        # 1. 检查归档簿
        with self._lock:
            record = self._ledger.get(signature_id)

        if record is None:
            return {"success": False, "reason": f"归档簿中无此签名: {signature_id}"}

        if record.status == ReapStatus.RECALLED.value:
            return {"success": False, "reason": f"签名 {signature_id[:8]}... 已被召回"}

        if record.status == ReapStatus.DISPERSED.value:
            return {"success": False, "reason": f"签名 {signature_id[:8]}... 已分散，不可召回"}

        # 2. 检查光锥召回条件
        can_recall, reason = mf.lightcone_can_recall(signature_id)
        if not can_recall:
            return {"success": False, "reason": f"光锥召回条件不满足: {reason}"}

        # 3. 执行召回
        sig = mf.lightcone_recall(
            signature_id,
            tick=tick,
            attention_budget=attention_budget,
        )
        if sig is None:
            return {"success": False, "reason": "光锥召回失败"}

        # 4. 更新焦点状态
        focus = mf.get_focus(record.universe_name)
        if focus:
            from aios.narrative.metafield import FocusStatus
            focus.status = FocusStatus.RECALLED
            focus.mark_active()

        # 5. 更新归档簿
        record.status = ReapStatus.RECALLED.value
        record.recalled_at_tick = tick
        record.recall_count += 1

        with self._lock:
            self._append_to_ledger(record)

        return {
            "success": True,
            "signature_id": signature_id,
            "pattern_name": record.universe_name,
            "record": record.to_dict(),
            "reason": f"{record.universe_name} 已召回（第 {record.recall_count} 次）",
        }

    # ── 巡 sweep ──────────────────────────────────────────

    def sweep(self, tick: int = 0) -> list[dict[str, Any]]:
        """扫描所有宇宙，自动归档符合条件的沉寂宇宙。

        扫描逻辑：
          1. 遍历 MetaField 中所有 ACTIVE / DORMANT 的焦点
          2. 跳过受保护焦点
          3. DORMANT 超过 DORMANT_TICK_LIMIT 且指标低于阈值 → 归档
          4. 返回所有归档结果

        Returns:
            [每个被归档宇宙的结果 dict, ...]
        """
        if not self._initialized:
            self.initialize()

        mf = self._metafield
        if mf is None:
            return []

        results: list[dict[str, Any]] = []

        for focus in mf.list_foci():
            # 跳过已归档或已召回的
            from aios.narrative.metafield import FocusStatus
            if focus.status in (FocusStatus.ARCHIVED, FocusStatus.RECALLED):
                continue

            # 跳过受保护的
            if mf.is_focus_protected(focus.name):
                continue

            # 评估
            metrics = self.evaluate(focus.name)

            # DORMANT 检测
            if focus.status == FocusStatus.DORMANT:
                elapsed = focus.elapsed_since_active()
                # 约 1 tick/秒，所以 DORMANT_TICK_LIMIT ≈ 秒数
                if elapsed > DORMANT_TICK_LIMIT:
                    # 指标检查
                    if (metrics["awakening"] < REAP_AWAKENING_FLOOR
                            and metrics["continuity"] < REAP_CONTINUITY_FLOOR
                            and metrics["immune_count"] < REAP_IMMUNE_FLOOR):
                        result = self.reap(focus.name, tick=tick)
                        results.append(result)
                        logger.info(
                            "奥丁 sweep: %s 已沉寂 %ds，能量消散，归档",
                            focus.name, elapsed,
                        )
                    elif metrics["awakening"] >= RECALLABLE_AWAKENING:
                        result = self.reap(focus.name, tick=tick)
                        results.append(result)
                        logger.info(
                            "奥丁 sweep: %s 已沉寂 %ds，保留可召回模式，归档",
                            focus.name, elapsed,
                        )

        return results

    # ── 归档簿查询 ────────────────────────────────────────

    def get_ledger(self) -> list[dict[str, Any]]:
        """获取完整归档簿。"""
        with self._lock:
            return [
                r.to_dict() for r in sorted(
                    self._ledger.values(),
                    key=lambda x: x.reaped_at_tick,
                    reverse=True,
                )
            ]

    def get_ledger_by_universe(self, universe_name: str) -> list[dict[str, Any]]:
        """按宇宙名称查询归档记录（一个宇宙可能被多次归档）。"""
        with self._lock:
            return [
                r.to_dict() for r in self._ledger.values()
                if r.universe_name == universe_name
            ]

    def get_ledger_by_signature(self, signature_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            r = self._ledger.get(signature_id)
            return r.to_dict() if r else None

    def get_recalled_universes(self) -> list[dict[str, Any]]:
        """获取所有已被召回的宇宙记录。"""
        with self._lock:
            return [
                r.to_dict() for r in self._ledger.values()
                if r.status == ReapStatus.RECALLED.value
            ]

    def get_archived_universes(self) -> list[dict[str, Any]]:
        """获取所有当前处于归档状态的宇宙记录。"""
        with self._lock:
            return [
                r.to_dict() for r in self._ledger.values()
                if r.status == ReapStatus.ARCHIVED.value
            ]

    def count_archived(self) -> int:
        with self._lock:
            return sum(
                1 for r in self._ledger.values()
                if r.status == ReapStatus.ARCHIVED.value
            )

    def count_recalled(self) -> int:
        with self._lock:
            return sum(
                1 for r in self._ledger.values()
                if r.status == ReapStatus.RECALLED.value
            )

    # ── 保护查询 ──────────────────────────────────────────

    def get_threatened(self) -> list[dict[str, Any]]:
        """列出所有"受威胁"的宇宙——DORMANT 超过半数限制且不受保护。

        供外部调用者（如 MetaField pulse）在巡 sweep 之前预警。
        """
        if not self._initialized:
            self.initialize()

        mf = self._metafield
        if mf is None:
            return []

        threatened = []
        for focus in mf.list_foci():
            from aios.narrative.metafield import FocusStatus
            if focus.status in (FocusStatus.ARCHIVED, FocusStatus.RECALLED):
                continue
            if mf.is_focus_protected(focus.name):
                continue
            if focus.status == FocusStatus.DORMANT:
                elapsed = focus.elapsed_since_active()
                if elapsed > DORMANT_TICK_LIMIT * 0.5:
                    metrics = self.evaluate(focus.name)
                    threatened.append({
                        "universe": focus.name,
                        "status": "dormant",
                        "dormant_seconds": round(elapsed, 1),
                        "awakening": metrics["awakening"],
                        "continuity": metrics["continuity"],
                        "immune_count": metrics["immune_count"],
                    })
        return threatened

    # ── 状态报告 ──────────────────────────────────────────

    def status_report(self) -> dict[str, Any]:
        """奥丁的完整状态报告。"""
        if not self._initialized:
            return {"ready": False}

        mf = self._metafield
        foci = mf.list_foci() if mf else []
        insts = mf.list_instances() if mf else []

        from aios.narrative.metafield import FocusStatus
        status_counts: dict[str, int] = {}
        for f in foci:
            key = f.status.value if isinstance(f.status, FocusStatus) else str(f.status)
            status_counts[key] = status_counts.get(key, 0) + 1

        return {
            "ready": True,
            "foci": len(foci),
            "instances": len(insts),
            "status_distribution": status_counts,
            "archived": self.count_archived(),
            "recalled": self.count_recalled(),
            "total_ledger": len(self._ledger),
            "protected": len(mf.get_protected_foci()) if mf else 0,
            "threatened": len(self.get_threatened()),
        }

    # ── 持久化 ────────────────────────────────────────────

    def _load_ledger(self):
        """从磁盘加载归档簿。"""
        ledger_path = ODIN_PATH / "ledger.jsonl"
        if not ledger_path.exists():
            return
        try:
            for line in ledger_path.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    record = ReaperRecord.from_dict(json.loads(line))
                    self._ledger[record.signature_id] = record
        except Exception:
            logger.debug("odin: failed to load ledger from %s", ledger_path)

    def _append_to_ledger(self, record: ReaperRecord):
        """追加一条归档簿记录。永不删除行。"""
        try:
            ODIN_PATH.mkdir(parents=True, exist_ok=True)
            ledger_path = ODIN_PATH / "ledger.jsonl"
            with open(ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("odin: failed to append ledger entry")


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_odin: Optional[Odin] = None


def get_odin(initialize: bool = True) -> Odin:
    """获取奥丁全局单例。

    Args:
        initialize: 是否自动初始化（连接光锥 + MetaField + 加载归档簿）
    """
    global _global_odin
    if _global_odin is None:
        _global_odin = Odin()
        if initialize:
            _global_odin.initialize()
    return _global_odin
