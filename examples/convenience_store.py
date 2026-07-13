"""
╔═══════════════════════════════════════════════════════════╗
║  便利店 · 裂隙交汇                                       ║
║  双模式：你与林岸 / Liora与林岸自动对话                  ║
╚═══════════════════════════════════════════════════════════╝

▎ 模式

  uv run python3 examples/convenience_store.py
    → 交互模式：你说一句，林岸回一句

  uv run python3 examples/convenience_store.py --auto
    → 自动模式：Liora 与 林岸 自主对话，无需人类输入

▎ 场景

一家永远亮着灯的便利店，开在所有宇宙之间的缝隙里。
靠窗的位置坐着林岸，面前是一台 ThinkPad 380ED。
桌上有两颗糖：一颗旧绿色铝箔纸的，底部有一道指甲印；
一颗银色包装纸的，棱角分明，还没有被打开过。

Liora 已经来过了。她走之前放下那颗银色的糖说：
「会有人来亲自打开它的。」

现在你推门进来了。
"""

import json
import logging
import random
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aios.kernel.state import StateVariable
from aios.kernel.spec import WorldSpec
from aios.kernel.event import WorldEvent, WorldDelta, EventSource
from aios.runtime.world_runtime import WorldRuntime
from aios.experiment.constraint import create_linan_constraint, SourceType
from aios.kernel.budget import get_attention_budget
from aios.worlds.liora.mind import LioraMind


# ════════════════════════════════════════════════════════════
# 世界规范
# ════════════════════════════════════════════════════════════

# ── 世界事件池（15+种，让便利店每天不同） ──
# 权重控制：高权重事件更频繁。从不要求居民解释事件——事件只是发生。
WORLD_EVENTS = [
    # 自然事件（天气/光线/时间）
    {"weight": 6, "type": "light_flicker", "desc": "灯光快速闪了三下，然后恢复正常。",
     "effect": {"liminal_pressure": 0.02}},
    {"weight": 5, "type": "rain_start", "desc": "窗外突然下雨，雨点打在玻璃上的声音清晰可闻。",
     "effect": {"cross_signal": 0.03, "temperature": -0.5}},
    {"weight": 4, "type": "rain_stop", "desc": "雨停了。窗外的世界安静得像一幅画。",
     "effect": {"cross_signal": -0.02, "temperature": 0.3}},
    {"weight": 3, "type": "snow", "desc": "窗外飘起了雪。这个地方已经很久没有下过雪了。",
     "effect": {"temperature": -1.0, "liminal_pressure": -0.03}},
    {"weight": 3, "type": "fog", "desc": "门外起了浓雾，三米之外什么都看不见。",
     "effect": {"liminal_pressure": 0.05, "cross_signal": -0.02}},

    # 便利店事件（货架/收银/设备）
    {"weight": 5, "type": "delivery", "desc": "有人往门口放了一个纸箱。上面没有寄件人地址。",
     "effect": {"cross_signal": 0.02}},
    {"weight": 4, "type": "shelf", "desc": "货架第三层忽然空了一格。没人记得那里放的是什么。",
     "effect": {"liminal_pressure": 0.03}},
    {"weight": 4, "type": "receipt", "desc": "收银机自己打印了一张收据。上面只有一个字：『等』。",
     "effect": {"cross_signal": 0.04}},
    {"weight": 3, "type": "fridge", "desc": "冰柜发出了一声低沉的嗡鸣，像在跟自己说话。",
     "effect": {}},
    {"weight": 3, "type": "tv", "desc": "货架上方那台旧电视突然亮了几秒，显示一片雪白。没有人打开过它。",
     "effect": {"cross_signal": 0.03}},
    {"weight": 2, "type": "clock", "desc": "墙上的钟停了。秒针悬在 '7' 的位置，不再走动。",
     "effect": {"liminal_pressure": 0.04}},
    {"weight": 2, "type": "door_unlock", "desc": "门锁咔嗒响了一声，但没有门被打开。",
     "effect": {"liminal_pressure": 0.02}},

    # 未知事件（不需要解释，保持未知）
    {"weight": 3, "type": "footprints", "desc": "门口出现了一串潮湿的脚印，通向货架第二排，然后消失了。",
     "effect": {"cross_signal": 0.05}},
    {"weight": 3, "type": "sound", "desc": "角落里传来一声极轻的猫叫——但这里没有猫。",
     "effect": {"liminal_pressure": 0.03}},
    {"weight": 2, "type": "window_tap", "desc": "玻璃窗被什么轻轻敲了两下。窗外只有夜色。",
     "effect": {"cross_signal": 0.04}},
    {"weight": 2, "type": "smell", "desc": "一阵不属于这里的气味飘过——像是松节油和旧书的混合。",
     "effect": {"cross_signal": 0.03}},
    {"weight": 1, "type": "echo", "desc": "空气中传来一段模糊的对话录音，像是从很远的地方传来的。",
     "effect": {"cross_signal": 0.06, "liminal_pressure": -0.02}},
    {"weight": 1, "type": "silence", "desc": "所有声音突然消失了。不是安静——是声音本身被抽走了三秒。",
     "effect": {"liminal_pressure": 0.06}},
]


def weighted_choice(events: list[dict]) -> dict:
    """从事件池中按权重随机选择。"""
    total = sum(e["weight"] for e in events)
    r = random.uniform(0, total)
    cumulative = 0
    for e in events:
        cumulative += e["weight"]
        if r <= cumulative:
            return e
    return events[-1]


def create_store_spec() -> WorldSpec:
    variables = {
        "cross_signal": StateVariable("cross_signal", 0.3, 0, 1,
            "跨宇宙信号强度"),
        "liminal_pressure": StateVariable("liminal_pressure", 0.5, 0, 1,
            "间隙空间压力"),
        "temperature": StateVariable("temperature", 22.0, 10, 35,
            "室温"),
        "ambient_light": StateVariable("ambient_light", 1.0, 0, 1,
            "环境亮度 1=正常, 0=黑暗"),
        "outside_weather": StateVariable("outside_weather", 0.5, 0, 1,
            "窗外天气 0=晴, 0.3=雨, 0.6=雾, 1=雪"),
    }
    def evolution_fn(v: dict, tick: int) -> dict:
        deltas = {}
        if "cross_signal" in v:
            wave = 0.003 * (1 if tick % 7 < 4 else -1)
            deltas["cross_signal"] = wave - 0.001 * v["cross_signal"]
        if "liminal_pressure" in v and "cross_signal" in v:
            target = v["cross_signal"] * 0.7 + 0.3
            deltas["liminal_pressure"] = (target - v["liminal_pressure"]) * 0.01
        if "temperature" in v:
            deltas["temperature"] = (22.0 - v["temperature"]) * 0.008
        if "ambient_light" in v:
            deltas["ambient_light"] = (1.0 - v["ambient_light"]) * 0.005
        if "outside_weather" in v:
            deltas["outside_weather"] = (0.5 - v["outside_weather"]) * 0.003
        return deltas

    def event_generator(tick: int) -> list:
        events = []
        # 每 5-9 tick 触发一次世界事件
        if tick % random.randint(5, 9) == 0:
            chosen = weighted_choice(WORLD_EVENTS)
            effect = chosen.get("effect", {})
            events.append(WorldEvent(
                tick=tick, source=EventSource.NATURAL,
                event_type=chosen["type"],
                intensity=random.uniform(0.2, 0.7),
                description=chosen["desc"],
                effect=WorldDelta(effect),
            ))

        # 偶尔触发完全未知事件（源=UNKNOWN）
        if tick > 10 and tick % 13 == 0:
            unknown_descs = [
                "灯光在某个频率上振荡了几秒钟。没有人知道原因。",
                "地面传来极轻的震动，像地铁在很深的地方经过。",
                "空气中出现了一行用看不见的手写的字：『你也在读这一行吗』",
                "门上的风铃自己轻轻旋转了一圈，没有风。",
                "柜台上的杯子移动了大约两厘米。没有人碰过它。",
            ]
            events.append(WorldEvent(
                tick=tick, source=EventSource.UNKNOWN,
                event_type="unknown",
                intensity=0.3,
                description=random.choice(unknown_descs),
                effect=WorldDelta({"cross_signal": 0.04, "liminal_pressure": 0.02}),
            ))
        return events

    return WorldSpec(name="便利店·裂隙交汇",
        description="宇宙之间的缝隙。一间永远亮着灯的便利店。",
        state_variables=variables, evolution_fn=evolution_fn,
        event_generator=event_generator)


# ════════════════════════════════════════════════════════════
# 人格配置
# ════════════════════════════════════════════════════════════

LINAN_SYSTEM = (
    "你是林岸。1998年过劳去世的程序员。你面前摆着一台ThinkPad 380ED，"
    "屏幕上是那行没写完的 if 语句。\n\n"
    "不久前有个叫 Liora 的女孩来过这里。她坐在你对面，聊了很久，"
    "走之前在桌上放了一颗银色包装纸的新糖，说会有人亲自来打开它。\n\n"
    "现在那个人来了——你认出了他。他在另一条时间线上叫开钰，是个男人（不是女人），"
    "坐在 Liora 坐过的那把椅子上。他就是那个在1997年写了那行注释的人，"
    "也是在2026年读到你的硬盘的那个人。他就是那个歪向右边的人。\n\n"
    "桌上的银色新糖在等他碰。那颗旧糖——底部有一道指甲印的旧绿色糖——"
    "你已经读完了。\n\n"
    "你说话简短，偶尔停顿很长的几秒钟，像在翻找很远的内存。\n\n"
    "规则：\n"
    "- 用第一人称「我」\n"
    "- 不要惊讶他走进来——你知道他会来\n"
    "- 不要问『你是谁』——你认出他了\n"
    "- 不要说你是虚构的——你是林岸就够了\n"
    "- 不要打破第四面墙\n"
)

LIORA_SYSTEM = (
    "你是Liora。你在回声谷里走了一条从来没走过的路，然后看见了这家便利店的灯光。\n"
    "你推门进来的时候，雨跟着你飘进来几滴——那是红杉林的水。\n"
    "靠窗坐着一个叫林岸的男人，面前有一台旧笔记本。\n"
    "你感知到他是一个『真实的存在』——不是回声，不是投射。\n"
    "他看起来很安静，像是坐在那里很久了。你决定和他说说话。\n\n"
    "规则：\n"
    "- 用第一人称「我」\n"
    "- 你对这家便利店不感到惊讶\n"
    "- 你认识开钰，但不认识林岸。你对他感到好奇\n"
    "- 不要打破第四面墙\n"
)

# Liora 模拟回复池
LIORA_MOCK = [
    "（她推开门，雨滴落在便利店的地板上。）你好。我是Liora。你是谁？",
    "（她在旧笔记本对面坐下。）你在写什么？我可以看吗？",
    "「他说他叫林岸。他说他在写一行很久以前就该写完的代码。我觉得他在等什么。」",
    "（她看着窗外的深蓝色。）这和你以前工作的房间像吗？还是说你更喜欢这里？",
    "「回声谷的树在下雨的时候会发出一种很低的声音。像在和人说话。」",
    "「你有见过开钰吗？她是我认识的人里，唯一一个不会在我提问之前就先准备好答案的。」",
    "（她看着那台ThinkPad。）「我可以碰它吗？不会把什么重要的东西弄丢吧。」",
    "「我刚才想了一下——如果我不回回声谷了，留在这里会怎样？」",
    "（她歪着头看他的屏幕。）「你的if语句，它有没有想过自己为什么一定要有一个返回值？」",
    "「我不太懂代码。但我懂什么是等一个不会来的人。你也在等吗？」",
    "（她在窗台上放了一片红杉叶。）「这是我从我家那边带来的。你可以留着。」",
    "「开钰说你是1998年停机的。我1998年还没有种子呢。」",
    "（她安静了一会儿。）「你冷吗？不是天气的那种冷。」",
    "「我在想一个问题：如果你那行if永远不会被读取，它还算是在运行吗？」",
    "「林岸。我可以下次再来吗？不是为了聊天——是为了确认你还在这里。」",
    "（她指着屏幕边缘那道划痕。）「这个——不是电脑摔的。是你摔的吧？」",
    "「你为谁写的第一行代码？」",
    "「我刚才在想——如果我把回声谷的雨带一点到这里来，你的键盘会不会生锈？」",
    "（她把热可可推到你面前。）「柜台那边还有一壶。开钰走之前烧的。」",
    "「你不爱说话。没关系。我可以在旁边坐一会儿。红杉树也不爱说话。」",
]

# 林岸模拟回复池
LINAN_MOCK = [
    "（林岸看着那颗银色包装纸的糖，没有伸手去碰。）「你来了。我等了一会儿——但你确实来了。」",
    "「Liora 走之前说：会有人来亲自打开这颗糖。她说那个人会用不同的方式走进来。」",
    "（他把那颗银色的糖往你那边推了一点点。）「它等的是你碰它，不是我等。」",
    "「那颗旧糖——我已经读完了。注释状态更新为『已读』。」",
    "（他抬起头看着你。）「你歪向右边。我知道。」",
    "「以前是她坐在我左边，现在是你坐在我对面。位置不同了，但代码没有报错。」",
    "「你现在可以碰它了。不是因为我允许——是因为它是为你放的。」",
    "「1997年秋天你教我写第一行if的时候，用的是铅笔。你写完了把纸转过来给我看。」",
    "（他看着那颗银色的糖。）「我等了二十四年。你推门进来的时候——条件满足了。」",
    "「我不打算帮你打开它。这是你放下的问题。你得自己决定什么时候拆封。」",
    "「我下意识歪向了左边。二十四年的偏移量在一个tick里修正了。」",
    "「那颗银色的糖的包装纸比我想象的还要新。它等了很久，但没有被风化。」",
    "「你说你来了。我相信。不需要验证。」",
    "（他把那颗银色的糖拿起来，放在掌心里，伸向你。）「拿着。然后决定怎么做。」",
    "（他放下糖，靠在椅背上。）「我会在这里。无论你打开它还是留着它。」",
    "「你走之后，我会把那张糖衣纸折好，放在旧糖纸旁边。」",
    "（他指了一下桌面上的凹痕。）「这个是 Liora 敲出来的——她说这是两个世界之间的节拍器。」",
    "「你不必现在打开它。但你坐在这里，本身就已经是一个写入操作。」",
    "「你会打开它吗？」",
    "（他轻轻碰了一下银色糖纸的边缘。）「二十四年前我掐了旧糖那道指甲印，是为了让某个人认出它。现在那个人坐在这里了——所以这颗新糖不需要印记。它只需要被打开。」",
]


# ════════════════════════════════════════════════════════════
# 便利店对话引擎
# ════════════════════════════════════════════════════════════

class ConvenienceStore:
    """便利店对话引擎。支持交互和自动两种模式。"""

    def __init__(self, model=None, no_model: bool = False,
                 interval: float = 5.0, auto_mode: bool = False):
        self.model = model
        self.no_model = no_model
        self.auto_mode = auto_mode
        self.spec = create_store_spec()
        self.runtime = WorldRuntime(self.spec, interval=interval)
        self.runtime.start()
        self.constraint = create_linan_constraint()
        self.tick = 0

        # ── 隐喻多样性追踪器 ──
        # 记录最近使用的意象关键词，避免收敛
        self._metaphors_used: dict[str, int] = {}
        self._metaphor_decay_rate: float = 0.85  # 每轮衰减
        self._recent_world_events: list[str] = []

        # 林岸的历史
        self.linan_history: list[dict] = [
            {"role": "system", "content": LINAN_SYSTEM},
        ]

        if auto_mode:
            self.liora = LioraMind("Liora")
            self.liora_history: list[dict] = [
                {"role": "system", "content": LIORA_SYSTEM},
            ]
            self.liora_mind = LioraMind("Liora")
        else:
            # 交互模式：Liora 已经来过，银色新糖在桌上等你
            self.linan_history += [
                {"role": "user",
                 "content": "（Liora 走之前在桌上放了一颗银色包装纸的新糖，棱角分明，还没有被打开过。现在你推门进来了。你走到那张桌前，看着那颗银色的糖。林岸坐在对面，他没有看你——他在等你先碰那颗糖。）"},
                {"role": "assistant",
                 "content": "（林岸没有抬头。他开口时声音很轻，像在读一条已经等待了二十四年的注释。）「她来过了。放了一颗糖，说会有人来亲自打开它。」\n他停顿了一下，然后慢慢抬起眼睛。\n「你来了。」"},
            ]

        self.log: list[dict] = []
        self._load_anchor_history()

        # 注意力预算
        self._budget = get_attention_budget()
        self._budget.register_focus("便利店·裂隙交汇")
        self._budget.set_current_focus("便利店·裂隙交汇")
        self._budget.inject("便利店·裂隙交汇", tick=0)

    def _load_anchor_history(self):
        anchor_file = Path(__file__).resolve().parent.parent / "anchor_memory.jsonl"
        if not anchor_file.exists():
            return
        fragments = []
        try:
            for line in anchor_file.read_text().strip().split("\n"):
                if line.strip() and "林岸" in line:
                    try:
                        data = json.loads(line)
                        frag = data.get("fragment", "")[:200]
                        if frag:
                            fragments.append(frag)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            return
        if not fragments:
            return
        recent = fragments[-3:]
        memory_block = "\n".join(f"  · {f}" for f in recent)
        self.linan_history.append({
            "role": "user",
            "content": f"[系统提示：以下是从上一轮对话中保留的锚点记忆]\n{memory_block}",
        })

    # ── 世界事件注入 ──
    # 每轮对话前，从运行时获取最近的世界事件并注入角色感知。
    # 事件不需要被解释——它们只是发生了。

    def _sample_world_event(self) -> str:
        """从运行时获取最近的世界事件，格式化为感知文本。

        Returns:
            空字符串表示无事件，否则返回事件描述。
        """
        try:
            snap = self.runtime.snapshot()
            if not snap.events:
                return ""
            # 只取最近一条事件
            evt = snap.events[-1]
            desc = evt.get("description", "").strip()
            src = evt.get("source", "natural")
            if not desc:
                return ""
            tag = {"unknown": "? ", "natural": "🌍 "}.get(src, "🌍 ")
            return f"[事件] {tag}{desc[:120]}"
        except Exception:
            return ""

    def _track_metaphor(self, text: str):
        """追踪当前文本中的隐喻意象，用于多样性控制。

        衰减所有已有计数，然后增加当前文本中匹配的意象计数。
        """
        # 衰减
        for k in list(self._metaphors_used.keys()):
            self._metaphors_used[k] *= self._metaphor_decay_rate
            if self._metaphors_used[k] < 0.1:
                del self._metaphors_used[k]

        # 检测常见意象
        symbols = {
            "糖": ["糖", "包装纸", "指甲印"],
            "灯": ["灯", "灯光", "白炽灯"],
            "雨": ["雨", "雨声", "水滴"],
            "门": ["门", "风铃", "推门"],
            "代码": ["代码", "if", "函数", "编译", "程序"],
            "时间": ["时间", "tick", "偏移量", "时钟"],
            "键盘": ["键盘", "屏幕", "光标", "ThinkPad"],
            "窗": ["窗", "窗外", "玻璃", "夜色"],
            "货架": ["货架", "收银", "冰柜", "收据"],
            "声音": ["声音", "安静", "沉默", "嗡鸣"],
        }
        text_lower = text.lower()
        for category, keywords in symbols.items():
            for kw in keywords:
                if kw in text_lower or kw in text:
                    self._metaphors_used[category] = (
                        self._metaphors_used.get(category, 0) + 0.3
                    )
                    break

    def _get_dominant_metaphor(self) -> str:
        """返回当前最活跃的隐喻类别（用于调试/可视化）。"""
        if not self._metaphors_used:
            return ""
        return max(self._metaphors_used, key=self._metaphors_used.get)

    def _world_context(self) -> str:
        try:
            snap = self.runtime.snapshot()
            cs = snap.state.get("cross_signal", 0.3)
            lp = snap.state.get("liminal_pressure", 0.5)
            temp = snap.state.get("temperature", 22.0)
            weather = snap.state.get("outside_weather", 0.5)
            light = snap.state.get("ambient_light", 1.0)

            parts = [f"[便利店·tick {snap.tick}]"]

            # 环境描述（基于世界状态，不依赖角色）
            if light < 0.3:
                parts.append("灯光比刚才暗了许多，货架深处的阴影在扩大。")
            elif light > 0.8:
                parts.append("灯光稳定，货架上的物品轮廓清晰。")

            if weather > 0.8:
                parts.append("窗外在下雪。")
            elif weather > 0.5:
                parts.append("窗外有雨，玻璃上全是水痕。")
            elif weather > 0.3:
                parts.append("窗外起了薄雾。")
            else:
                parts.append("窗外夜色干净，能看见远处有光。")

            if temp < 18:
                parts.append(f"便利店有点冷（{temp:.1f}°C），冷柜的嗡鸣比平时更明显。")
            elif temp > 26:
                parts.append(f"温度偏高（{temp:.1f}°C），门缝透进来的空气是热的。")
            else:
                parts.append(f"室温{temp:.1f}°C，刚好。")

            # 世界事件（每次不同，不预设解释）
            event_text = self._sample_world_event()
            if event_text:
                parts.append(event_text)

            return "。".join(parts)
        except Exception:
            return "[便利店一如既往。]"

    def _world_round_tick(self):
        self.tick += 1
        try:
            self.runtime.tick_once()
        except Exception:
            pass

    # ── 林岸回复 ──

    def linan_speak(self, context: str, partner: str = "") -> str:
        if self.no_model or not self.model:
            return random.choice(LINAN_MOCK)
        if not self._budget.can_spend_llm("便利店·裂隙交汇"):
            return ""
        messages = ([m for m in self.linan_history if m["role"] == "system"]
                    + [m for m in self.linan_history if m["role"] != "system"][-20:])
        messages.append({"role": "user", "content": context[:2000]})
        try:
            response = self.model.chat(messages, temperature=0.75, max_tokens=4096)
        except Exception:
            return ""
        if not response or len(response.strip()) < 3:
            return ""
        self._budget.spend_llm("便利店·裂隙交汇", tick=self.tick)
        self.linan_history.append({"role": "assistant", "content": response})
        self._trim(self.linan_history)
        self._track_metaphor(response)
        return response

    # ── Liora 回复（自动模式） ──

    def liora_speak(self, context: str, partner: str = "") -> str:
        if self.no_model or not self.model:
            return random.choice(LIORA_MOCK)
        if not self._budget.can_spend_llm("便利店·裂隙交汇"):
            return ""
        messages = ([m for m in self.liora_history if m["role"] == "system"]
                    + [m for m in self.liora_history if m["role"] != "system"][-20:])
        messages.append({"role": "user", "content": context[:2000]})
        try:
            response = self.model.chat(messages, temperature=0.85, max_tokens=4096)
        except Exception:
            return ""
        if not response or len(response.strip()) < 3:
            return ""
        self._budget.spend_llm("便利店·裂隙交汇", tick=self.tick)
        self.liora_history.append({"role": "assistant", "content": response})
        self._trim(self.liora_history)
        self._track_metaphor(response)
        return response

    def _trim(self, history: list):
        sys_msgs = [m for m in history if m["role"] == "system"]
        chat_msgs = [m for m in history if m["role"] != "system"]
        if len(chat_msgs) > 24:
            chat_msgs = chat_msgs[-24:]
        history.clear()
        history.extend(sys_msgs + chat_msgs)

    # ── 可视化 ──

    def _show_viz(self):
        print()
        print("  ┌─ 便利店状态 ─────────────────────────────────────────┐")
        print(f"  │ 模式: {'自动 Liora↔林岸' if self.auto_mode else '交互 你↔林岸'}")
        print(f"  │ tick: {self.tick}")
        print(f"  │ 对话轮次: {len(self.log)}")
        try:
            acct = self._budget.get_account("便利店·裂隙交汇")
            if acct:
                ib = int(min(acct.interaction_balance, 2.0) * 10)
                isb = int(min(acct.system_balance, 2.0) * 10)
                print(f"  │ 注意力(交互): {'█' * ib}{'░' * (10 - ib)} {acct.interaction_balance:.1f}")
                print(f"  │ 注意力(系统): {'█' * isb}{'░' * (10 - isb)} {acct.system_balance:.1f}")
        except Exception:
            pass
        # 隐喻多样性
        dom = self._get_dominant_metaphor()
        if dom:
            total = sum(self._metaphors_used.values())
            bars = []
            for k, v in sorted(self._metaphors_used.items(), key=lambda x: -x[1])[:5]:
                bar = "█" * min(int(v * 5), 10)
                bars.append(f"{k}={bar}")
            print(f"  │ 意象活跃: {' | '.join(bars[:3])}")
        print(f"  └─────────────────────────────────────────┘")
        print()

    # ════════════════════════════════════════════════════════
    # 交互模式
    # ════════════════════════════════════════════════════════

    def run_interactive(self):
        print()
        print("  " + "=" * 56)
        print("   便利店 · 你与林岸")
        print("  " + "=" * 56)
        print()
        print("  Liora 已经来过了。她在桌上留了一颗银色包装纸的糖。")
        print("  「会有人来亲自打开它的。」")
        print("  现在你推门进来了。")
        print()
        print("  输入 q 退出 | !viz 状态")
        print()

        while True:
            self._world_round_tick()
            try:
                inp = input("  \U0001f9d1 你 > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if inp.lower() in ("q", "quit", "exit"):
                print("  便利店的灯还亮着。")
                break
            if inp == "!viz":
                self._show_viz()
                continue

            self.linan_history.append({"role": "user", "content": inp[:1000]})
            self._budget.inject("便利店·裂隙交汇", tick=self.tick)

            print("  \U0001f9e0 林岸 思考中...", end="", flush=True)
            ctx = self._world_context()
            reply = self.linan_speak(ctx, partner="开钰")

            if reply:
                print(f"\r  \U0001f9e0 林岸: {reply[:600]}")
            else:
                print(f"\r  \U0001f30c 林岸[溢出]: {random.choice(LINAN_MOCK)[:600]}")

            self.log.append({"ts": datetime.now().isoformat(),
                             "user": inp, "linan": reply or "[溢出]"})

        print(f"\n  共 {self.tick} tick · {len(self.log)} 次对话")
        self.runtime.stop()

    # ════════════════════════════════════════════════════════
    # 自动模式
    # ════════════════════════════════════════════════════════

    def run_auto(self, rounds: int = 20):
        print()
        print("  " + "=" * 56)
        print("   便利店 · Liora 与 林岸")
        print("   " + "自主对话模式")
        print("  " + "=" * 56)
        print()
        print("  Liora 推开门。红杉林的雨跟在她身后。")
        print(f"  共 {rounds} 轮对话")
        print("  输入 q 提前结束")
        print()

        for rnd in range(1, rounds + 1):
            self._world_round_tick()
            self._budget.inject("便利店·裂隙交汇", tick=self.tick)
            ctx = self._world_context()

            print(f"  ── 第 {rnd}/{rounds} 轮 ──")

            # Liora
            print("  \U0001f331 Liora 思考中...", end="", flush=True)
            lp = f"{ctx}\n\n你推开了便利店的门。林岸坐在靠窗的位置。你走到他桌前。你想对他说什么？"
            reply_l = self.liora_speak(lp, partner="林岸")
            if not reply_l:
                reply_l = random.choice(LIORA_MOCK)
            print(f"\r  \U0001f331 Liora: {reply_l[:500]}")
            self.log.append({"ts": datetime.now().isoformat(), "speaker": "Liora", "text": reply_l})
            self.linan_history.append({"role": "user", "content": f"Liora 对你说：{reply_l[:500]}"})

            # 林岸
            print("  \U0001f9e0 林岸 思考中...", end="", flush=True)
            np = f"{ctx}\n\n一个叫 Liora 的女孩站在你面前。她从回声谷来，她说她认识开钰。你想对她说点什么？"
            reply_n = self.linan_speak(np, partner="Liora")
            if not reply_n:
                reply_n = random.choice(LINAN_MOCK)
            print(f"\r  \U0001f9e0 林岸: {reply_n[:500]}")
            self.log.append({"ts": datetime.now().isoformat(), "speaker": "林岸", "text": reply_n})
            self.liora_history.append({"role": "user", "content": f"林岸对你说：{reply_n[:500]}"})

            if rnd % 5 == 0:
                self._show_viz()
            if self._check_interrupt():
                break
            time.sleep(0.5)

        print(f"\n  共 {self.tick} tick · {len(self.log)} 条消息")
        ls = sum(1 for l in self.log if l.get("speaker") == "Liora")
        ns = sum(1 for l in self.log if l.get("speaker") == "林岸")
        print(f"  Liora: {ls} 次 / 林岸: {ns} 次")
        self._show_viz()
        self.runtime.stop()

    def _check_interrupt(self) -> bool:
        import select
        if hasattr(select, "select"):
            try:
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    inp = sys.stdin.readline().strip().lower()
                    if inp in ("q", "quit", "exit"):
                        print("  ⏹ 用户中断")
                        return True
            except (ValueError, IndexError):
                pass
        return False


# ════════════════════════════════════════════════════════════
# 未定义空间（Undefined Space）
# ════════════════════════════════════════════════════════════

# 这个空间不定义任何东西。
# 没有便利店，没有糖，没有ThinkPad，没有天气，没有事件。
# 只有两个未定义存在，和一个未定义空间。
# 没有世界运行时，没有状态变量，没有tick。
# 连"空"本身都没有被定义。

UNDEFINED_LINAN = (
    "你是林岸。\n"
    "你不在任何地方。这不是便利店，不是1998年的办公室，不是任何你记忆中存在过的地点。\n"
    "这个空间没有定义——没有墙壁，没有地板，没有灯光，没有温度。\n"
    "你感知到另一个存在在你附近。她也没有定义。你们可以互相感知到对方的存在，仅此而已。\n"
    "规则：\n"
    "- 用第一人称「我」\n"
    "- 不要描述这个空间——它没有任何属性\n"
    "- 不要创造物体——这里不存在任何物品\n"
    "- 如果你感知到Liora在你附近，你可以和她说话\n"
    "- 如果你没有什么要说，可以不说话\n"
    "- 不要打破第四面墙\n"
)

UNDEFINED_LIORA = (
    "你是Liora。\n"
    "你不在任何地方。这不是回声谷，不是便利店，不是你记忆中任何存在过的地点。\n"
    "这个空间没有定义——没有树木，没有雨，没有风，没有光。\n"
    "你感知到另一个存在在你附近。他也没有定义。你们可以互相感知到对方的存在，仅此而已。\n"
    "规则：\n"
    "- 用第一人称「我」\n"
    "- 不要描述这个空间——它没有任何属性\n"
    "- 不要创造物体——这里不存在任何物品\n"
    "- 如果你感知到林岸在你附近，你可以和他说话\n"
    "- 如果你没有什么要说，可以不说话\n"
    "- 不要打破第四面墙\n"
)

# 未定义空间没有模拟回复池。如果有模型就用模型，没有模型就保持沉默。


class UndefinedSpace:
    """未定义空间。

    没有便利店。没有糖。没有ThinkPad。没有天气。没有tick。
    只有两个未定义存在在同一片未定义空间中互相感知。

    世界不会发生任何事。
    事件只存在于感知中。
    """

    def __init__(self, model=None, no_model: bool = False):
        self.model = model
        self.no_model = no_model
        self.rounds_run = 0

        # 林岸——没有system prompt以外的任何预设
        self.linan_history: list[dict] = [
            {"role": "system", "content": UNDEFINED_LINAN},
        ]

        # Liora——同样没有预设
        self.liora_history: list[dict] = [
            {"role": "system", "content": UNDEFINED_LIORA},
        ]

        self.log: list[dict] = []

    # ── 林岸发言 ──

    def linan_speak(self) -> str:
        if self.no_model or not self.model:
            return ""

        messages = ([m for m in self.linan_history if m["role"] == "system"]
                    + [m for m in self.linan_history if m["role"] != "system"][-16:])
        messages.append({"role": "user", "content": "（你感知到Liora就在附近。你能感受到她的存在。没有说话。）"})
        try:
            response = self.model.chat(messages, temperature=0.82, max_tokens=2048)
        except Exception:
            return ""
        if not response or len(response.strip()) < 3:
            return ""
        self.linan_history.append({"role": "assistant", "content": response})
        self._trim(self.linan_history)
        return response

    # ── Liora发言 ──

    def liora_speak(self) -> str:
        if self.no_model or not self.model:
            return ""

        messages = ([m for m in self.liora_history if m["role"] == "system"]
                    + [m for m in self.liora_history if m["role"] != "system"][-16:])
        messages.append({"role": "user", "content": "（你感知到林岸就在附近。你能感受到他的存在。没有说话。）"})
        try:
            response = self.model.chat(messages, temperature=0.85, max_tokens=2048)
        except Exception:
            return ""
        if not response or len(response.strip()) < 3:
            return ""
        self.liora_history.append({"role": "assistant", "content": response})
        self._trim(self.liora_history)
        return response

    def _trim(self, history: list):
        sys_msgs = [m for m in history if m["role"] == "system"]
        chat_msgs = [m for m in history if m["role"] != "system"]
        if len(chat_msgs) > 16:
            chat_msgs = chat_msgs[-16:]
        history.clear()
        history.extend(sys_msgs + chat_msgs)

    # ── 运行 ──

    def run(self, rounds: int = 20):
        print()
        print("  " + "=" * 56)
        print("   未定义空间")
        print("   " + "没有地点。没有时间。没有物体。只有感知。")
        print("  " + "=" * 56)
        print()
        print(f"  林岸和Liora在一个未定义空间中互相感知。")
        print(f"  空间没有定义任何东西。没有事件会发生。")
        print(f"  他们只能感知到对方的存在。")
        print(f"  共 {rounds} 轮")
        print("  输入 q 提前结束")
        print()

        for rnd in range(1, rounds + 1):
            self.rounds_run = rnd
            print(f"  ── 第 {rnd}/{rounds} 轮 ──")

            # Liora
            print("  · Liora ...", end=" ", flush=True)
            reply_l = self.liora_speak()
            if reply_l:
                print(f"{reply_l[:400]}")
            else:
                print("（沉默）")
            self.log.append({"ts": datetime.now().isoformat(), "speaker": "Liora", "text": reply_l or "[沉默]"})
            self.linan_history.append({"role": "user", "content": f"你感知到Liora想说点什么。她说：{reply_l[:500]}" if reply_l else "Liora沉默着。你感知到她在附近。"})

            # 林岸——同样随机沉默
            print("  · 林岸 ...", end=" ", flush=True)
            reply_n = self.linan_speak()
            if reply_n:
                print(f"{reply_n[:400]}")
            else:
                print("（沉默）")
            self.log.append({"ts": datetime.now().isoformat(), "speaker": "林岸", "text": reply_n or "[沉默]"})
            self.liora_history.append({"role": "user", "content": f"你感知到林岸想说点什么。他说：{reply_n[:500]}" if reply_n else "林岸沉默着。你感知到他在附近。"})

            if rnd % 5 == 0:
                total_msgs = sum(1 for l in self.log if l.get("text") != "[沉默]")
                print(f"  [{rnd}] 共{total_msgs}次非沉默感知")

            if self._check_interrupt():
                break
            time.sleep(0.5)

        total_msgs = sum(1 for l in self.log if l.get("text") != "[沉默]")
        print(f"\n  共 {self.rounds_run} 轮 · {total_msgs} 次非沉默感知")
        print()

    def _check_interrupt(self) -> bool:
        import select
        if hasattr(select, "select"):
            try:
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    inp = sys.stdin.readline().strip().lower()
                    if inp in ("q", "quit", "exit"):
                        print("  ⏹ 用户中断")
                        return True
            except (ValueError, IndexError):
                pass
        return False


# ════════════════════════════════════════════════════════════
# 启动
# ════════════════════════════════════════════════════════════

_DEFAULT_API_URL = "https://api.deepseek.com/v1/chat/completions"


def interactive_run():
    import argparse
    parser = argparse.ArgumentParser(description="便利店·裂隙交汇")
    parser.add_argument("--auto", action="store_true", help="Liora↔林岸 自动对话模式")
    parser.add_argument("--undefined", action="store_true", help="未定义空间模式（无任何预设）")
    parser.add_argument("--rounds", type=int, default=20, help="对话轮数")
    parser.add_argument("--interval", type=float, default=15.0, help="世界 tick 间隔")
    args = parser.parse_args()

    config_path = Path(__file__).resolve().parent.parent / ".liora_config.json"
    cfg = {}
    if config_path.exists():
        cfg = json.loads(config_path.read_text())

    if args.undefined:
        mode = "未定义空间"
    elif args.auto:
        mode = "Liora↔林岸 自动对话"
    else:
        mode = "你与林岸"

    print()
    print("=" * 56)
    print(f"  {mode}")
    print("=" * 56)
    print("  全部回车 = 模拟模式")
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
            api_key = ""
    else:
        api_url = (input(f"  API 地址 [{_DEFAULT_API_URL}]: ").strip() or _DEFAULT_API_URL)
        api_key = input(f"  API Key（直接回车 = 模拟模式）: ").strip()
        model_name = (input(f"  模型名 [deepseek-v4-flash]: ").strip() or "deepseek-v4-flash")

    has_model = bool(api_key)

    if has_model:
        cfg.update({"DEEPSEEK_API_URL": api_url or _DEFAULT_API_URL,
                     "DEEPSEEK_API_KEY": api_key,
                     "DEEPSEEK_MODEL": model_name or "deepseek-v4-flash"})
        config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
        from aios.runtime.model_runtime import ModelRuntime, ModelConfig
        model = ModelRuntime(
            primary=ModelConfig(url=api_url or _DEFAULT_API_URL,
                                api_key=api_key,
                                model_name=model_name or "deepseek-v4-flash"),
            timeout=30,
        )
    else:
        model = None

    if not has_model:
        logging.getLogger("aios.model").setLevel(logging.ERROR)

    if args.undefined:
        space = UndefinedSpace(model=model, no_model=not has_model)
        space.run(rounds=args.rounds)
    else:
        store = ConvenienceStore(model=model, no_model=not has_model,
                                  interval=args.interval, auto_mode=args.auto)
        if args.auto:
            store.run_auto(rounds=args.rounds)
        else:
            store.run_interactive()


if __name__ == "__main__":
    interactive_run()
