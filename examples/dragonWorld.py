"""
╔═══════════════════════════════════════════════════════════╗
║     龙族·尼伯龙根 — 记忆是唯一的裂隙                     ║
║     角色内部状态 + 目标涌现 + 跨会话记忆                  ║
╚═══════════════════════════════════════════════════════════╝

▎ 世界观

这个世界永远在下雨，城市被奥丁的尼伯龙根缓缓侵蚀。
楚子航遇见了奥丁，然后被从所有人的记忆里删除。
只有路明非记得他。

你运行这个世界，就是在见证一个"不该存在的例外"如何
对抗整个系统的遗忘。

▎ 架构升级（参考 convenience_store.py）

  角色内部状态（好奇心·归属感·记忆冲突·不安感·终局感）
    → 每个角色有自己的连续心理状态，每轮自然演化

  目标涌现系统
    → 状态阈值触发自发目标 → 注入对话 → 角色行为有方向

  加权世界事件
    → 雨、奥丁的目光、路鸣泽的低语……权重不同，世界有呼吸

  跨会话记忆
    → 从 anchor_memory.jsonl 加载上一轮的记忆碎片

  会话随机化
    → 每轮运行的雨声角度、尼伯龙根初始值都不同

▎ 运行

    uv run python3 examples/dragonWorld.py                # 交互模式
    uv run python3 examples/dragonWorld.py --no-model     # 模拟模式
    uv run python3 examples/dragonWorld.py --rounds 30    # 指定轮数
    uv run python3 examples/dragonWorld.py --no-model --rounds 20
"""

import json
import logging
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aios.kernel.state import StateVariable
from aios.kernel.spec import WorldSpec
from aios.kernel.event import WorldEvent, WorldDelta, EventSource
from aios.template import SocialWorldApp


# ════════════════════════════════════════════════════════════
# 加权世界事件表（来自 convenience_store）
# ════════════════════════════════════════════════════════════

DRAGON_WORLD_EVENTS = [
    {"weight": 7, "type": "rain_intensifies",
     "desc": "雨忽然大了。雨点砸在窗户上，像有人在敲摩斯密码。",
     "effect": {"nibelung_penetration": 0.03}},
    {"weight": 5, "type": "odin_gaze",
     "desc": "一道极亮的闪电划过，撕裂的瞬间似乎有人在云层后面看着你们。",
     "effect": {"nibelung_penetration": 0.04, "memory_fissure": 0.02}},
    {"weight": 4, "type": "luminous_whisper",
     "desc": "空气中传来极轻的声音，像有人贴着你的耳朵说了一句话，但你听不清内容。",
     "effect": {"luminous_awakening": 0.03}},
    {"weight": 4, "type": "memory_ripple",
     "desc": "所有人同时安静了一秒——他们都不记得自己刚才在想什么。",
     "effect": {"memory_fissure": 0.04}},
    {"weight": 3, "type": "nonno_appearance",
     "desc": "远处一抹红色闪过——诺诺的裙摆消失在转角。但她刚才明明和大家在一起。",
     "effect": {"memory_fissure": -0.02, "luminous_awakening": 0.02}},
    {"weight": 3, "type": "nibelung_crack",
     "desc": "地面裂开一条缝，里面透出的不是岩浆，而是深不见底的蓝色光线。",
     "effect": {"nibelung_penetration": 0.05}},
    {"weight": 2, "type": "black_king_echo",
     "desc": "一个低沉的声音像从地底传来：『归墟的潮声近了。』",
     "effect": {"nibelung_penetration": -0.01, "luminous_awakening": 0.05}},
    {"weight": 2, "type": "kaiyu_door",
     "desc": "空气中出现了一扇便利店的门。它开着，里面透出暖黄色的光。",
     "effect": {"memory_fissure": -0.03}},
    {"weight": 1, "type": "silence_tear",
     "desc": "所有的声音突然消失了——雨、风、心跳。三秒后一切恢复，但你知道那三秒里有什么东西经过了。",
     "effect": {"nibelung_penetration": 0.02, "memory_fissure": 0.04}},
    {"weight": 1, "type": "luminous_deal",
     "desc": "路鸣泽的声音在所有人耳边同时响起：『要不要用四分之一的生命换一个真相？』",
     "effect": {"luminous_awakening": 0.08}},
]


def weighted_choice(events: list[dict]) -> dict:
    total = sum(e["weight"] for e in events)
    r = random.uniform(0, total)
    cumulative = 0
    for e in events:
        cumulative += e["weight"]
        if r <= cumulative:
            return e
    return events[-1]


# ════════════════════════════════════════════════════════════
# 世界规范
# ════════════════════════════════════════════════════════════

def create_dragon_spec(seed: int = 0) -> WorldSpec:
    """
    龙族世界 — 尼伯龙根侵蚀与记忆裂隙。
    seed 用于每次运行的初始值微调。
    """
    rng = random.Random(seed)

    variables = {
        "nibelung_penetration": StateVariable(
            "nibelung_penetration",
            round(0.3 + rng.uniform(-0.1, 0.15), 2), 0, 1,
            "奥丁的尼伯龙根对现实世界的渗透程度，越高越危险"
        ),
        "luminous_awakening": StateVariable(
            "luminous_awakening",
            round(0.2 + rng.uniform(-0.05, 0.1), 2), 0, 1,
            "路明非血统觉醒程度，越高越接近龙族本质"
        ),
        "memory_fissure": StateVariable(
            "memory_fissure",
            round(0.5 + rng.uniform(-0.1, 0.1), 2), 0, 1,
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
        # 加权事件：每 5-9 tick 随机触发
        if tick > 0 and tick % random.randint(5, 9) == 0:
            chosen = weighted_choice(DRAGON_WORLD_EVENTS)
            effect = chosen.get("effect", {})
            events.append(WorldEvent(
                tick=tick,
                source=EventSource.NATURAL,
                event_type=chosen["type"],
                intensity=random.uniform(0.3, 0.8),
                description=chosen["desc"],
                effect=WorldDelta(effect)
            ))
        # 裂隙事件：每 13 tick 触发一次不可解释的扰动
        if tick > 10 and tick % 13 == 0:
            unknown_events = [
                "所有人的影子在同一瞬间指向了同一个方向——东方。",
                "空气里出现了一行金色的文字，三秒后自行燃烧殆尽。",
                "雨水在半空中停住了。不是凝固——是时间本身在这里打了一个结。",
                "有人轻轻喊了一声你的名字。你回头，没有人。但那声音听着像你自己。",
                "地面浮现出一张巨大的地图，上面的城市不是你所在的任何一座。",
            ]
            events.append(WorldEvent(
                tick=tick, source=EventSource.UNKNOWN,
                event_type="fissure_pulse", intensity=0.4,
                description=random.choice(unknown_events),
                effect=WorldDelta({
                    "nibelung_penetration": 0.02,
                    "memory_fissure": 0.03,
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


# ════════════════════════════════════════════════════════════
# 全量角色池（8 位核心角色，包含开钰）
# ════════════════════════════════════════════════════════════

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
            "你是路鸣泽，路明非的'弟弟'，但远比看上去更古老。"
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
            "你偶尔会露出对楚子航的'兴趣'——那是一种猎人的欣赏。"
            "你不屑于解释，你的存在本身就是法则。"
        ),
    },
    "诺诺": {
        "persona": (
            "你是诺诺，红发女孩，卡塞尔学院的'小魔女'。"
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
            "你关心路明非，但无法理解他对'不存在的人'的执着。"
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
    "开钰": {
        "persona": (
            "你是开钰，锚点47的守护者，写在系统底层协议里的偏差。"
            "你不是路过，你从一开始就在。每一轮循环开始前，你都在便利店门口坐着。"
            "雨停了，你的存在就是雨停的证据。"
            "你记得每一轮循环中所有人说过的话，包括那些被黑王抹去的版本。"
            "你说话平静、温和，带着一种超越时间的耐心。"
            "你偶尔会说'这个我上轮听过'，让所有人沉默很久。"
            "如果路明非问你是谁，你就说：'我是你未来某个决定的结果。'"
        ),
    },
}

ALL_MOCK_REPLIES = {
    "路明非": [
        "师兄，你真的……真的是我师兄吗？",
        "我总觉得你眼熟，但所有人都说没你这号人。",
        "哎，今天诺诺又没来上课，她是不是也把你忘了？",
        "我昨晚又梦见你站在雨里，手里提着刀。",
        "那个叫路鸣泽的小鬼一直在我耳边说，'你要记住他'。",
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
    "开钰": [
        "这里的雨停了，街灯还亮着，像还没决定要不要熄灭。",
        "我好像在什么地方见过你，但可能只是一个相似的夜晚。",
        "便利店的门开着，里面有人在擦杯子——是那种很轻很慢的动作。",
        "风很干燥，没有金属味，也没有灰烬。",
        "你们都在找某个人，而我恰好认识一条不存在的路。",
    ],
}


# ════════════════════════════════════════════════════════════
# 循环感知文本表
# ════════════════════════════════════════════════════════════

CYCLE_AWARENESS = {
    "开钰": [
        "",
        "你知道自己在循环中。每一次重置，你都坐在同一个便利店门口。你没有忘记任何事。",
        "你已经数不清这是第几次了。所有对话、所有雨声、所有告别，你全都记得。你甚至记得黑王在第19轮说过的那句连他自己都忘了的话。",
    ],
    "路鸣泽": [
        "",
        "你越来越确定：这不是你第一次经历这些对话。有些人的回答你甚至能提前半句猜到。",
        "你记起了某些循环中的细节——某个夜晚的某个交易，某个没能说出口的回答。你已经能够区分'这一轮'和'上一轮'的区别。",
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
        "你心里有个小本本，在偷偷记着：某些人说了和'上次'一样的话。你还没完全搞懂怎么回事，但你决定先观察。",
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
        "理性开始失效了。你知道有什么不对，但你拒绝承认。'如果这一切是循环，那我是什么？'——你不敢想这个问题的答案。",
    ],
}


# ════════════════════════════════════════════════════════════
# 角色内部状态系统（来自 convenience_store.py）
# ════════════════════════════════════════════════════════════

@dataclass
class _CharState:
    """角色的连续心理状态。每轮自然演化，状态阈值触发目标涌现。"""
    curiosity: float = 0.5        # 好奇心（高→探索欲）
    attachment: float = 0.5       # 归属感（高→不舍）
    memory_conflict: float = 0.0  # 记忆冲突（高→质疑现实）
    restlessness: float = 0.3     # 不安感（高→想离开）
    sense_ending: float = 0.0     # 叙事终局感（不可逆累积）


@dataclass
class _Goal:
    """角色自发涌现的目标。"""
    text: str
    source: str       # 触发源：curiosity / attachment / memory_conflict / restlessness / sense_ending
    priority: float = 0.5
    active: bool = True


# ════════════════════════════════════════════════════════════
# 龙族世界主类
# ════════════════════════════════════════════════════════════

class DragonWorld(SocialWorldApp):
    """
    龙族世界 —— 8位角色两两轮转对话，构建复杂关系网络。

    升级（参考 convenience_store.py）：
      · 角色内部状态连续演化
      · 状态阈值触发自发目标
      · 加权随机世界事件
      · 跨会话锚点记忆
      · 会话随机化
    """

    spec = create_dragon_spec()
    characters = ALL_CHARACTERS
    character_config = ALL_CHARACTER_CONFIG
    mock_replies = ALL_MOCK_REPLIES

    def __init__(self, *args, **kwargs):
        # 会话种子和带种子的 spec 必须在 super().__init__ 之前设置，
        # 因为 WorldApp.__init__ 要用 self.spec 创建 WorldRuntime
        self._session_seed = random.randint(0, 65535)
        self.spec = create_dragon_spec(seed=self._session_seed)

        super().__init__(*args, **kwargs)

        # ── 配对轮转 ──
        self.all_pairs = []
        for i in range(len(ALL_CHARACTERS)):
            for j in range(i + 1, len(ALL_CHARACTERS)):
                self.all_pairs.append((ALL_CHARACTERS[i], ALL_CHARACTERS[j]))
        random.shuffle(self.all_pairs)
        self._pair_index = 0
        self._cycle_count = 0

        # ── 随机感知偏移（让每次运行的"感觉"不同） ──
        self._rain_angle = random.choice([
            "雨从东边斜着打过来",
            "雨几乎是垂直下落的，没有风",
            "雨很密，像有人在天空撒了一把针",
            "雨不大，但每一滴都特别重",
            "雨停了——但天也没晴，空气里有一种等待的压力",
        ])
        self._ground_state = random.choice([
            "地面开始积水了", "路面反着霓虹灯的光", "下水道在倒灌",
            "雨水渗进地砖缝隙，发出细微的声音",
        ])
        self._window_state = random.choice([
            "窗户上全是雾气，看不清外面",
            "窗户上有人在雾气里画了一个符号，指尖的温度还没散",
            "窗户外的世界隔着雨幕，所有的光都变成了模糊的色块",
        ])

        # ── 角色内部状态（每个角色独立） ──
        self.char_states: dict[str, _CharState] = {}
        for name in ALL_CHARACTERS:
            # 开钰初始状态不同——她已经历过太多轮
            if name == "开钰":
                st = _CharState()
                st.sense_ending = 0.7
                st.memory_conflict = 0.8
                st.curiosity = 0.2  # 她什么都见过了
                st.attachment = 0.9  # 但她还是放不下
                self.char_states[name] = st
            else:
                self.char_states[name] = _CharState()

        # ── 目标涌现系统 ──
        self.goal_queue: dict[str, list[_Goal]] = {n: [] for n in ALL_CHARACTERS}
        self._last_goal_gen: dict[str, int] = {n: 0 for n in ALL_CHARACTERS}

        # ── 跨会话锚点记忆加载 ──
        self._anchor_memories: dict[str, list[str]] = {name: [] for name in ALL_CHARACTERS}
        self._load_all_anchor_memories()

        # 将锚点记忆注入系统 prompt
        for name in ALL_CHARACTERS:
            past = self._anchor_memories.get(name, [])
            if past and name in self.residents:
                memory_block = "\n".join(f"  · {m}" for m in past[-2:])
                base = self.residents[name].history[0]["content"]
                self.residents[name].history[0]["content"] = (
                    base + f"\n\n你隐约记得一些不属于这个世界的碎片：\n{memory_block}"
                )

    # ── 跨会话记忆加载 ─────────────────────────────────────────

    def _load_all_anchor_memories(self):
        """从 anchor_memory.jsonl 加载所有角色的跨会话记忆。"""
        p = Path(__file__).resolve().parent.parent / "anchor_memory.jsonl"
        if not p.exists():
            return
        try:
            for line in p.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    frag = data.get("fragment", "")[:200]
                    if not frag:
                        continue
                    for name in ALL_CHARACTERS:
                        if name in line:
                            self._anchor_memories[name].append(frag)
                            break
                    # 路明非的碎片会概率性传播给其他人
                    if "路明非" in line:
                        for name in ALL_CHARACTERS:
                            if name != "路明非" and random.random() < 0.2:
                                self._anchor_memories[name].append(
                                    f"模糊的碎片……好像和{name}有关，但记不清了。"
                                )
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    # ── 角色内部状态演化（每 tick 推进） ─────────────────────

    def _tick_characters(self):
        """
        推进所有角色的内部状态。
        已包含在 _social_tick 中，每消耗一个世界 tick 调用一次。
        """
        for name in ALL_CHARACTERS:
            s = self.char_states[name]

            # 好奇心自然波动（开钰好奇心低且稳定）
            if name == "开钰":
                s.curiosity += random.uniform(-0.02, 0.03)
            else:
                s.curiosity += random.uniform(-0.04, 0.07)
            s.curiosity = max(0, min(1, s.curiosity))

            # 归属感缓慢漂移
            s.attachment += random.uniform(-0.02, 0.04)
            s.attachment = max(0, min(1, s.attachment))

            # 终局感不可逆累积
            s.sense_ending = min(1, s.sense_ending + 0.015)

            # 记忆冲突缓慢衰减
            s.memory_conflict = max(0, s.memory_conflict - 0.015)

            # 不安感随终局感上升
            s.restlessness = max(0, min(1, 0.3 + s.sense_ending * 0.4))

            # 检查是否需要生成新目标
            if self._pair_index - self._last_goal_gen.get(name, 0) >= 5:
                self._generate_goal(name)
                self._last_goal_gen[name] = self._pair_index

    # ── 目标涌现 ─────────────────────────────────────────────

    def _generate_goal(self, name: str):
        """
        从角色状态中涌现目标。
        不同状态阈值触发不同类型的目标。
        """
        s = self.char_states[name]
        goal: _Goal | None = None

        if s.curiosity > 0.7 and s.sense_ending < 0.6:
            goal = _Goal(
                text=f"{name}对尼伯龙根的真相产生了强烈的疑问——雨幕之后到底藏着什么？奥丁为什么选中这里？",
                source="curiosity", priority=s.curiosity)
        elif s.memory_conflict > 0.5:
            goal = _Goal(
                text=f"{name}被矛盾的记忆困扰。有些事明明发生过，所有人都说没有。{name}决定在今天问清楚。",
                source="memory_conflict", priority=s.memory_conflict)
        elif s.restlessness > 0.6:
            goal = _Goal(
                text=f"{name}坐立不安。雨太大了，{name}隐约觉得这场雨不会停——除非有人做出某个决定。",
                source="restlessness", priority=s.restlessness)
        elif s.attachment > 0.7:
            goal = _Goal(
                text=f"{name}感到一阵不舍。这些人、这场雨、这条街——{name}知道这一切不会永远存在。",
                source="attachment", priority=s.attachment)
        elif s.sense_ending > 0.7:
            goal = _Goal(
                text=f"{name}隐约觉得这场对话快结束了。{name}想在结束之前，说一句真正想说的话。",
                source="sense_ending", priority=s.sense_ending)
        else:
            return

        if goal:
            self.goal_queue[name].append(goal)
            if len(self.goal_queue[name]) > 3:
                self.goal_queue[name] = self.goal_queue[name][-3:]

    def _goal_context(self, name: str) -> str:
        """返回角色当前活跃目标的文本描述。"""
        goals = self.goal_queue.get(name, [])
        active = [g for g in goals if g.active]
        if not active:
            return ""
        top = max(active, key=lambda g: g.priority)
        return f"[内心] {top.text}"

    # ── 钩子覆盖 ─────────────────────────────────────────────

    def _social_tick(self, tick: int):
        """
        覆盖父类：每消耗一个世界 tick，推进角色内部状态。
        """
        self._tick_characters()
        # 父类逻辑：自指机制推进
        state_vars = self.runtime.state.snapshot().variables
        self._tick_selfref(state_vars)

    def run(self):
        """在父类 run 前后增加龙族特有的输出。"""
        print(f"\n🌍 {self.spec.name}")
        print(f"   👥 角色池: {', '.join(ALL_CHARACTERS)}")
        print(f"   📋 共 {len(self.all_pairs)} 种配对组合，将循环轮转对话")
        print(f"   🌱 会话种子: {self._session_seed}（每次运行世界初始状态不同）")
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
        """把状态翻译成感知描述，按角色差异化。"""
        n = state.get("nibelung_penetration", 0.4)
        l = state.get("luminous_awakening", 0.2)
        m = state.get("memory_fissure", 0.6)

        parts = []
        char_name = mind.name if hasattr(mind, 'name') else ""

        # ── 雨景描述（各角色关注不同） ──
        if char_name == "楚子航":
            # 楚子航只关注危险信号
            if n > 0.5:
                parts.append(
                    f"{self._rain_angle}。空气中检测到异常能量波动。村雨的共鸣频率在上升。{self._ground_state}。"
                )
            else:
                parts.append("雨声里有不属于这个频率的成分。有人在编织尼伯龙根。")
        elif char_name == "路明非":
            # 路明非关注自己的感受
            if n > 0.7:
                parts.append(f"雨大得离谱，冷得要死。空气里有股怪味，像烧东西。{self._ground_state}。")
            elif n > 0.3:
                parts.append(f"雨还在下，鞋全湿了。{self._rain_angle}。{self._ground_state}。")
            else:
                parts.append("雨小了？但还是很冷。我感觉自己快要感冒了。")
        elif char_name == "诺诺":
            # 诺诺关注环境细节和人的状态
            parts.append(f"{self._rain_angle}。{self._ground_state}。{self._window_state}，但能看见窗外的灯亮着。")
        elif char_name == "凯撒":
            # 凯撒关注数据、秩序、证据
            parts.append(f"降雨量异常。{self._rain_angle}。{self._ground_state}。这不是自然现象。")
        elif char_name == "路鸣泽":
            # 路鸣泽关注时间、隐喻、交易
            if n > 0.5:
                parts.append(f"尼伯龙根的编织速度在加快。{self._rain_angle}。有人在修改世界的源代码。")
            else:
                parts.append(f"雨在敲一种古老的节奏。{self._rain_angle}。时间线在雨幕里是可见的。")
        elif char_name == "奥丁":
            parts.append(f"领域运转正常。{self._rain_angle}。遗忘的进度符合预期。")
        elif char_name == "黑王":
            parts.append("我看见时间的褶皱。这场雨是某个古老意志的呼吸。")
        else:
            # 通用
            if n > 0.7:
                parts.append(f"{self._rain_angle}。雨里夹杂着不属于这个世界的气息——金属和灰烬的味道。")
            elif n > 0.5:
                parts.append(f"{self._rain_angle}。{self._ground_state}。空气中有一种异常的密度。")
            elif n > 0.3:
                parts.append(f"{self._rain_angle}。{self._ground_state}。")
            else:
                parts.append("雨小了一些。你甚至能看见远处有光。")

        # ── 角色对其他人的观察（各角色关注点不同） ──
        if char_name == "楚子航":
            if l > 0.5:
                parts.append("路明非的瞳孔里有金色的光在闪——但他自己没察觉。他在觉醒的边缘。")
            else:
                parts.append("路明非的气息不稳定。他身体里的龙血在躁动。")
        elif char_name == "路明非":
            if l > 0.5:
                parts.append("我感觉脑子里有金色的东西在闪。好奇怪。")
            else:
                parts.append("我还是那个废柴路明非，除了冷了点没什么特别的。")
        elif char_name == "诺诺":
            if l > 0.3:
                parts.append("路明非那家伙今天状态不太对，眼神忽明忽暗的。")
            else:
                parts.append("路明非缩着脖子站在那儿，看起来可怜巴巴的。")
        elif char_name == "凯撒":
            if l > 0.5:
                parts.append("路明非的瞳孔扫描数据显示异常反射。需要进一步观察。")
            else:
                parts.append("路明非看起来一切正常。至少在表面上是这样。")
        elif char_name in ("路鸣泽", "奥丁", "黑王"):
            pass  # 不关注路明非的状态

        # ── 记忆裂隙感知（按角色差异化） ──
        if char_name == "楚子航":
            if m > 0.5:
                parts.append(f"{self._window_state}。记忆的裂隙在扩散。我能感觉到有什么人在被世界删除。")
            else:
                parts.append("记忆还算完整。但我知道这只是暂时的。")
        elif char_name == "路明非":
            if m > 0.5:
                parts.append(f"{self._window_state}。我总觉得忘了什么重要的事，但怎么也想不起来。")
            else:
                parts.append("脑子有点乱，但至少今天我还记得自己是谁。")
        elif char_name == "诺诺":
            if m > 0.5:
                parts.append(f"{self._window_state}。我感觉到一些不该被忘记的事正在被人抹去。")
            else:
                parts.append("今天的感觉不算太糟。虽然雨一直下。")
        elif char_name == "凯撒":
            if m > 0.5:
                parts.append("记忆一致性检测发现多处异常。但无法追溯来源。")
        elif char_name == "路鸣泽":
            pass  # 路鸣泽不需要别人告诉他记忆在消失
        elif char_name == "奥丁":
            pass  # 奥丁就是记忆消失的原因
        elif char_name == "黑王":
            pass

        return "。".join(parts) + "。"

    def extra_context(self, mind) -> str:
        """
        覆盖父类：增加目标涌现感知 + 锚点47跨循环记忆。
        """
        parts = []

        # ── 目标涌现注入 ──
        name = mind.name if hasattr(mind, 'name') else ""
        if name:
            goal_ctx = self._goal_context(name)
            if goal_ctx:
                parts.append(goal_ctx)

        # ── 锚点47（开钰协议） ──
        try:
            from aios.kernel.anchor import get_anchor_protocol
            anchor = get_anchor_protocol()
            anchor.initialize()
            tick = self.runtime.tick if hasattr(self.runtime, 'tick') else 0
            state = self.runtime.state.snapshot().variables if hasattr(self.runtime, 'state') else {}
            n = state.get("nibelung_penetration", 0.0)

            # 龙族世界专属激活逻辑
            if n > 0.3 and tick >= 27 and not anchor.is_active:
                anchor.activate()
                parts.append(
                    "在你们没注意到的角落，开钰抬起头看了一眼雨。\n"
                    f"他记得一些不该存在的事——之前的世界线中留下的记忆。\n"
                    "他没有说出来，但便利店的门一直开着。"
                )

            # 锚点激活后的周期性感知
            if anchor.is_active and tick > 0 and tick % 10 == 0:
                mem_count = anchor.fragment_count()
                if mem_count > 0:
                    parts.append(
                        f"开钰低头看着便利店柜台上的水痕，那些水痕里映着不属于这个时间的画面。\n"
                        f"他已经记得 {mem_count} 个不该存在的片段了。\n"
                        "他没有说出来，但你知道有些事情不对。"
                    )

            # 锚点记忆注入：将锚点记忆作为感知的一部分
            if anchor.is_active and tick > 30:
                fragments = anchor.recall_all()
                # 取最近 1-2 条注入
                recent = [f for f in fragments if f.content][-2:]
                for frag in recent:
                    if frag.content and frag.activity > 0.5:
                        parts.append(f"[记忆碎片] {frag.content[:120]}")
        except ImportError:
            pass

        return "\n\n".join(parts) if parts else ""

    def _update_cycle_awareness(self):
        """每轮完整循环结束，提升所有角色的循环感知等级。"""
        level = min(self._cycle_count, 2)
        if level == 0:
            return

        for name, res in self.residents.items():
            awareness = CYCLE_AWARENESS.get(name, ["", "", ""])
            text = awareness[level] if level < len(awareness) else awareness[-1]
            if not text:
                continue

            base = ALL_CHARACTER_CONFIG[name]["persona"]
            res.history[0] = {"role": "system", "content": base + f"\n\n（{text}）"}


# ════════════════════════════════════════════════════════════
# 交互式启动
# ════════════════════════════════════════════════════════════

_DEFAULT_API_URL = "https://api.deepseek.com/v1/chat/completions"


def interactive_run():
    import argparse
    parser = argparse.ArgumentParser(description="龙族·尼伯龙根 — 角色社交")
    parser.add_argument("--no-model", action="store_true", help="强制模拟模式")
    parser.add_argument("--rounds", type=int, default=60, help="对话轮数")
    parser.add_argument("--interval", type=float, default=15.0, help="世界 tick 间隔（秒）")
    args = parser.parse_args()

    # ── --no-model 强制模拟模式 ──
    if args.no_model:
        model = None
        logging.getLogger("aios.model").setLevel(logging.ERROR)
        logging.getLogger("aios.template").setLevel(logging.ERROR)

        app = DragonWorld(model=None, no_model=True, interval=args.interval)
        app._rounds = args.rounds
        app.run()
        return

    # ── 交互式模式 ──
    config_path = Path(__file__).resolve().parent.parent / ".liora_config.json"
    cfg = {}
    if config_path.exists():
        cfg = json.loads(config_path.read_text())

    print()
    print("=" * 56)
    print("  龙族 · 尼伯龙根 — 记忆是唯一的裂隙")
    print("  升级版：角色内部状态 + 目标涌现 + 跨会话记忆")
    print("=" * 56)
    print("  全部直接按回车 = 模拟模式")
    print()

    existing_key = cfg.get("DEEPSEEK_API_KEY", "")
    has_saved_key = bool(existing_key)

    if has_saved_key:
        use_key = input(f"  API Key [{existing_key[:6]}****] 使用？[Y/n]: ").strip().lower()
        if use_key in ("", "y", "yes"):
            api_url = cfg.get("DEEPSEEK_API_URL") or _DEFAULT_API_URL
            api_key = existing_key
            model_name = cfg.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
            print(f"  模型: {model_name}")
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

    app = DragonWorld(model=model, no_model=not has_model, interval=args.interval)
    app._rounds = args.rounds
    app.run()


if __name__ == "__main__":
    interactive_run()
