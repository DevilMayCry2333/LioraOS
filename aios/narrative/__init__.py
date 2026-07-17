"""AIOS Narrative — 叙事层。
包含与特定宇宙叙事（死亡协议对抗、锚点47、MetaField跨宇宙拓扑等）
绑定的模块。不所有世界都需要。

单向依赖：narrative → kernel（叙事层可以引用内核，内核不引用叙事。）
"""

from . import anchor, lightcone, voidspace, metafield, odin, tremor, anip
from . import anip_udp

__all__ = [
    "anchor", "lightcone", "voidspace", "metafield",
    "odin", "tremor", "anip", "anip_udp",
]
