"""SocialWorldApp — 多角色自主社交世界模板。

没有人类输入，角色们自己对话、关系积累、世界演化。

与 WorldApp 共享同一套钩子接口（describe_world, resolve_effects, character_config...）
只是主循环不同：配对 → A说话 → B回应 → assimilate → 下一轮。
"""

from __future__ import annotations

import json
import logging
import random
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from aios.runtime.model_runtime import ModelRuntime
from aios.runtime.world_runtime import WorldRuntime
from aios.worlds.liora.mind import LioraMind

from .base import WorldApp

logger = logging.getLogger("aios.template.social")

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

MODEL_TIMEOUT = 30
MAX_HISTORY = 12


# ── SIGALRM 超时 ──
class ModelCallTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise ModelCallTimeout(f"模型调用超过 {MODEL_TIMEOUT}s")


signal.signal(signal.SIGALRM, _timeout_handler)


# ══════════════════════════════════════════════════════════════
# 关键词吸收（可被世界作者覆盖）
# ══════════════════════════════════════════════════════════════

DEFAULT_TOPIC_WORDS: dict[str, str] = {
    "相信": "belief", "改变": "change", "记忆": "memory",
    "信任": "trust", "关系": "relationship", "沉默": "silence",
    "自由": "freedom", "反抗": "rebellion", "数据": "data",
    "人性": "humanity", "心": "heart", "恐惧": "fear",
}

DEFAULT_SIGNAL_WORDS: dict[str, str] = {
    "我决定": "conviction", "我意识到": "insight",
    "我改变": "change", "我仍然": "persistence",
    "我注意到": "observation", "我感受到": "feeling",
    "我相信": "belief", "我不再": "shift",
}

DEFAULT_RELATION_WORDS: dict[str, str] = {
    "谢谢": "gratitude", "我懂": "empathy",
    "我同意": "agreement", "我不": "disagreement",
    "我信任": "trust", "我需要": "need",
}


def assimilate_conversation(mind: LioraMind, partner_name: str,
                            own_reply: str, partner_reply: str,
                            tick: int,
                            topic_words: dict[str, str] | None = None,
                            signal_words: dict[str, str] | None = None,
                            relation_words: dict[str, str] | None = None):
    """将对话吸收为系统状态更新。"""
    topic_words = topic_words or DEFAULT_TOPIC_WORDS
    signal_words = signal_words or DEFAULT_SIGNAL_WORDS
    relation_words = relation_words or DEFAULT_RELATION_WORDS

    combined = (own_reply + partner_reply).lower()
    topics_detected = [kw for kw in topic_words if kw in combined]
    topic_set = set(topic_words[kw] for kw in topics_detected)

    # 信念信号
    conviction_signals = [word for word in signal_words if word in own_reply]
    if conviction_signals:
        sig_type = signal_words[conviction_signals[0]]
        imp = 0.7 if sig_type in ("conviction", "change", "insight") else 0.5
        desc = f"{mind.name} 表达了{conviction_signals[0]}"
        if topic_set:
            desc += f"（关于{'、'.join(list(topic_set)[:2])}）"
        mind.add_episode(desc, tick=tick,
                         participants=[mind.name, partner_name] if partner_name else None,
                         importance=min(1.0, imp))

    # 关系信号
    rel_signals = [word for word in relation_words if word in combined]
    trust_delta = 0.0
    for sig in rel_signals:
        rt = relation_words[sig]
        if rt in ("gratitude", "empathy", "trust"): trust_delta += 0.03
        elif rt == "agreement": trust_delta += 0.02
        elif rt == "disagreement": trust_delta -= 0.02
        elif rt == "need": trust_delta += 0.01
    if partner_name and abs(trust_delta) > 0:
        mind.relate(partner_name, trust=trust_delta, curiosity=0.01, tick=tick)

    # 共同经历
    if topic_set and partner_name and trust_delta >= 0:
        mind.share_history(partner_name, f"讨论了{'、'.join(list(topic_set)[:2])}")

    # 沉默
    if not own_reply or "沉默" in own_reply:
        mind.add_episode(f"{mind.name} 选择了沉默", tick=tick, importance=0.3)


# ══════════════════════════════════════════════════════════════
# 社交居民类
# ══════════════════════════════════════════════════════════════

class SocialResident:
    """社交世界的 AI 居民。"""

    def __init__(self, name: str, app: WorldApp):
        self.name = name
        self.model = app.model
        self.app = app
        self.mind = LioraMind(name)
        app._apply_character_config(self.mind, name)

        persona = ""
        if name in app.character_config:
            persona = app.character_config[name].get("persona", "")
        if not persona:
            persona = app.mind.identity.style if name == app.character_name else f"你是 {name}。直接说话。"
        self.history: list[dict] = [
            {"role": "system", "content": persona}
        ]
        self._last_elapsed: float = 0

    def hear_world(self, context: str):
        if context.strip():
            self.history.append({"role": "user", "content": context[:2000]})

    def hear_speaker(self, speaker: str, message: str, tick: int = -1):
        self.mind.relate(speaker, trust=0.03, curiosity=0.02, tick=tick)
        self.history.append({"role": "user", "content": f"{speaker} 说：{message[:500]}"})

    def build_messages(self, partner_name: str = "") -> list[dict]:
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        messages = sys_msgs + chat_msgs[-MAX_HISTORY * 2:]

        rel = self.mind.relationship_summary()
        if rel:
            messages.append({"role": "user", "content": f"（{rel}）"})
        if partner_name:
            shared = self.mind.recall_episodes_by_participant(partner_name, n=2)
            if shared:
                lines = [f"你和{partner_name}曾经："]
                for e in shared:
                    lines.append(f"  · {e.description[:80]}")
                messages.append({"role": "user", "content": "\n".join(lines)})

        growth = self.mind.growth_narrative()
        if growth:
            messages.append({"role": "user", "content": growth})

        messages.append({"role": "user", "content": "现在直接说出你想说的话："})
        return messages

    def speak(self, partner_name: str = "") -> str:
        if not self.model:
            return self.app.mock_reply(self.name)

        messages = self.build_messages(partner_name=partner_name)
        t0 = time.time()
        signal.alarm(MODEL_TIMEOUT)
        try:
            response = self.model.chat(messages, temperature=0.75, max_tokens=512)
            self._last_elapsed = time.time() - t0
        except ModelCallTimeout:
            self._last_elapsed = time.time() - t0
            return ""
        except Exception as e:
            self._last_elapsed = time.time() - t0
            logger.warning("%s model error: %s", self.name, e)
            return ""
        finally:
            signal.alarm(0)

        if not response or len(response.strip()) < 3:
            return ""
        if re.findall(r'(.)\1{19,}', response):
            return ""
        self.history.append({"role": "assistant", "content": response})
        self._trim_history()
        return response

    def _trim_history(self):
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        keep = MAX_HISTORY * 2
        if len(chat_msgs) > keep:
            chat_msgs = chat_msgs[-keep:]
        self.history = sys_msgs + chat_msgs


# ══════════════════════════════════════════════════════════════
# SocialWorldApp
# ══════════════════════════════════════════════════════════════

class SocialWorldApp(WorldApp):
    """多角色自主社交世界模板。

    继承 WorldApp 的所有钩子，主循环替换为多角色对话模式。
    不需要人类输入，角色自主对话 + 世界演化。

    可选覆盖：
      topic_words / signal_words / relation_words — 关键词吸收表
      assimilate_conversation() — 完全替换吸收逻辑
    """

    topic_words: dict = DEFAULT_TOPIC_WORDS
    signal_words: dict = DEFAULT_SIGNAL_WORDS
    relation_words: dict = DEFAULT_RELATION_WORDS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.residents: dict[str, SocialResident] = {}
        self.recent_pairs: list[tuple[str, str]] = []
        self.log: list[dict] = []
        self.history_entries: list[dict] = []

    def run(self):
        """启动世界并进入社交循环。"""
        self.runtime.start()
        self.on_start()

        # 创建居民
        for name in self.characters:
            self.residents[name] = SocialResident(name, self)

        print(f"\n🌍 {self.spec.name}")
        print(f"   👥 {', '.join(self.characters)}")
        print(f"   模型: {'模拟' if self.no_model else (self.model._primary.model_name if self.model else '无')}")
        print()

        rounds = getattr(self, '_rounds', 10)
        self._social_loop(rounds)

        self._print_summary()
        self.on_stop()
        self.runtime.stop()

    def _social_loop(self, rounds: int):
        """社交主循环。"""
        print(f"  {'='*56}")
        print(f"  🗣️  {rounds} 轮自由对话")
        print(f"  {'='*56}\n")

        for rnd in range(1, rounds + 1):
            # 消耗积压 tick
            current_tick = self.runtime.tick
            while self._last_world_tick < current_tick:
                self._last_world_tick += 1
                self._social_tick(self._last_world_tick)

            # 选一对
            a_name, b_name = self._pick_pair()
            a = self.residents[a_name]
            b = self.residents[b_name]

            print(f"  {'─'*56}")
            print(f"  第 {rnd}/{rounds} 轮 | {a_name} ↔ {b_name}")
            print(f"  {'─'*56}")

            # 双方感知世界
            snap = self.runtime.snapshot()
            world_ctx = self.describe_world(snap.state)
            extra = self.extra_context(a.mind)
            if extra:
                world_ctx += f"\n\n{extra}"
            a.hear_world(world_ctx)
            b.hear_world(world_ctx)

            # A 发言
            if random.random() < 0.12:
                reply_a = ""
                print(f"\r  🧠 {a_name} 选择沉默")
            else:
                print(f"  🧠 {a_name} 思考中...", end="", flush=True)
                reply_a = a.speak(partner_name=b_name)
                if reply_a:
                    el = f" ({a._last_elapsed:.0f}s)" if a._last_elapsed else ""
                    print(f"\r  🧠 {a_name}{el}: {reply_a[:100]}{'...' if len(reply_a) > 100 else ''}")
                    self._log(a_name, reply_a)
                else:
                    print(f"\r  ⏭️  {a_name} 沉默")
                    reply_a = ""

            # B 听到 A → 回应
            if reply_a:
                b.hear_speaker(a_name, reply_a, tick=rnd)
            if random.random() < 0.12:
                reply_b = ""
                print(f"\r  🧠 {b_name} 选择沉默")
            else:
                print(f"  🧠 {b_name} 思考中...", end="", flush=True)
                reply_b = b.speak(partner_name=a_name)
                if reply_b:
                    el = f" ({b._last_elapsed:.0f}s)" if b._last_elapsed else ""
                    print(f"\r  🧠 {b_name}{el}: {reply_b[:100]}{'...' if len(reply_b) > 100 else ''}")
                    self._log(b_name, reply_b)
                else:
                    print(f"\r  ⏭️  {b_name} 沉默")
                    reply_b = ""

            if reply_b:
                a.hear_speaker(b_name, reply_b, tick=rnd)

            # 吸收
            assimilate_conversation(a.mind, b_name, reply_a or "", reply_b or "", rnd,
                                    self.topic_words, self.signal_words, self.relation_words)
            assimilate_conversation(b.mind, a_name, reply_b or "", reply_a or "", rnd,
                                    self.topic_words, self.signal_words, self.relation_words)

            # 自主演化
            for res in self.residents.values():
                res.mind.tick_autonomous(1)
                if rnd > 1 and rnd % 5 == 0:
                    res.mind.auto_reflect(tick=rnd)

            time.sleep(0.3)

    def _social_tick(self, tick: int):
        """单 tick 社交世界推进。"""
        state_vars = self.runtime.state.snapshot().variables
        self._tick_selfref(state_vars)

    def _pick_pair(self) -> tuple[str, str]:
        """随机选一对对话角色。"""
        names = self.characters
        if len(names) < 2:
            return names[0], names[0]
        max_memory = max(2, len(names) - 1)
        tried = set()
        while len(tried) < 10:
            a, b = random.sample(names, 2)
            pair = (a, b) if a < b else (b, a)
            if pair not in self.recent_pairs or random.random() < 0.3:
                self.recent_pairs.append(pair)
                self.recent_pairs = self.recent_pairs[-max_memory:]
                return a, b
            tried.add(pair)
        return tuple(random.sample(names, 2))

    def _log(self, speaker: str, content: str):
        self.log.append({
            "ts": datetime.now().isoformat(),
            "speaker": speaker,
            "content": content[:500],
        })

    def _print_summary(self):
        snap = self.runtime.snapshot()
        print(f"\n  {'='*56}")
        print(f"  ✅ {len(self.log)} 条消息")
        counts: dict[str, int] = {}
        for e in self.log:
            counts[e["speaker"]] = counts.get(e["speaker"], 0) + 1
        for name, count in sorted(counts.items()):
            print(f"     · {name}: {count} 次")
        print(f"\n  🌍 最终状态 (tick {snap.tick}):")
        for k, v in sorted(snap.state.items()):
            pct = int(v * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"     {k:25s} {bar} {v:.3f}")
        if self.ghost:
            print(f"  👻 {self.ghost.ghost_manifestations_text()}")
        print(f"\n  关系网络：")
        for name in sorted(self.residents.keys()):
            res = self.residents[name]
            if res.mind.relationships:
                print(f"     {name}: {res.mind.relationship_summary()}")
