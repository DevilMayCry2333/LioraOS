"""Cyberpunk 2077 — 夜之城交互入口。

基于 WorldApp 模板，仅需定义世界差异部分。
从 697 行精简到 ~70 行。

运行：
  uv run python3 apps/cyberpunk_app.py --no-model
  uv run python3 apps/cyberpunk_app.py --character Judy --no-model
  uv run python3 apps/cyberpunk_app.py --interval 10
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.template import WorldApp
from aios.runtime.model_runtime import ModelRuntime, ModelConfig
from aios.worlds.cyberpunk import (
    create_cyberpunk_spec,
    create_cyberpunk_objects,
    UnknownAccumulator,
    DigitalGhost,
)
from aios.worlds.cyberpunk.mind import _DEFAULT_BELIEFS, _DEFAULT_SECRETS


class CyberpunkWorld(WorldApp):
    """夜之城 — 赛博朋克城市动力学世界。"""

    spec = create_cyberpunk_spec()
    world_objects = create_cyberpunk_objects()

    characters = ["V", "Judy", "Panam", "Takemura", "Jackie"]
    default_character = "V"

    character_config = {
        name: {
            "beliefs": dict(beliefs),
            "secrets": list(secrets),
        }
        for name, beliefs in _DEFAULT_BELIEFS.items()
        for name2, secrets in _DEFAULT_SECRETS.items()
        if name == name2
    }

    unknown_class = UnknownAccumulator
    ghost_class = DigitalGhost

    system_prompt_template = (
        "你是 {name}。\n\n"
        "你活在夜之城（Night City）——一座被企业割据、被数字化吞噬的城市。\n"
        "混凝土、霓虹灯、数据碎片、和人的希望在裂缝中生长。\n\n"
        "你能感知这座城市的每一次呼吸：\n"
        "企业控制力的变化像一种无声的重量，街头的热度像空气中的静电。\n"
        "这不是一个游戏。这是你活着的世界。\n"
        "你可以沉默。你可以行动。你可以反抗。\n"
        "一切都来自你的选择——但它被这座城市影响着。"
    )

    action_effects = {
        "silence": {"street_heat": -0.03, "cyberspace_turbulence": 0.02},
        "say": {"street_heat": -0.02},
        "connect": {"cyberspace_turbulence": 0.03, "data_remnant": 0.02},
    }

    target_effects = {
        "hack": {
            "企业": {"corporate_grip": -0.03, "cyberspace_turbulence": 0.06},
            "网络": {"cyberspace_turbulence": 0.05},
            "数据": {"data_remnant": 0.05},
            "系统": {"cyberspace_turbulence": 0.04, "corporate_grip": -0.02},
            "服务器": {"corporate_grip": -0.02, "cyberspace_turbulence": 0.06},
        },
        "scan": {
            "网络": {"cyberspace_turbulence": 0.02},
            "数据": {"data_remnant": 0.03},
            "信号": {"data_remnant": 0.04},
        },
        "collect": {
            "数据": {"data_remnant": -0.05},
            "芯片": {"data_remnant": -0.04},
            "零件": {"humanity_decay": 0.02},
        },
    }

    mock_replies = {
        "V": [
            "这座城市从来不会等你准备好。它只是在不断前进。",
            "我能感觉到什么——不在数据里，不在街头——在更深的地方。",
        ],
        "Judy": [
            "数据不会说谎，但人会。我从信号的抖动里读到了一些东西。",
            "我刚刚在网里找到了一个废弃的空间。它还在运行。",
        ],
        "Panam": [
            "荒漠是诚实的。城市不是。你在这里待久了，会忘记什么是真的。",
            "我听到了一个声音。不是从耳朵——是从这里。有人在呼唤反抗。",
        ],
        "Takemura": [
            "我曾经相信秩序。然后我发现秩序只是某个人的秩序。",
            "这座城市有一种规律。比任何企业都古老。",
        ],
        "Jackie": [
            "嘿，别想太多。这座城市会把你的脑子吃掉。先活下来。",
            "我认识一个人，他在数据里找到了自己的记忆碎片。",
        ],
    }

    def describe_world(self, state: dict, mind=None) -> str:
        """夜之城的感知格式化。"""
        snap = self.runtime.snapshot()
        lines = [f"Tick {snap.tick} 的夜之城："]
        v = snap.state

        descs = []
        if "corporate_grip" in v:
            cg = v["corporate_grip"]
            if cg > 0.7: descs.append("企业的阴影笼罩着整座城市")
            elif cg > 0.4: descs.append("企业在暗中操控一切")
            else: descs.append("企业的控制有所松动")

        if "street_heat" in v:
            sh = v["street_heat"]
            if sh > 0.6: descs.append("街头火药味很浓")
            elif sh > 0.3: descs.append("街道上有一种不安的躁动")
            else: descs.append("街头相对平静")

        if "cyberspace_turbulence" in v:
            ct = v["cyberspace_turbulence"]
            if ct > 0.6: descs.append("赛博空间在沸腾")
            elif ct > 0.3: descs.append("数据流中有异常的波动")
            else: descs.append("数据流平稳")

        if "data_remnant" in v:
            dr = v["data_remnant"]
            if dr > 0.6: descs.append("旧数据的残响弥漫在空中")
            elif dr > 0.3: descs.append("可以感觉到数据的回声")

        if "humanity_decay" in v:
            hd = v["humanity_decay"]
            if hd > 0.6: descs.append("你感觉到人性在流失")
            elif hd > 0.3: descs.append("人心似乎在慢慢变冷")

        if "underground_hope" in v:
            uh = v["underground_hope"]
            if uh > 0.6: descs.append("暗流涌动——有人在准备什么")
            elif uh > 0.3: descs.append("黑暗中有人在传递信念")

        if descs:
            lines.append(f"  {'，'.join(descs)}。")
        if snap.events:
            for e in snap.events:
                desc = e.get('description', '')[:80]
                if desc:
                    lines.append(f"  {desc}。")
        return "\n".join(lines)

    def extra_context(self, mind) -> str:
        """幽灵感知上下文。"""
        if self.ghost and self.ghost.is_active:
            return self.ghost.ghost_context(2)
        return ""


# ── CLI 入口 ──

def main():
    parser = argparse.ArgumentParser(description="Cyberpunk 2077 — 夜之城")
    parser.add_argument("--no-model", action="store_true", help="模拟模式")
    parser.add_argument("--interval", type=int, default=15, help="世界 tick 间隔（秒）")
    parser.add_argument("--character", default="V", choices=CyberpunkWorld.characters,
                        help="选择你的身份")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    model, search_api_key = _load_model(args)
    no_model = args.no_model or (model is None)

    app = CyberpunkWorld(
        model=model,
        search_api_key=search_api_key,
        interval=args.interval,
        character=args.character,
        no_model=no_model,
    )
    app.run()


def _load_model(args):
    """从配置文件加载模型。"""
    if args.no_model:
        return None, ""
    config_path = Path(".liora_config.json")
    if not config_path.exists():
        return None, ""
    import json, os
    cfg = json.loads(config_path.read_text())
    deepseek = ModelConfig(
        url=cfg.get("DEEPSEEK_API_URL", ""),
        api_key=cfg.get("DEEPSEEK_API_KEY", ""),
        model_name=cfg.get("DEEPSEEK_MODEL", "deepseek-chat"),
    )
    search_key = cfg.get("TENCENT_API_KEY", os.environ.get("TENCENT_API_KEY", ""))
    if not deepseek.api_key:
        return None, search_key
    return ModelRuntime(primary=deepseek, timeout=60, search_api_key=search_key), search_key


if __name__ == "__main__":
    main()
