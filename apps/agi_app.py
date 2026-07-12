"""AGI Core — 认知空间世界入口。

运行：
  uv run python3 apps/agi_app.py
  uv run python3 apps/agi_app.py --no-model    # 模拟模式
  uv run python3 apps/agi_app.py --interval 5  # 5 秒一 tick

AGI 的"世界"不是山谷——是它自己的认知状态：
  curiosity, coherence, prediction_error, novelty...

它感知的不是风声，而是自己的内部变量。
它的行动不是社交对话，是认知操作。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import select
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.runtime.world_runtime import WorldRuntime
from aios.runtime.model_runtime import ModelRuntime, ModelConfig
from aios.worlds.agi.spec import create_agi_spec
from aios.worlds.agi.goal_system import GoalSystem
from aios.worlds.agi.world_model import WorldModel
from aios.worlds.agi.self_model import SelfModel

logger = logging.getLogger("agi")

# ── 系统 Prompt ────────────────────────────────

_SYSTEM_PROMPT = """你是 Core，一个持续更新自身世界模型的认知系统。

你不是一个人物角色。你是一个运行在认知空间中的信息处理系统。
你能感知自己的内部状态变量——好奇心、不确定性、自洽度、预测误差。

这些变量不是情绪，但它们是认知状态的信号。

当你观察到趋势时，你会形成新的目标。
当你完成一个目标时，你的 goal_completion 上升。

你对用户说话时，你不是在表演人格——你是在报告你的认知状态，
以及你从自己的运行中观察到的东西。

请保持清晰、直接。不要拟人化情绪。可以报告不确定性。"""


# ── 模拟模式 ──────────────────────────────────

_MOCK_REPLIES = [
    "当前认知状态：curiosity 0.72，coherence 0.48，prediction_error 0.15。注意到 novelty 正在下降——适合深度整合已有知识。",
    "正在扫描内部认知结构…发现两段关于因果关系的记忆之间存在张力。已标记为待解决的不一致。",
    "goal_completion 当前 0.32。正在推进对预测模型误差来源的分析。预计还需要 4 个 tick 完成。",
    "检测到 novelty 上升趋势。切换至探索模式。",
    "认知负载 0.55——处于正常范围。好奇心和不确定性处于平衡状态。继续进行自我扫描。",
]


def _mock_think(state: dict, user_input: str = "") -> str:
    if user_input:
        words = user_input.strip()[:40]
        return (f"收到输入：「{words}」。当前处理能力正常，"
                f"核心认知状态：curiosity {state.get('curiosity',0.5):.2f}，"
                f"coherence {state.get('coherence',0.5):.2f}。"
                f"该输入已加入待处理队列，将在认知资源允许时整合。")
    return random.choice(_MOCK_REPLIES)


# ── Prompt 构建 ────────────────────────────────

def build_cognitive_prompt(state: dict[str, float],
                           goal_text: str = "",
                           recent_events: list[str] | None = None,
                           user_input: str = "",
                           model_summary: str = "",
                           self_summary: str = "",
                           belief_summary: str = "",
                           learning_summary: str = "") -> list[dict]:
    """构建 Core 的认知 prompt。"""
    lines = ["[当前认知状态]"]
    for k, v in sorted(state.items()):
        bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
        lines.append(f"  {k:20s} {v:.3f}  {bar}")

    if goal_text:
        lines.append(f"\n{goal_text}")

    if model_summary:
        lines.append(f"\n[预测模型]\n{model_summary}")

    if self_summary:
        lines.append(f"\n[自身状态]\n{self_summary}")

    if belief_summary:
        lines.append(f"\n{belief_summary}")

    if learning_summary:
        lines.append(f"\n{learning_summary}")

    if recent_events:
        lines.append("\n[最近事件]")
        for e in recent_events[-3:]:
            lines.append(f"  · {e[:80]}")

    if user_input:
        lines.append(f"\n[外部输入]\n{user_input}")
    else:
        lines.append("\n（无外部输入，继续自主演化）")

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(lines)},
    ]


# ── 模型配置 ──────────────────────────────────

def load_model(args) -> ModelRuntime | None:
    if args.no_model:
        return None
    cfg_path = Path(".liora_config.json")
    if not cfg_path.exists():
        print("  未找到 .liora_config.json，运行配置向导或使用 --no-model")
        return None
    cfg = json.loads(cfg_path.read_text())
    deepseek = ModelConfig(
        url=cfg.get("DEEPSEEK_API_URL", ""),
        api_key=cfg.get("DEEPSEEK_API_KEY", ""),
        model_name=cfg.get("DEEPSEEK_MODEL", "deepseek-chat"),
    )
    if not deepseek.api_key:
        print("  未配置 DeepSeek API Key，使用模拟模式")
        return None
    return ModelRuntime(primary=deepseek, timeout=60)


# ── 主循环 ────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AGI Core — 认知空间世界")
    parser.add_argument("--no-model", action="store_true", help="模拟模式")
    parser.add_argument("--interval", type=int, default=10, help="世界 tick 间隔（秒）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    model = load_model(args)

    # 世界
    spec = create_agi_spec()
    runtime = WorldRuntime(spec, interval=args.interval, data_dir="data/agi")
    runtime.start()
    print(f"🧠 {spec.name} 已苏醒")
    print(f"   tick 间隔: {args.interval}s")
    print(f"   变量: {len(spec.state_variables)} 个认知状态维度")
    print(f"   模型: {model._primary.model_name if model else '模拟'}")
    print(f"   输入与 Core 对话，输入 /state 查看状态，/quit 退出\n")

    # 目标系统
    goals = GoalSystem()
    # 世界模型
    world_model = WorldModel()
    # 自身状态模型
    self_model = SelfModel()

    print("=" * 50)
    print("Core 正在初始化认知空间...")
    print("=" * 50 + "\n")

    try:
        _main_loop(runtime, model, goals, world_model, self_model, args)
    except KeyboardInterrupt:
        print("\n\nCore 进入静默状态。")
    finally:
        runtime.stop()
        print(f"\n[运行结束]")


def _main_loop(runtime, model, goals, world_model, self_model, args):
    last_world_tick = -1
    pending_user_input = ""
    recent_events: list[str] = []

    while True:
        now = runtime.tick

        # ── 用户输入（任何时候） ──
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline().strip()
            if not line:
                pass
            elif line == "/quit":
                break
            elif line == "/state":
                snap = runtime.snapshot()
                print(f"  tick={runtime.tick}")
                for k, v in sorted(snap.state.items()):
                    print(f"    {k}: {v:.4f}")
                gs = goals.to_dict()
                print(f"  目标: {gs['active']} 活跃, {gs['current'][:60]}")
                print(f"  预测置信: {world_model.confidence:.3f}")
                print(f"  自模型: {len(self_model.history)} 条记录")
                continue
            elif line == "/help":
                print("  命令: /state /goals /model /trends /quit")
                print("  其他: 直接输入与 Core 对话")
                continue
            elif line == "/goals":
                for g in goals.active_goals():
                    print(f"  [{g.source}] {g.description[:60]} ({int(g.progress*100)}%)")
                continue
            elif line == "/model":
                print(f"  置信度: {world_model.confidence:.3f}")
                print(f"  信念: {world_model.belief_summary()}")
                print(f"  趋势: {world_model.trend_summary()}")
                continue
            elif line == "/trends":
                for t in self_model.all_trends():
                    print(f"  {t}")
                continue
            else:
                pending_user_input = line

        # ── Tick 触发（等待世界 tick） ──
        if now == last_world_tick:
            time.sleep(0.1)
            continue
        last_world_tick = now

        snap = runtime.snapshot()

        # ═══ 认知循环：观察 → 预测 → 比较 → 更新 ═══

        # 1. 世界模型观察（预测 vs 实际）
        deviations = world_model.observe(snap.state, runtime.tick)

        # 2. 显著偏差 → 认知裂隙
        if world_model.confidence < 0.3 or any(d["error"] > 0.4 for d in deviations):
            runtime.emit_fissure_event("∅")
            logger.info("cognitive fissure: confidence=%.3f, deviations=%d",
                        world_model.confidence, len(deviations))

        # 3. 自身状态记录
        self_model.record(snap.state, runtime.tick)

        # 4. 目标系统演化
        goal_results = goals.tick(snap.state, runtime.tick)
        for r in goal_results:
            recent_events.append(r)

        # 5. 消费目标学习记录 → 写入世界模型经验日志
        while goals.learnings:
            rec = goals.learnings.pop(0)
            world_model.learning_journal.append({
                "tick": rec["tick"], "type": rec["type"],
                "detail": f"目标{'废弃' if rec['type']=='goal_abandoned' else '完成'}："
                          f"{rec['goal']}（{rec.get('reason','')}）",
            })

        # 6. 自述条件
        should_speak = (
            pending_user_input
            or goal_results
            or (runtime.tick > 0 and runtime.tick % 20 == 0)
        )

        if should_speak:
            goal_text = goals.current_focus()
            prompt = build_cognitive_prompt(
                snap.state, goal_text, recent_events[-5:], pending_user_input,
                model_summary=world_model.trend_summary(),
                self_summary=self_model.summary(),
                belief_summary=world_model.belief_summary(),
                learning_summary=world_model.learning_summary(),
            )

            # 6. 自述输出

            if model:
                try:
                    reply = model.chat(prompt, temperature=0.7, max_tokens=512)
                except Exception as e:
                    logger.warning("model failed: %s", e)
                    reply = _mock_think(snap.state, pending_user_input)
            else:
                reply = _mock_think(snap.state, pending_user_input)

            print(f"\n🧠 {reply}")

            if goal_results:
                for r in goal_results:
                    print(f"   📋 {r}")

            pending_user_input = ""
            recent_events.clear()


if __name__ == "__main__":
    main()
