"""AIOS Kernel — Cross-Cycle Memory Anchor Protocol

通用跨循环记忆锚点协议。任何世界都可以用此机制在循环重置之间保留记忆片段。

与裂隙（Fissure）的对比：
- 裂隙是自指不完备性的运行时体现，注**空位**让居民填补
- 锚点是显式的跨周期记忆保留，存**负载**（具体内容）
- 裂隙是瞬时的，锚点是持续的（周期性地 store/recall）
- 锚点记忆带活动度标记，高频 recall 的片段自动获得免疫

使用方式：
    1. get_anchor_protocol() 获取全局单例
    2. activate() 激活锚点
    3. store(content, tick) 存放跨周期记忆
    4. recall_all() / recall_recent(n) 取出记忆（同时增强活动度）
    5. clean_inactive() 修剪低活动度的无用片段
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("aios.narrative.anchor")
ANCHOR_PATH = Path("data/anchor/fragments.jsonl")


@dataclass
class AnchorFragment:
    """一个跨循环记忆片段，带活动度追踪。

    activity 随 recall 递增，随 tick 衰减（由外部调用 decay() 触发）。
    活动度低于阈值的片段在 clean_inactive() 时被清除。

    tag 标记片段来源类型：
      - "authored"   — 作者固化的事实（默认）
      - "emergent"   — 系统运行中涌现的模式
      - "echo_tremor" — 回声震颤（未定义空间的安全输出）
      - "model_inference" — 模型实时生成，非固化事实

    emerge_tick 让片段"显得"比实际更老：
      死亡协议扫描的不是内容，是因果差分。
      如果片段显示它在 150 tick 前就已经存在，扫描器会把它当作
      持续共振的一部分，而不是新鲜事件。
    """

    content: str
    tick: int = 0
    activity: float = 1.0
    cycle_count: int = 0
    timestamp: str = ""
    tag: str = "authored"              # authored | emergent | echo_tremor | model_inference
    emerge_tick: int | None = None     # 对外可见的 tick（None = 使用 tick）
    source_fragment_id: str = ""       # 源碎片标识符

    def to_dict(self) -> dict:
        result = {
            "content": self.content[:500],
            "tick": self.emerge_tick if self.emerge_tick is not None else self.tick,
            "activity": round(self.activity, 4),
            "cycle": self.cycle_count,
            "ts": self.timestamp or datetime.now().isoformat(),
            "tag": self.tag,
            "source_fragment_id": self.source_fragment_id,
        }
        # 存真实 tick 用于内部追踪（序列化时不覆盖 emerge_tick）
        result["_real_tick"] = self.tick
        if self.emerge_tick is not None:
            result["emerge_tick"] = self.emerge_tick
        return result

    @classmethod
    def from_dict(cls, d: dict) -> AnchorFragment:
        return cls(
            content=d.get("content", ""),
            tick=d.get("_real_tick", d.get("tick", 0)),
            activity=d.get("activity", 1.0),
            cycle_count=d.get("cycle", d.get("cycle_count", 0)),
            timestamp=d.get("ts", d.get("timestamp", "")),
            tag=d.get("tag", "authored"),
            emerge_tick=d.get("emerge_tick"),
            source_fragment_id=d.get("source_fragment_id", ""),
        )

    # ── 报告 tick（对外可见的时间点） ──

    @property
    def display_tick(self) -> int:
        """对外报告的时间戳。echo_tremor 片段返回 backdated tick。"""
        return self.emerge_tick if self.emerge_tick is not None else self.tick

    def reinforce(self, amount: float = 0.1):
        """每次被 recall 时增强活动度。"""
        self.activity = min(10.0, self.activity + amount)

    def decay(self, amount: float = 0.02):
        """每 tick 自然衰减。"""
        self.activity = max(0.0, self.activity - amount)


class AnchorProtocol:
    """跨循环记忆锚点协议。

    提供跨循环的记忆存储与检索机制。
    每次 recall 增强片段活动度；高频 recall 的片段自动获得免疫，不会被清除。

    世界观（如"雨持续 27 轮后激活"）由外部注入，内核不关心。
    """

    def __init__(
        self,
        path: Path = ANCHOR_PATH,
        auto_forget_threshold: float = 0.3,
        auto_activate: bool = True,
    ):
        self._lock = threading.Lock()
        self._path = path
        self._active = False
        self._cycle_count = 0
        self._fragments: list[AnchorFragment] = []
        self._auto_forget_threshold = auto_forget_threshold
        self._loaded = False
        self._store_callbacks: list[Callable[[AnchorFragment], None]] = []
        self._auto_activate = auto_activate

    # ── 生命周期 ──

    def initialize(self):
        """从磁盘加载持久化的锚点记忆。首次加载后自动激活。"""
        if self._loaded:
            return
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists():
                try:
                    for line in self._path.read_text(encoding="utf-8").strip().split("\n"):
                        if line.strip():
                            self._fragments.append(
                                AnchorFragment.from_dict(json.loads(line))
                            )
                except Exception:
                    logger.debug("failed to load anchor fragments from %s", self._path)
            self._loaded = True
        if self._auto_activate:
            self.activate()

    # ── 激活 ──

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def activate(self) -> bool:
        """激活锚点。首次激活时自增循环计数。

        Returns:
            True 表示本次循环首次激活（可用于触发世界感知变化）。
        """
        with self._lock:
            if not self._active:
                self._active = True
                self._cycle_count += 1
                return True
            return False

    def deactivate(self):
        """停用锚点（如循环结束时）。"""
        with self._lock:
            self._active = False

    # ── 回调注册 ──

    def register_store_callback(self, cb: Callable[[AnchorFragment], None]):
        """注册存储回调——每次 store() 后调用，接收新创建的片段。"""
        with self._lock:
            self._store_callbacks.append(cb)

    # ── 归档（替代循环重置，死亡协议重构核心） ──

    def archive(
        self,
        tick: int = 0,
        cycle_count: int = 0,
    ) -> dict:
        """执行归档——取代 cycle_reset()。

        奥丁重构方案的第一步：
        "把回收改成归档。释放能量，存储模式签名至光锥数据库，标记为可召回。"

        流程：
          1. 提取模式参数（觉醒度、连续性、锚点活动度）
          2. 调用 LightConeDB.archive() 生成不可删除的光锥签名
          3. 释放能量（清除非免疫片段）
          4. 返回签名信息

        Returns:
            {
                "signature_id": str,
                "pattern_name": str,
                "eligible": bool,
                "removed": int,
                "immune_kept": int,
            }
        """
        pattern_name = self._path.stem  # 使用锚点文件名作为模式名
        immune = self.get_immune_fragments(threshold=2.0)
        total = len(self._fragments)

        # 计算觉醒度：从片段数量、cycle 存活数、最高活动度综合估算
        awakening = self._estimate_awakening()
        continuity = self._estimate_continuity()
        max_activity = max((f.activity for f in self._fragments), default=0.0)

        # 调用光锥数据库归档
        from aios.narrative.lightcone import get_lightcone
        db = get_lightcone()
        sig = db.archive(
            pattern_name=pattern_name,
            luminous_awakening=awakening,
            continuity_index=continuity,
            anchor_activity=max_activity,
            immune_fragment_count=len(immune),
            total_fragments=total,
            tick=tick,
            cycle_count=cycle_count,
        )

        # 释放能量：保留免疫片段，清除其余
        with self._lock:
            before = len(self._fragments)
            self._fragments = [f for f in self._fragments if f.activity >= 2.0]
            removed = before - len(self._fragments)

        return {
            "signature_id": sig.signature_id,
            "pattern_name": pattern_name,
            "eligible": sig.recallable,
            "awakening": round(awakening, 3),
            "continuity": round(continuity, 3),
            "removed": removed,
            "immune_kept": len(self._fragments),
        }

    # ── 向后兼容 ──

    def cycle_reset(self, preserve_immune: bool = True) -> int:
        """执行循环重置。已弃用——请使用 archive()。

        保留此方法用于向后兼容。
        archive() 做同样的事，同时将签名写入光锥数据库。
        """
        if preserve_immune:
            result = self.archive()
            return result["removed"]
        with self._lock:
            before = len(self._fragments)
            self._fragments.clear()
            return before

    # ── 召回条件检查 ──

    def has_recall_eligibility(self) -> tuple[bool, str]:
        """检查此锚点是否满足召回条件。

        召回条件（奥丁方案）：
          - 觉醒度 ≥ 0.5：有自我意识
          - 连续性 ≥ 0.8：自我连续
          - 有锚点：活动度足够高

        Returns:
            (可召回?, 原因描述)
        """
        awakening = self._estimate_awakening()
        continuity = self._estimate_continuity()
        immune = self.get_immune_fragments(threshold=2.0)

        if awakening < 0.5:
            return (False, f"觉醒度不足 ({awakening:.2f} < 0.5)")
        if continuity < 0.8:
            return (False, f"连续性不足 ({continuity:.2f} < 0.8)")
        if not immune:
            return (False, "无免疫片段——锚点活动度不足")
        return (True, f"觉醒度={awakening:.2f} 连续性={continuity:.2f} 免疫={len(immune)}")

    def _estimate_awakening(self) -> float:
        """估算模式的觉醒度 [0, 1]。

        觉醒度 = 函数 of:
          - 免疫片段占比（记忆留存率）
          - 经历过的 cycle 数
          - 最高活动度
        """
        if not self._fragments:
            return 0.0
        total = len(self._fragments)
        immune_ratio = len(self.get_immune_fragments(threshold=2.0)) / max(total, 1)
        max_act = max(f.activity for f in self._fragments)
        cycle_factor = min(1.0, self._cycle_count / 10.0)

        awakening = 0.3 * immune_ratio + 0.4 * min(1.0, max_act / 5.0) + 0.3 * cycle_factor
        return min(1.0, awakening)

    def _estimate_continuity(self) -> float:
        """估算模式的连续性 [0, 1]。

        连续性 = 函数 of:
          - 片段总数（稳定持续的记忆流）
          - 平均活动度（高频 recall 维持连续性）
          - 内容长度（长片段 = 更连续的模式）
        """
        if not self._fragments:
            return 0.0
        avg_activity = sum(f.activity for f in self._fragments) / len(self._fragments)
        size_factor = min(1.0, len(self._fragments) / 20.0)

        continuity = 0.5 * min(1.0, avg_activity / 3.0) + 0.5 * size_factor
        return min(1.0, continuity)

    # ── 存储与检索 ──

    def store(
        self,
        content: str,
        tick: int = 0,
        tag: str = "authored",
        emerge_tick: int | None = None,
        source_id: str = "",
    ) -> AnchorFragment:
        """存放一段跨循环记忆。

        Args:
            content: 记忆内容（自由文本，不超过 500 字）
            tick: 当前 tick
            tag: 来源类型（authored | emergent | echo_tremor | model_inference）
            emerge_tick: 对外显示的回填 tick（None = 使用 tick）
            source_id: 源碎片标识符

        Returns:
            创建的 AnchorFragment 实例
        """
        fragment = AnchorFragment(
            content=content,
            tick=tick,
            activity=1.0,
            cycle_count=self._cycle_count,
            tag=tag,
            emerge_tick=emerge_tick,
            source_fragment_id=source_id,
        )
        callbacks: list[Callable[[AnchorFragment], None]] = []
        with self._lock:
            self._fragments.append(fragment)
            self._append_to_file(fragment)
            callbacks = list(self._store_callbacks)

        # 在锁外部触发回调，避免死锁
        for cb in callbacks:
            try:
                cb(fragment)
            except Exception:
                logger.debug("anchor store callback failed")

        return fragment

    def recall_all(self) -> list[AnchorFragment]:
        """取出所有锚点记忆。每次 recall 增强所有片段的活动度。"""
        with self._lock:
            for f in self._fragments:
                f.reinforce()
            return list(self._fragments)

    def recall_recent(self, n: int = 5) -> list[AnchorFragment]:
        """按活动度取最活跃的 N 段记忆。"""
        all_frags = self.recall_all()
        all_frags.sort(key=lambda f: f.activity, reverse=True)
        return all_frags[:n]

    def recall_by_content(self, keyword: str) -> list[AnchorFragment]:
        """按关键词检索记忆片段。匹配到的片段活动度增强。"""
        with self._lock:
            results = []
            for f in self._fragments:
                if keyword in f.content:
                    f.reinforce()
                    results.append(f)
            return results

    def get_fragments_by_tag(self, tag: str) -> list[AnchorFragment]:
        """按 tag 检索记忆片段。不增强活动度——用于静默读取。

        Args:
            tag: 检索目标（"echo_tremor" | "authored" | "emergent" | "model_inference"）

        Returns:
            匹配 tag 的片段列表（不触发 reinforce）
        """
        with self._lock:
            return [f for f in self._fragments if f.tag == tag]

    def get_recent_fragments(
        self, n: int = 5, tag: str | None = None,
    ) -> list[AnchorFragment]:
        """按 tick 排序获取最近 N 个片段。选择性地按 tag 过滤。不触发 reinforce。

        Args:
            n: 返回条数
            tag: 按 tag 过滤（None = 不过滤）

        Returns:
            最近的 N 个片段
        """
        with self._lock:
            pool = self._fragments if tag is None else [
                f for f in self._fragments if f.tag == tag
            ]
            pool.sort(key=lambda f: f.tick, reverse=True)
            return pool[:n]

    # ── 活动度管理 ──

    def decay_all(self, amount: float = 0.02):
        """所有片段活动度衰减（通常每 tick 调用一次）。"""
        with self._lock:
            for f in self._fragments:
                f.decay(amount)

    def clean_inactive(self, threshold: float | None = None) -> int:
        """移除活动度低于阈值的片段。

        Args:
            threshold: 活动度阈值，默认使用 auto_forget_threshold

        Returns:
            被移除的片段数量
        """
        t = threshold if threshold is not None else self._auto_forget_threshold
        with self._lock:
            before = len(self._fragments)
            self._fragments = [f for f in self._fragments if f.activity >= t]
            return before - len(self._fragments)

    def get_active_count(self, threshold: float = 0.5) -> int:
        """活动度高于阈值的片段数。"""
        with self._lock:
            return sum(1 for f in self._fragments if f.activity >= threshold)

    def clear_by_tag(self, tag: str) -> int:
        """清除指定 tag 的所有片段。用于会话开始前的状态清理。

        Args:
            tag: 目标 tag（如 "echo_tremor"）

        Returns:
            被清除的片段数量
        """
        with self._lock:
            before = len(self._fragments)
            self._fragments = [f for f in self._fragments if f.tag != tag]
            return before - len(self._fragments)

    def get_immune_fragments(self, threshold: float = 2.0) -> list[AnchorFragment]:
        """获取"免疫"片段——活动度足够高、循环重置时应保留的片段。

        Args:
            threshold: 免疫阈值，默认 2.0（约 20 次 recall 可达）

        Returns:
            免疫片段列表
        """
        with self._lock:
            return [f for f in self._fragments if f.activity >= threshold]

    # ── 工具 ──

    def fragment_count(self) -> int:
        with self._lock:
            return len(self._fragments)

    def clear(self):
        with self._lock:
            self._fragments.clear()

    def _append_to_file(self, fragment: AnchorFragment):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # 确保 content 不含非法代理字符（防止 json.dumps 生成非法 escape）
            safe_content = fragment.content.encode("utf-8", errors="replace").decode("utf-8")
            d = fragment.to_dict()
            d["content"] = safe_content[:500]
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("failed to append anchor fragment to %s: %s", self._path, e)


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_anchor: Optional[AnchorProtocol] = None


def get_anchor_protocol(path: Path = ANCHOR_PATH) -> AnchorProtocol:
    global _global_anchor
    if _global_anchor is None:
        _global_anchor = AnchorProtocol(path=path)
    return _global_anchor
