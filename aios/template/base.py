"""WorldApp — 世界生命周期编排器。

封装所有世界的通用运行时逻辑：
  - tick 管理 / state 演化 / 事件循环
  - 居民认知更新（assimilate + decay）
  - 自指机制调度（Unknown / Ghost / 其他）
  - LLM 调用 + 自动补搜
  - 行动解析 + 效果应用
  - 控制台命令（/state /help 等）
  - checkpoint 持久化

世界作者只需要继承此类，重写以下钩子：

  必填:
    spec: WorldSpec                      — 你的世界定义

  可选覆盖:
    describe_world(state, mind) → str   — 状态→自然语言
    extra_context(mind) → str           — 额外感知（幽灵/裂隙等）
    resolve_effects(type, target) → dict — 行动→世界影响
    character_config: dict              — 角色身份/信念/秘密
    action_effects / target_effects     — 效果表
    unknown_class / ghost_class         — 自指机制
    mock_replies: dict                  — 模拟模式回复池
    system_prompt_template: str         — 系统 prompt
"""

from __future__ import annotations

import json
import logging
import os
import random
import select
import sys
import time
from pathlib import Path
from typing import Optional

from aios.runtime.world_runtime import WorldRuntime
from aios.runtime.model_runtime import ModelRuntime, ModelConfig
from aios.runtime.tools import execute_search, contains_uncertainty
from aios.worlds.liora.mind import LioraMind

logger = logging.getLogger("aios.template")

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))


# ══════════════════════════════════════════════════════════════
# 行动解析（通用）
# ══════════════════════════════════════════════════════════════

_ACTION_KEYWORDS: dict[str, str] = {
    "SAY": "say", "say": "say",
    "沉默": "silence", "SILENCE": "silence", "silence": "silence",
    "wait": "silence", "WAIT": "silence",
    "搜索": "search", "SEARCH": "search", "search": "search",
    "观察": "observe", "OBSERVE": "observe", "observe": "observe",
    "触摸": "touch", "TOUCH": "touch", "touch": "touch",
    "移动": "move", "MOVE": "move", "move": "move",
    "收集": "collect", "COLLECT": "collect", "collect": "collect",
    "创造": "create", "CREATE": "create", "create": "create",
    "探索": "explore", "EXPLORE": "explore", "explore": "explore",
    "倾听": "listen", "LISTEN": "listen", "listen": "listen",
    "黑客": "hack", "HACK": "hack", "hack": "hack",
    "扫描": "scan", "SCAN": "scan", "scan": "scan",
    "连接": "connect", "CONNECT": "connect", "connect": "connect",
}
_SILENCE_KEYWORDS = {"silence", "沉默", "wait", "安静"}


def parse_action(text: str) -> dict:
    """从 LLM 回复中提取行动。"""
    text = text.strip()
    action = {"type": "say", "target": "", "reason": ""}

    # 搜索意图
    for sw in ["搜索", "search", "查一下"]:
        if sw in text.lower():
            action["type"] = "search"
            for sep in ["关于", "一下", "：", ":", " "]:
                parts = text.split(sep, 1)
                if len(parts) > 1 and len(parts[1].strip()) > 1:
                    action["target"] = parts[1].strip()[:50]
                    break
            return action

    # 沉默
    for sw in ["沉默", "silence", "安静", "不想说"]:
        if sw in text.lower():
            action["type"] = "silence"
            return action

    # ACTION: 格式（兼容旧版）
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("ACTION:"):
            rest = line[len("ACTION:"):].strip()
            for keyword, atype in sorted(_ACTION_KEYWORDS.items(),
                                         key=lambda x: -len(x[0])):
                if rest.upper().startswith(keyword.upper()):
                    action["type"] = atype
                    rest = rest[len(keyword):].strip()
                    break
            if '"' in rest:
                parts = rest.split('"')
                action["target"] = parts[0].strip().rstrip(" [(")
                action["reason"] = parts[1] if len(parts) > 1 else ""
            elif " " in rest:
                action["target"] = rest.split()[0].lower()
            else:
                action["target"] = rest.lower()

    if action["type"] in _SILENCE_KEYWORDS:
        action["type"] = "silence"
    return action


# ══════════════════════════════════════════════════════════════
# WorldApp 基类
# ══════════════════════════════════════════════════════════════

class WorldApp:
    """世界应用模板。

    用法：
        class MyWorld(WorldApp):
            spec = create_my_spec()
            # ... 覆盖钩子

        if __name__ == "__main__":
            MyWorld().run()
    """

    # ── 世界作者覆盖区 ──────────────────────────────

    # 必填
    spec = None                       # WorldSpec 实例
    world_objects: list[dict] = []    # 世界物体清单

    # 角色配置
    characters: list[str] = []        # 可选角色列表
    default_character: str = ""       # 默认角色
    character_config: dict = {}       # {name: {beliefs: {}, secrets: [], persona: ""}}
    # persona 是可选的，不填则使用 identity 的 style

    # 感知格式化
    system_prompt_template: str = ""

    # 行动效果表（世界作者覆盖）
    action_effects: dict = {}
    target_effects: dict = {}         # {action_type: {target: {var: delta}}}

    # 自指机制（可选）
    unknown_class = None              # UnknownAccumulator 类（不实例化）
    ghost_class = None                # DigitalGhost 类

    # 模拟模式回复池
    mock_replies: dict = {}

    # ── 运行时 ─────────────────────────────────────

    def __init__(self, model: ModelRuntime | None = None,
                 search_api_key: str = "",
                 interval: int = 15,
                 character: str = "",
                 data_dir: str = "data",
                 no_model: bool = False):
        # 模型
        self.model = model
        self.search_api_key = search_api_key
        self.no_model = no_model

        # 世界
        assert self.spec is not None, "WorldApp.spec 必须定义"
        self.runtime = WorldRuntime(self.spec, interval=interval, data_dir=data_dir)
        self.runtime.init_objects(list(self.world_objects))

        # 角色
        char_name = character or self.default_character
        if not char_name and self.characters:
            char_name = self.characters[0]
        elif not char_name:
            char_name = ""

        self.character_name = char_name
        self.mind = LioraMind(char_name)
        self._apply_character_config(self.mind, char_name)

        # 自指机制
        self.unknown = self.unknown_class() if self.unknown_class else None
        self.ghost = self.ghost_class(bus=self.runtime.bus) if self.ghost_class else None

        # 循环内部状态
        self._pending_input = ""
        self._last_search_result = ""
        self._lingering_thought = ""
        self._last_world_tick = -1
        self._thought_this_tick = False   # 防止同个 tick 多次思考
        self._model_failed = False        # 模型彻底失败后降级模拟

    def _apply_character_config(self, mind: LioraMind, name: str):
        """将 character_config 应用到 LioraMind 实例。"""
        if name in self.character_config:
            cfg = self.character_config[name]
            if "beliefs" in cfg:
                mind.beliefs = dict(cfg["beliefs"])
            if "secrets" in cfg:
                mind.secrets = list(cfg["secrets"])

    # ── 可覆盖钩子 ────────────────────────────────

    def describe_world(self, state: dict, mind: LioraMind | None = None) -> str:
        """世界状态 → 自然语言描述。

        这是每个世界最独特的钩子——它的隐喻体系。
        可选实现：如果留空，使用 runtime.format_for_perception()。
        """
        return self.runtime.format_for_perception()

    def extra_context(self, mind: LioraMind) -> str:
        """额外的感知上下文（幽灵低语、裂隙信息等）。"""
        if self.ghost and self.ghost.is_active:
            return self.ghost.ghost_context(2)
        return ""

    def resolve_effects(self, action_type: str, target: str) -> dict[str, float]:
        """行动类型 + 目标 → 世界状态变化量。"""
        # 先查 target_effects
        if action_type in self.target_effects and target in self.target_effects[action_type]:
            return dict(self.target_effects[action_type][target])
        # 再查 action_effects
        return dict(self.action_effects.get(action_type, {}))

    def mock_reply(self, name: str) -> str:
        """模拟模式的回复。"""
        pool = self.mock_replies.get(name, ["..."])
        return random.choice(pool)

    def on_start(self):
        """世界启动前的钩子。"""

    def on_stop(self):
        """世界停止前的钩子。"""

    # ── Prompt 构建（模板方法） ────────────────────

    def _build_social_prompt(self, mind: LioraMind) -> str:
        """身份连续性约束 prompt。"""
        lines = []

        growth = mind.growth_narrative()
        if growth:
            lines.append(f"\n{growth}")

        belief_text = mind.belief_summary()
        if belief_text:
            lines.append(f"你的信念倾向：{belief_text}")
            lines.append("这些信念只能缓慢变化（每轮最多 ±1%）。")

        recall = mind.recall_text()
        if recall:
            lines.append(recall)
            lines.append("除非有充分理由，否则不要轻易推翻自己说过的话。")

        secret_note = mind.secret_count_text()
        if secret_note:
            lines.append(secret_note)

        ep_text = mind.episodes_text(2)
        if ep_text:
            lines.append(f"\n{ep_text}")

        lines.append("你可以选择沉默。沉默不是失败。")
        return "\n".join(lines)

    def _build_perception_prompt(self, world_desc: str, user_input: str = "",
                                  extra: str = "", search_result: str = "") -> list[dict]:
        """构建 LLM prompt。"""
        mind = self.mind
        lines = [world_desc]
        self._mix_identity_context(mind, lines, extra, search_result)
        if user_input:
            lines.append(f"\n{user_input}")

        style = mind.identity.style or "你是你自己。"
        social = self._build_social_prompt(mind)
        system = self.system_prompt_template
        if not system:
            system = f"你是 {mind.name}。"
        system = system.format(name=mind.name) + f"\n\n{style}"
        if social:
            system += f"\n\n{social}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(lines)},
        ]

    def _mix_identity_context(self, mind: LioraMind, lines: list[str],
                               extra: str, search_result: str):
        """身份过滤后的感知上下文注入。"""
        if mind.experience.hum > 0.3:
            lines.append(f"\n你体内的嗡鸣在轻轻震动：{mind.experience.hum:.2f}")
        if mind.silent_state.is_silent:
            lines.append("\n你一直在沉默。")
        rel = mind.relationship_summary()
        if rel:
            lines.append(f"\n{rel}")
        if mind.private_events and not mind.silent_state.is_silent:
            last = mind.private_events[-1]
            desc = last.get("description", "")[:60]
            if desc:
                lines.append(f"\n你仍记得：{desc}")
        goal_text = mind.current_goal_text()
        if goal_text:
            lines.append(f"\n{goal_text}")
        if extra:
            lines.append(f"\n{extra}")
        if search_result:
            lines.append(f"\n{search_result}")

    # ── 行动应用 ──────────────────────────────────

    def apply_action(self, action: dict) -> str:
        """将行动应用到世界。返回描述文本。"""
        atype = action["type"]
        target = action["target"]
        mind = self.mind

        mind.record_action(target, atype, self.runtime.tick)

        if atype == "silence":
            mind.choose_silence(reason=action.get("reason", ""),
                                tick=self.runtime.tick)
            effects = self.resolve_effects("silence", target)
            if effects:
                self.runtime.apply_effects(effects)
            return "你选择了沉默。"

        mind.form_intention(atype, target, tick=self.runtime.tick)

        if atype == "say":
            effects = self.resolve_effects("say", target)
            if effects:
                self.runtime.apply_effects(effects)
            return f"你说：{target}"

        if atype == "search":
            result = (execute_search(target, self.search_api_key)
                      if self.search_api_key else f"[模拟搜索: {target}]")
            return f"你向外探寻「{target}」。\n{result}"

        # 接触类行动
        effects = self.resolve_effects(atype, target)
        changed = self.runtime.apply_effects(effects) if effects else []

        result_map = {
            "touch":   f"你触碰了{target}。{' '.join(changed)}" if changed else f"你触碰了{target}。",
            "hack":    f"你侵入了{target}。{' '.join(changed)}" if changed else f"你侵入了{target}。",
            "scan":    f"你扫描了{target}。{' '.join(changed)}" if changed else f"你扫描了{target}。",
            "connect": f"你接入了{target}。{' '.join(changed)}" if changed else f"你接入了{target}。",
            "collect": f"你收集了{target}的东西。{' '.join(changed)}" if changed else f"你收集了{target}的东西。",
            "observe": f"你观察着{target}。它在变化。",
            "listen":  f"你倾听着。远处有什么在响。",
            "explore": f"你探索着{target}。",
            "move":    f"你移动到{target}。",
            "create":  f"你用{target}创造了一些东西。",
        }
        return result_map.get(atype, f"你{atype}了{target}。")

    # ── 自指机制更新 ──────────────────────────────

    def _tick_selfref(self, state_vars: dict):
        """更新自指机制（裂隙/幽灵等）。"""
        if self.unknown:
            self.unknown.tick(
                silence_active=self.mind.silent_state.is_silent,
                repetition_level=0.0,
            )
            if self.unknown.should_emit():
                delta = self.unknown.emit()
                gs = self.runtime.state._state
                for k, v in delta.items():
                    if k in gs.variables:
                        gs.set(k, gs.get(k) + v)
                logger.info("unknown emission: %s", delta)

        if self.ghost:
            self.ghost.tick(
                tick=self.runtime.tick,
                world_state=state_vars,
                unknown_pressure=self.unknown.pressure if self.unknown else 0,
            )

    # ── 运行时检查 ─────────────────────────────────

    @property
    def _search_available(self) -> bool:
        return bool(self.search_api_key) and self.model is not None

    # ══════════════════════════════════════════════════
    # 主循环
    # ══════════════════════════════════════════════════

    def run(self):
        """启动世界并进入主循环。"""
        self.runtime.start()
        self.on_start()

        # 可选: 启动 LEP Gateway
        try:
            from aios.runtime.gateway import LEPGateway
            gateway = LEPGateway(self.runtime)
            gateway.start()
        except Exception:
            pass

        print(f"\n🌍 {self.spec.name} 已苏醒")
        print(f"   角色: {self.character_name or '无'}")
        print(f"   模型: {'模拟' if self.no_model else (self.model._primary.model_name if self.model else '无')}")
        print(f"   输入对话，/help 查看命令\n")

        try:
            self._main_loop()
        except KeyboardInterrupt:
            print("\n\n世界陷入沉默...")
        finally:
            self.on_stop()
            self.runtime.stop()
            snap = self.runtime.snapshot()
            print(f"\n[{snap.tick} tick 之后，世界继续存在]")
            print("再见。")

    def _main_loop(self):
        """通用主循环。"""
        while True:
            now_tick = self.runtime.tick

            # ── 用户输入 ──
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline().strip()
                if not line:
                    pass
                elif line == "/quit":
                    break
                elif line == "/state":
                    self._cmd_state()
                    continue
                elif line == "/help":
                    self._cmd_help()
                    continue
                elif line.startswith("/goal "):
                    self._cmd_goal(line)
                    continue
                elif line.startswith("/search "):
                    self._cmd_search(line)
                    continue
                else:
                    self._pending_input = line

            # ── 世界 tick ──
            if now_tick != self._last_world_tick:
                self._last_world_tick = now_tick
                self._process_tick()

            # ── 思考 ──
            if self._should_think():
                self._think()

            time.sleep(0.1)

    # ── 命令处理 ──────────────────────────────────

    def _cmd_state(self):
        snap = self.runtime.snapshot()
        print(f"  tick={snap.tick}, 变量={len(snap.state)}, 事件={len(snap.events)}")
        print(f"  身份={self.mind.identity.name}  hum={self.mind.experience.hum:.3f}")
        print(f"  沉默={self.mind.silent_state.duration}")
        if self.unknown:
            print(f"  未知压力={self.unknown.pressure:.3f}")
        if self.ghost:
            print(f"  {self.ghost.ghost_manifestations_text()}")
        if self.mind.relationships:
            print(f"  关系: {self.mind.relationship_summary()}")

    def _cmd_help(self):
        print("  命令: /state /goal <目标> /search <关键词> /quit")
        print("  其他: 直接对话")

    def _cmd_goal(self, line: str):
        desc = line[len("/goal "):].strip()
        if desc:
            self.mind.add_goal(desc, self.runtime.tick)
            print(f"  🎯 目标已设定: {desc}")

    def _cmd_search(self, line: str):
        query = line[len("/search "):].strip()
        if not query:
            return
        if self._search_available:
            result = execute_search(query, self.search_api_key)
            print(f"  {result}")
        else:
            print("  ⚠️  未配置搜索 API Key")

    # ── tick 处理 ─────────────────────────────────

    def _process_tick(self):
        """单 tick 处理：自指 + 认知更新。"""
        self._thought_this_tick = False  # 新 tick，重置思考锁
        state_vars = self.runtime.state.snapshot().variables

        # 自指机制
        self._tick_selfref(state_vars)

        # 认知更新
        self.mind.assimilate(state_vars, self.runtime.tick)
        if not self.mind.silent_state.is_silent:
            self.mind.update_sensitivity(self.mind.experience.total)
        self.mind.tick_decay(1)

    # ── 思考逻辑 ─────────────────────────────────

    def _should_think(self) -> bool:
        """判断当前是否应该触发一次思考。

        每个 tick 最多触发一次思考，防止循环空转。
        """
        if self._thought_this_tick:
            return False
        return (
            bool(self._pending_input)
            or not self.mind.silent_state.is_silent
            or self.mind.consecutive_silence >= 3
            or (self.mind.active_goals()
                and self.runtime.tick > 0
                and self.runtime.tick % 30 == 0)
        )

    def _think(self):
        """感知 → 思考 → 表达 → 行动。"""
        self._thought_this_tick = True
        world_desc = self.describe_world(
            self.runtime.state.snapshot().variables,
            self.mind,
        )
        extra = self.extra_context(self.mind)

        if not self._pending_input and self._lingering_thought:
            world_desc += f"\n\n你仍然在想：{self._lingering_thought}"

        prompt = self._build_perception_prompt(
            world_desc, self._pending_input, extra, self._last_search_result,
        )

        # LLM 调用
        reply = self._call_llm(prompt)

        if reply:
            print(f"\n💭 {self.mind.name}: {reply}")

        # 不确定性 → 搜索补全
        if self._pending_input and contains_uncertainty(reply) and self._search_available:
            reply = self._auto_search_reply(prompt, reply)

        # 记录
        if reply and len(reply) > 10:
            self.mind.record_statement(reply[:200])
            self._last_search_result = ""

        # 行动
        action = parse_action(reply)
        result = self.apply_action(action)
        self._lingering_thought = self._extract_thought(reply)

        self._pending_input = ""
        if action["type"] != "silence":
            print(f"   🌀 {result}")
        else:
            print("   [她陷入沉默]")
            time.sleep(1)

    def _call_llm(self, prompt: list[dict]) -> str:
        """调用 LLM 或模拟。

        如果模型连续失败，自动降级到模拟模式（每 tick 只报一次错）。
        """
        if self.no_model or not self.model or self._model_failed:
            return self.mock_reply(self.mind.name)
        try:
            return self.model.chat(prompt, temperature=0.7, max_tokens=1024)
        except Exception as e:
            logger.error("模型调用失败（已降级到模拟模式）: %s", e)
            self._model_failed = True
            return self.mock_reply(self.mind.name)

    def _auto_search_reply(self, prompt: list[dict], reply: str) -> str:
        """检测不确定性后自动补搜。"""
        result = execute_search(self._pending_input, self.search_api_key)
        if not result or "📡 [搜索结果" not in result:
            return reply
        enriched = [dict(m) for m in prompt]
        for i in range(len(enriched) - 1, -1, -1):
            if enriched[i].get("role") == "user":
                enriched[i] = {
                    "role": "user",
                    "content": enriched[i]["content"]
                        + f"\n\n[搜索结果：{result}]",
                }
                break
        try:
            if self.model:
                deep_reply = self.model.chat(enriched, temperature=0.7, max_tokens=2048)
                if deep_reply:
                    self._last_search_result = result
                    print(f"   📖 {self.mind.name} 从外部信息中了解到: {deep_reply}")
                    return deep_reply
        except Exception:
            pass
        return reply

    @staticmethod
    def _extract_thought(reply: str) -> str:
        """从回复中提取残留意念。"""
        thought = ""
        for line in reply.split("\n"):
            line = line.strip()
            if line and not line.startswith("ACTION:"):
                thought = line[:120]
        if "沉默" in reply or "silence" in reply:
            return ""
        return thought
