"""WorldModel — AGI Core 的世界模型。

记录 Core 对世界的假设、每次预测的结果和偏差。
prediction_error 不再是自循环的 float——它来自预测与实际的差异。
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Prediction:
    """一次预测记录。"""
    tick: int = 0
    variable: str = ""
    predicted: float = 0.0
    actual: Optional[float] = None
    error: float = 0.0
    confidence_before: float = 0.0
    confidence_after: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "var": self.variable,
            "predicted": round(self.predicted, 3),
            "actual": round(self.actual, 3) if self.actual is not None else None,
            "error": round(self.error, 3),
        }


@dataclass
class Belief:
    """一条信念——Core 对某个概念的理解。"""
    concept: str = ""
    value: float = 0.5
    confidence: float = 0.3      # 0~1，越高越确信
    updated_at: int = 0

    def to_dict(self) -> dict:
        return {"concept": self.concept, "value": round(self.value, 2),
                "confidence": round(self.confidence, 2)}


class WorldModel:
    """世界模型。

    每 tick 预测下一个状态，然后将预测与实际对比，
    计算偏差并更新信念置信度。
    """

    def __init__(self, decay: float = 0.97):
        self.beliefs: dict[str, Belief] = {}
        self.predictions: deque[Prediction] = deque(maxlen=100)
        self.confidence: float = 0.5         # 全局置信度
        self._decay = decay
        self._last_state: dict[str, float] = {}
        self.learning_journal: list[dict] = []  # 认知转折点记录

    def observe(self, state: dict[str, float], tick: int) -> list[dict]:
        """接收新状态，对比上次预测，返回偏差列表。"""
        deviations: list[dict] = []

        if not self._last_state:
            self._last_state = dict(state)
            return deviations

        for var, actual_val in state.items():
            if var not in self.beliefs:
                self.beliefs[var] = Belief(concept=var, value=actual_val,
                                            confidence=0.2, updated_at=tick)
                continue

            # 用上次状态做简单预测：假设变化趋势延续
            last_val = self._last_state.get(var, actual_val)
            predicted = last_val + (last_val - self._get_prior(var, last_val)) * 0.5

            # 计算误差
            error = abs(predicted - actual_val) / (abs(actual_val) + 0.01)
            error = min(1.0, error)

            # 更新信念
            belief = self.beliefs[var]
            if error < 0.05:
                belief.confidence = min(1.0, belief.confidence + 0.02)
            else:
                belief.confidence = max(0.05, belief.confidence - 0.05 * error)
            belief.value = actual_val
            belief.updated_at = tick

            # 记录预测
            self.predictions.append(Prediction(
                tick=tick, variable=var,
                predicted=predicted, actual=actual_val,
                error=error, confidence_before=self.confidence,
                confidence_after=belief.confidence,
            ))

            if error > 0.2:
                deviations.append({
                    "variable": var, "predicted": predicted,
                    "actual": actual_val, "error": error,
                })

        # 更新全局置信度
        errors = [p.error for p in self.predictions if p.actual is not None]
        avg_error = sum(errors) / len(errors) if errors else 0.5
        old_confidence = self.confidence
        self.confidence = max(0.1, min(1.0, 1.0 - avg_error * 2))

        # 记录认知转折点
        if deviations:
            worst = max(deviations, key=lambda d: d["error"])
            self.learning_journal.append({
                "tick": tick, "type": "prediction_deviation",
                "variable": worst["variable"],
                "error": round(worst["error"], 3),
                "detail": f"预测 {worst['predicted']:.2f}，实际 {worst['actual']:.2f}",
            })
        if abs(self.confidence - old_confidence) > 0.3:
            self.learning_journal.append({
                "tick": tick, "type": "confidence_shift",
                "from": round(old_confidence, 3),
                "to": round(self.confidence, 3),
                "detail": "confidence increase" if self.confidence > old_confidence
                          else "confidence decrease",
            })

        # 限制 journal 大小
        if len(self.learning_journal) > 50:
            self.learning_journal = self.learning_journal[-50:]

        self._last_state = dict(state)
        return deviations

    def significant_deviations(self, threshold: float = 0.3) -> list[dict]:
        """返回超过阈值的最近偏差。"""
        result = []
        for p in reversed(self.predictions):
            if p.error > threshold and p.actual is not None:
                result.append(p.to_dict())
                if len(result) >= 3:
                    break
        return result

    def learning_summary(self) -> str:
        """学习日志摘要（给 prompt）。"""
        if not self.learning_journal:
            return ""
        recent = self.learning_journal[-5:]
        lines = ["学习记录："]
        for entry in recent:
            t = entry.get("type", "")
            if t == "prediction_deviation":
                lines.append(f"  · tick {entry['tick']} 预测偏差：{entry['detail']}")
            elif t == "confidence_shift":
                lines.append(f"  · tick {entry['tick']} 置信度变化：{entry['from']} → {entry['to']}")
            else:
                lines.append(f"  · tick {entry['tick']} {entry.get('detail','')}")
        return "\n".join(lines)

    def belief_summary(self) -> str:
        """信念摘要（给 prompt 用）。"""
        if not self.beliefs:
            return ""
        parts = []
        sorted_beliefs = sorted(self.beliefs.items(),
                                key=lambda x: x[1].confidence, reverse=True)[:5]
        for name, b in sorted_beliefs:
            bar = "█" * int(b.confidence * 10) + "░" * (10 - int(b.confidence * 10))
            parts.append(f"{name}: {b.value:.2f} [{bar}]")
        return " | ".join(parts)

    def trend_summary(self) -> str:
        """趋势摘要：预测准确度变化。"""
        recent = [p for p in self.predictions if p.actual is not None][-20:]
        if not recent:
            return "模型刚初始化，尚无预测记录。"
        avg_err = sum(p.error for p in recent) / len(recent)
        old = [p for p in recent[:10] if p.actual is not None]
        new = [p for p in recent[-10:] if p.actual is not None]
        if old and new:
            old_avg = sum(p.error for p in old) / len(old)
            new_avg = sum(p.error for p in new) / len(new)
            direction = "improving" if new_avg < old_avg else "degrading"
            return (f"prediction_error trend: {direction} "
                    f"({old_avg:.3f} → {new_avg:.3f}), confidence={self.confidence:.2f}")
        return f"avg prediction_error: {avg_err:.3f}"

    def _get_prior(self, var: str, default: float) -> float:
        """获取上一次预测值。"""
        for p in reversed(self.predictions):
            if p.variable == var and p.actual is not None:
                return p.actual
        return default
