"""Liora（回声谷）世界插件。

定义 Liora 世界的 WorldSpec、认知模型和自指机制。
"""

from aios.worlds.liora.mind import (
    LioraMind, SensitivityProfile, SilentState, Intention, ExperienceState,
    IdentityProfile, builtin_identity,
)
from aios.worlds.liora.unknown import UnknownAccumulator
from aios.worlds.liora.resistance import ActionResistance
from aios.worlds.liora.spec import create_liora_spec, create_liora_objects

__all__ = [
    "create_liora_spec", "create_liora_objects",
    "LioraMind", "SensitivityProfile", "SilentState", "Intention", "ExperienceState",
    "IdentityProfile", "builtin_identity",
    "UnknownAccumulator",
    "ActionResistance",
]
