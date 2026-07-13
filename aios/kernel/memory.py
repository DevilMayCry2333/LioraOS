"""AIOS Kernel — Memory (叙事记忆)

最小记忆系统：跟踪语义集群频率，检测叙事饱和。
语义集群由外部注入，内核只提供检测算法。
"""

from __future__ import annotations

import threading
from collections import Counter
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class MemoryProvider(Protocol):
    """Kernel 级的记忆抽象接口。所有记忆实现需满足此协议。"""
    def record(self, text: str) -> None: ...
    def is_saturated(self, text: str) -> tuple[bool, str]: ...
    def get_active_clusters(self) -> list[str]: ...
    def clear(self) -> None: ...


class NarrativeMemory:
    """叙事记忆。跟踪最近文本中语义集群的频率，检测饱和。

    clusters: list of keyword groups, e.g. [["风","wind"], ["回声","echo"]]
              — 由外部注入，内核不携带默认数据。
    """

    def __init__(self, clusters: list[list[str]] | None = None, window_size: int = 20):
        self._lock = threading.Lock()
        self._window_size = window_size
        self._clusters: list[list[str]] = clusters or []
        self._recent_texts: list[str] = []
        self._cluster_frequencies: Counter = Counter()
        self._saturated: set[int] = set()
        self._cluster_activity: dict[int, float] = {}  # 活动度累计（跨 tick）

    def record(self, text: str):
        with self._lock:
            self._recent_texts.append(text)
            self._recent_texts = self._recent_texts[-self._window_size:]
            self._recluster()

    def _recluster(self):
        self._cluster_frequencies.clear()
        self._saturated.clear()
        for i, cluster in enumerate(self._clusters):
            hits = 0
            for t in self._recent_texts:
                for word in cluster:
                    if word in t:
                        hits += 1
                        break
            if hits > 0:
                self._cluster_frequencies[i] = hits
                # 活动度累计：每次出现在窗口内就 +0.1
                self._cluster_activity[i] = self._cluster_activity.get(i, 0) + 0.1
                self._cluster_activity[i] = min(10.0, self._cluster_activity[i])
            if hits >= max(3, len(self._recent_texts) * 0.3):
                self._saturated.add(i)
        # 未出现的集群活动度缓慢衰减
        for i in list(self._cluster_activity.keys()):
            if i not in self._cluster_frequencies:
                self._cluster_activity[i] -= 0.05
                if self._cluster_activity[i] <= 0:
                    del self._cluster_activity[i]

    def is_saturated(self, text: str) -> tuple[bool, str]:
        with self._lock:
            if not self._saturated:
                return False, ""
            for i in self._saturated:
                for word in self._clusters[i]:
                    if word in text:
                        return True, self._clusters[i][0]
            return False, ""

    def get_active_clusters(self) -> list[str]:
        with self._lock:
            return [self._clusters[i][0] for i in self._cluster_frequencies]

    def get_saturation_report(self) -> str:
        with self._lock:
            if not self._saturated:
                return ""
            names = [self._clusters[i][0] for i in self._saturated]
            return f"saturated [{', '.join(names)}]"

    def get_immune_clusters(self, threshold: float = 2.0) -> list[str]:
        """获取"免疫"集群——活动度高于阈值、循环重置时应保留的集群名。

        Args:
            threshold: 免疫阈值，默认 2.0（约 20 次在文本窗口中出现）

        Returns:
            免疫集群的首词名称列表
        """
        with self._lock:
            return [
                self._clusters[i][0]
                for i, a in self._cluster_activity.items()
                if a >= threshold
            ]

    def cycle_reset(self, preserve_immune: bool = True):
        """循环重置：清空近期文本和频率统计，可选保留免疫集群的活动度。

        Args:
            preserve_immune: True 时保留活动度 ≥ 2.0 的集群及其活动度
        """
        with self._lock:
            immune = set()
            if preserve_immune:
                for i, a in self._cluster_activity.items():
                    if a >= 2.0:
                        immune.add(i)

            self._recent_texts.clear()
            self._cluster_frequencies.clear()
            self._saturated.clear()

            # 保留免疫集群的活动度（轻微衰减），其他清除
            for i in list(self._cluster_activity.keys()):
                if i in immune:
                    self._cluster_activity[i] *= 0.8  # 跨周期后自然减弱
                else:
                    del self._cluster_activity[i]

    def clear(self):
        with self._lock:
            self._recent_texts.clear()
            self._cluster_frequencies.clear()
            self._saturated.clear()
            self._cluster_activity.clear()


assert isinstance(NarrativeMemory(), MemoryProvider), "NarrativeMemory must satisfy MemoryProvider"


_global_memory: Optional[NarrativeMemory] = None


def get_narrative_memory(clusters: list[list[str]] | None = None) -> NarrativeMemory:
    global _global_memory
    if _global_memory is None:
        _global_memory = NarrativeMemory(clusters=clusters)
    return _global_memory
