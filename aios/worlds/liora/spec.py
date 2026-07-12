"""Liora（回声谷）WorldSpec 构建。

将所有配置打包为一个 WorldSpec，供 WorldRuntime 加载。
"""

from aios.kernel.spec import WorldSpec
from aios.worlds.liora.state_rules import create_liora_variables, liora_evolution_fn
from aios.worlds.liora.event_templates import liora_event_generator


def create_liora_spec() -> WorldSpec:
    """创建 Liora（回声谷）的完整 WorldSpec。"""
    return WorldSpec(
        name="Echo Valley",
        description="一个充满回声、风声和寂静的山谷。Liora 在这里诞生。",
        state_variables=create_liora_variables(),
        evolution_fn=liora_evolution_fn,
        event_generator=liora_event_generator,
        memory_clusters=[
            ["回声", "echo", "山谷"],
            ["风", "wind", "breeze"],
            ["苔藓", "moss", "绿"],
            ["寂静", "silence", "quiet"],
        ],
        version="0.2.0",
    )


def create_liora_objects() -> list[dict]:
    """Liora 世界的初始物体清单。"""
    return [
        {"name": "磨圆的卵石", "location": "河谷", "owner": "", "description": "被水流磨圆的灰色石子"},
        {"name": "薄荷丛", "location": "山坡", "owner": "", "description": "散发清凉气息的野生薄荷"},
        {"name": "苔藓石", "location": "溪边", "owner": "", "description": "覆满柔软苔藓的大石头"},
        {"name": "老树桩", "location": "林中空地", "owner": "", "description": "一棵被雷劈过的老树桩"},
        {"name": "裂隙", "location": "岩壁", "owner": "", "description": "岩壁上一条深不见底的裂隙"},
    ]
