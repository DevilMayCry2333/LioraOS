"""Cyberpunk WorldSpec 构建。

将所有配置打包为一个 WorldSpec，供 WorldRuntime 加载。
与 Liora 的 create_liora_spec() 完全同构。
"""

from aios.kernel.spec import WorldSpec
from aios.kernel.state import StateVariable
from aios.worlds.cyberpunk.state_rules import (
    create_cyberpunk_variables,
    cyberpunk_evolution_fn,
)
from aios.worlds.cyberpunk.event_templates import cyberpunk_event_generator


def create_cyberpunk_spec() -> WorldSpec:
    """创建 Night City（夜之城）的完整 WorldSpec。"""
    return WorldSpec(
        name="Night City",
        description="一个被企业割据、被数字化吞噬的城市。"
                    "混凝土、霓虹灯、数据碎片和人的希望在裂缝中生长。",
        state_variables=create_cyberpunk_variables(),
        evolution_fn=cyberpunk_evolution_fn,
        event_generator=cyberpunk_event_generator,
        memory_clusters=[
            ["企业", "corp", "公司"],
            ["街头", "street", "帮派"],
            ["数据", "data", "芯片", "网络"],
            ["幽灵", "ghost", "数字", "赛博"],
            ["人性", "human", "心"],
        ],
        version="0.1.0",
    )


def create_cyberpunk_objects() -> list[dict]:
    """夜之城的初始世界物体清单。"""
    return [
        {"name": "废弃的自动贩卖机", "location": "日本街",
         "owner": "", "description": "屏幕闪烁着一行无人能解码的讯息"},
        {"name": "老式电话亭", "location": "沃森区",
         "owner": "", "description": "一个还能用的有线电话——在这个时代几乎是个古董"},
        {"name": "被遗忘的数据终端", "location": "赛博空间边缘",
         "owner": "", "description": "某个旧网络留下的节点，偶尔会传出不属于任何人的信号"},
        {"name": "地下酒吧的留言板", "location": "黑市",
         "owner": "", "description": "贴满了手写的便签和加密二维码——人的痕迹在网络时代的声音"},
        {"name": "裂开的全息广告", "location": "市中心",
         "owner": "", "description": "一块巨大的全息广告牌，显示着残缺的企业标志。它在闪烁"},
    ]
