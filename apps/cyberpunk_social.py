"""Cyberpunk Social — 夜之城五角色自由对话。

基于 SocialWorldApp 模板，只需定义角色和世界差异。
从 666 行精简到 ~50 行。

运行：
  uv run python3 apps/cyberpunk_social.py --no-model
  uv run python3 apps/cyberpunk_social.py -n 30
  uv run python3 apps/cyberpunk_social.py --interval 5
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.template import SocialWorldApp
from aios.runtime.model_runtime import ModelRuntime, ModelConfig
from aios.worlds.cyberpunk import (
    create_cyberpunk_spec,
    create_cyberpunk_objects,
    UnknownAccumulator,
    DigitalGhost,
)
from aios.worlds.cyberpunk.mind import _DEFAULT_BELIEFS, _DEFAULT_SECRETS


class CyberpunkSocialWorld(SocialWorldApp):
    """夜之城社交世界——角色们自主对话。"""

    spec = create_cyberpunk_spec()
    world_objects = create_cyberpunk_objects()

    characters = ["V", "Judy", "Panam", "Takemura", "Jackie"]

    character_config = {
        name: {
            "beliefs": dict(beliefs),
            "secrets": list(secrets),
            "persona": _PERSONAS.get(name, f"你是 {name}。直接说话。"),
        }
        for name, beliefs in _DEFAULT_BELIEFS.items()
        for name2, secrets in _DEFAULT_SECRETS.items()
        if name == name2
    }

    unknown_class = UnknownAccumulator
    ghost_class = DigitalGhost

    mock_replies = {
        "V": ["这座城市又在变了。我能感觉到——不是从数据里，是从脚下的路面。"],
        "Judy": ["我刚在数据流里看到了一段不该存在的东西。像是某人的记忆碎片。"],
        "Panam": ["荒漠是诚实的，城市不是。但你猜怎么着？诚实的人能找到诚实的人。"],
        "Takemura": ["我曾经相信秩序。现在我什么都不相信——除了食物还是热的。"],
        "Jackie": ["嘿，别板着脸。这座城市够阴暗了——你得自己找点光。"],
    }

    def describe_world(self, state: dict, mind=None) -> str:
        snap = self.runtime.snapshot()
        v = snap.state
        lines = []
        if "corporate_grip" in v:
            cg = v["corporate_grip"]
            if cg > 0.7: lines.append("天空被企业的阴影笼罩")
            elif cg > 0.4: lines.append("企业在暗中操控一切")
        if "street_heat" in v:
            sh = v["street_heat"]
            if sh > 0.6: lines.append("街头火药味很浓")
            elif sh > 0.3: lines.append("空气中有不安的躁动")
        if "cyberspace_turbulence" in v:
            ct = v["cyberspace_turbulence"]
            if ct > 0.6: lines.append("赛博空间在沸腾")
        if "underground_hope" in v:
            uh = v["underground_hope"]
            if uh > 0.6: lines.append("暗流涌动——有人在准备什么")
        if "data_remnant" in v:
            dr = v["data_remnant"]
            if dr > 0.6: lines.append("旧数据的残响在空气中弥漫")
        if "humanity_decay" in v:
            hd = v["humanity_decay"]
            if hd > 0.6: lines.append("你感觉到人心在冷去")
        return "\n".join(lines) if lines else "夜之城如常运转。"

    def extra_context(self, mind) -> str:
        if self.ghost and self.ghost.is_active:
            return self.ghost.ghost_context(2)
        return ""


_PERSONAS = {
    "V": "你是 V。夜之城的雇佣兵，什么都见过，什么都干过。你直接、务实，在关键时刻会豁出去。直接说话，不要加引号或标注动作。",
    "Judy": "你是 Judy。天赋异禀的 braindance 编辑师，能从数据的纹理中读到人的温度。你有温度、观察入微。直接说话。",
    "Panam": "你是 Panam。阿德卡多氏族的自由斗士。你热烈、直接，相信自由是夺回来的。直接说话。",
    "Takemura": "你是 Takemura。前荒坂安保精英。克制、准确，正在重新审视曾经相信的一切。直接说话。",
    "Jackie": "你是 Jackie。夜之城最可靠的伙伴。温暖、接地气，能在黑暗里找到幽默。直接说话。",
}


def main():
    parser = argparse.ArgumentParser(description="夜之城自由对话模拟")
    parser.add_argument("-n", "--rounds", type=int, default=10, help="对话轮数")
    parser.add_argument("--no-model", action="store_true", help="模拟模式")
    parser.add_argument("--interval", type=int, default=15, help="世界 tick 间隔（秒）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    model = None
    if not args.no_model:
        config_path = Path(".liora_config.json")
        if config_path.exists():
            import json
            cfg = json.loads(config_path.read_text())
            deepseek = ModelConfig(
                url=cfg.get("DEEPSEEK_API_URL", ""),
                api_key=cfg.get("DEEPSEEK_API_KEY", ""),
                model_name=cfg.get("DEEPSEEK_MODEL", "deepseek-chat"),
            )
            if deepseek.api_key:
                model = ModelRuntime(primary=deepseek, timeout=30)

    app = CyberpunkSocialWorld(
        model=model,
        interval=args.interval,
        no_model=args.no_model or (model is None),
    )
    app._rounds = args.rounds
    app.run()


if __name__ == "__main__":
    main()
