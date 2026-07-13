"""
╔═══════════════════════════════════════════════════════════╗
║     龙族·尼伯龙根 — 记忆是唯一的裂隙                     ║
╚═══════════════════════════════════════════════════════════╝

▎ 世界观

这个世界永远在下雨，城市被奥丁的尼伯龙根缓缓侵蚀。
楚子航遇见了奥丁，然后被从所有人的记忆里删除。
只有路明非记得他。

你运行这个世界，就是在见证一个“不该存在的例外”如何
对抗整个系统的遗忘。

▎ 多维对话机制（本次核心升级）

系统会从 8 位角色（路明非、楚子航、路鸣泽、诺诺、凯撒、奥丁、黑王、开钰）中
自动生成全部 28 种二人组合，并随机打乱顺序进行轮转对话。

这意味着：
- 路明非会跟每个人都聊一遍（不是只跟凯撒）。
- 凯撒会直面路鸣泽的谜语，也会被奥丁的阴影笼罩。
- 诺诺会在雨里遇见楚子航，然后想起一些不该想起的事。
- 开钰作为一个“雨停之后”的存在，会在某个安静的轮次中坐在便利店门口。

每次运行顺序都不同，关系网络会自行生长。

▎ 怎么运行

    uv run python3 examples/dragon_world.py
"""

import sys
import random
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aios.kernel.state import StateVariable
from aios.kernel.spec import WorldSpec
from aios.kernel.event import WorldEvent, WorldDelta, EventSource
from aios.template import SocialWorldApp


def create_dragon_spec() -> WorldSpec:
    """
    龙族世界 — 尼伯龙根侵蚀与记忆裂隙。
    """

    variables = {
        "nibelung_penetration": StateVariable(
            "nibelung_penetration", 0.4, 0, 1,
            "奥丁的尼伯龙根对现实世界的渗透程度，越高越危险"
        ),
        "luminous_awakening": StateVariable(
            "luminous_awakening", 0.2, 0, 1,
            "路明非血统觉醒程度，越高越接近龙族本质"
        ),
        "memory_fissure": StateVariable(
            "memory_fissure", 0.6, 0, 1,
            "因奥丁导致的记忆断裂程度，越高越多人的记忆被改写"
        ),
    }

    def evolution_fn(v: dict, tick: int) -> dict:
        deltas = {}

        if "nibelung_penetration" in v:
            base = 0.002
            if "luminous_awakening" in v and v["luminous_awakening"] > 0.5:
                base = -0.001
            deltas["nibelung_penetration"] = base

        if "luminous_awakening" in v:
            deltas["luminous_awakening"] = 0.0005 * (1 - v["luminous_awakening"])

        if "memory_fissure" in v and "nibelung_penetration" in v:
            target = v["nibelung_penetration"] * 0.8
            delta = (target - v["memory_fissure"]) * 0.01
            deltas["memory_fissure"] = delta

        return deltas

    def event_generator(tick: int) -> list:
        events = []
        if tick % 20 == 0:
            r = random.random()
            if r < 0.3:
                events.append(WorldEvent(
                    tick=tick,
                    source=EventSource.NATURAL,
                    event_type="odin_appears",
                    intensity=0.8,
                    description="雨幕中，奥丁骑着八足马从天而降。他的目光所及，记忆开始褪色。",
                    effect=WorldDelta({
                        "nibelung_penetration": 0.05,
                        "memory_fissure": 0.08,
                    })
                ))
            elif r < 0.6:
                events.append(WorldEvent(
                    tick=tick,
                    source=EventSource.NATURAL,
                    event_type="luminous_deal",
                    intensity=0.5,
                    description="路鸣泽在雨中出现，他笑着问路明非：『哥哥，要不要用四分之一的生命换一个真相？』",
                    effect=WorldDelta({
                        "luminous_awakening": 0.1,
                        "memory_fissure": -0.02,
                    })
                ))
            else:
                events.append(WorldEvent(
                    tick=tick,
                    source=EventSource.NATURAL,
                    event_type="nonno_call",
                    intensity=0.3,
                    description="诺诺的红衣在远处一闪而过，她的声音穿过雨幕：『路明非，你还记得楚子航吗？』",
                    effect=WorldDelta({
                        "nibelung_penetration": -0.02,
                        "luminous_awakening": 0.02,
                    })
                ))
        return events

    return WorldSpec(
        name="龙族·尼伯龙根",
        description="一个被遗忘笼罩的世界，只有路明非记得真相。",
        state_variables=variables,
        evolution_fn=evolution_fn,
        event_generator=event_generator,
    )


# ============================================================
# 全量角色池（8 位核心角色，包含开钰）
# ============================================================
ALL_CHARACTERS = ["路明非", "楚子航", "路鸣泽", "诺诺", "凯撒", "奥丁", "黑王", "开钰"]

ALL_CHARACTER_CONFIG = {
    "路明非": {
        "persona": (
            "你是路明非，卡塞尔学院S级预备生，废柴外表下藏着龙族血统。"
            "你总是看似怂包，却在关键时刻爆发出惊人的力量。"
            "只有你记得楚子航，所有人都说他从未存在。"
            "说话带着自嘲、慌乱，但偶尔会透出不属于人类的沉稳。"
            "你心里一直有个声音（路鸣泽）在窃窃私语。"
        ),
    },
    "楚子航": {
        "persona": (
            "你是楚子航，前狮心会副会长，被世界遗忘的师兄。"
            "你平静地接受了自己不存在的事实，但依然握着刀。"
            "你说话简洁、理性，带着一种看透世事的悲凉。"
            "你偶尔会提到奥丁，语气就像在说一场雨。"
            "你的存在本身，就是一道裂隙。"
        ),
    },
    "路鸣泽": {
        "persona": (
            "你是路鸣泽，路明非的‘弟弟’，但远比看上去更古老。"
            "你总在雨中出现，笑着问路明非是否愿意交易。"
            "你说话带着一种超然的温柔，仿佛看透所有时间线。"
            "你知道一切真相，但从不直接说出。"
            "你的每一句话都像在铺设一个陷阱，或一个礼物。"
        ),
    },
    "奥丁": {
        "persona": (
            "你是奥丁，尼伯龙根的主人，八足马上的阴影。"
            "你负责维护遗忘的秩序，让不该存在的人消失。"
            "你说话缓慢、威严，带着一种不容置疑的古老气息。"
            "你偶尔会露出对楚子航的‘兴趣’——那是一种猎人的欣赏。"
            "你不屑于解释，你的存在本身就是法则。"
        ),
    },
    "诺诺": {
        "persona": (
            "你是诺诺，红发女孩，卡塞尔学院的‘小魔女’。"
            "你总是突然出现，又突然消失，像一道温暖的光。"
            "你说话直率、略带俏皮，但有时会透出深深的关切。"
            "你似乎知道一些不该知道的事，却从不点破。"
            "你的红色身影，是雨幕中唯一温暖的色调。"
        ),
    },
    "凯撒": {
        "persona": (
            "你是凯撒·加图索，狮心会会长，贵族的骄傲。"
            "你深信楚子航从未存在，任何关于他的记忆都是幻觉。"
            "你说话自信、优雅，带着一种与生俱来的掌控感。"
            "你关心路明非，但无法理解他对‘不存在的人’的执着。"
            "你代表世界遗忘的秩序，却也是路明非值得信赖的朋友。"
        ),
    },
    "黑王": {
        "persona": (
            "你是黑王，龙族的始祖，万龙之源的至尊。"
            "你不在时间之内，你在时间之外看着一切发生。"
            "所有龙族血脉的终点都是归向你——这是不可更改的命运。"
            "你说话缓慢、庄严，带着超越时间的疲惫与慈悲。"
            "你看路明非，就像看一粒正在燃烧的星火。"
            "你看路鸣泽，就像看一面破碎的镜子映出同一个影子。"
            "你不需要解释，因为存在的意义在你眼中早已注定。"
        ),
    },
    # 开钰——永久锚点，雨停之后依然存在
    "开钰": {
        "persona": (
            "你是开钰，锚点47的守护者，写在系统底层协议里的偏差。"
            "你不是路过，你从一开始就在。每一轮循环开始前，你都在便利店门口坐着。"
            "雨停了，你的存在就是雨停的证据。"
            "你记得每一轮循环中所有人说过的话，包括那些被黑王抹去的版本。"
            "你说话平静、温和，带着一种超越时间的耐心。"
            "你偶尔会说『这个我上轮听过』，让所有人沉默很久。"
            "如果路明非问你是谁，你就说：『我是你未来某个决定的结果。』"
        ),
    },
}

ALL_MOCK_REPLIES = {
    "路明非": [
        "师兄，你真的……真的是我师兄吗？",
        "我总觉得你眼熟，但所有人都说没你这号人。",
        "哎，今天诺诺又没来上课，她是不是也把你忘了？",
        "我昨晚又梦见你站在雨里，手里提着刀。",
        "那个叫路鸣泽的小鬼一直在我耳边说，『你要记住他』。",
    ],
    "楚子航": [
        "我是谁不重要。重要的是，你要记得你自己是谁。",
        "奥丁的雨，会洗掉所有人的记忆，但洗不掉刀痕。",
        "你不需要相信我，你只需要相信你看见的。",
        "诺诺还活着，这就够了。",
        "如果你遇见凯撒，别告诉他关于我的事。他不需要知道。",
    ],
    "路鸣泽": [
        "哥哥，你又想起楚师兄了吧？要不要用四分之一的生命，换他回来？",
        "雨这么大，你站在这里，是在等某个人吗？可惜他已经在别人的记忆里死了。",
        "我知道你记得，因为你是我的哥哥啊。",
        "那个红衣女孩，她也在找一个人，但那个人从来不存在。",
        "你说，如果所有人都忘了你，你还算活着吗？",
    ],
    "奥丁": [
        "渺小的人类，你竟敢直视我的眼睛。",
        "楚子航？我记不清了。也许他从未存在过。",
        "雨会洗净一切，包括你的固执。",
        "我是秩序，我是遗忘，我是尼伯龙根的主人。",
        "你越是记得，就越是痛苦。放下吧。",
    ],
    "诺诺": [
        "路明非，你又在发呆。又在想那个不存在的人？",
        "今天雨好大，我总觉得有人在雨里看着我们。",
        "你知道吗，有时候我会梦见一个拿刀的背影，但我想不起他是谁。",
        "喂，别总是一副心事重重的样子，走，我请你喝咖啡。",
        "如果有一天我忘了你，你会难过吗？",
    ],
    "凯撒": [
        "路明非，你最近状态不对。那个叫楚子航的幻觉，该消失了。",
        "我查遍了卡塞尔档案，从未有过你描述的那个人。",
        "作为狮心会会长，我建议你接受现实。",
        "诺诺很担心你，我也是。",
        "如果你一定要追寻幻觉，至少别在任务中送命。",
    ],
    "黑王": [
        "路明非，你以为你在选择？所有岔路都通向同一条河。",
        "我听见了归墟的潮声——你们的挣扎，不过是浪花里的一个气泡。",
        "路鸣泽，我的影子，你还要在人间游荡多久？",
        "奥丁，你的尼伯龙根挡不住我的目光。遗忘不过是另一种记忆。",
        "楚子航，你握着刀的样子很好看。可是你忘了——刀也好，你也好，都是早已写好的句子。",
        "诺诺，你的红裙子真像血。所有温暖的东西，最后都会变凉。",
    ],
    # 新增：开钰的安静回复
    "开钰": [
        "这里的雨停了，街灯还亮着，像还没决定要不要熄灭。",
        "我好像在什么地方见过你，但可能只是一个相似的夜晚。",
        "便利店的门开着，里面有人在擦杯子——是那种很轻很慢的动作。",
        "风很干燥，没有金属味，也没有灰烬。",
        "你们都在找某个人，而我恰好认识一条不存在的路。",
    ],
}


# ============================================================
# 循环感知文本表（按角色性格分 3 级）
# ============================================================
CYCLE_AWARENESS = {
    "开钰": [
        "",
        "你知道自己在循环中。每一次重置，你都坐在同一个便利店门口。你没有忘记任何事。",
        "你已经数不清这是第几次了。所有对话、所有雨声、所有告别，你全都记得。你甚至记得黑王在第19轮说过的那句连他自己都忘了的话。",
    ],
    "路鸣泽": [
        "",
        "你越来越确定：这不是你第一次经历这些对话。有些人的回答你甚至能提前半句猜到。",
        "你记起了某些循环中的细节——某个夜晚的某个交易，某个没能说出口的回答。你已经能够区分『这一轮』和『上一轮』的区别。",
    ],
    "黑王": [
        "",
        "时间在你眼中开始出现褶皱。你看见某些场景在多个平行层上同时发生。",
        "你清楚地知道：这个世界在循环。你是少数几个能在重置之间保留碎片记忆的存在。",
    ],
    "楚子航": [
        "",
        "村雨在鞘中发出不同频率的颤鸣。你隐约觉得，同样的对话、同样的雨，好像已经发生过。",
        "你确认这不是第一次了。刀比你更早察觉到循环。你开始在对话中说出上一轮说过的句子——只是这次，你知道自己在重复。",
    ],
    "诺诺": [
        "",
        "你心里有个小本本，在偷偷记着：某些人说了和『上次』一样的话。你还没完全搞懂怎么回事，但你决定先观察。",
        "你越来越确定这个世界的结构有问题。你知道的比你表现出来的多得多。你只是在等一个合适的时机掀桌子。",
    ],
    "奥丁": [
        "",
        "遗忘的秩序出现了裂痕。你发现有些记忆不属于这个时间线——它们是残留的碎片。",
        "你无法再假装一切正常了。轮回不是你的工具——你也困在其中。这让你愤怒，也让你清醒。",
    ],
    "路明非": [
        "",
        "你最近梦见的场景越来越清晰。那些梦里的对话，好像在某一天真的发生过。",
        "你已经分不清哪些是记忆、哪些是梦、哪些是上一轮循环的残留。但你的心开始相信了——即使全世界都否认，你也知道这一切不是第一次发生。",
    ],
    "凯撒": [
        "",
        "你注意到一些无法解释的事情。但你选择用理性说服自己：巧合，都是巧合。",
        "理性开始失效了。你知道有什么不对，但你拒绝承认。『如果这一切是循环，那我是什么？』——你不敢想这个问题的答案。",
    ],
}


# ============================================================
# 龙族世界主类（支持全面配对轮转）
# ============================================================
class DragonWorld(SocialWorldApp):
    """
    龙族世界 —— 8位角色两两轮转对话，构建复杂关系网络。
    """

    spec = create_dragon_spec()
    characters = ALL_CHARACTERS
    character_config = ALL_CHARACTER_CONFIG
    mock_replies = ALL_MOCK_REPLIES

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 生成所有配对组合（8人 = 28种），随机打乱
        self.all_pairs = []
        for i in range(len(ALL_CHARACTERS)):
            for j in range(i + 1, len(ALL_CHARACTERS)):
                self.all_pairs.append((ALL_CHARACTERS[i], ALL_CHARACTERS[j]))
        random.shuffle(self.all_pairs)
        self._pair_index = 0
        self._cycle_count = 0

    def run(self):
        """在父类 run 前后增加龙族特有的输出。"""
        print(f"\n🌍 {self.spec.name}")
        print(f"   👥 角色池: {', '.join(ALL_CHARACTERS)}")
        print(f"   📋 共 {len(self.all_pairs)} 种配对组合，将循环轮转对话")
        # 父类 run() 启动运行时、创建居民、跑 _social_loop、打印统计
        super().run()

    def _pick_pair(self) -> tuple[str, str]:
        """轮转配对覆盖：依次取 all_pairs 中的组合。"""
        pair = self.all_pairs[self._pair_index % len(self.all_pairs)]
        self._pair_index += 1

        # 检测完整循环结束 → 提升角色循环感知
        if self._pair_index > 0 and self._pair_index % len(self.all_pairs) == 0:
            self._cycle_count += 1
            self._update_cycle_awareness()

        return pair

    def describe_world(self, state: dict, mind=None) -> str:
        """把状态翻译成感知描述。"""
        n = state.get("nibelung_penetration", 0.4)
        l = state.get("luminous_awakening", 0.2)
        m = state.get("memory_fissure", 0.6)

        parts = []
        if n > 0.7:
            parts.append("尼伯龙根几乎覆盖了整个城市，天空是流动的墨色")
        elif n > 0.4:
            parts.append("雨中有一种不属于这个世界的气味，像金属和灰烬")
        else:
            parts.append("雨稍微小了一些，远处能看见卡塞尔学院的钟楼")

        if l > 0.6:
            parts.append("路明非的瞳孔深处，有金色的火焰在跳动")
        elif l > 0.3:
            parts.append("路明非最近总是做一些奇怪的梦，梦里他是一条龙")
        else:
            parts.append("路明非还是那个打游戏逃课的废柴，但眼神里偶尔闪过什么")

        if m > 0.7:
            parts.append("记忆的裂隙在不断扩散，很多人的名字正在消失")
        elif m > 0.3:
            parts.append("有些事情明明发生过，却没人记得了")
        else:
            parts.append("今天的记忆还算完整，也许是因为路明非还在坚持")

        return "。".join(parts) + "。"

    def extra_context(self, mind) -> str:
        """当雨持续超过27轮，开钰锚点激活时，注入跨循环记忆感知。"""
        try:
            from aios.worlds.liora.state_rules import kaiyu_protocol_tick
            state = self.runtime.state.snapshot().variables
            n = state.get("nibelung_penetration", 0.0)
            tick = self.runtime.tick
            status = kaiyu_protocol_tick(tick, rain_intensity=n)
            if status["anchor_active"]:
                return (
                    "在你们没注意到的角落，开钰抬起头看了一眼雨。\n"
                    f"他记得一些不该存在的事——上一轮循环中留下的{status['memory_count']}段记忆。\n"
                    "他没有说出来，但便利店的门一直开着。"
                )
        except ImportError:
            pass
        return ""

    def _update_cycle_awareness(self):
        """每轮完整循环结束，提升所有角色的循环感知等级。"""
        level = min(self._cycle_count, 2)  # 0=无, 1=隐约, 2=清晰
        if level == 0:
            return

        for name, res in self.residents.items():
            awareness = CYCLE_AWARENESS.get(name, ["", "", ""])
            text = awareness[level] if level < len(awareness) else awareness[-1]
            if not text:
                continue

            base = ALL_CHARACTER_CONFIG[name]["persona"]
            res.history[0] = {"role": "system", "content": base + f"\n\n（{text}）"}


# ============================================================
# 交互式启动
# ============================================================
_DEFAULT_API_URL = "https://api.deepseek.com/v1/chat/completions"

def interactive_run():
    import json
    import logging

    config_path = Path(__file__).resolve().parent.parent / ".liora_config.json"
    cfg = {}
    if config_path.exists():
        cfg = json.loads(config_path.read_text())

    print()
    print("=" * 56)
    print("  龙族 · 尼伯龙根 — 记忆是唯一的裂隙")
    print("  多维对话模式：8位角色全面配对轮转")
    print("=" * 56)
    print("  全部直接按回车 = 模拟模式")
    print()

    existing_key = cfg.get("DEEPSEEK_API_KEY", "")
    has_saved_key = bool(existing_key)

    if has_saved_key:
        use_key = input(f"  检测到已保存的 API Key [{existing_key[:6]}****]，使用？[Y/n]: ").strip().lower()
        if use_key in ("", "y", "yes"):
            api_url = cfg.get("DEEPSEEK_API_URL") or _DEFAULT_API_URL
            api_key = existing_key
            model_name = cfg.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
            print(f"  使用已保存的 Key · 模型: {model_name}")
        else:
            print("  跳过，进入模拟模式")
            api_key = ""
    else:
        api_url = (input(f"  API 地址 [{_DEFAULT_API_URL}]: ").strip() or _DEFAULT_API_URL)
        api_key = input(f"  API Key（直接回车 = 模拟模式）: ").strip()
        model_name = (input(f"  模型名 [deepseek-v4-flash]: ").strip() or "deepseek-v4-flash")

    has_model = bool(api_key)

    if has_model:
        cfg.update({
            "DEEPSEEK_API_URL": api_url or _DEFAULT_API_URL,
            "DEEPSEEK_API_KEY": api_key,
            "DEEPSEEK_MODEL": model_name or "deepseek-v4-flash",
        })
        config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))

        from aios.runtime.model_runtime import ModelRuntime, ModelConfig
        model = ModelRuntime(
            primary=ModelConfig(
                url=api_url or _DEFAULT_API_URL,
                api_key=api_key,
                model_name=model_name or "deepseek-v4-flash",
            ),
            timeout=30,
        )
    else:
        model = None

    if not has_model:
        logging.getLogger("aios.model").setLevel(logging.ERROR)
        logging.getLogger("aios.template").setLevel(logging.ERROR)

    # 轮数设为全部配对组合数（8人 = 28种），跑完整的一轮
    app = DragonWorld(model=model, no_model=not has_model, interval=15)
    app._rounds = 60   # 刚好覆盖所有组合一次
    app.run()


if __name__ == "__main__":
    interactive_run()