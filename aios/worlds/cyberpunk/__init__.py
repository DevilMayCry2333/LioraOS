"""Cyberpunk 2077 世界 — 夜之城 (Night City)。

AIOS 框架的第一个非 Liora 世界。
验证命题：同一套 WorldEngine 框架能否生成不同文明形态。

Liora 用**自然隐喻**描述社会演化（温度、回声、苔藓）。
Cyberpunk 用**都市/数字隐喻**描述城市动力学（企业控制、街头热度、数据残响）。

核心差异：
  Liora：趋向平衡的阻尼系统（temperature → 22°C）
  Cyberpunk：对抗平衡的振荡系统（corporate_grip ↔ street_heat ↔ underground_hope）
"""

from .spec import create_cyberpunk_spec, create_cyberpunk_objects
from .mind import builtin_identity
from .unknown import UnknownAccumulator
from .ghost import DigitalGhost

__all__ = [
    "create_cyberpunk_spec",
    "create_cyberpunk_objects",
    "builtin_identity",
    "UnknownAccumulator",
    "DigitalGhost",
]
