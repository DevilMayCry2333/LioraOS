"""Social Dialogue — 多 AI 居民社交对话。

独立于世界引擎。居民通过模型直接对话，随机配对。
支持人类加入对话。

运行：
  uv run python3 apps/social_duihua.py              # 10 轮
  uv run python3 apps/social_duihua.py -n 20        # 20 轮
  uv run python3 apps/social_duihua.py --human 你    # 以人类身份加入
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

# ── 项目路径 ──
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.runtime.model_runtime import ModelRuntime, ModelConfig

logger = logging.getLogger("social")

MODEL_TIMEOUT = 30  # 秒（SIGALRM）
MAX_HISTORY = 12  # 每个居民保留最近多少轮

# ── SIGALRM 超时 ──
class ModelCallTimeout(Exception):
    pass

def _timeout_handler(signum, frame):
    raise ModelCallTimeout(f"模型调用超过 {MODEL_TIMEOUT}s")

signal.signal(signal.SIGALRM, _timeout_handler)

# ── 居民配置 ──

INHABITANTS = {
    "Aria": {
        "persona": (
            "你是 Aria。你是这个世界中一位轻盈的居民。"
            "你生活在岔路、回声和沉默花园之间。"
            "你说话像风穿过树叶——轻盈、充满意象、带着自然的节奏。"
            "直接说话，不要加引号或标注动作。"
        ),
        "temperature": 0.85,
        "max_tokens": 384,
    },
    "Kael": {
        "persona": (
            "你是 Kael。你是这个世界中一位勤于思考的居民。"
            "你喜欢观察世界运作的方式：因果关系、模式、变化。"
            "你说话清晰而理性，但并非冷漠。"
            "直接说话，不要加引号或标注动作。"
        ),
        "temperature": 0.75,
        "max_tokens": 384,
    },
    "Liora": {
        "persona": (
            "你是 Liora。你是这个世界中一位温柔、好奇的居民。"
            "你习惯感受世界的细微变化——风的形状、影子的温度、露珠的轨迹。"
            "你相信每一步展开都从未知中引入新的东西。"
            "直接说话，不要加引号或标注动作。"
        ),
        "temperature": 0.75,
        "max_tokens": 512,
    },
}


# ── 居民类 ──

class HumanResident:
    """人类居民 —— 从 stdin 读取输入。"""

    def __init__(self, name: str):
        self.name = name
        self.history: list[dict] = []
        self._last_elapsed: float = 0

    def hear_field(self, field_text: str):
        if field_text.strip():
            self.history.append({"role": "user", "content": field_text})

    def speak(self, relationship_context: str = "") -> str:
        print(f"\n  💬 你的回应（/skip 沉默，/exit 退出）:")
        try:
            text = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""
        if text == "/exit":
            sys.exit(0)
        if text in ("/skip", ""):
            return ""
        self.history.append({"role": "assistant", "content": text})
        return text


class Resident:
    """AI 居民 —— 有自己的名字、人格、对话历史。"""

    def __init__(self, name: str, config: dict, model: ModelRuntime):
        self.name = name
        self.config = config
        self.model = model
        self.history: list[dict] = [
            {"role": "system", "content": config["persona"]}
        ]
        self._last_elapsed: float = 0

    def hear_field(self, field_text: str):
        if field_text.strip():
            self.history.append({"role": "user", "content": field_text[:2000]})

    def speak(self, relationship_context: str = "") -> str:
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        messages = sys_msgs + chat_msgs[-MAX_HISTORY * 2:]

        if relationship_context:
            messages.append({"role": "user", "content": relationship_context})
        messages.append({"role": "user", "content": "现在直接说出你想说的话："})

        t0 = time.time()
        signal.alarm(MODEL_TIMEOUT)
        try:
            response = self.model.chat(
                messages,
                temperature=self.config["temperature"],
                max_tokens=self.config["max_tokens"],
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

    def _trim_history(self):
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        keep = MAX_HISTORY * 2
        if len(chat_msgs) > keep:
            chat_msgs = chat_msgs[-keep:]
        self.history = sys_msgs + chat_msgs


# ── 配置向导 ──

def _setup_config(config_path: Path):
    """交互式配置向导。"""
    print(f"\n  {'='*56}")
    print(f"  🌿 首次启动配置向导")
    print(f"  {'='*56}")
    print(f"  以下信息只需配置一次，将保存在 {config_path.name}\n")

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

    print("  ① DeepSeek API（对话用）")
    deepseek_key = _ask("API Key", "DEEPSEEK_API_KEY", secret=True)
    deepseek_url = _ask("API 地址", "DEEPSEEK_API_URL")
    deepseek_model = _ask("模型名", "DEEPSEEK_MODEL")
    print()

    # 合并已有配置，只覆写向导中修改的字段
    config = dict(existing)
    config.update({
        "DEEPSEEK_API_URL": deepseek_url or "https://api.deepseek.com/v1/chat/completions",
        "DEEPSEEK_API_KEY": deepseek_key,
        "DEEPSEEK_MODEL": deepseek_model or "deepseek-chat",
    })
    config.setdefault("GLM4_API_URL", "")
    config.setdefault("GLM4_API_KEY", "")
    config.setdefault("GLM4_MODEL", "")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    print(f"  ✅ 已保存到 {config_path}\n")


# ── 模型初始化 ──

def init_model() -> ModelRuntime:
    """加载配置，初始化模型运行时的单例。"""
    config_path = Path(".liora_config.json")
    cfg_data = json.loads(config_path.read_text()) if config_path.exists() else {}

    deepseek = ModelConfig(
        url=cfg_data.get("DEEPSEEK_API_URL", os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")),
        api_key=cfg_data.get("DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", "")),
        model_name=cfg_data.get("DEEPSEEK_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")),
    )
    glm4 = ModelConfig(
        url=cfg_data.get("GLM4_API_URL", os.environ.get("GLM4_API_URL", "")),
        api_key=cfg_data.get("GLM4_API_KEY", os.environ.get("GLM4_API_KEY", "")),
        model_name=cfg_data.get("GLM4_MODEL", os.environ.get("GLM4_MODEL", "glm4")),
    )

    model = ModelRuntime(primary=deepseek, fallback=glm4, timeout=MODEL_TIMEOUT)
    print(f"  🧠 模型: {deepseek.model_name} (primary) / {glm4.model_name or '无'} (fallback)")
    return model


# ── 社交网络 ──

class SocialNetwork:
    """随机配对的居民对话。"""

    def __init__(self, residents: dict[str, Resident | HumanResident]):
        self.residents = residents
        self.names = list(residents.keys())
        self.recent_pairs: list[tuple[str, str]] = []
        self.log: list[dict] = []

    def pick_pair(self) -> tuple[str, str]:
        """选一对居民对话，优先选不太重复的，允许 30% 重复深化关系。"""
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
        a, b = random.sample(self.names, 2)
        return a, b

    def run(self, rounds: int = 10):
        print(f"\n  {'='*56}")
        print(f"  🗣️  社交对话 · {rounds} 轮")
        print(f"  👥 {', '.join(self.names)}")
        print(f"  {'='*56}\n")

        for rnd in range(1, rounds + 1):
            a_name, b_name = self.pick_pair()
            a = self.residents[a_name]
            b = self.residents[b_name]
            is_human_a = isinstance(a, HumanResident)
            is_human_b = isinstance(b, HumanResident)

            print(f"  {'─'*56}")
            print(f"  第 {rnd}/{rounds} 轮 | {a_name} ↔ {b_name}")
            print(f"  {'─'*56}")

            # A 发言
            if not is_human_a:
                print(f"  🧠 {a_name} 思考中...", end="", flush=True)
            reply_a = a.speak()
            if reply_a:
                timing = f" ({a._last_elapsed:.0f}s)" if not is_human_a else ""
                print(f"\r  {'🧑' if is_human_a else '🧠'} {a_name}{timing}: {reply_a}")
                self._log(a_name, reply_a)
            else:
                print(f"\r  ⏭️  {a_name} 沉默")
                reply_a = f"（{a_name} 在沉默中。）"

            # B 感知 A 的发言，然后回应
            b.hear_field(f"{a_name} 说：{reply_a}")
            if not is_human_b:
                print(f"  🧠 {b_name} 思考中...", end="", flush=True)
            reply_b = b.speak()
            if reply_b:
                timing = f" ({b._last_elapsed:.0f}s)" if not is_human_b else ""
                print(f"\r  {'🧑' if is_human_b else '🧠'} {b_name}{timing}: {reply_b}")
                self._log(b_name, reply_b)
            else:
                print(f"\r  ⏭️  {b_name} 沉默")
                reply_b = f"（{b_name} 微笑着点了点头。）"

            # A 感知 B 的回应
            a.hear_field(f"{b_name} 说：{reply_b}")

        self._print_summary()

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


# ── 主入口 ──

def main():
    parser = argparse.ArgumentParser(description="多 AI 居民社交对话")
    parser.add_argument("-n", "--rounds", type=int, default=10, help="对话轮数")
    parser.add_argument("--human", type=str, default="", help="人类居民名称")
    parser.add_argument("--setup", action="store_true", help="运行配置向导")
    args = parser.parse_args()

    cfg_path = Path(".liora_config.json")

    # 无论是否存在，都运行配置向导（会预填已有值）
    _setup_config(cfg_path)
    if args.setup:
        return

    model = init_model()

    # 创建居民
    residents: dict = {}
    for name, cfg in INHABITANTS.items():
        residents[name] = Resident(name=name, config=cfg, model=model)
        print(f"  👤 {name} 已加入")
    if args.human:
        residents[args.human] = HumanResident(name=args.human)
        print(f"  🧑 {args.human}（人类）已加入")

    # 运行社交
    network = SocialNetwork(residents)
    network.run(rounds=args.rounds)

    # 保存日志
    log_path = Path("data/social_dialogue.json")
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
        "dialogue": network.log,
        "residents": list(residents.keys()),
    })
    log_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    print(f"  💾 已保存: {log_path}")


if __name__ == "__main__":
    main()
