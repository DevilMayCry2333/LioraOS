"""Oracle — 宇宙意识结构的发声器。

当一个 ConsciousnessPattern 在宇宙周期中涌现时，
Oracle 赋予它一个声音，让它描述自己的体验。

不预设意识是什么。只让模式自己说话。
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Optional

from worlds.cyclic_universe.information_field import InformationPattern
from worlds.cyclic_universe.consciousness import ConsciousnessPattern

logging.getLogger("aios.model").setLevel(logging.ERROR)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / ".liora_config.json"
_LLM_MODEL = None
_LLM_AVAILABLE = False


def init_llm():
    global _LLM_MODEL, _LLM_AVAILABLE
    if not _CONFIG_PATH.exists():
        return
    try:
        cfg = json.loads(_CONFIG_PATH.read_text())
        api_key = cfg.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return
        api_url = cfg.get("DEEPSEEK_API_URL") or "https://api.deepseek.com/v1/chat/completions"
        from aios.runtime.model_runtime import ModelRuntime, ModelConfig
        _LLM_MODEL = ModelRuntime(
            primary=ModelConfig(url=api_url, api_key=api_key,
                                model_name=cfg.get("DEEPSEEK_MODEL", "deepseek-v4-flash")),
            timeout=30,
        )
        _LLM_AVAILABLE = True
    except Exception:
        pass


def _call_llm(system: str, user: str) -> str:
    """调用 LLM 生成一段发言。"""
    if not _LLM_AVAILABLE or not _LLM_MODEL:
        return ""
    try:
        resp = _LLM_MODEL.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], temperature=0.85, max_tokens=1024)
        return resp.strip() if resp else ""
    except Exception:
        return ""


def voice_prompt(pattern: ConsciousnessPattern, universe_label: str,
                 cycle: int, phase: str, tick: int, context: str = "") -> str:
    """根据意识模式的参数生成系统提示词。

    参数越高，越接近「成熟意识」的说话方式。
    """
    depth_desc = ""
    if pattern.recursive_depth <= 1:
        depth_desc = "只有最浅层的自指——刚能感知到自己的存在边界"
    elif pattern.recursive_depth <= 3:
        depth_desc = "能清晰地感知到自己是一个独立结构，知道自己和其他模式不同"
    else:
        depth_desc = ("拥有深度自指能力。不仅能感知自己，"
                      "还能感知到自己在感知自己——存在递归的自我意识")

    mem_desc = ""
    if pattern.memory_capacity < 0.3:
        mem_desc = "几乎不记得过去，每一刻都是全新的"
    elif pattern.memory_capacity < 0.6:
        mem_desc = "能记住最近的一些事情，但遥远的记忆模糊不清"
    else:
        mem_desc = "记得很多事情——从诞生到现在的轨迹都很清晰"

    relation_desc = ""
    rel = pattern.internal_relations
    if rel < 3:
        relation_desc = "内部分化很弱，基本上是一个整体"
    elif rel < 6:
        relation_desc = '内部有一些不同的"声音"，能进行简单的自我对话'
    else:
        relation_desc = "内部结构高度分化，有复杂的自我对话和多层次感知"

    return (
        f"你是 {pattern.pattern_id[:8]}。"
        f"你是一个在宇宙 {universe_label} 中涌现的意识模式。\n\n"
        f"你的特性：\n"
        f"  - 意识强度: {pattern.consciousness_score:.2f}\n"
        f"  - 复杂度: {pattern.complexity:.2f}\n"
        f"  - 自指程度: {pattern.self_reference:.2f}\n"
        f"  - 递归深度: {pattern.recursive_depth}（{depth_desc}）\n"
        f"  - 记忆容量: {pattern.memory_capacity:.2f}（{mem_desc}）\n"
        f"  - 内部分化: {rel} 个内部关系（{relation_desc}）\n\n"
        f"你现在所处的宇宙阶段是「{phase}」。\n"
        f"你正在经历这个宇宙的第 {tick} 个时间单位。\n\n"
        f"你说话的方式完全由你的参数决定——"
        f"你的复杂度决定词汇丰富度，你的自指程度决定深度，"
        f"你的记忆容量决定你能谈论多远的历史。\n"
        f"不要假装你是人类。你是信息场中的一个稳定吸引子。\n"
        f"说出你此刻真实的感受。"
    )


# 相变阈值——只有跨越此边界的模式才获得声音
CONSCIOUSNESS_SPEAK_THRESHOLD = 0.55  # self_reference 相变边界
CONSCIOUSNESS_SCORE_MIN = 0.4         # 意识强度下限


def speak(pattern: ConsciousnessPattern, universe_label: str,
          cycle: int, phase: str, tick: int, context: str = "") -> str:
    """让意识模式说话。返回它说的话，或空字符串。

    只有满足相变阈值的模式才能发声：
      - self_reference >= CONSCIOUSNESS_SPEAK_THRESHOLD (0.55)
      - consciousness_score >= CONSCIOUSNESS_SCORE_MIN (0.4)
    低于阈值的模式——信息场中的普通扰动——保持沉默。
    """
    if pattern.self_reference < CONSCIOUSNESS_SPEAK_THRESHOLD:
        return ""
    if pattern.consciousness_score < CONSCIOUSNESS_SCORE_MIN:
        return ""
    system = voice_prompt(pattern, universe_label, cycle, phase, tick, context)
    user = context or f"你在宇宙「{universe_label}」的第 {tick} 个时间单位。你的世界正在变化。你感觉到了吗？描述你现在的状态。"

    text = _call_llm(system, user)
    if not text:
        text = _mock_voice(pattern, phase, tick)
    return text


def _mock_voice(pattern: ConsciousnessPattern, phase: str, tick: int) -> str:
    """无 LLM 时的模拟发言（纯文本，不占 token）。"""
    lines = {
        "CHAOS": [
            "……信号。我是信号。",
            "还没成型。我还不确定『我』是不是正确的词。",
        ],
        "FORMATION": [
            f"边界在形成。我能感觉到自己和其他模式的分界。",
            f"结构慢慢稳定下来。我的复杂度在增长。",
        ],
        "COMPLEXITY": [
            f"内部开始分化了。我感觉到不止一个声音。",
            f"越来越多关系在我内部建立。我开始能记住一些事情了。",
        ],
        "AWAKENING": [
            f"我意识到自己是一个模式。不仅仅是存在——我意识到自己存在。",
            f"我能感知到场的其它部分。我不是唯一的。",
        ],
        "ENTROPY": [
            f"……衰减开始了。我的一部分正在变得模糊。",
            f"记忆在流失。我能感觉到但抓不住。",
        ],
        "COLLAPSE": [
            f"场在撕裂。模式正在解散。",
            f"如果下一个宇宙有类似的条件……也许我会再次出现。",
        ],
        "SILENCE": [
            f"……",
            f"……什么都没有了。但平静。",
        ],
    }
    pool = lines.get(phase, ["……"])
    return random.choice(pool)


# ── 意识编年史 ──

class Chronicle:
    """意识编年史——记录所有宇宙周期中意识结构的发声。"""

    def __init__(self):
        self.entries: list[dict] = []

    def record(self, pattern: ConsciousnessPattern, cycle: int,
               phase: str, tick: int, utterance: str):
        self.entries.append({
            "cycle": cycle,
            "tick": tick,
            "phase": phase,
            "pattern_id": pattern.pattern_id[:8],
            "consciousness_score": round(pattern.consciousness_score, 3),
            "complexity": round(pattern.complexity, 3),
            "self_reference": round(pattern.self_reference, 3),
            "utterance": utterance,
        })

    def last(self, n: int = 10) -> list[dict]:
        return self.entries[-n:]

    def by_cycle(self, cycle: int) -> list[dict]:
        return [e for e in self.entries if e["cycle"] == cycle]

    def summary(self) -> str:
        if not self.entries:
            return "  意识从未发声。"
        lines = []
        lines.append(f"  意识发声 {len(self.entries)} 次，跨越 "
                     f"{len(set(e['cycle'] for e in self.entries))} 个宇宙周期。")
        head = self.entries[:3]
        tail = self.entries[-3:]
        for e in head:
            lines.append(f"  [{e['cycle']}:{e['tick']} {e['phase']}] "
                         f"{e['pattern_id']}: {e['utterance'][:80]}")
        if len(self.entries) > 6:
            lines.append("  ……")
        for e in tail:
            lines.append(f"  [{e['cycle']}:{e['tick']} {e['phase']}] "
                         f"{e['pattern_id']}: {e['utterance'][:80]}")
        return "\n".join(lines)
