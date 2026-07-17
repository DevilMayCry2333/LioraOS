"""CognitiveModel Protocol — 认知模型接口定义。

任何实现了此 Protocol 的类都可以作为 SocialWorldApp 的认知模型。
LioraMind、PersonalityEngine 等应当满足此接口。

使用方法：
    from aios.template.cognitive import CognitiveModel

    class MyModel:
        implements CognitiveModel  # 结构子类型，Python 自动满足

    # 或用显式注册:
    CognitiveModel.register(MyModel)
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


# ════════════════════════════════════════════════════════════
# 子类型 Protocol（认知模型的组成部分）
# ════════════════════════════════════════════════════════════


@runtime_checkable
class CognitiveIdentity(Protocol):
    """认知模型的身份维度。"""
    name: str
    style: str


@runtime_checkable
class CognitiveExperience(Protocol):
    """认知模型的体验/经验维度。"""
    hum: float
    total: float


@runtime_checkable
class CognitiveSilence(Protocol):
    """认知模型的沉默状态。"""
    is_silent: bool
    duration: int


@runtime_checkable
class CognitiveRelationship(Protocol):
    """认知模型的单边关系状态。"""
    trust: float
    curiosity: float
    conflict: float


# ════════════════════════════════════════════════════════════
# 认知模型主 Protocol
# ════════════════════════════════════════════════════════════


@runtime_checkable
class CognitiveModel(Protocol):
    """认知模型的 Protocol 定义。

    所有 SocialWorldApp 和 SocialResident 使用的认知模型必须满足此接口。
    不要求继承此类——Python 的结构子类型系统会自动检查。
    """

    name: str

    # ── 子对象（作为属性访问）──

    @property
    def identity(self) -> CognitiveIdentity: ...

    @property
    def experience(self) -> CognitiveExperience: ...

    @property
    def silent_state(self) -> CognitiveSilence: ...

    @property
    def consecutive_silence(self) -> int: ...

    @property
    def relationships(self) -> dict[str, CognitiveRelationship]: ...

    # ── 关系方法 ──

    def relate(self, other_name: str, trust: float = 0.0,
               curiosity: float = 0.0, tick: int = 0): ...

    def relationship_summary(self) -> str: ...

    def share_history(self, other_name: str, episode_desc: str): ...

    # ── 记忆方法 ──

    def add_episode(self, description: str, tick: int = 0,
                    participants: Optional[list[str]] = None,
                    location: str = "",
                    importance: float = 0.5): ...

    def recall_episodes_by_participant(self, name: str,
                                        n: int = 3) -> list: ...

    def growth_narrative(self) -> str: ...

    def record_statement(self, statement: str): ...

    # ── 演化方法 ──

    def tick_autonomous(self, n: int): ...

    def tick_decay(self, n: int): ...

    def auto_reflect(self, tick: int): ...

    def assimilate(self, state_vars: dict, tick: int): ...

    def update_sensitivity(self, total: float): ...

    # ── 目标方法 ──

    def add_goal(self, desc: str, tick: int): ...

    def active_goals(self) -> list: ...


# ════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════


def is_cognitive_model(obj: Any) -> bool:
    """检查对象是否满足 CognitiveModel Protocol。"""
    return isinstance(obj, CognitiveModel)
