"""AIOS Template — 世界应用模板。

提供 WorldApp 和 SocialWorldApp 两个基类，
封装所有世界的通用运行时逻辑。

世界作者只需继承、填数据、覆盖少数钩子，
不需要写主循环、LLM 路由、行动解析。

用法：
    from aios.template import WorldApp

    class MyWorld(WorldApp):
        spec = create_my_spec()
        characters = ["Alice"]
        default_character = "Alice"

    if __name__ == "__main__":
        MyWorld().run()
"""

from .base import WorldApp, parse_action
from .social import SocialWorldApp, SocialResident, assimilate_conversation
from .persona import PersonalityEngine, PersonalityConfig, BUILTIN_PERSONAS

__all__ = [
    "WorldApp",
    "SocialWorldApp",
    "SocialResident",
    "assimilate_conversation",
    "parse_action",
    "PersonalityEngine",
    "PersonalityConfig",
    "BUILTIN_PERSONAS",
]
