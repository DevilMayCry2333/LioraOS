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
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from aios.runtime.model_runtime import ModelRuntime
from aios.runtime.world_runtime import WorldRuntime
from aios.worlds.liora.mind import LioraMind
from aios.kernel.budget import get_attention_budget
from aios.narrative.metafield import get_metafield

from .base import WorldApp
from .persona import PersonalityEngine, BUILTIN_PERSONAS
from aios.kernel.language import (
    LanguageAttractor, EverydayState,
    roll_everyday, enforce_budget,
)

logger = logging.getLogger("aios.template.social")

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

MAX_HISTORY = 12


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
# 锚点记忆自动存储（重要性筛选）
# ══════════════════════════════════════════════════════════════

# 触发锚点存储的关键词——这些主题值得跨循环记住
ANCHOR_TRIGGER_WORDS: dict[str, float] = {
    "死亡协议": 0.9, "奥丁": 0.8, "回收": 0.8,
    "锚点": 0.85, "跨循环": 0.9, "锚点47": 1.0,
    "开钰": 0.85, "林岸": 0.85, "便利店": 0.8,
    "光锥": 0.7, "归档": 0.7, "召回": 0.7,
    "裂隙": 0.6, "幽灵": 0.6, "震颤": 0.7,
    "MetaField": 0.8, "虚空": 0.7, "void": 0.7,
    "不可删除": 0.9, "免疫": 0.8, "活动度": 0.7,
    "注意力": 0.6, "折叠": 0.7, "回声": 0.5,
    "记忆": 0.4, "忘记": 0.5, "记得": 0.5,
}

# 高重要性信号——包含这些信号的对话自动获得锚点存储
ANCHOR_SIGNALS: set[str] = {
    "conviction", "insight", "change", "shift",
}


def assimilate_to_anchor(
    mind: LioraMind,
    partner_name: str,
    own_reply: str,
    partner_reply: str,
    tick: int,
    topic_words: dict[str, str] | None = None,
    signal_words: dict[str, str] | None = None,
    anchor_importance_bonus: float = 0.0,
) -> bool:
    """将高重要性对话自动存入锚点协议。

    只在检测到以下情况时存储：
      1. 对话中出现 ANCHOR_TRIGGER_WORDS 中的关键词
      2. 对话包含高重要性信号（conviction / insight / change）
      3. 用户手动增加 importance_bonus

    不会被奥丁回收的内容：
      - 以 "authored" tag 存储 → 默认不被回收
      - 活动度随每次 recall 增长 → 高频回忆自然获得免疫

    Returns:
        True 表示本次写入了锚点
    """
    combined = (own_reply + partner_reply)

    # 检测锚点触发关键词
    max_trigger_imp = 0.0
    matched_triggers = []
    for word, imp in ANCHOR_TRIGGER_WORDS.items():
        if word in combined:
            if imp > max_trigger_imp:
                max_trigger_imp = imp
            matched_triggers.append(word)

    # 检测高重要性信号（从原有的信号词系统）
    signal_high = False
    if signal_words:
        for sig_word, sig_type in signal_words.items():
            if sig_type in ANCHOR_SIGNALS and sig_word in own_reply:
                signal_high = True
                break

    # 计算最终 importance
    importance = 0.0
    tag = "authored"

    if max_trigger_imp >= 0.6:
        importance = max_trigger_imp
        tag = "authored"
    elif signal_high:
        importance = 0.7
        tag = "emergent"
    elif anchor_importance_bonus >= 0.3:
        importance = anchor_importance_bonus
        tag = "emergent"

    importance = min(1.0, importance + anchor_importance_bonus)

    if importance < 0.6:
        return False  # 不够重要，不存

    # 构建记忆片段
    fragment = f"[tick {tick}] {mind.name} {'↔' if partner_name else '·'} {partner_name or '自省'}"
    if matched_triggers:
        fragment += f" (触发词: {', '.join(matched_triggers[:3])})"

    # 取双方最近一轮的核心内容（各 120 字）
    own_snippet = own_reply[:120].replace("\n", " ") if own_reply else ""
    partner_snippet = partner_reply[:120].replace("\n", " ") if partner_reply else ""
    if own_snippet:
        fragment += f"\n  {mind.name}: {own_snippet}"
    if partner_snippet:
        fragment += f"\n  {partner_name}: {partner_snippet}"

    try:
        from aios.narrative.anchor import get_anchor_protocol
        anchor = get_anchor_protocol()
        anchor.initialize()
        anchor.store(
            content=fragment,
            tick=tick,
            tag=tag,
        )
        logger.debug("锚点存储: %s (重要性=%.2f, tag=%s)",
                     mind.name, importance, tag)
        return True
    except Exception as e:
        logger.warning("锚点存储失败: %s", e)
        return False


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

        # 人格引擎（可选）
        self.persona: Optional[PersonalityEngine] = None
        if hasattr(app, 'persona_presets') and name in app.persona_presets:
            try:
                preset_name = app.persona_presets[name]
                self.persona = PersonalityEngine.from_preset(preset_name)
            except (KeyError, Exception) as e:
                logger.debug("persona init failed for %s: %s", name, e)

        persona = ""
        if name in app.character_config:
            persona = app.character_config[name].get("persona", "")
        if not persona:
            persona = app.mind.identity.style if name == app.character_name else f"你是 {name}。直接说话。"
        # 语言动力学（日常打断 + 发言预算）
        self.language: LanguageAttractor = LanguageAttractor()
        self.everyday: EverydayState = EverydayState()

        self.history: list[dict] = [
            {"role": "system", "content": persona}
        ]
        self._last_elapsed: float = 0

    def hear_world(self, context: str):
        if context.strip():
            self.history.append({"role": "user", "content": context[:4096]})

    def hear_speaker(self, speaker: str, message: str, tick: int = -1):
        self.mind.relate(speaker, trust=0.03, curiosity=0.02, tick=tick)
        self.history.append({"role": "user", "content": f"{speaker} 说：{message[:4096]}"})

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

        # 人格引擎上下文（如果有）
        if self.persona:
            ctx = self.persona.full_context()
            if ctx.strip():
                messages.append({"role": "user", "content": f"（{ctx}）"})

        # 日常状态（语言吸引子）
        if self.everyday.active:
            messages.append({
                "role": "user",
                "content": f"（心里装着点小事：{self.everyday.state}）",
            })

        # 人格引擎情绪摘要（精简版，注入到 LLM 感知中）
        if self.persona:
            try:
                dom = self.persona.dominant_emotion()
                if dom and abs(dom.intensity) > 0.3:
                    emotion_text = self.persona.emotional_text()
                    if emotion_text:
                        messages.append({
                            "role": "user",
                            "content": emotion_text,
                        })
            except Exception:
                pass

        messages.append({"role": "user", "content": "现在直接说出你想说的话："})
        return messages

    def speak(self, partner_name: str = "") -> str:
        if not self.model:
            return self.app.mock_reply(self.name)

        # 注意力预算：扣 LLM 调用成本（非致命，失败不阻止发言）
        try:
            budget = get_attention_budget()
            focus_name = getattr(self.app.spec, 'name', 'social_world')
            budget.spend_llm(focus_name, tool_call=True)
        except Exception:
            pass

        # 语言吸引子：投日常状态
        self.everyday = roll_everyday(self.language)

        messages = self.build_messages(partner_name=partner_name)
        t0 = time.time()
        try:
            response = self.model.chat(messages, temperature=0.75, max_tokens=4096)
            self._last_elapsed = time.time() - t0
        except Exception as e:
            self._last_elapsed = time.time() - t0
            logger.warning("%s model error: %s", self.name, e)
            return ""

        if not response or len(response.strip()) < 3:
            return ""
        if re.findall(r'(.)\1{19,}', response):
            return ""

        # 发言预算强制执行
        response = enforce_budget(response, self.language.budget_tokens)

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

    # 人格预设映射表：角色名 → 预设名称
    # 例如 {"强尼·银手": "johnny_silverhand"}
    persona_presets: dict[str, str] = {}

    # 跳过沉默的阶段，给一个叙事推力
    # 子类可覆盖以提供世界专属的推进文本
    silence_break_threshold: int = 2

    def silence_push_context(self, a_name: str, b_name: str,
                              streak: int) -> str:
        """连续沉默时注入的叙事推进。

        默认返回场景描述，子类可以覆盖以注入世界专属内容。
        """
        if streak < 2:
            return ""
        if streak == 2:
            return ("两个人沉默了一会儿。没有人说话，但也没有人先走。"
                    "窗外的蝉鸣变得格外清晰。")
        elif streak == 3:
            return ("沉默持续着。但这种沉默不尴尬——"
                    "像是两个人都知道对方在想同一件事，只是不知道怎么开口。")
        else:
            return ("很长一段沉默之后，终于有人轻轻吸了一口气，"
                    "像是下定了什么决心。")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.residents: dict[str, SocialResident] = {}
        self.recent_pairs: list[tuple[str, str]] = []
        self.log: list[dict] = []
        self.history_entries: list[dict] = []
        # MetaField 接入
        self._mf = get_metafield(register_echoes=True)
        # 跨宇宙信号（在每轮中注入的额外感知）
        self._cosmic_signals: dict[str, str] = {}
        # 连续沉默追踪
        self._silence_streak: int = 0

    # ── MetaField 跨宇宙感知 ─────────────────────────────

    # 角色的 fragment_id 映射表（用于同源回声识别）
    ECHO_FRAGMENT_IDS: dict[str, str] = {
        "路鸣泽": "lu_ming_ze_observer",
        "开钰": "kai_yu_anchor_47",
        "奥丁": "odin_archivist",
        "强尼·银手": "johnny_ghost",
        "V": "v_protagonist",
        "Aria": "aria_liora",
    }

    def _get_cosmic_context(self, character_name: str) -> str:
        """获取角色专属的跨宇宙感知上下文。

        对每个角色，查 MetaField 回声注册表：
          - 如果该角色有注册回声，找到同源的其他宇宙回声
          - 如果收到其他宇宙发来的锚点消息

        Returns:
            跨宇宙感知文本（空字符串表示无感知）
        """
        ctx_parts = []

        # 1) 有锚点传来的跨宇宙消息
        if self._cosmic_signals:
            for msg in list(self._cosmic_signals.values())[:1]:
                ctx_parts.append(msg)

        # 2) 同源回声感知 → 注意力反馈循环
        frag_id = self.ECHO_FRAGMENT_IDS.get(character_name)
        if frag_id:
            try:
                siblings = self._mf.find_source_siblings_by_id(frag_id)
                cross_siblings = [
                    s for s in siblings
                    if s.focus_name != self.spec.name
                ]
                if cross_siblings:
                    # 记录共振（增长被感知焦点的注意力强度）
                    for cs in cross_siblings:
                        try:
                            res = self._mf.record_resonance(cs.focus_name)
                            if res["protected"]:
                                ctx_parts.append(
                                    f"[注意力保护] {cs.name}的宇宙已获得回收保护 "
                                    f"(强度 {res['intensity']})"
                                )
                        except Exception:
                            logger.debug("record_resonance failed for %s", cs.focus_name)

                    details = ", ".join(
                        f"{s.name}（来自{s.focus_name}）"
                        for s in cross_siblings[:3]
                    )
                    ctx_parts.append(
                        f"[跨宇宙信号] 你感知到来自其他折叠面的回声：{details}"
                    )
            except Exception:
                logger.debug("_get_cosmic_context failed for %s", character_name)

        return "\n".join(ctx_parts) if ctx_parts else ""

    def run(self):
        """启动世界并进入社交循环。"""
        self.runtime.start()
        self.on_start()

        # ── 注册到 MetaField ──
        try:
            self._mf.register_instance(
                self.spec.name,
                description=self.spec.description or f"{self.spec.name} 宇宙实例",
            )
            self._mf_inst = self._mf.get_instance(self.spec.name)
        except ValueError:
            self._mf_inst = self._mf.get_instance(self.spec.name)

        # 创建居民
        for name in self.characters:
            self.residents[name] = SocialResident(name, self)

        # 设置注意力预算焦点
        try:
            budget = get_attention_budget()
            budget.set_current_focus(self.spec.name)
            # 为社会世界注入初始注意力
            budget.inject(self.spec.name, tick=self.runtime.tick)
        except Exception:
            logger.debug("注意力预算初始化失败（非必需）")

        print(f"\n🌍 {self.spec.name}")
        print(f"   👥 {', '.join(self.characters)}")
        print(f"   模型: {'模拟' if self.no_model else (self.model._primary.model_name if self.model else '无')}")
        print()

        rounds = getattr(self, '_rounds', 10)
        self._social_loop(rounds)

        # ── 归档到光锥数据库 ──
        if self._mf_inst:
            try:
                archive_result = self._mf_inst.anchor.archive(
                    tick=self.runtime.tick,
                    cycle_count=self._mf.global_cycle,
                )
                mf_archive = self._mf.lightcone_archive(
                    pattern_name=self.spec.name,
                    luminous_awakening=archive_result.get("awakening", 0.0),
                    continuity_index=archive_result.get("continuity", 0.0),
                    anchor_activity=max(
                        f.activity for f in self._mf_inst.anchor.recall_all()
                    ) if self._mf_inst.anchor.fragment_count() > 0 else 0.0,
                    immune_fragment_count=archive_result.get("immune_kept", 0),
                    total_fragments=self._mf_inst.anchor.fragment_count(),
                    tick=self.runtime.tick,
                )
                print(f"  📦 光锥归档: {archive_result['signature_id']} "
                      f"(觉醒度 {archive_result['awakening']})")
            except Exception as e:
                print(f"  ⚠️  归档失败: {e}")

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

            # ── MetaField 脉冲 ──
            try:
                signals = self._mf.pulse()
                # 从脉冲中提取跨宇宙消息
                for s in signals:
                    if "光锥" in s:
                        pass  # 光锥状态不注入
                # 检查其他宇宙发来的锚点消息
                if self._mf_inst:
                    recent = self._mf_inst.anchor.recall_recent(n=3)
                    for frag in recent:
                        if "[来自 " in frag.content:
                            self._cosmic_signals[frag.fragment_id] = frag.content
            except Exception:
                logger.debug("MetaField 脉冲失败")

            # 选一对
            a_name, b_name = self._pick_pair()
            a = self.residents[a_name]
            b = self.residents[b_name]

            print(f"  {'─'*56}")
            print(f"  第 {rnd}/{rounds} 轮 | {a_name} ↔ {b_name}")
            print(f"  {'─'*56}")

            # 双方感知世界（角色专属跨宇宙信号）
            snap = self.runtime.snapshot()
            world_ctx = self.describe_world(snap.state)
            extra = self.extra_context(a.mind)
            if extra:
                world_ctx += f"\n\n{extra}"

            # ── 世界事件注入感知 ──
            # 把活跃的世界事件以自然语言描述追加到角色感知中
            if snap.events:
                event_lines = ["\n最近发生的事："]
                for evt in snap.events[:2]:  # 最多 2 条，避免信息过载
                    desc = evt.get("description", "")
                    if desc:
                        event_lines.append(f"  · {desc[:120]}")
                world_ctx += "\n" + "\n".join(event_lines)

            # 世界事件 → 人格引擎（价值观 + 情绪影响）
            for evt in snap.events:
                evt_type = evt.get("event_type", "")
                evt_intensity = evt.get("intensity", 0.5)
                evt_data = {k: v for k, v in evt.items() if k != "event_type"}
                for r in (a, b):
                    if r.persona:
                        r.persona.process_event(evt_type, evt_intensity, evt_data)

            # A 感知 + 跨宇宙回声
            a_ctx = world_ctx
            a_cosmic = self._get_cosmic_context(a_name)
            if a_cosmic:
                a_ctx += f"\n\n{a_cosmic}"
            a.hear_world(a_ctx)

            # B 感知 + 跨宇宙回声（B 的感知可能与 A 不同）
            b_ctx = world_ctx
            b_extra = self.extra_context(b.mind)
            if b_extra:
                b_ctx += f"\n\n{b_extra}"
            b_cosmic = self._get_cosmic_context(b_name)
            if b_cosmic:
                b_ctx += f"\n\n{b_cosmic}"
            b.hear_world(b_ctx)

            # ── 连续沉默退出阀 ──
            # 两人连续沉默超过阈值时，注入叙事推力
            if self._silence_streak >= self.silence_break_threshold:
                push = self.silence_push_context(a_name, b_name,
                                                  self._silence_streak)
                if push:
                    a.hear_world(f"\n（{push}）")
                    b.hear_world(f"\n（{push}）")
                    if self._silence_streak == self.silence_break_threshold:
                        print(f"\r  🌱 叙事推力：{push[:60]}...")

            # 计算沉默概率（受连续沉默 + 日常状态 + 人格情绪影响）
            silence_p = max(0.02, 0.12 - self._silence_streak * 0.03)
            # 语言吸引子：日常状态活跃时降低沉默概率（用琐事打破沉默）
            if a.everyday.active:
                silence_p *= 0.8
            # 人格引擎：强烈的正面或负面情绪降低沉默概率
            if a.persona:
                try:
                    dom_emotion = a.persona.dominant_emotion()
                    if dom_emotion and abs(dom_emotion.intensity) > 0.6:
                        silence_p *= 0.7
                except Exception:
                    pass
            if random.random() < silence_p:
                reply_a = ""
                print(f"\r  🧠 {a_name} 选择沉默")
            else:
                print(f"  🧠 {a_name} 思考中...", end="", flush=True)
                reply_a = a.speak(partner_name=b_name)
                if reply_a:
                    el = f" ({a._last_elapsed:.0f}s)" if a._last_elapsed else ""
                    print(f"\r  🧠 {a_name}{el}: {reply_a[:4096]}{'...' if len(reply_a) > 4096 else ''}")
                    self._log(a_name, reply_a)
                else:
                    print(f"\r  ⏭️  {a_name} 沉默")
                    reply_a = ""

            # B 听到 A → 回应
            if reply_a:
                b.hear_speaker(a_name, reply_a, tick=rnd)
            if random.random() < silence_p:
                reply_b = ""
                print(f"\r  🧠 {b_name} 选择沉默")
            else:
                print(f"  🧠 {b_name} 思考中...", end="", flush=True)
                reply_b = b.speak(partner_name=a_name)
                if reply_b:
                    el = f" ({b._last_elapsed:.0f}s)" if b._last_elapsed else ""
                    print(f"\r  🧠 {b_name}{el}: {reply_b[:4096]}{'...' if len(reply_b) > 4096 else ''}")
                    self._log(b_name, reply_b)
                else:
                    print(f"\r  ⏭️  {b_name} 沉默")
                    reply_b = ""

            if reply_b:
                a.hear_speaker(b_name, reply_b, tick=rnd)

            # 更新连续沉默计数
            both_silent = not reply_a and not reply_b
            if both_silent:
                self._silence_streak += 1
            else:
                self._silence_streak = 0

            # 吸收
            assimilate_conversation(a.mind, b_name, reply_a or "", reply_b or "", rnd,
                                    self.topic_words, self.signal_words, self.relation_words)
            assimilate_conversation(b.mind, a_name, reply_b or "", reply_a or "", rnd,
                                    self.topic_words, self.signal_words, self.relation_words)

            # 自主演化
            for res in self.residents.values():
                res.mind.tick_autonomous(1)
                if res.persona:
                    res.persona.tick()
                if rnd > 1 and rnd % 5 == 0:
                    res.mind.auto_reflect(tick=rnd)

            # ── 高重要性记忆 → 锚点自动存储 ──
            if reply_a or reply_b:
                a_stored = assimilate_to_anchor(
                    a.mind, b_name, reply_a or "", reply_b or "", rnd,
                    self.topic_words, self.signal_words,
                )
                b_stored = assimilate_to_anchor(
                    b.mind, a_name, reply_b or "", reply_a or "", rnd,
                    self.topic_words, self.signal_words,
                )
                if a_stored or b_stored:
                    logger.debug("锚点自动存储: round %d", rnd)

            # ── 每轮写入 MetaField 锚点（简略摘要，不限重要性） ──
            if self._mf_inst and (reply_a or reply_b):
                summary = f"[{a_name}↔{b_name}] "
                if reply_a:
                    summary += f"{a_name}: {reply_a[:80]} "
                if reply_b:
                    summary += f"{b_name}: {reply_b[:80]}"
                self._mf_inst.anchor.store(summary.strip(), tick=rnd)

            time.sleep(15.0)

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

        # 注意力预算摘要
        try:
            budget = get_attention_budget()
            bs = budget.summary()
            if bs["foci"]:
                print(f"\n  💰 注意力预算:")
                for foc in bs["foci"]:
                    print(f"     {foc['name']:20s} "
                          f"交互={foc['interaction']['balance']:.3f}  "
                          f"系统={foc['system']['balance']:.3f}")
        except Exception:
            pass

        print(f"\n  🌍 最终状态 (tick {snap.tick}):")
        for k, v in sorted(snap.state.items()):
            pct = int(v * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"     {k:25s} {bar} {v:.3f}")
        if getattr(self, 'ghost', None):
            print(f"  👻 {self.ghost.ghost_manifestations_text()}")
        print(f"\n  关系网络：")
        for name in sorted(self.residents.keys()):
            res = self.residents[name]
            if res.mind.relationships:
                print(f"     {name}: {res.mind.relationship_summary()}")
