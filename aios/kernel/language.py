"""LanguageAttractor — 角色语言动力学机制。

不告诉角色"怎么说"，而是提供运行时约束：
  - 日常打断（Everyday Pull）：随机用日常琐事覆盖史诗叙事
  - 发言预算（Speak Budget）：限制每次发言长度
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


# ════════════════════════════════════════════════════════════
# 语言吸引子
# ════════════════════════════════════════════════════════════


@dataclass
class LanguageAttractor:
    """角色的语言动力学参数——只存数据，不生成 prompt。"""

    # ── 发言预算 ──
    budget_tokens: int = 120

    # ── 日常引力 ──
    everyday_probability: float = 0.25
    everyday_states: list[str] = field(default_factory=lambda: [
        "肚子有点饿了",
        "鞋湿了，脚很不舒服",
        "肩膀好酸",
        "昨晚没睡好，一直在做梦",
        "想喝杯热的",
        "这个天气让人想回家",
        "衣服湿透了，好冷",
        "想抽根烟",
        "有点头疼",
        "脖子后面有点发凉",
    ])

    # ── 叙事反差系数：越高越容易无视世界事件 ──
    everyday_pull: float = 0.3


@dataclass
class EverydayState:
    """当前轮次的日常状态。"""
    state: str = ""
    active: bool = False


def roll_everyday(attractor: LanguageAttractor) -> EverydayState:
    """根据吸引子随机生成日常状态。"""
    if attractor.everyday_states and random.random() < attractor.everyday_probability:
        return EverydayState(
            state=random.choice(attractor.everyday_states),
            active=True,
        )
    return EverydayState(active=False)


def enforce_budget(text: str, max_tokens: int) -> str:
    """强制执行发言预算。"""
    if max_tokens <= 0:
        return ""
    if len(text) > max_tokens * 1.5:
        truncated = text[:int(max_tokens * 1.2)]
        last_period = max(truncated.rfind("。"), truncated.rfind("."))
        if last_period > 0:
            return truncated[:last_period + 1]
        return truncated + "……"
    return text
