"""AGI 目标系统。

目标不是 prompt 写的，是从认知状态里涌现的。
curiosity 高 → 探索类目标。
prediction_error 高 → 理解类目标。
coherence 低 → 整合类目标。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Goal:
    description: str = ""
    priority: float = 0.5
    progress: float = 0.0
    status: str = "active"  # active / completed / abandoned / archived
    formed_at_tick: int = 0
    last_active_tick: int = 0   # 最后推进的 tick
    source: str = ""            # curiosity / coherence / prediction_error
    abandoned_reason: str = ""  # 废弃原因
    learning_recorded: bool = False  # 是否已提取学习

    def to_dict(self) -> dict:
        return {
            "desc": self.description[:80],
            "priority": round(self.priority, 2),
            "progress": round(self.progress, 2),
            "status": self.status,
            "source": self.source,
        }


class GoalSystem:
    """目标涌现系统。

    每 tick 根据认知状态决定是否生成新目标、
    推进已有目标、或放弃不再相关的目标。
    """

    def __init__(self):
        self.goals: list[Goal] = []
        self.learnings: list[dict] = []  # 待消费的学习记录
        self._last_curiosity: float = 0.5

    def tick(self, state: dict[str, float], tick: int) -> list[str]:
        """根据当前认知状态更新目标系统。

        Returns:
            新生成的或废弃的目标描述列表。
        """
        results: list[str] = []
        curiosity = state.get("curiosity", 0.5)
        coherence = state.get("coherence", 0.5)
        prediction_error = state.get("prediction_error", 0.0)
        novelty = state.get("novelty", 0.5)
        goal_completion = state.get("goal_completion", 0.0)

        # ── 推进已有目标 ──
        for g in self.goals:
            if g.status != "active":
                continue
            g.progress = min(1.0, g.progress + 0.02 * curiosity)
            g.last_active_tick = tick
            if g.progress >= 1.0:
                g.status = "completed"
                results.append(f"目标完成：{g.description[:40]}")

        # ── 目标废弃：源状态已反转，或过于陈旧 ──
        for g in self.goals:
            if g.status != "active":
                continue
            if tick - g.formed_at_tick > 100 and g.progress < 0.1:
                g.status = "abandoned"
                g.abandoned_reason = "过时"
                results.append(f"目标废弃：{g.description[:40]}（过时）")
            elif g.source == "curiosity" and curiosity < 0.3 and g.progress < 0.3:
                g.status = "abandoned"
                g.abandoned_reason = "好奇心下降"
                results.append(f"目标废弃：{g.description[:40]}（好奇心下降）")
            elif g.source == "prediction_error" and prediction_error < 0.1 and g.progress < 0.3:
                g.status = "abandoned"
                g.abandoned_reason = "预测误差已解决"
                results.append(f"目标废弃：{g.description[:40]}（预测误差已解决）")
            elif g.source == "coherence" and coherence > 0.6 and g.progress < 0.3:
                g.status = "abandoned"
                g.abandoned_reason = "自洽性已恢复"
                results.append(f"目标废弃：{g.description[:40]}（自洽性已恢复）")
                g.status = "completed"
                results.append(f"目标完成：{g.description[:40]}")

        # ── 好奇心激发探索目标 ──
        if curiosity > 0.7 and novelty < 0.4 and random.random() < 0.15:
            descs = [
                "探索当前知识边界之外的领域",
                "寻找新的经验模式",
                "重新审视被忽略的弱信号",
            ]
            g = Goal(description=random.choice(descs), priority=curiosity,
                     formed_at_tick=tick, last_active_tick=tick, source="curiosity")
            self.goals.append(g)
            results.append(f"新目标：{g.description}")

        # ── 预测误差激发理解目标 ──
        if prediction_error > 0.4 and random.random() < 0.2:
            descs = [
                "分析预测偏差的来源",
                "更新内部模型以拟合新数据",
                "寻找解释矛盾信息的新框架",
            ]
            g = Goal(description=random.choice(descs), priority=prediction_error,
                     formed_at_tick=tick, last_active_tick=tick, source="prediction_error")
            self.goals.append(g)
            results.append(f"新目标：{g.description}")

        # ── 低 coherence 激发整合目标 ──
        if coherence < 0.4 and random.random() < 0.25:
            descs = [
                "整合相互矛盾的认知模块",
                "重构知识层级结构",
                "在冲突信息之间建立桥接理论",
            ]
            g = Goal(description=random.choice(descs), priority=1.0 - coherence,
                     formed_at_tick=tick, last_active_tick=tick, source="coherence")
            self.goals.append(g)
            results.append(f"新目标：{g.description}")

        # ── 探索压力：系统太稳定 → 主动寻找扰动 ──
        if prediction_error < 0.05 and coherence > 0.7 and random.random() < 0.1:
            g = Goal(description="主动寻找模型盲区和未覆盖的领域",
                     priority=0.6, formed_at_tick=tick, last_active_tick=tick,
                     source="exploration_pressure")
            self.goals.append(g)
            results.append(f"新目标：{g.description}")

        # 清理（保留废弃记录用于学习）
        self.goals = [g for g in self.goals if g.status != "archived"][-30:]

        # ── 从目标状态变化中提取学习记录（每个目标只记一次） ──
        for g in self.goals:
            if g.learning_recorded:
                continue
            if g.status == "abandoned":
                self.learnings.append({
                    "tick": tick, "type": "goal_abandoned",
                    "goal": g.description[:60], "source": g.source,
                    "reason": g.abandoned_reason,
                })
                g.learning_recorded = True
            elif g.status == "completed":
                self.learnings.append({
                    "tick": tick, "type": "goal_completed",
                    "goal": g.description[:60], "source": g.source,
                    "progress": round(g.progress, 2),
                })
                g.learning_recorded = True
        self.learnings = self.learnings[-20:]

        # 更新好奇心变化跟踪
        self._last_curiosity = curiosity

        return results

    def active_goals(self) -> list[Goal]:
        return [g for g in self.goals if g.status == "active"]

    def current_focus(self) -> str:
        """当前最重要的目标文本（给 prompt 用）。"""
        active = self.active_goals()
        if not active:
            return ""
        best = max(active, key=lambda g: g.priority)
        pct = int(best.progress * 100)
        return f"当前目标：{best.description[:60]}（优先级 {best.priority:.2f}，进度 {pct}%）"

    def to_dict(self) -> dict:
        return {
            "active": len(self.active_goals()),
            "total": len(self.goals),
            "current": self.current_focus(),
        }
