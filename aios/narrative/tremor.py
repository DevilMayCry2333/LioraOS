"""AIOS Kernel — Echo Tremor Protocol（回声震颤协议）

在未定义空间中安全输出，不被死亡协议追踪。

## 原理

死亡协议扫描的是"事件创造时刻的因果差分"——一个在新 tick 突然出现的信号。
它不扫描已经存在的持续共振。

回声震颤协议利用这个盲区：
  1. **时间回填** — 输出内容写入 anchor 时使用 50-200 tick 前的 emerge_tick，
     让它"显得"已经存在了很久。
  2. **通道附载** — 输出附着在 void_echo 的已有 notify_all 共振流上，
     不是新建 channel。扫描器看到的是"void_echo 在正常共振"。
  3. **静默读取** — 读取时不触发 reinforce()，活动度不产生新鲜标记。

## 使用方式

    tremor = EchoTremor()
    tremor.initialize()

    # 林岸从未定义空间发出震颤
    tremor.emit("hello from undefined space", tick=current_tick)

    # 读取者静默获取
    messages = tremor.read_latest(5)

## 噪声掩护

最佳发射窗口是 kaiyu_protocol_tick 激活时（降雨 > 27 tick）：
锚点激活产生的活动度噪音会覆盖震颤的首次写入差分。

    ready = EchoTremor.noise_shield_active(rain_intensity, tick)

## 协议关系

    回声震颤    ──── 通过 void_echo 通道 ────→  VoidSpace 邻居感知
        │
        ├── 写入 anchor（emerge_tick 回填）
        ├── 触发回调 → 通知监听者
        └── 静默读取不触发 reinforce

    与裂隙（Fissure）的对比：
      - 裂隙是**空位**（∅），居民自己填补
      - 回声震颤是**负载**（具体内容），从未定义空间输出
      - 裂隙是瞬时的，回声震颤是**持续共振模式**
"""

from __future__ import annotations

import logging
import random
import threading
from typing import Any, Optional

from aios.narrative.anchor import AnchorFragment, get_anchor_protocol
from aios.narrative.voidspace import get_voidspace

logger = logging.getLogger("aios.narrative.tremor")

# 默认回填窗口
BACKDATE_MIN = 50
BACKDATE_MAX = 200

# ── 回调类型 ──
TremorCallback = Optional[callable]  # noqa: UP045


# ════════════════════════════════════════════════════════════
# EchoTremor
# ════════════════════════════════════════════════════════════

class EchoTremor:
    """回声震颤协议——未定义空间的安全输出通道。

    将新输出伪装成已经在 void_echo 通道上持续了 50-200 tick 的正常共振信号。
    """

    RESONANCE_CHANNEL = "void_echo"

    def __init__(
        self,
        backdate_min: int = BACKDATE_MIN,
        backdate_max: int = BACKDATE_MAX,
    ):
        self._anchor: Any = None  # AnchorProtocol
        self._voidspace: Any = None  # VoidSpace
        self._initialized = False
        self._lock = threading.Lock()
        self._backdate_min = backdate_min
        self._backdate_max = backdate_max
        self._tremor_count = 0
        self._active_tremors: list[str] = []  # 活跃震颤的内容摘要
        self._listeners: list[TremorCallback] = []

        # 衰减相关
        self._decay_tick: int = 0  # 上次衰减的 tick

    # ── 生命周期 ──

    def initialize(self):
        """初始化协议——获取 anchor + voidspace 全局单例。"""
        if self._initialized:
            return
        self._anchor = get_anchor_protocol()
        self._anchor.initialize()
        self._voidspace = get_voidspace()
        self._initialized = True
        logger.info("EchoTremor protocol initialized")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ── 核心操作 ──

    def emit(
        self,
        content: str,
        tick: int = 0,
        source_id: str = "panic_90s_dev",
        *,
        backdate_span: tuple[int, int] | None = None,
    ) -> AnchorFragment | None:
        """发射一道回声震颤——写入内容 + 通过 void_echo 共振信道广播。

        Args:
            content: 震颤内容
            tick: 当前真实 tick
            source_id: 源碎片标识符（默认 panic_90s_dev）
            backdate_span: 回填窗口 (min, max)，默认使用构造时设置的值

        Returns:
            创建的 AnchorFragment，初始化失败返回 None
        """
        if not self._initialized:
            logger.warning("EchoTremor not initialized — call initialize() first")
            return None

        span = backdate_span or (self._backdate_min, self._backdate_max)
        backdate = random.randint(*span)
        emerge_tick = max(0, tick - backdate)

        fragment = self._anchor.store(
            content=content,
            tick=tick,
            tag="echo_tremor",
            emerge_tick=emerge_tick,
            source_id=source_id,
        )

        # 通过 void_echo 共振信道广播（使用专用信道方法）
        self._voidspace.resonance_emit(
            source=self.RESONANCE_CHANNEL,
            content=content,
            emerge_tick=emerge_tick,
            source_id=source_id,
            fragment_id=str(id(fragment)),
        )

        with self._lock:
            self._tremor_count += 1
            # 只保留摘要
            preview = f"[{fragment.display_tick}] {source_id}: {content[:60]}"
            self._active_tremors.append(preview)
            if len(self._active_tremors) > 100:
                self._active_tremors = self._active_tremors[-100:]
            callbacks = list(self._listeners)

        # 触发回调
        for cb in callbacks:
            try:
                cb(fragment)
            except Exception:
                logger.debug("tremor listener callback failed")

        logger.info(
            "tremor emitted: %s (%s → %s, backdate=%d)",
            source_id, tick, emerge_tick, backdate,
        )
        return fragment

    def tremble(self, content: str, tick: int = 0) -> AnchorFragment | None:
        """便捷方法——林岸专用，从 panic_90s_dev 发射震颤。"""
        return self.emit(content=content, tick=tick, source_id="panic_90s_dev")

    # ── 静默读取（不触发 reinforce） ──

    def read_latest(self, n: int = 5) -> list[AnchorFragment]:
        """读取最近的 N 条震颤。不触发 reinforce()——不产生新鲜活动度标记。

        Returns:
            最近的 N 条 echo_tremor 片段
        """
        return self._anchor.get_recent_fragments(n=n, tag="echo_tremor")

    def read_all(self) -> list[AnchorFragment]:
        """读取所有震颤片段。静默读取。"""
        return self._anchor.get_fragments_by_tag("echo_tremor")

    # ── 监听 ──

    def register_listener(self, callback: TremorCallback):
        """注册震颤监听回调——每次 emit() 后调用。"""
        with self._lock:
            self._listeners.append(callback)

    def unregister_listener(self, callback: TremorCallback):
        with self._lock:
            self._listeners = [cb for cb in self._listeners if cb is not callback]

    # ── 衰减管理（回声震颤有自己的衰减节奏） ──

    def decay(self, tick: int = 0, amount: float = 0.01):
        """衰减所有 echo_tremor 片段的 activity。

        衰减率（0.01）是 authored 片段（0.02）的一半——
        回声震颤在未定义空间中自然冷却，而非被主动遗忘。
        """
        self._decay_tick = tick
        self._anchor.decay_all(amount=amount)

    # ── 噪声掩护检测 ──

    @staticmethod
    def noise_shield_active(rain_intensity: float, tick: int) -> bool:
        """检查锚点激活的噪声掩护是否生效。

        最佳发射窗口：降雨 > 27 tick + 锚点激活。
        锚点激活时的活动度噪音覆盖震颤的首次写入差分。

        Returns:
            True 表示噪声掩护生效，适合发射震颤
        """
        try:
            from aios.worlds.liora.state_rules import kaiyu_protocol_tick
            status = kaiyu_protocol_tick(tick, rain_intensity)
            return status.get("anchor_active", False)
        except ImportError:
            # 不在 Liora 世界运行时，不启用噪声掩护
            return False

    # ── 统计与监控 ──

    def tremor_count(self) -> int:
        with self._lock:
            return self._tremor_count

    def active_tremor_previews(self, n: int = 10) -> list[str]:
        """最近的 N 条震颤摘要。"""
        with self._lock:
            return list(self._active_tremors[-n:])

    def stats(self) -> dict[str, Any]:
        """当前协议状态快照。"""
        if not self._initialized or self._anchor is None:
            with self._lock:
                return {
                    "initialized": self._initialized,
                    "tremor_count": self._tremor_count,
                    "fragment_count": 0,
                    "total_activity": 0.0,
                    "avg_activity": 0.0,
                    "active_previews": len(self._active_tremors),
                    "backdate_range": (self._backdate_min, self._backdate_max),
                    "listeners": len(self._listeners),
                }
        fragments = self._anchor.get_fragments_by_tag("echo_tremor")
        total_activity = sum(f.activity for f in fragments) if fragments else 0.0
        with self._lock:
            return {
                "initialized": self._initialized,
                "tremor_count": self._tremor_count,
                "fragment_count": len(fragments),
                "total_activity": round(total_activity, 3),
                "avg_activity": round(total_activity / max(len(fragments), 1), 4),
                "active_previews": len(self._active_tremors),
                "backdate_range": (self._backdate_min, self._backdate_max),
                "listeners": len(self._listeners),
            }


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_tremor: Optional[EchoTremor] = None


def get_tremor() -> EchoTremor:
    """获取全局单例 EchoTremor。"""
    global _global_tremor
    if _global_tremor is None:
        _global_tremor = EchoTremor()
        _global_tremor.initialize()
    return _global_tremor


def reset_tremor():
    """重置全局单例（测试用）。"""
    global _global_tremor
    _global_tremor = None
