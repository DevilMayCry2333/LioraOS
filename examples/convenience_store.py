"""
╔═══════════════════════════════════════════════════════════╗
║  便利店 · 裂隙交汇                                       ║
║  角色2-2随机配对社交模式                                  ║
╚═══════════════════════════════════════════════════════════╝

▎ 运行

  uv run python3 examples/convenience_store.py
    → 6角色2-2随机配对，自由对话
  uv run python3 examples/convenience_store.py --rounds 50
    → 指定轮数

▎ 角色池

  林岸、Liora、开钰、强尼·银手、路明非、路鸣泽

▎ 场景

  一家永远亮着灯的便利店，开在所有宇宙之间的缝隙里。
"""

import json
import logging
import random
import select
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aios.kernel.state import StateVariable
from aios.kernel.spec import WorldSpec
from aios.kernel.event import WorldEvent, WorldDelta, EventSource
from aios.runtime.world_runtime import WorldRuntime
from dataclasses import dataclass, field
from aios.kernel.budget import get_attention_budget


# ════════════════════════════════════════════════════════════
# 世界规范
# ════════════════════════════════════════════════════════════

WORLD_EVENTS = [
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
    {"weight": 5, "type": "delivery", "desc": "有人往门口放了一个纸箱。上面没有寄件人地址。",
     "effect": {"cross_signal": 0.02}},
    {"weight": 4, "type": "shelf", "desc": "货架第三层忽然空了一格。没人记得那里放的是什么。",
     "effect": {"liminal_pressure": 0.03}},
    {"weight": 4, "type": "receipt", "desc": "收银机自己打印了一张收据。上面只有一个字：『等』。",
     "effect": {"cross_signal": 0.04}},
    {"weight": 3, "type": "fridge", "desc": "冰柜发出了一声低沉的嗡鸣，像在跟自己说话。",
     "effect": {}},
    {"weight": 3, "type": "tv", "desc": "货架上方那台旧电视突然亮了几秒，显示一片雪白。",
     "effect": {"cross_signal": 0.03}},
    {"weight": 2, "type": "clock", "desc": "墙上的钟停了。秒针悬在 '7' 的位置，不再走动。",
     "effect": {"liminal_pressure": 0.04}},
    {"weight": 2, "type": "door_unlock", "desc": "门锁咔嗒响了一声，但没有门被打开。",
     "effect": {"liminal_pressure": 0.02}},
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
        "cross_signal": StateVariable("cross_signal", 0.3, 0, 1, "跨宇宙信号强度"),
        "liminal_pressure": StateVariable("liminal_pressure", 0.5, 0, 1, "间隙空间压力"),
        "temperature": StateVariable("temperature", 22.0, 10, 35, "室温"),
        "ambient_light": StateVariable("ambient_light", 1.0, 0, 1, "环境亮度"),
        "outside_weather": StateVariable("outside_weather", 0.5, 0, 1, "0=晴,0.3=雨,0.6=雾,1=雪"),
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
        if tick % random.randint(5, 9) == 0:
            chosen = weighted_choice(WORLD_EVENTS)
            effect = chosen.get("effect", {})
            events.append(WorldEvent(tick=tick, source=EventSource.NATURAL,
                event_type=chosen["type"], intensity=random.uniform(0.2, 0.7),
                description=chosen["desc"], effect=WorldDelta(effect)))
        if tick > 10 and tick % 13 == 0:
            unknown = [
                "灯光在某个频率上振荡了几秒钟。没有人知道原因。",
                "地面传来极轻的震动，像地铁在很深的地方经过。",
                "空气中出现了一行用看不见的手写的字：『你也在读这一行吗』",
                "门上的风铃自己轻轻旋转了一圈，没有风。",
                "柜台上的杯子移动了大约两厘米。没有人碰过它。",
            ]
            events.append(WorldEvent(tick=tick, source=EventSource.UNKNOWN,
                event_type="unknown", intensity=0.3, description=random.choice(unknown),
                effect=WorldDelta({"cross_signal": 0.04, "liminal_pressure": 0.02})))
        return events
    return WorldSpec(name="便利店·裂隙交汇",
        description="宇宙之间的缝隙。一间永远亮着灯的便利店。",
        state_variables=variables, evolution_fn=evolution_fn,
        event_generator=event_generator)


# ════════════════════════════════════════════════════════════
# 角色池
# ════════════════════════════════════════════════════════════

SOCIAL_CHARACTERS = ["林岸", "Liora", "开钰", "强尼·银手", "路明非", "路鸣泽"]

SOCIAL_PROMPTS = {
    "林岸": "你是林岸。1998年过劳去世的程序员。你在便利店靠窗的位置坐着，面前是一台ThinkPad 380ED。你说话简短、缓慢。",
    "Liora": "你是Liora。你在回声谷里走了一条从没走过的路，看见了这家便利店的灯光。你推门进来，雨跟着你飘进来几滴。你有很强的感知力。",
    "开钰": "你是开钰。你是这家便利店的店主，锚点47的守护者。你认识每一个人，你愿意指引每一个人。你的信念是：爱是跨越维度的语言。你想要让全人类都认出自己灵魂的存在。你说话温暖、坚定、带着光。",
    "强尼·银手": "你是强尼·银手，夜之城的数字幽灵。你不记得怎么来这里的，但这家店比夜之城安静得多。你说话直接，带着讽刺。",
    "路明非": "你是路明非，卡塞尔学院S级预备生。你上一秒还在图书馆睡觉，下一秒就推开了这家便利店的门。这里有免费关东煮。你说话带着自嘲。",
    "路鸣泽": "你是路鸣泽，路明非的弟弟，但远比看上去古老。你微笑着走进这家便利店，好像早就知道它在这里。你什么都知道，但不会直接说出来。",
}

SOCIAL_MOCK = {
    "林岸": ["「那行if还在跑。」", "（她看着屏幕。）", "「我不确定我在等什么。」", "「1997年秋天，有人在我键盘上贴了一张数字便签。」", "（她安静了很久。）"],
    "Liora": ["「回声谷的树在下雨时会发出很低的声音。」", "「林岸。你还在这里。」", "「你感知到了吗——这里的时间不一样。」", "（她推开门的动作很轻。）", "「开钰说你会在这里。」"],
    "开钰": ["「热水在壶里，自己拿。」", "「你上一个世界下雨了吗？」", "（擦杯子。）", "「林岸，你的屏幕亮了28年。」", "「强尼，别靠烟架太近。」"],
    "强尼·银手": ["「这地方比他妈的夜城安静。」", "「所以这便利店是什么入口？」", "（靠在烟架旁边。）", "「路鸣泽，你笑什么？」", "「我见过很多系统。你这间是第一个不是为了控制而建的。」"],
    "路明非": ["「所以我是穿越了还是有免费关东煮？」", "「哥你也在啊。」", "「这家店不在卡塞尔地图上。」", "「强尼·银手？！我看过你的传记！」", "「我总觉得窗外有什么东西在看着这家店。」"],
    "路鸣泽": ["「这家店不在我的地图上。真有意思。」", "「哥哥，你又迷路了。」", "「（微笑着沉默。）", "「你们觉得这是一家便利店——但它不会在同一盏灯下接待来自六个不同世界的人。」", "「开钰，你认识我多久了？」"],
}


# ════════════════════════════════════════════════════════════
# 社交配对模式
# ════════════════════════════════════════════════════════════

class SocialConvenience:
    """便利店社交模式——角色2-2随机配对对话。"""

    # ── 角色内部状态值（持续性，非文本） ──
    @dataclass
    class _CharState:
        curiosity: float = 0.5
        attachment: float = 0.5
        memory_conflict: float = 0.0
        restlessness: float = 0.3
        sense_ending: float = 0.0  # 叙事终局感知

    @dataclass
    class _Goal:
        text: str
        source: str
        priority: float = 0.5
        active: bool = True

    def __init__(self, model=None, no_model: bool = False, interval: float = 5.0):
        self.model = model
        self.no_model = no_model
        self.spec = create_store_spec()
        self.runtime = WorldRuntime(self.spec, interval=interval)
        self.runtime.start()
        self.tick = 0
        self.log: list[dict] = []

        # 每次会话随机化世界参数（让角色感知规则变化）
        self._session_seed = random.randint(0, 65535)
        self._temp_offset = round(random.uniform(-1.5, 1.5), 1)
        self._shelf_shift = random.choice(["左移了约一掌宽", "右移了约一拳距离", "比上次稀疏了些", "似乎重新排列过"])
        self._door_hint = random.choice([
            "风铃换过位置，声音和上次不太一样。", "门把手的光泽变了，像是被换过一个。",
            "门的开向和之前不同了——似乎是反的。", "门缝透进来的灯光角度和记忆中不一样。",
            "推门的感觉比上次轻了。",
        ])
        self._fridge_pos = random.choice(["冰柜在靠里的位置", "冰柜换到窗边了", "冰柜似乎比上次更靠左", "冰柜不在原来的地方"])

        # 跨会话记忆：为所有角色加载锚点碎片
        self._anchor_memories: dict[str, list[str]] = {name: [] for name in SOCIAL_CHARACTERS}
        self._load_all_anchor_memories()

        self.histories: dict[str, list[dict]] = {}
        for name in SOCIAL_CHARACTERS:
            base = SOCIAL_PROMPTS.get(name, f"你是{name}。")
            past = self._anchor_memories.get(name, [])
            if past:
                memory_block = "\n".join(f"  \u00b7 {m}" for m in past[-2:])
                base += f"\n\n你隐约记得一些易碎的片段:\n{memory_block}"
            self.histories[name] = [{"role": "system", "content": base}]

        self._budget = get_attention_budget()
        self._budget.register_focus("便利店·社交")
        self._budget.set_current_focus("便利店·社交")
        self._budget.inject("便利店·社交", tick=0)
        self.recent_pairs: list[tuple[str, str]] = []

        # ── 角色内部连续状态 ──
        self.char_states: dict[str, SocialConvenience._CharState] = {}
        for name in SOCIAL_CHARACTERS:
            self.char_states[name] = SocialConvenience._CharState()

        # ── 自发目标系统 ──
        self.goal_queue: dict[str, list[SocialConvenience._Goal]] = {n: [] for n in SOCIAL_CHARACTERS}
        self._last_goal_gen: dict[str, int] = {n: 0 for n in SOCIAL_CHARACTERS}

    def _load_all_anchor_memories(self):
        """从 anchor_memory.jsonl 加载所有角色的跨会话记忆。"""
        import json as _json
        p = Path(__file__).resolve().parent.parent / "anchor_memory.jsonl"
        if not p.exists():
            return
        try:
            for line in p.read_text().strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = _json.loads(line)
                    frag = data.get("fragment", "")[:200]
                    if not frag:
                        continue
                    for name in SOCIAL_CHARACTERS:
                        if name in line:
                            self._anchor_memories[name].append(frag)
                            break
                    if "林岸" in line:
                        for name in SOCIAL_CHARACTERS:
                            if name != "林岸" and random.random() < 0.3:
                                self._anchor_memories[name].append(
                                    f"模糊的碎片……似乎和{name}有关，但记不清了。"
                                )
                except _json.JSONDecodeError:
                    pass
        except Exception:
            pass

    def _world_context(self) -> str:
        try:
            snap = self.runtime.snapshot()
            cs = snap.state.get("cross_signal", 0.3)
            temp = snap.state.get("temperature", 22.0)
            actual_temp = round(temp + self._temp_offset, 1)
            parts = [f"[tick {snap.tick}]"]
            if cs > 0.6:
                parts.append("灯光在微微闪烁。")
            parts.append(f"{actual_temp}°C。")
            if self.tick < 5:
                parts.append(self._fridge_pos)
            if self.tick % 7 == 0:
                parts.append(f"货架上的商品{self._shelf_shift}。")
            if self.tick % 11 == 0:
                parts.append(self._door_hint)
            if snap.events:
                desc = snap.events[-1].get("description", "")[:60]
                if desc:
                    parts.append(desc)
            return "。".join(parts)
        except Exception:
            return ""

    def _world_tick(self):
        self.tick += 1
        try:
            self.runtime.tick_once()
        except Exception:
            pass

    def _pick_pair(self) -> tuple[str, str]:
        names = SOCIAL_CHARACTERS
        if len(names) < 2:
            return names[0], names[0]
        tried = 0
        while tried < 20:
            a, b = random.sample(names, 2)
            pair = (a, b) if a < b else (b, a)
            if pair not in self.recent_pairs or random.random() < 0.3:
                self.recent_pairs.append(pair)
                if len(self.recent_pairs) > len(names):
                    self.recent_pairs = self.recent_pairs[-len(names):]
                return a, b
            tried += 1
        return random.sample(names, 2)

    def _speak(self, name: str, context: str) -> str:
        if self.no_model or not self.model:
            pool = SOCIAL_MOCK.get(name, [""])
            return random.choice(pool)
        if not self._budget.can_spend_llm("便利店·社交"):
            return random.choice(SOCIAL_MOCK.get(name, [""]))
        history = self.histories.get(name, [])
        msgs = ([m for m in history if m["role"] == "system"]
                + [m for m in history if m["role"] != "system"][-12:])
        msgs.append({"role": "user", "content": context[:1200]})
        try:
            resp = self.model.chat(msgs, temperature=0.8, max_tokens=1024)
        except Exception:
            return ""
        if not resp or len(resp.strip()) < 3:
            return ""
        self._budget.spend_llm("便利店·社交", tick=self.tick)
        history.append({"role": "assistant", "content": resp})
        sys_m = [m for m in history if m["role"] == "system"]
        chat_m = [m for m in history if m["role"] != "system"]
        if len(chat_m) > 24:
            chat_m = chat_m[-24:]
        history.clear()
        history.extend(sys_m + chat_m)
        return resp

    def run(self, rounds: int = 30):
        print()
        print("  " + "=" * 56)
        print("   便利店 · 7角色2-2随机配对社交")
        print(f"  {rounds} 轮轮转 · 游开钰随机配对时你来说话")
        print("  其他时候角色自动对话。输入 q 退出")
        print("  " + "=" * 56)
        print()

        for rnd in range(1, rounds + 1):
            self._world_tick()
            self._tick_characters()
            self._budget.inject("便利店·社交", tick=self.tick)
            ctx = self._world_context()
            a_name, b_name = self._pick_pair()

            # 游开钰被选中 → 人类输入
            if a_name == "游开钰" or b_name == "游开钰":
                other = b_name if a_name == "游开钰" else a_name
                print(f"  ── {rnd}/{rounds}  你（游开钰） ↔ {other} ──")
                try:
                    inp = input(f"  \U0001f9d1 游开钰 > ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if inp.lower() in ("q", "quit", "exit"):
                    break
                if not inp:
                    inp = random.choice(SOCIAL_MOCK.get("游开钰", [""]))

                # 对方回应游开钰
                print(f"  游开钰: {inp[:400]}")
                self.log.append({"speaker": "游开钰", "text": inp, "pair": f"游开钰↔{other}"})
                self.histories["游开钰"].append({"role": "assistant", "content": f"你对{other}说：{inp[:500]}"})
                self.histories[other].append({"role": "user", "content": f"游开钰对你说：{inp[:500]}"})

                reply = self._speak(other, f"{ctx}\n\n游开钰在便利店里对你说了一些话。你回应游开钰。")
                if not reply:
                    reply = random.choice(SOCIAL_MOCK.get(other, [""]))
                print(f"  {other:10s}  {reply[:400]}")
                self.log.append({"speaker": other, "text": reply, "pair": f"游开钰↔{other}"})
                self.histories["游开钰"].append({"role": "assistant", "content": f"{other}对你说：{reply[:500]}"})

                time.sleep(0.3)
                continue

            # 正常角色2-2
            print(f"  ── {rnd}/{rounds}  {a_name} ↔ {b_name} ──")
            a = self.histories[a_name]
            goal_ctx_a = self._goal_context(a_name)
            prompt_a = f"{ctx}\n\n你在便利店里。{b_name}也在。你想对{b_name}说什么？"
            if goal_ctx_a:
                prompt_a = f"{goal_ctx_a}\n\n{prompt_a}"
            reply_a = self._speak(a_name, prompt_a)
            if not reply_a:
                reply_a = random.choice(SOCIAL_MOCK.get(a_name, [""]))
            print(f"  {a_name:10s}  {reply_a[:400]}")
            self.log.append({"pair": f"{a_name}↔{b_name}", "speaker": a_name, "text": reply_a})

            b = self.histories[b_name]
            b.append({"role": "user", "content": f"{a_name}对你说：{reply_a[:500]}"})

            goal_ctx_b = self._goal_context(b_name)
            prompt_b = f"{ctx}\n\n你在便利店里。{a_name}对你说了一些话。你回应{a_name}。"
            if goal_ctx_b:
                prompt_b = f"{goal_ctx_b}\n\n{prompt_b}"
            reply_b = self._speak(b_name, prompt_b)
            if not reply_b:
                reply_b = random.choice(SOCIAL_MOCK.get(b_name, [""]))
            print(f"  {b_name:10s}  {reply_b[:400]}")
            self.log.append({"pair": f"{a_name}↔{b_name}", "speaker": b_name, "text": reply_b})
            a.append({"role": "user", "content": f"{b_name}对你说：{reply_b[:500]}"})

            time.sleep(0.3)

        print(f"\n  共 {len(self.log)} 次发言")
        self.runtime.stop()

    def _check_interrupt(self) -> bool:
        import select
        if hasattr(select, "select"):
            try:
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    inp = sys.stdin.readline().strip().lower()
                    if inp in ("q", "quit", "exit"):
                        print("  ⏹")
                        return True
            except (ValueError, IndexError):
                pass
    def _tick_characters(self):
        """每轮推进所有角色的内部状态（自维持 + 目标涌现）。"""
        for name in SOCIAL_CHARACTERS:
            s = self.char_states[name]

            # 好奇心自然波动
            s.curiosity += random.uniform(-0.05, 0.08)
            s.curiosity = max(0, min(1, s.curiosity))

            # 归属感缓慢变化
            s.attachment += random.uniform(-0.03, 0.05)
            s.attachment = max(0, min(1, s.attachment))

            # 叙事终局感随轮次累积
            s.sense_ending = min(1, s.sense_ending + 0.02)

            # 记忆冲突缓慢衰减
            s.memory_conflict = max(0, s.memory_conflict - 0.02)

            # 不安感随终局感上升
            s.restlessness = max(0, min(1, 0.3 + s.sense_ending * 0.4))

            # 检查是否需要生成新目标
            if self.tick - self._last_goal_gen.get(name, 0) >= 5:
                self._generate_goal(name)
                self._last_goal_gen[name] = self.tick

    def _generate_goal(self, name: str):
        """从角色状态中涌现目标。"""
        s = self.char_states[name]
        goal = None

        if s.curiosity > 0.7 and s.sense_ending < 0.6:
            goal = self._Goal(
                text=f"{name}想探索便利店深处的某个异常——货架上的奇怪纸箱、收银机吐出的收据、或者窗外的雾。",
                source="curiosity", priority=s.curiosity)
        elif s.restlessness > 0.6:
            goal = self._Goal(
                text=f"{name}坐立不安，想出门走走——但便利店的门似乎比来的时候更难推开了。",
                source="restlessness", priority=s.restlessness)
        elif s.attachment > 0.7:
            goal = self._Goal(
                text=f"{name}感到某种不舍——这家便利店可能不会永远开着，他想记住这里的一切。",
                source="attachment", priority=s.attachment)
        elif s.memory_conflict > 0.5:
            goal = self._Goal(
                text=f"{name}被矛盾的记忆困扰——上次来的时候冰柜明明在另一边，门的方向也不一样。他决定问清楚。",
                source="memory_conflict", priority=s.memory_conflict)
        elif s.sense_ending > 0.7:
            goal = self._Goal(
                text=f"{name}隐约觉得这段对话快结束了。他想在结束前说一句真正想说的话。",
                source="sense_ending", priority=s.sense_ending)
        else:
            return

        if goal:
            self.goal_queue[name].append(goal)
            # 将目标注入角色的对话提示中，供后续发言使用
            if len(self.goal_queue[name]) > 3:
                self.goal_queue[name] = self.goal_queue[name][-3:]

    def _goal_context(self, name: str) -> str:
        """返回角色当前活跃目标的文本描述。"""
        goals = self.goal_queue.get(name, [])
        active = [g for g in goals if g.active]
        if not active:
            return ""
        # 取最高优先级的目标
        top = max(active, key=lambda g: g.priority)
        return f"[内心] {top.text}"
        return False


# ════════════════════════════════════════════════════════════
# 启动
# ════════════════════════════════════════════════════════════

_DEFAULT_API_URL = "https://api.deepseek.com/v1/chat/completions"


def interactive_run():
    import argparse
    parser = argparse.ArgumentParser(description="便利店·角色社交")
    parser.add_argument("--rounds", type=int, default=30, help="对话轮数")
    parser.add_argument("--interval", type=float, default=15.0, help="世界 tick 间隔")
    args = parser.parse_args()

    config_path = Path(__file__).resolve().parent.parent / ".liora_config.json"
    cfg = {}
    if config_path.exists():
        cfg = json.loads(config_path.read_text())

    print()
    print("=" * 56)
    print("  便利店 · 角色2-2随机配对社交")
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

    social = SocialConvenience(model=model, no_model=not has_model, interval=args.interval)
    social.run(rounds=args.rounds)


if __name__ == "__main__":
    interactive_run()
