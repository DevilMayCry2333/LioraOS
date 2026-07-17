"""AIOS Template — 人格动力学引擎（Personality Dynamics）

不是一堆经典台词，是一套持续影响感知、情绪、决策和行为的内在机制。

链条：
  价值观（Values）→ 信念（Beliefs）→ 情绪（Emotions）
  → 决策（Decisions）→ 行动（Actions）

任何 Resident 都可以 attach 一个 PersonalityEngine 作为人格组件。
同一个人格引擎适用于回声谷的诗人、夜之城的佣兵、龙族的观察者——

只是参数不同。

使用方式：
    from aios.template.persona import PersonalityEngine, BUILTIN_PERSONAS

    # 用预设（强尼·银手）
    engine = PersonalityEngine.from_preset("johnny_silverhand")

    # 每 tick
    engine.tick()
    engine.process_event(event_type, intensity, data)

    # 生成 LLM 上下文
    ctx = engine.llm_context()
"""

from __future__ import annotations

import copy
import logging
import random
from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional

logger = logging.getLogger("aios.template.persona")


# ════════════════════════════════════════════════════════════════
# 第一层：数据模型
# ════════════════════════════════════════════════════════════════

# ── 价值观 ──────────────────────────────────────────────────


@dataclass
class Value:
    """一个价值观维度。

    importance: 这个人有多看重这个价值观（0-1）
    fulfillment: 当前感到被满足/违背的程度（-1 到 1）
               正值 = 被满足、被尊重
               负值 = 被违背、被侵犯
    """

    name: str
    importance: float = 0.5          # 0-1，权重
    fulfillment: float = 0.0         # -1 到 1

    def delta(self, amount: float):
        """调整 fulfillment，限幅。"""
        self.fulfillment = max(-1.0, min(1.0, self.fulfillment + amount))

    def drift(self, rate: float = 0.005):
        """缓慢向零回归（情绪冷却）。"""
        if abs(self.fulfillment) < rate:
            self.fulfillment = 0.0
        elif self.fulfillment > 0:
            self.fulfillment -= rate
        else:
            self.fulfillment += rate

    def salience(self) -> float:
        """这个价值观当前的"显著性"——重要性 × 违背程度。

        如果 fulfillment 是负的（被违背了），显著性高 → 驱动行动。
        如果 fulfillment 是正的（被满足了），显著性低 → 安静。
        """
        if self.fulfillment < 0:
            return self.importance * abs(self.fulfillment)
        return self.importance * (1.0 - self.fulfillment) * 0.3

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "importance": round(self.importance, 3),
            "fulfillment": round(self.fulfillment, 3),
        }


# ── 情绪 ────────────────────────────────────────────────────


@dataclass
class EmotionalState:
    """情绪状态 — 使用 Valence-Arousal-Dominance (VAD) 模型。

    valence:   -1 到 1，负=不愉快，正=愉快
    arousal:    0 到 1，低=平静，高=激动
    dominance:  0 到 1，低=顺从/无力，高=掌控/有力

    primary: 当前主导情绪标签（由 VAD 推导）
    """

    valence: float = 0.0
    arousal: float = 0.5
    dominance: float = 0.5
    primary: str = "neutral"

    # 类变量（不被 dataclass 视为字段）
    _decay_rate: ClassVar[float] = 0.03
    _PRIMARY_MAP: ClassVar[dict[tuple[str, str, str], str]] = {
        # (valence_band, arousal_band, dominance_band) → emotion
        ("pos", "high", "high"): "joy",
        ("pos", "high", "low"): "excitement",
        ("pos", "low", "high"): "contentment",
        ("pos", "low", "low"): "serenity",
        ("neg", "high", "high"): "anger",
        ("neg", "high", "low"): "fear",
        ("neg", "low", "high"): "contempt",
        ("neg", "low", "low"): "sadness",
        ("zero", "high", "high"): "surprise",
        ("zero", "high", "low"): "anxiety",
        ("zero", "low", "high"): "calm",
        ("zero", "low", "low"): "boredom",
    }

    def _band(self, v: float, high_thresh: float = 0.3) -> str:
        if v > high_thresh:
            return "pos"
        if v < -high_thresh:
            return "neg"
        return "zero"

    def _arousal_band(self) -> str:
        return "high" if self.arousal >= 0.55 else "low"

    def _dominance_band(self) -> str:
        return "high" if self.dominance >= 0.55 else "low"

    def resolve_primary(self):
        """从 VAD 值推导当前主导情绪标签。"""
        vb = self._band(self.valence)
        ab = self._arousal_band()
        db = self._dominance_band()
        self.primary = self._PRIMARY_MAP.get((vb, ab, db), "neutral")

    def apply_impulse(self, valence_delta: float, arousal_delta: float,
                      dominance_delta: float):
        """施加一个情绪脉冲（由事件触发）。"""
        self.valence = max(-1.0, min(1.0, self.valence + valence_delta))
        self.arousal = max(0.0, min(1.0, self.arousal + arousal_delta))
        self.dominance = max(0.0, min(1.0, self.dominance + dominance_delta))
        self.resolve_primary()

    def decay(self, target: EmotionalState | None = None):
        """向基准状态回归。"""
        t = target or EmotionalState()
        rate = self._decay_rate
        self.valence += (t.valence - self.valence) * rate
        self.arousal += (t.arousal - self.arousal) * rate
        self.dominance += (t.dominance - self.dominance) * rate

    # ── 自然语言标签（给 LLM 用） ──

    @property
    def intensity_label(self) -> str:
        a = self.arousal
        if a >= 0.8:
            return "非常强烈"
        if a >= 0.6:
            return "强烈"
        if a >= 0.4:
            return "中等"
        if a >= 0.2:
            return "轻微"
        return "几乎感觉不到"

    @property
    def natural_description(self) -> str:
        """用自然语言描述当前情绪。"""
        intensity = self.intensity_label
        return f"{intensity}的{self.primary}（效价{self.valence:.2f}，唤醒{self.arousal:.2f}）"

    def to_dict(self) -> dict:
        return {
            "primary": self.primary,
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
        }


# ── 决策参数 ──────────────────────────────────────────────


@dataclass
class DecisionParameters:
    """决策风格参数—决定价值观如何转化为行动。"""

    # 价值观对齐度：做决定时在多大程度上被价值观过滤
    # 1.0 = 绝对按价值观行事（强尼）；0.0 = 完全实用主义
    value_alignment: float = 0.7

    # 风险承受度
    risk_tolerance: float = 0.5

    # 冲动性（0=深思熟虑，1=先做再想）
    impulsivity: float = 0.5

    # 同理心（0=冷漠，1=高度共情）
    empathy: float = 0.5

    # 改变意愿（0=抗拒变化，1=拥抱变化）
    openness_to_change: float = 0.5

    def to_dict(self) -> dict:
        return {
            "value_alignment": round(self.value_alignment, 2),
            "risk_tolerance": round(self.risk_tolerance, 2),
            "impulsivity": round(self.impulsivity, 2),
            "empathy": round(self.empathy, 2),
            "openness_to_change": round(self.openness_to_change, 2),
        }


# ── 对话风格 ──────────────────────────────────────────────


@dataclass
class DialogStyle:
    """对话风格参数——不是说"什么内容"，是说"怎么说话"。"""

    # 话量：0=极度简短（"不"），1=长篇大论
    verbosity: float = 0.5

    # 讽刺程度
    sarcasm: float = 0.3

    # 直接程度：0=委婉暗示，1=直球
    directness: float = 0.7

    # 正式程度：0=街头俚语，1=学术报告
    formality: float = 0.3

    # 脏话频率
    profanity: float = 0.3

    # 幽默类型
    humor_type: str = "none"  # "dark", "dry", "self_deprecating", "absurd", "none"
    humor_frequency: float = 0.0

    # 修辞偏好（可多选）
    rhetorical_devices: list[str] = field(default_factory=lambda: ["metaphor"])

    def style_guide(self) -> str:
        """生成给 LLM 的风格指引。"""
        parts = []

        if self.verbosity < 0.3:
            parts.append("说话极其简短，能用三个词说完不用四个")
        elif self.verbosity > 0.7:
            parts.append("不介意展开说，有时会说很多")
        else:
            parts.append("该短则短，该长则长")

        if self.sarcasm > 0.6:
            parts.append("习惯性讽刺")
        if self.directness > 0.7:
            parts.append("说话直接，不拐弯抹角")
        if self.formality < 0.3:
            parts.append("用词街头，不讲究语法")
        if self.profanity > 0.5:
            parts.append("偶尔会爆粗口")

        if self.humor_type != "none" and self.humor_frequency > 0.3:
            types = {
                "dark": "黑色幽默",
                "dry": "冷幽默",
                "self_deprecating": "自嘲",
                "absurd": "荒诞幽默",
            }
            label = types.get(self.humor_type, self.humor_type)
            parts.append(f"讲话带有{label}")

        if self.rhetorical_devices:
            if "metaphor" in self.rhetorical_devices:
                parts.append("喜欢用比喻")

        return "，".join(parts) + "。"

    def to_dict(self) -> dict:
        return {
            "verbosity": round(self.verbosity, 2),
            "sarcasm": round(self.sarcasm, 2),
            "directness": round(self.directness, 2),
            "formality": round(self.formality, 2),
            "humor": self.humor_type,
            "profanity": round(self.profanity, 2),
        }


# ── 内藏特质 ──────────────────────────────────────────────


@dataclass
class HiddenTraits:
    """角色藏起来的、不会轻易表露的部分。

    这些是 LLM 看不到的——除非在特定条件下被触发。
    """

    loneliness: float = 0.3       # 0-1
    guilt: float = 0.2            # 0-1
    compassion: float = 0.5       # 0-1
    hope: float = 0.5             # 0-1
    regret: float = 0.2           # 0-1
    pride: float = 0.5            # 0-1

    def to_dict(self) -> dict:
        return {
            "loneliness": round(self.loneliness, 2),
            "guilt": round(self.guilt, 2),
            "compassion": round(self.compassion, 2),
            "hope": round(self.hope, 2),
            "regret": round(self.regret, 2),
            "pride": round(self.pride, 2),
        }


# ── 完整人格配置 ──────────────────────────────────────────


@dataclass
class PersonalityConfig:
    """人格配置——人格的静态定义。

    这是"出厂设置"。
    运行为由 PersonalityEngine 读取，根据事件和 tick 发生偏移。
    """

    name: str                                # 人格名称（通常等于角色名）
    archetype: str                           # 原型标签（"Rebel", "Sage", "Caregiver"...）
    description: str                         # 一句话描述

    # 核心价值观：name → importance
    core_values: dict[str, float]

    # 默认情绪（未受刺激时的基线）
    default_emotion: EmotionalState = field(default_factory=EmotionalState)

    # 决策参数
    decision_params: DecisionParameters = field(default_factory=DecisionParameters)

    # 对话风格
    dialog_style: DialogStyle = field(default_factory=DialogStyle)

    # 内藏特质
    hidden_traits: HiddenTraits = field(default_factory=HiddenTraits)

    # 厌恶/反感表：stimulus → 强度
    # 触发时直接推高 specific value 的违背感
    aversions: dict[str, float] = field(default_factory=dict)

    # 价值观敏感性矩阵：事件类型 → {受影响的价值: 影响量}
    # 例如 "corporate_action" → {"freedom": -0.3, "dignity": -0.2}
    value_sensitivity: dict[str, dict[str, float]] = field(default_factory=dict)

    # 情绪敏感性矩阵：事件类型 → {valence_delta, arousal_delta, dominance_delta}
    emotion_sensitivity: dict[str, dict[str, float]] = field(default_factory=dict)

    # 决策优先级（字符串列表，按优先级从高到低）
    decision_priority: list[str] = field(default_factory=list)

    # 典型行动模式（给 LLM 参考的倾向）
    action_tendencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "archetype": self.archetype,
            "core_values": {k: round(v, 2) for k, v in self.core_values.items()},
            "default_emotion": self.default_emotion.to_dict(),
            "decision_params": self.decision_params.to_dict(),
            "dialog_style": self.dialog_style.to_dict(),
            "hidden_traits": self.hidden_traits.to_dict(),
            "decision_priority": self.decision_priority,
        }


# ════════════════════════════════════════════════════════════════
# 第二层：运行时
# ════════════════════════════════════════════════════════════════


class PersonalityEngine:
    """人格引擎运行时。

    每个 Resident 可拥有一个实例，作为其"人格组件"。
    每 tick 处理：
      1. 价值观 fulfillment 向零回归
      2. 情绪向基准状态回归
      3. 事件影响（如果事件类型匹配 value_sensitivity / emotion_sensitivity）

    每轮对话提供：
      - 当前情绪状态
      - 当前最被违背/满足的价值观
      - 决策倾向
      - 对话风格指引
    """

    def __init__(self, config: PersonalityConfig):
        self.config = config

        # 运行时状态（深拷贝——不改动原始配置）
        self.values: dict[str, Value] = {
            name: Value(name=name, importance=imp)
            for name, imp in config.core_values.items()
        }
        self.emotion = copy.deepcopy(config.default_emotion)
        self.emotion.resolve_primary()

        # 事件记忆（最近 N 条事件类型，用于情绪累积）
        self._recent_events: list[tuple[str, int]] = []   # (type, tick)
        self._max_recent_events: int = 10

        # 上一轮的高显著性价值观（给 LLM 上下文用）
        self._top_values: list[str] = []

        # 总 tick 计数
        self._ticks: int = 0

    # ── 工厂方法 ──────────────────────────────────────────

    @classmethod
    def from_preset(cls, name: str) -> PersonalityEngine:
        """从内置预设创建人格引擎。

        Args:
            name: 预设名称，如 "johnny_silverhand"

        Returns:
            配置好的 PersonalityEngine

        Raises:
            KeyError: 预设不存在
        """
        if name not in BUILTIN_PERSONAS:
            raise KeyError(f"人格预设不存在: {name}，可选: {list(BUILTIN_PERSONAS.keys())}")
        config = BUILTIN_PERSONAS[name]
        return cls(config)

    # ── 运行时 ────────────────────────────────────────────

    def tick(self):
        """每 tick 处理。

        1. 价值观 fulfillment 向零回归
        2. 情绪向基准回归
        3. 更新高显著性价值观列表
        """
        self._ticks += 1

        for v in self.values.values():
            v.drift(rate=0.005)

        self.emotion.decay(target=self.config.default_emotion)

        # 更新高显著性价值观（供 LLM 上下文用）
        sorted_vals = sorted(
            self.values.values(),
            key=lambda v: v.salience(),
            reverse=True,
        )
        self._top_values = [v.name for v in sorted_vals[:3]]

    def process_event(self, event_type: str, intensity: float = 0.5,
                      data: dict | None = None):
        """处理一个事件——影响价值观 fulfillment 和情绪。

        Args:
            event_type: 事件类型，匹配 value_sensitivity / emotion_sensitivity
            intensity: 事件强度放缩因子
            data: 可选的事件数据
        """
        # 1. 价值观影响
        sensitivity = self.config.value_sensitivity.get(event_type, {})
        for value_name, delta in sensitivity.items():
            if value_name in self.values:
                self.values[value_name].delta(delta * intensity)

        # 2. 检查 aversions
        if data:
            for stimulus, strength in self.config.aversions.items():
                if stimulus in str(data).lower():
                    for v in self.values.values():
                        if v.name in ("freedom", "dignity", "authenticity"):
                            v.delta(-strength * intensity * 0.5)

        # 3. 情绪影响
        emo_sens = self.config.emotion_sensitivity.get(event_type, {})
        if emo_sens:
            self.emotion.apply_impulse(
                valence_delta=emo_sens.get("valence", 0.0) * intensity,
                arousal_delta=emo_sens.get("arousal", 0.0) * intensity,
                dominance_delta=emo_sens.get("dominance", 0.0) * intensity,
            )

        # 4. 记录事件
        self._recent_events.append((event_type, self._ticks))
        if len(self._recent_events) > self._max_recent_events:
            self._recent_events.pop(0)

    # ── LLM 上下文 ────────────────────────────────────────

    def value_context(self) -> str:
        """当前价值观状态的自然语言描述（给 LLM）。"""
        if not self._top_values:
            sorted_vals = sorted(
                self.values.values(),
                key=lambda v: v.salience(),
                reverse=True,
            )
            self._top_values = [v.name for v in sorted_vals[:3]]

        parts = []
        for name in self._top_values:
            v = self.values.get(name)
            if v is None:
                continue
            if v.fulfillment < -0.3:
                parts.append(f"{name} 被严重违背了（当前 {v.fulfillment:.2f}）")
            elif v.fulfillment < 0:
                parts.append(f"{name} 轻微受挫（当前 {v.fulfillment:.2f}）")
            elif v.fulfillment > 0.3:
                parts.append(f"{name} 得到了满足（当前 {v.fulfillment:.2f}）")

        if not parts:
            return "目前没有价值观受到强烈挑战。"

        return "你现在的心理状态：" + "；".join(parts)

    def emotion_context(self) -> str:
        """当前情绪状态的自然语言描述（给 LLM）。"""
        return f"你的情绪：{self.emotion.natural_description}。"

    def decision_context(self) -> str:
        """决策倾向（给 LLM）。"""
        params = self.config.decision_params
        priority = self.config.decision_priority

        parts = ["做决定时，你倾向于："]
        if params.value_alignment > 0.6:
            parts.append("- 优先考虑是否符合自己的价值观")
        if params.risk_tolerance > 0.6:
            parts.append("- 不害怕冒险")
        elif params.risk_tolerance < 0.3:
            parts.append("- 倾向于保守和稳妥")
        if params.impulsivity > 0.6:
            parts.append("- 相信直觉，快速行动")
        elif params.impulsivity < 0.3:
            parts.append("- 习惯深思熟虑")
        if params.empathy > 0.6:
            parts.append("- 会考虑对他人的影响")

        if priority:
            parts.append(f"你的首要原则：{' > '.join(priority[:3])}")

        return "\n".join(parts)

    def style_context(self) -> str:
        """对话风格指引（给 LLM）。"""
        return self.config.dialog_style.style_guide()

    def full_context(self) -> str:
        """完整人格上下文（给 LLM 注入 prompt）。"""
        parts = [
            f"[人格] 你是一个{self.config.archetype}。{self.config.description}",
            "",
            self.value_context(),
            self.emotion_context(),
            "",
            self.decision_context(),
            "",
            self.style_context(),
        ]
        return "\n".join(parts)

    def hidden_context(self, trigger_condition: str = "") -> str:
        """内藏特质——只有在特定条件下才暴露给 LLM。

        Args:
            trigger_condition: 触发条件描述（如 "deep trust", "vulnerable moment"）
        """
        if not trigger_condition:
            return ""
        traits = self.config.hidden_traits
        threshold_map = {
            "deep trust": ("loneliness", "compassion", "hope"),
            "vulnerable": ("loneliness", "guilt", "regret"),
            "loss": ("guilt", "regret", "sadness"),
            "victory": ("pride", "hope"),
            "reflection": ("regret", "hope", "loneliness"),
        }
        relevant = threshold_map.get(trigger_condition, [])
        if not relevant:
            return ""
        lines = [f"[内心深处——因为你信任对方]"]
        for trait in relevant:
            val = getattr(traits, trait, 0.0)
            if val > 0.5:
                lines.append(f"  其实你有着较强的{trait}")
            elif val > 0.2:
                lines.append(f"  你偶尔会感到{trait}")
        if len(lines) > 1:
            return "\n".join(lines)
        return ""

    def aversions_context(self) -> str:
        """当前触发厌恶感的事物。"""
        av = self.config.aversions
        if not av:
            return ""
        high = [(k, v) for k, v in av.items() if v > 0.5]
        if not high:
            return ""
        lines = ["你本能地厌恶："]
        for k, v in high:
            lines.append(f"  - {k}（强度 {v:.1f}）")
        return "\n".join(lines)

    # ── 行动建议 ─────────────────────────────────────────

    def action_tendencies_context(self) -> str:
        """行动倾向（给 LLM 参考）。"""
        tendencies = self.config.action_tendencies
        if not tendencies:
            return ""
        return f"你的本能反应：{'、'.join(tendencies)}。"

    # ── 查询 ──────────────────────────────────────────────

    def dominant_emotion(self) -> Optional[EmotionalState]:
        """当前主导情绪——强度 > 0.3 时返回 EmotionalState，否则返回 None。

        供 SocialResident 在计算沉默概率时使用。
        """
        if self.emotion.arousal > 0.3 or abs(self.emotion.valence) > 0.3:
            return self.emotion
        return None

    def emotional_text(self) -> str:
        """当前情绪的简短自然语言描述（给 LLM 注入）。

        强度 > 0.3 时返回描述，否则返回空字符串。
        """
        dom = self.dominant_emotion()
        if dom is None:
            return ""
        return (
            f"（你的情绪：{dom.natural_description}。"
            f"这个情绪正在影响你的判断——但你不一定时刻意识到它。）"
        )

    def most_violated_values(self, top_n: int = 2) -> list[Value]:
        """当前被违背最严重的价值观。"""
        vals = sorted(
            [v for v in self.values.values() if v.fulfillment < 0],
            key=lambda v: v.fulfillment,
        )
        return vals[:top_n]

    def summary(self) -> dict[str, Any]:
        """人格当前状态的总结。"""
        all_vals = sorted(
            self.values.values(),
            key=lambda v: v.salience(),
            reverse=True,
        )
        return {
            "archetype": self.config.archetype,
            "emotion": self.emotion.to_dict(),
            "top_values": [
                {"name": v.name, "fulfillment": round(v.fulfillment, 3),
                 "salience": round(v.salience(), 3)}
                for v in all_vals[:3]
            ],
            "ticks": self._ticks,
        }


# ════════════════════════════════════════════════════════════════
# 第三层：内置人格预设
# ════════════════════════════════════════════════════════════════

BUILTIN_PERSONAS: dict[str, PersonalityConfig] = {}


def _register_persona(name: str, config: PersonalityConfig):
    BUILTIN_PERSONAS[name] = config


# ── 强尼·银手 ───────────────────────────────────────────


JOHNNY_SILVERHAND = PersonalityConfig(
    name="约翰尼·银手",
    archetype="Rebel",
    description="极端自由主义革命者，浪漫主义理想家，愤怒的反权威者。"
               "你的身体被毁了，你的记忆被别人活着。但你还在反抗——因为不反抗就不是你了。",

    core_values={
        "freedom": 1.0,
        "dignity": 0.98,
        "authenticity": 0.95,
        "loyalty": 0.90,
        "justice": 0.88,
    },

    default_emotion=EmotionalState(
        valence=-0.35,
        arousal=0.6,
        dominance=0.7,
        primary="anger",
    ),

    decision_params=DecisionParameters(
        value_alignment=0.95,     # 几乎绝对按价值观行事
        risk_tolerance=0.85,      # 不怕冒险
        impulsivity=0.75,         # 先做再想
        empathy=0.65,             # 嘴硬心软
        openness_to_change=0.5,
    ),

    dialog_style=DialogStyle(
        verbosity=0.4,            # 短句为主
        sarcasm=0.7,              # 习惯性讽刺
        directness=0.9,           # 直球
        formality=0.15,           # 街头俚语
        profanity=0.65,           # 时不时爆粗
        humor_type="dark",        # 黑色幽默
        humor_frequency=0.5,
        rhetorical_devices=["metaphor", "sarcasm"],
    ),

    hidden_traits=HiddenTraits(
        loneliness=0.8,
        guilt=0.65,
        compassion=0.85,          # 其实很在意——但绝不承认
        hope=0.3,                  # 嘴上说没有，底层有一点点
        regret=0.7,
        pride=0.9,
    ),

    aversions={
        "corporation": 1.0,
        "authority": 0.95,
        "hypocrisy": 0.96,
        "cowardice": 0.90,
        "control": 0.85,
        "surveillance": 0.8,
    },

    value_sensitivity={
        "corporate_action": {
            "freedom": -0.3,
            "dignity": -0.2,
            "justice": -0.25,
        },
        "oppression": {
            "freedom": -0.35,
            "dignity": -0.25,
            "authenticity": -0.2,
        },
        "resistance": {
            "freedom": 0.2,
            "dignity": 0.15,
            "authenticity": 0.2,
        },
        "betrayal": {
            "loyalty": -0.3,
            "dignity": -0.15,
        },
        "friendship": {
            "loyalty": 0.15,
            "authenticity": 0.1,
        },
        "injustice": {
            "justice": -0.3,
            "freedom": -0.15,
        },
        "silence": {
            "authenticity": -0.1,
        },
        "hypocrisy": {
            "authenticity": -0.3,
            "dignity": -0.2,
        },
    },

    emotion_sensitivity={
        "corporate_action": {"valence": -0.2, "arousal": 0.2, "dominance": -0.05},
        "oppression": {"valence": -0.25, "arousal": 0.25, "dominance": -0.1},
        "resistance": {"valence": 0.15, "arousal": 0.2, "dominance": 0.1},
        "betrayal": {"valence": -0.3, "arousal": 0.15, "dominance": -0.2},
        "friendship": {"valence": 0.15, "arousal": -0.1, "dominance": 0.05},
        "injustice": {"valence": -0.25, "arousal": 0.2, "dominance": -0.05},
        "loss": {"valence": -0.2, "arousal": -0.1, "dominance": -0.15},
    },

    decision_priority=[
        "protect freedom",
        "oppose oppression",
        "protect companions",
        "pursue survival",
    ],

    action_tendencies=[
        "面对压迫时选择反抗而非沉默",
        "保护弱者时不计代价",
        "面对权威时本能地质疑",
        "认定的人会拼命保护",
    ],
)

_register_persona("johnny_silverhand", JOHNNY_SILVERHAND)

# ── 以后可以加更多 ──────────────────────────────────────
# V 的预设 → pragmatist / survivor
# Aria 的预设 → poet / observer
# 路鸣泽的预设 → trickster / meta_observer
