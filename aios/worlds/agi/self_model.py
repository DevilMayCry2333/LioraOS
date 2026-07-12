"""SelfModel — AGI Core 对自身状态变化的观察。

不是意识模拟。是状态趋势分析——Core 观察自己"正在变成什么"。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrendPoint:
    """一个时间点的状态快照。"""
    tick: int = 0
    values: dict[str, float] = field(default_factory=dict)


class SelfModel:
    """自身状态模型。

    记录状态变化历史，计算趋势，输出"我如何变化"的描述。
    """

    def __init__(self, window: int = 50):
        self.history: deque[TrendPoint] = deque(maxlen=window)
        self._window = window

    def record(self, state: dict[str, float], tick: int):
        """记录一个时间点的状态快照。"""
        self.history.append(TrendPoint(tick=tick, values=dict(state)))

    def trend(self, var: str, window: int = 20) -> str:
        """某个变量的变化趋势描述。"""
        pts = [p for p in self.history if var in p.values][-window:]
        if len(pts) < 3:
            return "数据不足"

        first = pts[0].values[var]
        last = pts[-1].values[var]
        delta = last - first

        # 波动率
        vals = [p.values[var] for p in pts]
        volatility = max(vals) - min(vals)

        direction = "上升" if delta > 0.05 else ("下降" if delta < -0.05 else "稳定")
        return (f"{var}: {first:.2f} → {last:.2f} "
                f"({direction}, Δ={delta:+.3f}, 波动={volatility:.2f})")

    def all_trends(self) -> list[str]:
        """所有变量的趋势。"""
        if not self.history:
            return ["系统刚启动，尚无状态历史。"]
        latest = self.history[-1].values
        return [self.trend(var) for var in sorted(latest.keys())]

    def summary(self) -> str:
        """整体状态变化摘要（给 prompt 用）。"""
        if len(self.history) < 3:
            return ""

        trends = self.all_trends()
        significant = [t for t in trends if "上升" in t or "下降" in t]

        if not significant:
            return "所有状态变量基本稳定。"

        lines = ["自身状态趋势："]
        for t in significant[:5]:
            lines.append(f"  · {t}")

        # 变量间相关性
        latest = self.history[-1].values
        pairs = [("curiosity", "novelty"), ("coherence", "prediction_error"),
                 ("cognitive_load", "uncertainty")]
        for v1, v2 in pairs:
            if v1 in latest and v2 in latest:
                lines.append(f"  · {v1}={latest[v1]:.2f}, {v2}={latest[v2]:.2f}")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "records": len(self.history),
            "ticks": f"{self.history[0].tick}-{self.history[-1].tick}" if self.history else "none",
            "latest": dict(self.history[-1].values) if self.history else {},
        }
