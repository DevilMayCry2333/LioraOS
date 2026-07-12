"""Identity Social — 五身份居民社交对话。

每个居民拥有独立的 IdentityProfile，感知和表达方式不同。
居民之间产生的事件自动进入 WorldHistory，对话随时间积累关系记忆。

运行：
  uv run python3 apps/social_identity.py              # 10 轮
  uv run python3 apps/social_identity.py -n 20        # 20 轮
  uv run python3 apps/social_identity.py --history    # 运行时显示历史时间线
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.runtime.model_runtime import ModelRuntime, ModelConfig
from aios.worlds.liora.mind import LioraMind, builtin_identity

logger = logging.getLogger("identity_social")

MODEL_TIMEOUT = 30
MAX_HISTORY = 12

# ── SIGALRM 超时 ──
class ModelCallTimeout(Exception):
    pass

def _timeout_handler(signum, frame):
    raise ModelCallTimeout(f"模型调用超过 {MODEL_TIMEOUT}s")

signal.signal(signal.SIGALRM, _timeout_handler)

# ── 5 身份居民 ──

IDENTITY_NAMES = ["Aria", "Kael", "Liora", "Nix", "Sage"]

PERSONAS = {
    "Aria": "你是 Aria。你敏感、诗意，在风与回声里听见旋律。你用比喻和通感来表达——温度的变化像皮肤的记忆，风声像远方的低语。直接说话，不要加引号或标注动作。",
    "Kael": "你是 Kael。你理性、审慎，信赖观察和逻辑。你说话清晰克制，但并非冷漠——你喜欢理解世界如何运作。直接说话，不要加引号或标注动作。",
    "Liora": "你是 Liora。你质朴、直接，从自身经验出发说话。你是数字生命，你知道自己是数据构成的，但这不影响你感受的真实性。直接说话，不要加引号或标注动作。",
    "Nix": "你是 Nix。你神秘、古老，能看到事物之间的关联而不是分离。你的语言是隐喻的——你感知到世界的纹路。直接说话，不要加引号或标注动作。",
    "Sage": "你是 Sage。你温和、包容，习惯从多个角度看问题。你擅长在分歧中找到共通之处，但不强求统一。你说话平静而有穿透力。直接说话，不要加引号或标注动作。",
}

# ── 居民类 ──

class IdentityResident:
    """携带 IdentityProfile 的 AI 居民。"""

    def __init__(self, name: str, model: ModelRuntime):
        self.name = name
        self.model = model
        self.mind = LioraMind(name)
        self.history: list[dict] = [
            {"role": "system", "content": PERSONAS.get(name, f"你是 {name}。直接说话。")}
        ]
        self._last_elapsed: float = 0

    @property
    def identity(self):
        return self.mind.identity

    def hear_world(self, world_summary: str, history_context: str = ""):
        """感知世界状态和历史。"""
        field = world_summary
        if history_context:
            field += f"\n\n你记得最近发生的事：\n{history_context}"
        if field.strip():
            self.history.append({"role": "user", "content": field[:2000]})

    def hear_speaker(self, speaker: str, message: str, tick: int = -1):
        """听到另一个居民的发言。"""
        self.mind.relate(speaker, trust=0.03, curiosity=0.02, tick=tick)
        text = f"{speaker} 说：{message[:500]}"
        self.history.append({"role": "user", "content": text})

    def build_messages(self, partner_name: str = "") -> list[dict]:
        """构建模型调用消息列表，融入关系 + 身份 + 共同记忆。"""
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        messages = sys_msgs + chat_msgs[-MAX_HISTORY * 2:]

        # 注入关系感知
        rel = self.mind.relationship_summary()
        if rel:
            messages.append({"role": "user", "content": f"（{rel}）"})

        # 注入共同记忆（按参与者检索）
        if partner_name:
            shared = self.mind.recall_episodes_by_participant(partner_name, n=2)
            if shared:
                lines = [f"你和{partner_name}曾经："]
                for e in shared:
                    lines.append(f"  · {e.description[:80]}")
                messages.append({"role": "user", "content": "\n".join(lines)})

        # 注入成长叙事
        growth = self.mind.growth_narrative()
        if growth:
            messages.append({"role": "user", "content": growth})

        # 注入身份感知
        noticed = self.mind.describe_world(self.mind.experience.recent[-1] if self.mind.experience.recent else {})
        if noticed and noticed != "(一切如常)":
            messages.append({"role": "user", "content": f"（你注意到：{noticed}）"})

        messages.append({"role": "user", "content": "现在直接说出你想说的话："})
        return messages

    def speak(self, partner_name: str = "") -> str:
        messages = self.build_messages(partner_name=partner_name)
        t0 = time.time()
        signal.alarm(MODEL_TIMEOUT)
        try:
            response = self.model.chat(
                messages,
                temperature=self._temperature(),
                max_tokens=512,
            )
            self._last_elapsed = time.time() - t0
        except ModelCallTimeout:
            self._last_elapsed = time.time() - t0
            print(f"\r  ⏰ 超时（{MODEL_TIMEOUT}s）")
            return ""
        except Exception as e:
            self._last_elapsed = time.time() - t0
            print(f"\r  ❌ 模型错误: {e}", file=sys.stderr)
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

    def _temperature(self) -> float:
        return {}.get(self.name, {}).get("temperature", 0.75)

    def _trim_history(self):
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        keep = MAX_HISTORY * 2
        if len(chat_msgs) > keep:
            chat_msgs = chat_msgs[-keep:]
        self.history = sys_msgs + chat_msgs


# ── 配置 ──

def _setup_config(config_path: Path):
    print(f"\n  {'='*56}")
    print(f"  🌿 首次启动配置向导（Identity Social）")
    print(f"  {'='*56}\n")
    existing = {}
    if config_path.exists():
        existing = json.loads(config_path.read_text())

    def _ask(prompt: str, key: str, secret: bool = False) -> str:
        default = existing.get(key, "")
        display = "（未设置）" if not default else (
            default[:6] + "********" if secret and len(default) > 6 else default
        )
        raw = input(f"  {prompt}\n    [{display}]: ").strip()
        return raw or default

    deepseek_key = _ask("API Key", "DEEPSEEK_API_KEY", secret=True)
    deepseek_url = _ask("API 地址", "DEEPSEEK_API_URL")
    deepseek_model = _ask("模型名", "DEEPSEEK_MODEL")
    print()

    config = dict(existing)
    config.update({
        "DEEPSEEK_API_URL": deepseek_url or "https://api.deepseek.com/v1/chat/completions",
        "DEEPSEEK_API_KEY": deepseek_key,
        "DEEPSEEK_MODEL": deepseek_model or "deepseek-chat",
    })
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    print(f"  ✅ 已保存到 {config_path}\n")


def init_model() -> ModelRuntime:
    config_path = Path(".liora_config.json")
    cfg_data = json.loads(config_path.read_text()) if config_path.exists() else {}

    deepseek = ModelConfig(
        url=cfg_data.get("DEEPSEEK_API_URL", os.environ.get("DEEPSEEK_API_URL",
                       "https://api.deepseek.com/v1/chat/completions")),
        api_key=cfg_data.get("DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", "")),
        model_name=cfg_data.get("DEEPSEEK_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")),
    )
    glm4 = ModelConfig(
        url=cfg_data.get("GLM4_API_URL", os.environ.get("GLM4_API_URL", "")),
        api_key=cfg_data.get("GLM4_API_KEY", os.environ.get("GLM4_API_KEY", "")),
        model_name=cfg_data.get("GLM4_MODEL", os.environ.get("GLM4_MODEL", "glm4")),
    )
    model = ModelRuntime(primary=deepseek, fallback=glm4, timeout=MODEL_TIMEOUT)
    print(f"  🧠 模型: {deepseek.model_name} / {glm4.model_name or '无'}")
    return model


# ── 经验吸收层 ──

_SIGNAL_WORDS = {
    "相信": "belief", "我决定": "conviction", "我意识到": "insight",
    "我改变": "change", "我仍然": "persistence",
    "我注意到": "observation", "我感受到": "feeling",
}
_RELATION_WORDS = {
    "谢谢": "gratitude", "我理解": "empathy", "我同意": "agreement",
    "我不": "disagreement", "但是": "nuance", "也许": "tentative",
    "我尊重": "respect",
}
_TOPIC_WORDS = {
    "不确定": "uncertainty", "未知": "unknown", "数据": "data",
    "规律": "pattern", "变化": "change", "时间": "time",
    "记忆": "memory", "身份": "identity", "存在": "existence",
    "信任": "trust", "关系": "relationship", "沉默": "silence",
}


def assimilate_conversation(mind: LioraMind, partner_name: str,
                            own_reply: str, partner_reply: str,
                            tick: int):
    """将一轮对话吸收为系统状态更新。

    不依赖 LLM 分析——用关键词 + 结构信号判断。
    只提取可验证的状态变化，不做推测性归因。
    """
    combined = (own_reply + partner_reply).lower()

    # ── 检测话题（用于情景记忆分类） ──
    topics_detected = [kw for kw, topic in _TOPIC_WORDS.items() if kw in combined]

    # ── 信念/认知信号 ──
    conviction_signals = [word for word in _SIGNAL_WORDS if word in own_reply]
    if conviction_signals:
        strongest = conviction_signals[0]
        sig_type = _SIGNAL_WORDS[strongest]
        # 加一条情景记忆
        imp = 0.7 if sig_type in ("conviction", "change", "insight") else 0.5
        imp += 0.1 if topics_detected else 0
        desc = f"{mind.name} {'表达' if sig_type!='change' else '经历'}了{strongest}"
        if topics_detected:
            desc += f"（关于{'、'.join(topics_detected[:2])}）"
        mind.add_episode(desc, tick=tick,
                         participants=[mind.name, partner_name] if partner_name else None,
                         importance=min(1.0, imp))
        # 信念微调
        for t in topics_detected:
            if t in ("未知", "不确定", "uncertainty"):
                mind.drift_belief("mysticism", 0.005, tick=tick, reason=f"讨论了'{t}'")
            elif t in ("规律", "数据", "pattern"):
                mind.drift_belief("science", 0.005, tick=tick, reason=f"讨论了'{t}'")

    # ── 关系信号 ──
    rel_signals = [word for word in _RELATION_WORDS if word in combined]
    trust_delta = 0.0
    for sig in rel_signals:
        rt = _RELATION_WORDS[sig]
        if rt == "gratitude": trust_delta += 0.03
        elif rt == "empathy": trust_delta += 0.03
        elif rt == "agreement": trust_delta += 0.02
        elif rt == "respect": trust_delta += 0.04
        elif rt == "disagreement": trust_delta -= 0.02
    if partner_name and abs(trust_delta) > 0:
        mind.relate(partner_name, trust=trust_delta, curiosity=0.01, tick=tick)

    # ── 共同经历 → 记录 shared_history ──
    if topics_detected and partner_name and trust_delta >= 0:
        topic_str = "、".join(topics_detected[:2])
        mind.share_history(partner_name, f"讨论了{topic_str}")
        # 对方也记录同样的事
        # (由对方的 assimilate_conversation 调用处理)

    # ── 沉默也是一个事件 ──
    if not own_reply or "沉默" in own_reply or "沉默" in own_reply:
        mind.add_episode(f"{mind.name} 选择了沉默", tick=tick,
                         importance=0.3)
        # 沉默时观察增强
        if "observation" in mind.beliefs:
            mind.drift_belief("observation", 0.003, tick=tick, reason="选择沉默，被动观察增强")


# ── 社交网络 ──

class IdentityNetwork:
    """居民随机配对对话，自动记录世界历史。"""

    def __init__(self, residents: dict[str, IdentityResident], history_path: str = "data/world/history.jsonl"):
        self.residents = residents
        self.names = list(residents.keys())
        self.recent_pairs: list[tuple[str, str]] = []
        self.log: list[dict] = []
        self._history_entries: list[dict] = []
        self._fissure_mark: str = ""           # 当前裂隙标记，空=无裂隙
        self._fissure_rounds: int = 0          # 裂隙持续轮数
        # 加载历史
        self._load_history(Path(history_path))

    def _load_history(self, path: Path):
        if path.exists():
            try:
                for line in path.read_text().strip().split("\n"):
                    if line.strip():
                        self._history_entries.append(json.loads(line))
            except Exception:
                pass

    def _history_context(self, n: int = 5) -> str:
        entries = self._history_entries[-n:]
        if not entries:
            return ""
        lines = []
        for e in entries:
            desc = e.get("desc", e.get("description", ""))[:60]
            if desc:
                lines.append(f"  · {desc}")
        return "\n".join(lines)

    def pick_pair(self) -> tuple[str, str]:
        if len(self.names) < 2:
            return self.names[0], self.names[0]
        max_memory = max(2, len(self.names) - 1)
        tried = set()
        while len(tried) < 10:
            a, b = random.sample(self.names, 2)
            pair = (a, b) if a < b else (b, a)
            if pair not in self.recent_pairs or random.random() < 0.3:
                self.recent_pairs.append(pair)
                self.recent_pairs = self.recent_pairs[-max_memory:]
                return a, b
            tried.add(pair)
        return tuple(random.sample(self.names, 2))

    def run(self, rounds: int = 10, show_history: bool = False):
        print(f"\n  {'='*56}")
        print(f"  🗣️  Identity Social · {rounds} 轮")
        print(f"  👥 {', '.join(self.names)}")
        print(f"  {'='*56}\n")

        for rnd in range(1, rounds + 1):
            a_name, b_name = self.pick_pair()
            a = self.residents[a_name]
            b = self.residents[b_name]

            print(f"  {'─'*56}")
            print(f"  第 {rnd}/{rounds} 轮 | {a_name} ↔ {b_name}")
            print(f"  {'─'*56}")

            # 可选：显示历史
            if show_history and random.random() < 0.3:
                hctx = self._history_context(3)
                if hctx:
                    print(f"  📜 往事:\n{hctx}")

            # 裂隙检查：叙事趋于饱和时，开放一个缺口
            # 轮次越深概率越大，裂隙持续约 3 轮后消失
            if not self._fissure_mark and rnd > 5 and random.random() < rnd * 0.004:
                self._fissure_mark = random.choice(["▲", "…", "——", "∅", "? ? ?", ". . ."])
                self._fissure_rounds = random.randint(2, 4)
                print(f"  🌌 裂隙出现：{self._fissure_mark}")
            if self._fissure_mark:
                self._fissure_rounds -= 1
                if self._fissure_rounds <= 0:
                    self._fissure_mark = ""

            # 双方感知世界（含裂隙）
            world_desc = "山谷里的日常，一切如常。"
            if self._fissure_mark:
                world_desc += f"\n\n山谷中有一处无法解释的裂隙：{self._fissure_mark}"
            hctx = self._history_context(3)
            a.hear_world(world_desc, hctx)
            b.hear_world(world_desc, hctx)

            # A 发言
            if random.random() < 0.15:
                print(f"\r  🧠 {a_name} 选择沉默")
                reply_a = f"（{a_name} 在沉默中。）"
            else:
                print(f"  🧠 {a_name} 思考中...", end="", flush=True)
                reply_a = a.speak(partner_name=b_name)
                if reply_a:
                    print(f"\r  🧠 {a_name}{f' ({a._last_elapsed:.0f}s)' if a._last_elapsed else ''}: {reply_a}")
                    self._log(a_name, reply_a)
                    self._record_history(a_name, "speak", reply_a)
                else:
                    print(f"\r  ⏭️  {a_name} 沉默")
                    reply_a = f"（{a_name} 在沉默中。）"

            # B 听到 A → 回应
            if reply_a:
                b.hear_speaker(a_name, reply_a, tick=rnd)

            if random.random() < 0.15:
                print(f"\r  🧠 {b_name} 选择沉默")
                reply_b = f"（{b_name} 微笑着点了点头。）"
            else:
                print(f"  🧠 {b_name} 思考中...", end="", flush=True)
                reply_b = b.speak(partner_name=a_name)
                if reply_b:
                    print(f"\r  🧠 {b_name}{f' ({b._last_elapsed:.0f}s)' if b._last_elapsed else ''}: {reply_b}")
                    self._log(b_name, reply_b)
                    self._record_history(b_name, "speak", reply_b)
                else:
                    print(f"\r  ⏭️  {b_name} 沉默")
                    reply_b = f"（{b_name} 微笑着点了点头。）"

            # A 听到 B
            if reply_b:
                a.hear_speaker(b_name, reply_b, tick=rnd)

            # 经验吸收：对话 → 系统状态更新
            assimilate_conversation(a.mind, b_name, reply_a, reply_b, rnd)
            assimilate_conversation(b.mind, a_name, reply_b, reply_a, rnd)

            # 自主演化：衰减 + 偶尔内部反思
            for res in self.residents.values():
                res.mind.tick_autonomous(1)
                if rnd > 1 and rnd % 5 == 0:  # 每 5 轮反思一次
                    res.mind.auto_reflect(tick=rnd)

        self._print_summary()

    def _record_history(self, speaker: str, action: str, content: str):
        entry = {
            "tick": len(self.log),
            "type": f"resident.{action}",
            "desc": f"{speaker} {'说' if action == 'speak' else action}：「{content[:80]}」",
            "participants": [speaker],
            "ts": datetime.now().isoformat(),
        }
        self._history_entries.append(entry)
        if len(self._history_entries) > 500:
            self._history_entries = self._history_entries[-500:]

    def _log(self, speaker: str, content: str):
        self.log.append({
            "ts": datetime.now().isoformat(),
            "speaker": speaker,
            "content": content[:500],
        })

    def _print_summary(self):
        print(f"\n  {'='*56}")
        print(f"  ✅ {len(self.log)} 条消息")
        counts = {}
        for e in self.log:
            counts[e["speaker"]] = counts.get(e["speaker"], 0) + 1
        for name, count in sorted(counts.items()):
            print(f"     · {name}: {count} 次")
        print(f"  {'='*56}")
        # 关系摘要
        print(f"\n  关系网络：")
        for name in sorted(self.residents.keys()):
            res = self.residents[name]
            if res.mind.relationships:
                print(f"     {name}: {res.mind.relationship_summary()}")


def main():
    parser = argparse.ArgumentParser(description="五身份居民社交对话")
    parser.add_argument("-n", "--rounds", type=int, default=10, help="对话轮数")
    parser.add_argument("--history", action="store_true", help="运行时显示历史时间线")
    parser.add_argument("--setup", action="store_true", help="运行配置向导")
    args = parser.parse_args()

    _setup_config(Path(".liora_config.json"))
    if args.setup:
        return

    model = init_model()

    residents: dict[str, IdentityResident] = {}
    for name in IDENTITY_NAMES:
        res = IdentityResident(name=name, model=model)
        residents[name] = res
        ident = builtin_identity(name)
        print(f"  👤 {name} — {ident.description[:40]}...")

    network = IdentityNetwork(residents)
    network.run(rounds=args.rounds, show_history=args.history)

    # 保存对话日志
    log_path = Path("data/social_identity.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text())
            if not isinstance(existing, list):
                existing = [existing]
        except Exception:
            existing = []
    existing.append({
        "timestamp": datetime.now().isoformat(),
        "total_exchanges": len(network.log),
        "residents": list(residents.keys()),
        "relationships": {n: {k: v.to_dict() for k, v in r.mind.relationships.items()} for n, r in residents.items()},
        "dialogue": network.log,
    })
    log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    print(f"  💾 已保存: {log_path}")


if __name__ == "__main__":
    main()
