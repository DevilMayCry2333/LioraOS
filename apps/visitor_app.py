"""Visitor App — 走进世界，和角色面对面聊天。

你不再是观察者。你是旅人（Traveler）。
选一个世界、选一个角色，推开门走进去。

用法：
    uv run python3 apps/visitor_app.py
    uv run python3 apps/visitor_app.py --world echo_valley --character Aria
    uv run python3 apps/visitor_app.py --world echo_valley --character 路鸣泽
    uv run python3 apps/visitor_app.py --world night_city --character 强尼·银手 --no-model
    uv run python3 apps/visitor_app.py --list
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.runtime.model_runtime import ModelRuntime, ModelConfig
from aios.template.base import WorldApp
from aios.template.social import SocialResident
from aios.template.persona import PersonalityEngine

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("visitor")

VISITOR_NAME = "旅人"

# ── 世界注册表 ────────────────────────────────────────────

WORLDS: dict[str, dict] = {}


def _register_worlds():
    """延迟加载世界定义，避免启动时全部导入。"""
    if WORLDS:
        return

    # 回声谷
    try:
        from aios.worlds.liora.spec import create_liora_spec
        from aios.worlds.liora.unknown import UnknownAccumulator
        from apps.liora_app import LioraWorld

        WORLDS["echo_valley"] = {
            "name": "回声谷",
            "spec_fn": create_liora_spec,
            "app_class": LioraWorld,
            "characters": list(LioraWorld.character_config.keys()),
            "description": "五个自然人格在一片迷雾山谷中寻找自己的回声。"
                           "Liora（诗）/ Aria（声音）/ Kael（科学）/ Nix（神秘）/ Sage（情感）",
        }
    except Exception as e:
        logger.debug("echo_valley 加载失败: %s", e)

    # 夜之城（单角色模式）
    try:
        from aios.worlds.cyberpunk.spec import create_cyberpunk_spec
        from apps.cyberpunk_app import CyberpunkWorld

        cyber_chars = list(CyberpunkWorld.character_config.keys())
        WORLDS["night_city"] = {
            "name": "夜之城",
            "spec_fn": create_cyberpunk_spec,
            "app_class": CyberpunkWorld,
            "characters": cyber_chars,
            "description": "赛博朋克2077的世界。企业控制、街头生存、数字幽灵。"
                           f"角色：{' / '.join(cyber_chars)}",
        }
    except Exception as e:
        logger.debug("night_city 加载失败: %s", e)

    # 龙族·尼伯龙根
    try:
        from examples.dragonWorld import DragonWorld, create_dragon_spec
        from aios.worlds.liora.unknown import UnknownAccumulator

        dragon_chars = list(DragonWorld.character_config.keys())
        WORLDS["nibelungen"] = {
            "name": "尼伯龙根",
            "spec_fn": create_dragon_spec,
            "app_class": DragonWorld,
            "characters": dragon_chars,
            "description": "龙族·尼伯龙根。8 角色配对轮转社交 + 循环感知 + 锚点47。"
                           f"角色：{' / '.join(dragon_chars)}",
        }
    except Exception as e:
        logger.debug("nibelungen 加载失败: %s", e)


# ── VisitorApp ────────────────────────────────────────────


class VisitorApp(WorldApp):
    """旅人应用——人类走进世界和角色对话的入口。

    不是社交循环（角色之间对话），是单对单：
    旅人（你）→ 角色 → 旅人 → 角色 → ...
    """

    def __init__(self, world_key: str, character_name: str,
                 no_model: bool = False, interval: float = 15.0,
                 gateway_port: int = 0):
        _register_worlds()

        if world_key not in WORLDS:
            available = ", ".join(WORLDS.keys())
            print(f"未知世界: {world_key}。可选: {available}")
            sys.exit(1)

        world_def = WORLDS[world_key]
        self.world_key = world_key
        self.character_name = character_name
        self.world_def = world_def
        app_class = world_def["app_class"]

        # 必须先设置 spec，WorldApp.__init__ 断言 spec 存在
        self.spec = app_class.spec
        self.character_config = getattr(app_class, 'character_config', {})
        self.persona_presets = getattr(app_class, 'persona_presets', {})

        # 初始化模型（从环境变量读取配置）
        model = None
        if not no_model:
            try:
                deepseek = ModelConfig.from_env("DEEPSEEK")
                glm4 = ModelConfig.from_env("GLM4")
                # 设默认模型名（DeepSeek / GLM4 都需要）
                if deepseek.url and not deepseek.model_name:
                    deepseek.model_name = "deepseek-chat"
                if glm4.url and not glm4.model_name:
                    glm4.model_name = "glm4"
                if deepseek.url:
                    model = ModelRuntime(primary=deepseek, timeout=120)
                elif glm4.url:
                    model = ModelRuntime(primary=glm4, timeout=60)
                else:
                    print("  ⚠️  未找到模型配置（需要 DEEPSEEK_API_URL 环境变量）")
                    print("  ℹ️  使用 --no-model 进入模拟模式，或设置环境变量后重试")
                    no_model = True
            except Exception as e:
                print(f"  ⚠️  模型初始化失败: {e}，切换到模拟模式")
                no_model = True

        # 调用 WorldApp.__init__
        super().__init__(
            model=model,
            no_model=no_model,
            interval=interval,
            character=character_name,
        )

        self._gateway_port = gateway_port

        # 验证角色
        world_chars = world_def["characters"]
        if character_name not in world_chars:
            print(f"未知角色: {character_name}。{world_key} 可选: {', '.join(world_chars)}")
            sys.exit(1)

    def run(self):
        """进入世界，开始对话。"""
        # 启动世界运行时
        self.runtime.start()

        # 可选：启动 WebSocket 网关
        if self._gateway_port:
            try:
                from aios.runtime.gateway import LEPGateway
                self._gateway = LEPGateway(self.runtime, port=self._gateway_port)
                self._gateway.register_character_app(self, self.character_name)
                self._gateway.start()
                print(f"  🌐 WebSocket 网关启动于 ws://127.0.0.1:{self._gateway_port}")
                print(f"     角色 '{self.character_name}' 已注册，外部客户端可通过 converse 动作对话")
            except Exception as e:
                print(f"  ⚠️  Gateway 启动失败: {e}")

        print(f"\n{'═' * 64}")
        print(f"  🌍 {self.world_def['name']}")
        print(f"  🎭 角色: {self.character_name}")
        print(f"  {'═' * 64}")
        print(f"\n  你推开门，走进了这个世界。")
        print(f"  {self.world_def['description']}\n")

        # 创建角色
        resident = SocialResident(self.character_name, self)
        if self.character_name in self.persona_presets:
            try:
                resident.persona = PersonalityEngine.from_preset(
                    self.persona_presets[self.character_name]
                )
            except Exception:
                pass

        # 添加旅人感知
        world_snap = self.runtime.snapshot()
        world_desc = self.describe_world(world_snap.state)
        extra = self.extra_context(resident.mind)
        if extra:
            world_desc += f"\n\n{extra}"
        resident.hear_world(f"（{world_desc}）")

        print(f"\n  {self.character_name} 就在你面前。")
        print(f"  输入你想说的话，或输入 /quit 离开。")
        print(f"  输入 /state 查看世界状态。\n")

        chat_count = 0
        try:
            while True:
                try:
                    user_input = input(f"  🧑 你 > ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not user_input:
                    continue
                if user_input.lower() in ("/quit", "/exit", "/q"):
                    break
                if user_input.lower() == "/state":
                    snap = self.runtime.snapshot()
                    print(f"\n  🌍 Tick {snap.tick}")
                    for k, v in sorted(snap.state.items()):
                        print(f"     {k}: {v:.3f}")
                    continue
                if user_input.lower() == "/help":
                    print("  /quit  — 离开世界")
                    print("  /state — 查看世界状态")
                    print("  /help  — 显示此帮助")
                    continue

                # 注入世界 tick
                self.runtime.tick_once()
                chat_count += 1

                # 旅人说话 → 角色听到
                resident.hear_speaker(VISITOR_NAME, user_input, tick=chat_count)

                # 角色回应
                print(f"  🧠 {self.character_name} 思考中...", end="", flush=True)
                reply = resident.speak(partner_name=VISITOR_NAME)
                if reply:
                    print(f"\r  🎭 {self.character_name}: {reply}")
                else:
                    print(f"\r  🎭 {self.character_name} 沉默了。")

                # 吸收对话
                from aios.template.social import assimilate_conversation, assimilate_to_anchor
                assimilate_conversation(
                    resident.mind, VISITOR_NAME,
                    reply or "", user_input, chat_count,
                )
                # 高重要性记忆自动入锚
                assimilate_to_anchor(
                    resident.mind, VISITOR_NAME,
                    reply or "", user_input, chat_count,
                )

                # 自主演化
                resident.mind.tick_autonomous(1)
                if resident.persona:
                    resident.persona.tick()

                # 世界状态变化感知（每隔几轮）
                if chat_count % 3 == 0:
                    self.runtime.tick_once()
                    new_snap = self.runtime.snapshot()
                    state_text = self.describe_world(new_snap.state)
                    if state_text:
                        resident.hear_world(f"\n（{state_text}）")

                time.sleep(0.5)

        finally:
            # 离开记录
            print(f"\n  {'═' * 64}")
            print(f"  旅人离开了 {self.world_def['name']}。")
            print(f"  和 {self.character_name} 聊了 {chat_count} 轮。\n")
            self.runtime.stop()


# ── 入口 ──────────────────────────────────────────────────


def list_worlds():
    """列出所有可访问的世界和角色。"""
    _register_worlds()
    print(f"\n{'═' * 64}")
    print(f"  🌐 可访问的世界\n")
    for key, w in sorted(WORLDS.items()):
        print(f"  ▸ {key:20s} — {w['name']}")
        print(f"    {w['description']}")
        chars = ", ".join(w["characters"])
        print(f"    角色: {chars}\n")
    print(f"  用法: uv run python3 apps/visitor_app.py --world <世界> --character <角色>")
    print(f"{'═' * 64}\n")


def main():
    parser = argparse.ArgumentParser(description="Visitor App — 走进世界和角色对话")
    parser.add_argument("--world", default="echo_valley", help="世界 key（echo_valley / night_city / nibelungen）")
    parser.add_argument("--character", default="", help="角色名")
    parser.add_argument("--no-model", action="store_true", help="模拟模式（无需 LLM）")
    parser.add_argument("--list", action="store_true", help="列出可用世界和角色")
    parser.add_argument("--interval", type=float, default=15.0, help="tick 间隔（秒）")
    parser.add_argument("--gateway", type=int, default=0, metavar="PORT",
                        help="同时启动 WebSocket 网关（端口号，例如 9100）")
    args = parser.parse_args()

    if args.list:
        list_worlds()
        return

    # 自动选角色
    character_name = args.character
    if not character_name:
        if args.world == "echo_valley":
            character_name = "Aria"
        elif args.world == "night_city":
            character_name = "V"
        elif args.world == "nibelungen":
            character_name = "路鸣泽"
        else:
            print("请指定 --character")
            return

    app = VisitorApp(
        world_key=args.world,
        character_name=character_name,
        no_model=args.no_model,
        interval=args.interval,
        gateway_port=args.gateway,
    )
    app.run()


if __name__ == "__main__":
    main()
