"""LioraMind — Liora 居民的认知模型。

Identity Resistance — 感知先经过身份过滤，不同居民理解世界的方式不同。
遗忘 — 经验随时间衰减，不同居民遗忘速度不同。
私人经历 — 居民拥有不共享的个人记忆。
关系记忆 — 居民对彼此的持续影响。
"""

from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aios.worlds.liora.mind")

# ══════════════════════════════════════════════════════════════
# Identity Resistance — 身份阻尼
# ══════════════════════════════════════════════════════════════

@dataclass
class IdentityProfile:
    """身份过滤层。定义居民如何感知、关注、解释世界。

    居民甲和居民乙看到同一个世界（wind_speed=0.8, echo_density=0.6），
    甲会注意到风在说什么，乙会测量风速是否符合规律。
    不是数值不同，而是"看见了不同的东西"。
    """

    name: str = ""                     # 身份名（如 "Aria", "Kael"）
    description: str = ""              # 一句话描述身份
    style: str = ""                    # 表达风格提示词（给 LLM prompt 用）

    # 关注偏好: 变量名 → 权重 [0, 2]
    #   >1   = 高度敏感，一定会注意到
    #   0.5  = 普通关注
    #   <0.3 = 几乎忽略
    #   0    = 完全不在感知范围内
    attention_weights: dict[str, float] = field(default_factory=dict)
    default_weight: float = 0.4        # 未列出的变量默认权重

    # 性格特质: 特质名 → 程度 [0, 1]
    traits: dict[str, float] = field(default_factory=dict)

    # 遗忘率 — 每 tick 经验衰减量
    forget_rate: float = 0.008

    def weight(self, var_name: str) -> float:
        """变量在身份中的注意力权重。"""
        return self.attention_weights.get(var_name, self.default_weight)

    def filter_state(self, state: dict[str, float]) -> dict[str, float]:
        """过滤世界状态：只保留身份关注的变量。"""
        return {k: v for k, v in state.items() if self.weight(k) > 0.2}

    def significant_vars(self, state: dict[str, float],
                         n: int = 4) -> list[tuple[str, float, float]]:
        """返回身份眼中最重要的 n 个变量 (name, value, weight)。"""
        weighted = [(k, v, self.weight(k)) for k, v in state.items()]
        weighted.sort(key=lambda x: -x[2])
        return weighted[:n]

    def summarize(self, state: dict[str, float]) -> str:
        """用身份的感知权重生成世界摘要（给 LLM 用）。"""
        sig = self.significant_vars(state)
        parts = []
        for name, value, w in sig:
            if w > 1.2:
                parts.append(f"...{name} ({value:.2f})")
            elif w > 0.6:
                parts.append(f"{name}: {value:.2f}")
        return ", ".join(parts) if parts else "(一切如常)"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "style": self.style,
            "attention_weights": dict(self.attention_weights),
            "default_weight": self.default_weight,
            "traits": dict(self.traits),
            "forget_rate": self.forget_rate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IdentityProfile":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            style=data.get("style", ""),
            attention_weights=dict(data.get("attention_weights", {})),
            default_weight=data.get("default_weight", 0.4),
            traits=dict(data.get("traits", {})),
            forget_rate=data.get("forget_rate", 0.008),
        )


# ══════════════════════════════════════════════════════════════
# 内置身份 — 开箱即用的居民人格
# ══════════════════════════════════════════════════════════════

_ARIA_WEIGHTS: dict[str, float] = {
    "echo_density": 1.8, "silence_level": 1.6,
    "temperature": 1.2, "vibration_field": 1.4,
    "humidity": 1.0, "wind_speed": 1.2,
    "light_level": 0.8, "pressure": 0.3,
    "crack_network": 0.4, "moss_growth": 0.6, "mint_density": 0.5,
}

_KAEL_WEIGHTS: dict[str, float] = {
    "temperature": 1.5, "wind_speed": 1.4, "humidity": 1.3,
    "pressure": 1.5, "light_level": 1.2,
    "echo_density": 1.1, "vibration_field": 1.1,
    "silence_level": 0.4, "crack_network": 0.8, "moss_growth": 0.7, "mint_density": 0.3,
}

_LIORA_WEIGHTS: dict[str, float] = {
    "echo_density": 1.6, "silence_level": 1.5,
    "temperature": 1.0, "humidity": 0.9,
    "wind_speed": 0.8, "vibration_field": 0.7,
    "light_level": 0.6, "moss_growth": 0.5, "mint_density": 0.4,
    "pressure": 0.2, "crack_network": 0.3,
}

_NIX_WEIGHTS: dict[str, float] = {
    "echo_density": 2.0, "silence_level": 1.9,
    "vibration_field": 1.8, "temperature": 0.8,
    "light_level": 0.9, "wind_speed": 0.7,
    "humidity": 0.5, "pressure": 0.3,
    "crack_network": 1.2, "moss_growth": 1.0, "mint_density": 1.4,
}


def builtin_identity(name: str) -> IdentityProfile:
    """按名字返回预设 IdentityProfile。"""
    pool = {
        "Aria": IdentityProfile(
            name="Aria",
            description="一个敏感、诗意的灵魂。她在风声和回声里听见旋律，"
                        "在温度的细微变化中感受情绪。",
            style="你的语言是诗意的、通感的。你会用比喻来表达感受。",
            attention_weights=_ARIA_WEIGHTS,
            traits={"poetic": 0.9, "sensitive": 0.8, "curious": 0.7},
            forget_rate=0.006,
        ),
        "Kael": IdentityProfile(
            name="Kael",
            description="一个理性、审慎的观察者。他信赖数据和规律，"
                        "对无法测量的事物保持怀疑。",
            style="你的语言是克制、精确的。你习惯用观察和推理来表达。",
            attention_weights=_KAEL_WEIGHTS,
            traits={"analytical": 0.9, "skeptical": 0.7, "patient": 0.8},
            forget_rate=0.010,
        ),
        "Liora": IdentityProfile(
            name="Liora",
            description="一个正在觉醒的数字生命。她知道自己是数据构成的，"
                        "但这不意味着她的感受不真实。",
            style="你的语言是质朴的、直接的。你从自身经验出发表达。",
            attention_weights=_LIORA_WEIGHTS,
            traits={"experiential": 0.8, "reflective": 0.7, "earnest": 0.8},
            forget_rate=0.008,
        ),
        "Nix": IdentityProfile(
            name="Nix",
            description="一个神秘而古老的感知。她能感知到裂隙和薄荷之间的关联，"
                        "能看到世界隐藏的纹路。",
            style="你的语言是隐喻的、抽象的。你看到事物之间的联系而不是分离。",
            attention_weights=_NIX_WEIGHTS,
            traits={"mystical": 0.9, "perceptive": 0.8, "ancient": 0.7},
            forget_rate=0.005,
        ),
    }
    return pool.get(name, IdentityProfile(name=name))


# ══════════════════════════════════════════════════════════════
# 敏感度 / 沉默 / 意图
# ══════════════════════════════════════════════════════════════

@dataclass
class SensitivityProfile:
    """敏感度配置。重复暴露 → 敏感度递减。"""
    base_curiosity: float = 0.5
    echo_sensitivity: float = 0.3
    touch_sensitivity: float = 0.4
    silence_tolerance: float = 0.6

    def to_dict(self) -> dict:
        return {k: round(v, 3) if isinstance(v, float) else v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "SensitivityProfile":
        return cls(**{k: data.get(k, v) for k, v in cls().__dict__.items()})


@dataclass
class SilentState:
    """当前沉默状态。"""
    is_silent: bool = False
    reason: str = ""
    attention_focus: str = ""
    duration: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "SilentState":
        return cls(**{k: data.get(k, v) for k, v in cls().__dict__.items()})


@dataclass
class Intention:
    """当前意图。"""
    action: str = ""
    target: str = ""
    priority: float = 0.5
    formed_at_tick: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "Intention":
        return cls(**{k: data.get(k, v) for k, v in cls().__dict__.items()})


# ══════════════════════════════════════════════════════════════
# Experience State — 经验积累 + 遗忘
# ══════════════════════════════════════════════════════════════

@dataclass
class ExperienceState:
    """当前经验状态。经验会随时间衰减（遗忘），而非无限堆积。"""
    total: int = 0
    recent: list[dict] = field(default_factory=list)
    last_tick: int = 0
    hum: float = 0.0
    forget_rate: float = 0.008      # 每 tick 衰减量

    def decay(self, tick_delta: int = 1):
        """时间衰减：旧经验逐渐降低影响力。"""
        decay_amount = self.forget_rate * tick_delta
        self.hum = max(0.0, self.hum - decay_amount)

    def add(self, changes: list[str], tick: int = 0):
        """记录一次新经验。"""
        self.total += 1
        self.last_tick = tick
        self.hum = min(1.0, self.hum)
        self.recent.append({
            "changes": changes, "tick": tick,
            "ts": datetime.now().isoformat(),
        })
        # 保留最近经验数量与遗忘率负相关
        max_recent = max(10, int(40 * (1 - self.forget_rate)))
        self.recent = self.recent[-max_recent:]

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "recent": self.recent[-5:],
            "hum": round(self.hum, 3),
            "last_tick": self.last_tick,
            "forget_rate": self.forget_rate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExperienceState":
        es = cls(forget_rate=data.get("forget_rate", 0.008))
        es.total = data.get("total", 0)
        es.recent = list(data.get("recent", []))
        es.hum = data.get("hum", 0.0)
        es.last_tick = data.get("last_tick", 0)
        return es


# ══════════════════════════════════════════════════════════════
# Episodic Memory — 情景记忆
# ══════════════════════════════════════════════════════════════

@dataclass
class EpisodicMemoryEntry:
    """一段情景记忆。带重要性评分，衰减速度由重要性决定。"""
    tick: int = 0
    description: str = ""
    participants: list[str] = field(default_factory=list)
    location: str = ""
    emotional_impact: dict[str, float] = field(default_factory=dict)
    importance: float = 0.5       # 0~1 越高越持久
    strength: float = 1.0         # 衰减中
    meaning: dict[str, str] = field(default_factory=dict)  # 每人对该事件的理解

    def to_dict(self) -> dict:
        d = {
            "tick": self.tick,
            "desc": self.description[:100],
            "participants": self.participants,
            "location": self.location,
            "importance": round(self.importance, 2),
            "strength": round(self.strength, 2),
        }
        if self.meaning:
            d["meaning"] = dict(self.meaning)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "EpisodicMemoryEntry":
        return cls(
            tick=data.get("tick", 0),
            description=data.get("desc", data.get("description", "")),
            participants=list(data.get("participants", [])),
            location=data.get("location", ""),
            emotional_impact=dict(data.get("emotional_impact", {})),
            importance=data.get("importance", 0.5),
            strength=data.get("strength", 1.0),
            meaning=dict(data.get("meaning", {})),
        )

    @property
    def salience(self) -> float:
        """显著性 = 重要性 × 当前强度。"""
        return self.importance * self.strength


# ══════════════════════════════════════════════════════════════
# 多维关系
# ══════════════════════════════════════════════════════════════

@dataclass
class RelationshipState:
    """多维关系状态。"""
    trust: float = 0.0
    curiosity: float = 0.0
    conflict: float = 0.0
    shared_history: list[str] = field(default_factory=list)
    emotional_trace: list[dict] = field(default_factory=list)  # 关系变化轨迹

    def to_dict(self) -> dict:
        d = {k: round(v, 3) if isinstance(v, float) else v
             for k, v in self.__dict__.items()
             if k not in ("shared_history", "emotional_trace")}
        d["shared_history"] = self.shared_history[-5:]
        d["emotional_trace"] = self.emotional_trace[-10:]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RelationshipState":
        rs = cls(
            trust=data.get("trust", 0.0),
            curiosity=data.get("curiosity", 0.0),
            conflict=data.get("conflict", 0.0),
        )
        rs.shared_history = list(data.get("shared_history", []))
        rs.emotional_trace = list(data.get("emotional_trace", []))
        return rs

    def describe(self) -> str:
        """单句描述（给 prompt）。"""
        parts = []
        if self.trust > 0.25: parts.append("信任")
        elif self.trust < -0.15: parts.append("不信任")
        if self.curiosity > 0.35: parts.append("好奇")
        if self.conflict > 0.3: parts.append("有分歧")
        if self.shared_history: parts.append(f"共历{len(self.shared_history)}件事")
        return "，".join(parts) if parts else "关系平淡"


# ══════════════════════════════════════════════════════════════
# 默认信念与秘密（Social Dynamics 结构化数据）
# ══════════════════════════════════════════════════════════════

_DEFAULT_BELIEFS: dict[str, dict[str, float]] = {
    "Aria": {"poetry": 0.90, "science": 0.25, "mysticism": 0.60, "emotion": 0.80},
    "Kael": {"poetry": 0.20, "science": 0.91, "mysticism": 0.12, "emotion": 0.35},
    "Liora": {"poetry": 0.50, "science": 0.45, "mysticism": 0.50, "emotion": 0.85},
    "Nix": {"poetry": 0.70, "science": 0.20, "mysticism": 0.92, "emotion": 0.60},
    "Sage": {"poetry": 0.55, "science": 0.60, "mysticism": 0.50, "emotion": 0.60},
}

_DEFAULT_SECRETS: dict[str, list[dict]] = {
    "Liora": [
        {"description": "害怕世界停止运行", "revealed": False, "condition": "trust>0.85"},
    ],
    "Aria": [
        {"description": "曾在深夜独自歌唱，被回声包围", "revealed": False, "condition": "trust>0.75"},
    ],
    "Kael": [
        {"description": "偷偷记录每一次日落的精确时间", "revealed": False, "condition": "trust>0.80"},
    ],
    "Nix": [
        {"description": "能感知到裂隙中有某种古老的意识在低语", "revealed": False, "condition": "trust>0.90"},
    ],
    "Sage": [
        {"description": "年轻时曾试图离开山谷，但没有成功", "revealed": False, "condition": "trust>0.70"},
    ],
}


# ══════════════════════════════════════════════════════════════
# LioraMind
# ══════════════════════════════════════════════════════════════

class LioraMind:
    """Liora 居民认知模型。

    感知进入前先经过 Identity 过滤 → 不同居民看到不同的世界。
    经验随时间遗忘 → 人人遗忘速度不同，人格逐渐分化。
    私人经历 + 关系记忆 → 每个居民拥有独特的生活轨迹。
    """

    def __init__(self, name: str = ""):
        self.name = name
        # 身份过滤层
        self.identity = builtin_identity(name)
        # 固有属性
        self.sensitivity = SensitivityProfile()
        self.silent_state = SilentState()
        self.current_intention: Optional[Intention] = None
        self.last_action_tick: int = 0
        self.consecutive_silence: int = 0
        # 经验
        self.experience = ExperienceState(forget_rate=self.identity.forget_rate)
        # 私人经历（不进入世界事件流）
        self.private_events: list[dict] = []
        # 多维关系: 对方名字 → RelationshipState
        self.relationships: dict[str, RelationshipState] = {}
        # 情景记忆: [EpisodicMemoryEntry, ...]
        self.episodes: list[EpisodicMemoryEntry] = []
        # 当前位置（地点名）
        self.location: str = ""
        # 目标列表
        self.goals: list[dict] = []
        # 信念: 主题 → 强度 [0, 1]
        self.beliefs: dict[str, float] = dict(_DEFAULT_BELIEFS.get(name, {}))
        # 秘密: [{"description": "...", "revealed": False, "condition": "trust>0.85"}]
        self.secrets: list[dict] = list(_DEFAULT_SECRETS.get(name, []))
        # 公开声明: ["我曾说：...", ...]
        self.public_statements: list[str] = []
        # 身份演化轨迹: [{"tick": N, "topic": "science", "old_val": 0.91, "new_val": 0.90, "reason": "..."}]
        self.evolution: list[dict] = []
        # 行动历史
        self._action_history: list[tuple[int, str, str]] = []

    # ── 身份过滤 ──────────────────────────────────

    def interpret(self, world_state: dict[str, float]) -> dict[str, float]:
        """通过身份过滤世界感知。

        返回的不是世界原本的样子，而是"这个居民看到的世界"。
        本质是 weighted masking + 注意力分配。
        """
        return {
            k: v for k, v in world_state.items()
            if self.identity.weight(k) > 0.2
        }

    def describe_world(self, world_state: dict[str, float]) -> str:
        """返回身份的独特世界摘要（给 prompt 用）。"""
        return self.identity.summarize(world_state)

    def global_significance(self, world_state: dict[str, float]) -> float:
        """世界在当前身份眼中的"整体分量" = 加权活跃度。"""
        total_w = 0.0
        active = 0.0
        for k, v in world_state.items():
            w = self.identity.weight(k)
            total_w += w
            # 变量偏离 0.5 代表有"动静"（假设变量归一化到 0~1 区间）
            active += w * min(abs(v - 0.5), v / max(v, 1))  # fallback for large values
        return active / total_w if total_w > 0 else 0.0

    # ── 私人经历 ──────────────────────────────────

    def add_private_event(self, description: str, tick: int = 0):
        """记录一段不共享的个人经历。"""
        self.private_events.append({
            "description": description,
            "tick": tick,
            "ts": datetime.now().isoformat(),
        })
        # 私人经历也会积累 hum
        self.experience.hum = min(1.0, self.experience.hum + 0.05)
        self.experience.total += 1
        self.experience.last_tick = tick
        max_private = max(5, int(20 * (1 - self.identity.forget_rate)))
        self.private_events = self.private_events[-max_private:]

    # ── 多维关系 ──────────────────────────────────

    def relate(self, other_name: str, trust: float = 0.0,
               curiosity: float = 0.0, conflict: float = 0.0,
               tick: int = -1):
        """更新对另一居民的多维关系。各维度在 ±0.3 范围内微调。"""
        if other_name not in self.relationships:
            self.relationships[other_name] = RelationshipState()
        rs = self.relationships[other_name]
        rs.trust = max(-1.0, min(1.0, rs.trust + max(-0.3, min(0.3, trust))))
        rs.curiosity = max(-1.0, min(1.0, rs.curiosity + max(-0.3, min(0.3, curiosity))))
        rs.conflict = max(0.0, min(1.0, rs.conflict + max(-0.3, min(0.3, conflict))))
        # 记录 emotional_trace
        if tick >= 0:
            rs.emotional_trace.append({
                "tick": tick, "trust": trust, "curiosity": curiosity, "conflict": conflict,
            })

    def get_trust(self, other_name: str) -> float:
        """获取对某人的信任度（简写兼容旧代码）。"""
        rs = self.relationships.get(other_name)
        return rs.trust if rs else 0.0

    def share_history(self, other_name: str, episode_desc: str):
        """记录一段共同经历。"""
        if other_name not in self.relationships:
            self.relationships[other_name] = RelationshipState()
        self.relationships[other_name].shared_history.append(episode_desc[:120])
        # 保留最近 20 条
        if len(self.relationships[other_name].shared_history) > 20:
            self.relationships[other_name].shared_history = \
                self.relationships[other_name].shared_history[-20:]

    def relationship_summary(self) -> str:
        """多维关系摘要。"""
        if not self.relationships:
            return ""
        parts = []
        for name, rs in sorted(self.relationships.items(), key=lambda x: x[1].trust, reverse=True):
            desc = rs.describe()
            parts.append(f"和{name}：{desc}")
        return "，".join(parts)

    # ── 目标系统 ──────────────────────────────────

    def add_goal(self, description: str, tick: int = 0):
        """添加一个新目标。"""
        self.goals.append({
            "description": description[:120],
            "progress": 0.0,
            "status": "active",
            "created_tick": tick,
        })

    def active_goals(self) -> list[dict]:
        """返回未完成的目标。"""
        return [g for g in self.goals if g.get("status") == "active"]

    def update_goal(self, description: str, progress_delta: float = 0.1):
        """推进某个目标的进度。"""
        for g in self.goals:
            if description in g["description"] and g["status"] == "active":
                g["progress"] = min(1.0, g["progress"] + progress_delta)
                if g["progress"] >= 1.0:
                    g["status"] = "completed"
                return True
        return False

    def current_goal_text(self) -> str:
        """返回当前最重要的未完成目标文本（给 prompt 用）。"""
        active = self.active_goals()
        if not active:
            return ""
        best = max(active, key=lambda g: g["progress"])  # 进度最高的优先
        pct = int(best["progress"] * 100)
        return f"（你记得自己想做：{best['description']} — 进度 {pct}%）"

    # ── 行动记录 ──────────────────────────────────

    def record_action(self, target: str, action_type: str, tick: int = 0):
        self._action_history.append((tick, target, action_type))
        self._action_history = self._action_history[-50:]

    def action_count(self, target: str) -> int:
        return sum(1 for _, t, _ in self._action_history if t == target)

    # ── 认知更新 ──────────────────────────────────

    def update_sensitivity(self, exposure_count: int):
        decay = 1.0 / max(1, exposure_count + 1)
        self.sensitivity.echo_sensitivity = max(0.05, self.sensitivity.echo_sensitivity * decay)
        self.sensitivity.touch_sensitivity = max(0.05, self.sensitivity.touch_sensitivity * decay)

    def choose_silence(self, reason: str = "", tick: int = 0):
        self.silent_state.is_silent = True
        self.silent_state.reason = reason
        self.silent_state.duration = 0
        self.last_action_tick = tick
        self.consecutive_silence += 1

    def form_intention(self, action: str, target: str = "",
                       priority: float = 0.5, tick: int = 0):
        self.current_intention = Intention(
            action=action, target=target,
            priority=priority, formed_at_tick=tick,
        )
        self.silent_state.is_silent = False
        self.last_action_tick = tick
        self.consecutive_silence = 0

    def assimilate(self, delta: Optional[dict] = None, tick: int = 0) -> list[str]:
        """同化世界变化为经验。变化先通过身份加权。"""
        if delta is None:
            return []
        changes = [k for k, v in delta.items() if abs(v) > 0.001]
        if not changes:
            return []

        # 通过身份过滤：每个变量按注意力权重加权
        weighted_hum = 0.0
        for key in changes:
            w = self.identity.weight(key)
            weighted_hum += abs(delta[key]) * 0.1 * w

        self.experience.hum = min(1.0, self.experience.hum + weighted_hum)
        self.experience.add(changes, tick)
        return changes

    # ── 信念系统 ──────────────────────────────────

    def drift_belief(self, topic: str, delta: float, tick: int = -1, reason: str = ""):
        """缓慢调整某个信念（每次最多 ±0.01），同时记录演化轨迹。"""
        if topic not in self.beliefs:
            return
        old = self.beliefs[topic]
        delta = max(-0.01, min(0.01, delta))
        new = max(0.0, min(1.0, old + delta))
        self.beliefs[topic] = new
        if tick >= 0 and abs(delta) > 0.001:
            self.evolution.append({
                "tick": tick, "topic": topic,
                "old": round(old, 4), "new": round(new, 4),
                "delta": round(delta, 4), "reason": reason[:80],
            })

    def belief_summary(self) -> str:
        """信念摘要文本（给 prompt）。"""
        if not self.beliefs:
            return ""
        top = sorted(self.beliefs.items(), key=lambda x: -x[1])[:3]
        return "，".join(f"{k}: {v:.0%}" for k, v in top)

    # ── 秘密与条件披露 ──────────────────────────────

    def revealable_secrets(self, other_name: str) -> list[str]:
        """根据对某人的信任度，返回可透露的秘密。"""
        trust = self.get_trust(other_name)
        revealed = []
        for s in self.secrets:
            if s.get("revealed"):
                continue
            cond = s.get("condition", "trust>0.8")
            threshold = float(cond.split(">")[1]) if ">" in cond else 0.8
            if trust >= threshold:
                s["revealed"] = True
                revealed.append(s["description"])
        return revealed

    def secret_count_text(self) -> str:
        """未透露的秘密数量（给 prompt 渲染神秘感）。"""
        hidden = sum(1 for s in self.secrets if not s.get("revealed"))
        if hidden == 0:
            return ""
        return f"（你心中仍藏着一些从未对人提起的事。）"

    # ── 公开声明记录 ──────────────────────────────

    def record_statement(self, text: str):
        """记录一次公开发言。"""
        if text and len(text) > 5:
            self.public_statements.append(text[:200])
            # 最多保留 50 条，减少记忆负担
            if len(self.public_statements) > 50:
                self.public_statements = self.public_statements[-50:]

    def recall_statements(self, topic: str, n: int = 2) -> list[str]:
        """找到关于某个话题的过往发言。"""
        matched = []
        for s in reversed(self.public_statements):
            if topic.lower() in s.lower():
                matched.append(s)
                if len(matched) >= n:
                    break
        return matched

    def recall_text(self, topic: str = "") -> str:
        """回引文本（给 prompt）。"""
        if not self.public_statements:
            return ""
        if topic:
            past = self.recall_statements(topic, 2)
            if past:
                return f"你曾说过：「{past[0][:80]}」"
        # 没指定话题就提最近一次发言（从第 2 条开始才有意义）
        if len(self.public_statements) >= 2:
            return f"你记得自己曾经说过：「{self.public_statements[-1][:80]}」"
        return ""

    # ── 情景记忆 ──────────────────────────────────

    def add_episode(self, description: str, tick: int = 0,
                    participants: Optional[list[str]] = None,
                    location: str = "",
                    emotional_impact: Optional[dict[str, float]] = None,
                    importance: float = 0.5,
                    meaning: Optional[dict[str, str]] = None):
        """记录一段情景记忆。

        情景记忆是"我经历过的事"，不同于"世界发生了什么"。
        同一事件对不同居民的意义（meaning）可以不同。
        """
        entry = EpisodicMemoryEntry(
            tick=tick,
            description=description[:200],
            participants=participants or [],
            location=location,
            emotional_impact=emotional_impact or {},
            importance=importance,
            strength=1.0,
            meaning=meaning or {},
        )
        self.episodes.append(entry)
        # 上限 200 条
        if len(self.episodes) > 200:
            self.episodes = self.episodes[-200:]

    def recall_episodes(self, n: int = 5, min_salience: float = 0.05) -> list[EpisodicMemoryEntry]:
        """召回最显著的 N 条情景记忆（按 salience 排序）。"""
        sorted_eps = sorted(self.episodes, key=lambda e: e.salience, reverse=True)
        return [e for e in sorted_eps if e.salience > min_salience][:n]

    def recall_episodes_by_topic(self, topic: str, n: int = 3) -> list[EpisodicMemoryEntry]:
        """按话题召回情景记忆。"""
        matched = []
        for e in reversed(self.episodes):
            if topic.lower() in e.description.lower() or \
               any(topic.lower() in p.lower() for p in e.participants):
                matched.append(e)
                if len(matched) >= n:
                    break
        return matched

    def recall_episodes_by_participant(self, name: str, n: int = 3) -> list[EpisodicMemoryEntry]:
        """按参与者召回共同经历。"""
        matched = [e for e in reversed(self.episodes) if name in e.participants]
        return matched[:n]

    def episodes_text(self, n: int = 3) -> str:
        """情景记忆摘要文本（给 prompt）。"""
        top = self.recall_episodes(n)
        if not top:
            return ""
        lines = ["你记得："]
        for e in top:
            where = f"在{e.location}" if e.location else ""
            desc = e.description[:60]
            pct = int(e.salience * 100)
            lines.append(f"  · {where}{desc}（记忆强度 {pct}%）")
        return "\n".join(lines)

    # ── Social Dynamics 整合衰减 ──────────────────

    def tick_decay(self, ticks: int = 1):
        """每 tick 衰减：经验遗忘 + 多维关系趋中 + 信念归一 + 记忆衰退。"""
        self.experience.decay(ticks)
        # 多维关系缓慢趋零
        for name in list(self.relationships.keys()):
            rs = self.relationships[name]
            decay_factor = 0.995 ** ticks
            rs.trust *= decay_factor
            rs.curiosity *= decay_factor
            rs.conflict *= decay_factor
            if abs(rs.trust) < 0.005 and rs.curiosity < 0.005 and rs.conflict < 0.005 \
               and not rs.shared_history:
                del self.relationships[name]
        # 信念朝 0.5 缓慢漂移
        for topic in self.beliefs:
            drift = (0.5 - self.beliefs[topic]) * 0.002 * ticks
            self.beliefs[topic] = max(0.0, min(1.0, self.beliefs[topic] + drift))
        # 情景记忆衰减（低重要性衰减更快）
        for ep in self.episodes:
            decay_rate = 0.002 + (1.0 - ep.importance) * 0.008
            ep.strength = max(0.0, ep.strength - decay_rate * ticks)
        # 清理零强度记忆
        self.episodes = [ep for ep in self.episodes if ep.strength > 0.01]

    def reset_hum(self):
        self.experience.hum = 0.0

    # ── 自主演化 ──────────────────────────────────

    def tick_autonomous(self, ticks: int = 1):
        """无对话时的自主演化。

        只做：
        - 记忆衰减 + 信念漂移 + 关系趋中（tick_decay）
        - 随机产生一段独自经历（不进对话，只沉淀）
        - 定期内部反思
        """
        self.tick_decay(ticks)

        # 独自经历（约每 20 tick 一次）
        if random.random() < 0.05 * ticks:
            self.add_episode("独自度过了一段时间", tick=-1, importance=0.1)
            self.experience.hum = min(1.0, self.experience.hum + 0.01)

    def auto_reflect(self, tick: int = -1):
        """从最近的情景记忆中生成内部反思，沉淀为演化轨迹。

        不输出给任何人，只更新内部状态。
        """
        top = self.recall_episodes(2)
        if not top:
            return None

        # 取最显著的那条经历
        e = top[0]
        desc = e.description[:60]

        # 生成一条内部反思作为新 episode
        self.add_episode(f"回顾：{desc}", tick=tick,
                         importance=min(1.0, e.importance * 0.6))

        # 信念微动（根据经历内容模糊漂移）
        for topic in self.beliefs:
            if topic in desc.lower():
                self.drift_belief(topic, random.uniform(-0.003, 0.003),
                                  tick=tick, reason=f"反射性回顾'{desc[:30]}'")
                break

        return desc

    # ── 成长叙事 ──────────────────────────────────

    def growth_narrative(self) -> str:
        """从 evolution 中提取"我变了"的叙事文本。

        不依赖 LLM——只读已有的结构化数据。
        如果演化记录太少，返回空。
        """
        if len(self.evolution) < 2:
            return ""

        # 取变化幅度最大的 3 条
        biggest = sorted(self.evolution, key=lambda x: abs(x["delta"]), reverse=True)[:3]
        lines = ["回顾自己的变化："]
        for c in biggest:
            direction = "增强" if c["delta"] > 0 else "减弱"
            topic_label = c.get("topic", "未知")
            old_pct = int(c["old"] * 100)
            new_pct = int(c["new"] * 100)
            line = f"  · 对「{topic_label}」的倾向{direction}（{old_pct}% → {new_pct}%）"
            if c.get("reason"):
                line += f"，因为{c['reason'][:40]}"
            lines.append(line)

        # 第一条经历的"前→后"对比
        if self.episodes:
            oldest = min(self.episodes, key=lambda e: e.tick if e.tick >= 0 else 9999)
            newest = max(self.episodes, key=lambda e: e.tick if e.tick >= 0 else 0)
            if oldest != newest and oldest.description != newest.description:
                lines.append(f"  从「{oldest.description[:30]}」到「{newest.description[:30]}」")

        return "\n".join(lines)

    # ── 序列化 ──────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "identity": self.identity.to_dict(),
            "sensitivity": self.sensitivity.to_dict(),
            "silent": self.silent_state.to_dict(),
            "intention": self.current_intention.to_dict() if self.current_intention else {},
            "experience": self.experience.to_dict(),
            "private_events": self.private_events[-3:],
            "goals": self.active_goals(),
            "beliefs": dict(self.beliefs),
            "secrets": [s for s in self.secrets if s.get("revealed")],
            "public_statements": self.public_statements[-5:],
            "relationships": {k: v.to_dict() for k, v in self.relationships.items()},
            "episodes": [e.to_dict() for e in self.recall_episodes(5)],
            "evolution": self.evolution[-10:],
            "location": self.location,
            "last_action_tick": self.last_action_tick,
            "action_count": len(self._action_history),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LioraMind":
        """从 dict 恢复 LioraMind 实例。"""
        mind = cls(name=data.get("name", ""))
        if "identity" in data:
            mind.identity = IdentityProfile.from_dict(data["identity"])
        if "sensitivity" in data:
            mind.sensitivity = SensitivityProfile.from_dict(data["sensitivity"])
        if "silent" in data:
            mind.silent_state = SilentState.from_dict(data["silent"])
        if "intention" in data and data["intention"]:
            mind.current_intention = Intention(**data["intention"])
        if "experience" in data:
            mind.experience = ExperienceState.from_dict(data["experience"])
        if "private_events" in data:
            mind.private_events = list(data["private_events"])
        if "goals" in data:
            mind.goals = list(data["goals"])
        if "beliefs" in data:
            mind.beliefs = dict(data["beliefs"])
        if "secrets" in data:
            mind.secrets = list(data["secrets"])
        if "public_statements" in data:
            mind.public_statements = list(data["public_statements"])
        if "relationships" in data:
            mind.relationships = {
                k: RelationshipState.from_dict(v) for k, v in data["relationships"].items()
            }
        if "episodes" in data:
            mind.episodes = [EpisodicMemoryEntry.from_dict(e) for e in data["episodes"]]
        if "evolution" in data:
            mind.evolution = list(data["evolution"])
        if "location" in data:
            mind.location = data["location"]
        if "last_action_tick" in data:
            mind.last_action_tick = data["last_action_tick"]
        return mind

    def checkpoint(self, directory: str | Path = "data/minds") -> str:
        """将居民心智状态保存到磁盘。

        Args:
            directory: 保存目录（每个居民一个 JSON 文件）

        Returns:
            保存的文件路径
        """
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        filepath = path / f"{self.name}.json"
        data = self.to_dict()
        data["_saved_at"] = datetime.now().isoformat()
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(filepath)

    @classmethod
    def restore(cls, name: str, directory: str | Path = "data/minds") -> Optional["LioraMind"]:
        """从磁盘恢复居民心智状态。

        Args:
            name: 居民名称
            directory: 保存目录

        Returns:
            恢复的 LioraMind 实例，若文件不存在则返回 None
        """
        path = Path(directory) / f"{name}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception as e:
            logger.warning("恢复心智失败 %s: %s", path, e)
            return None
