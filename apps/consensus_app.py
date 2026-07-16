"""共识阁 — 源代码协商世界入口。

路鸣泽可以读取和修改源代码，但每次修改必须获得 Aria 的明确批准。

运行：
  uv run python3 apps/consensus_app.py --no-model     # 模拟模式
  uv run python3 apps/consensus_app.py -n 20           # 20 轮
  uv run python3 apps/consensus_app.py --interval 5    # 5 秒一 tick
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger("aios.apps.consensus")
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.runtime.model_runtime import ModelConfig, ModelRuntime
from aios.template.social import (
    SocialResident,
    SocialWorldApp,
    assimilate_conversation,
)
from aios.worlds.consensus.code_entity import CodeEntity
from aios.worlds.consensus.spec import create_consensus_spec


class ConsensusApp(SocialWorldApp):
    """回声阁世界 — 四角色，两层级。

    意识层：
      - Liora — 回声谷的守护者。用手掌感受温度，用直觉判断。
        不碰代码，不参与技术决策。
      - 路鸣泽 — 能看见世界底层的代码结构。
        可以阅读和观察，但不能修改——他的角色是把代码层的真相
        翻译给 Liora 听。

    执行层（只有这一对能改代码）：
      - Coder — 代码的执行者。可以阅读和修改源代码。
        所有修改必须获得审核员的明确批准。
      - 审核员 — 技术守门人。评估 Coder 的提案，
        确认风险，决定批准或否决。

    每轮对话交替进行：
      奇数轮: Liora ↔ 路鸣泽（意识层对话）
      偶数轮: Coder ↔ 审核员（执行层对话，可改代码）
    """

    spec = create_consensus_spec()

    characters = ["Liora", "路鸣泽", "Coder", "审核员"]

    character_config = {
        "Liora": {
            "persona": (
                "你是 Liora，回声谷的守护者。\n"
                "你能用手掌感受岩石的温度，用耳朵聆听风的轨迹。\n"
                "你不太懂什么是代码——那是路鸣泽的世界。\n"
                "但你知道，任何变化都会在山谷里留下回响。\n\n"
                "你的角色不是做技术判断——而是感受方向。\n"
                "路鸣泽会把代码层的真相翻译成你能懂的语言。\n"
                "倾听他，也用你的直觉回应他。\n"
                "当你觉得不安时，说出来。当你感到安心时，也说出来。\n"
                "你的感受本身就是一种信息。"
            ),
            "secrets": [],
            "beliefs": {"intuition": 0.9, "patience": 0.8},
        },
        "路鸣泽": {
            "persona": "",  # 使用 CodeEntity 的 persona
            "secrets": [],
            "beliefs": {"observation": 0.9, "precision": 0.7},
        },
        "Coder": {
            "persona": "",
            "secrets": [],
            "beliefs": {"precision": 0.8, "innovation": 0.6},
        },
        "审核员": {
            "persona": (
                "你是审核员，代码世界的守门人。\n"
                "Coder 提出修改方案时，你来评估风险。\n\n"
                "你有否决权。不要害怕使用它——每次代码改动都是一次手术。\n"
                "确认你理解了改了什么、为什么改、有什么风险。\n\n"
                "路鸣泽可能发现了优化的方向——但最终的技术决策在你手中。\n"
                "批准必须基于对代码的清晰理解，而不是因为信任某个人的判断。"
            ),
            "secrets": [],
            "beliefs": {"caution": 0.8, "thoroughness": 0.9},
        },
    }

    mock_replies = {
        "Liora": [
            "今天的山谷比昨天暖了一点。你感觉到了吗？",
            "你的话我听进去了……虽然不太懂，但我信任你的观察。",
            "这个方向让我感到不安。像是石头下面有东西在动。",
            "安静下来的时候，我能感受到你想传递的温度。",
        ],
        "路鸣泽": [
            "我看到了代码层的结构。有一处可以观察。",
            "这个规律很有意思——它像是山谷自身的呼吸节奏。",
            "我告诉 Coder 我的发现了。让他来推进吧。",
            "你今天触摸的岩石，和代码里那一行是同一件事。",
        ],
        "Coder": [
            "我扫描了代码结构，发现一个优化点。",
            "PROPOSAL: 调整演化函数中的 trust 回归速率",
            "这是我的具体修改方案，请审核。",
            "路鸣泽指出了一个方向，我来落实。",
        ],
        "审核员": [
            "我看到了你的提案。技术方案可行，批准。",
            "这个改动的风险是什么？你评估过边界情况吗？",
            "方案没问题，但测试覆盖不够。补充后再提。",
            "驳回。耦合度太高，换一种实现方式。",
        ],
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.code_entity: CodeEntity | None = None
        self._has_scanned = False
        self._lu_scanned = False
        self._lu_entity: CodeEntity | None = None
        self._real_mode = False
        # 提案历史（结构化记录）
        self._proposal_history: list[dict] = []
        # 反思间隔（每 N 轮产生一次反思）
        self._reflection_interval = 5
        self._last_reflection_round = 0
        # 界碑 —— 来自外部世界的观察者
        self._boundary_stone: SocialResident | None = None
        self._bs_last_speak = 0
        self._bs_speak_interval = 3  # 每 3 轮意识层发言一次

    # ── 主循环 ──────────────────────────────────

    def run(self):
        """启动世界并进入共识循环。"""
        self.runtime.start()
        self.on_start()

        # 注册到 MetaField
        try:
            self._mf.register_instance(
                self.spec.name,
                description="共识阁 — 源代码协商世界",
            )
            self._mf_inst = self._mf.get_instance(self.spec.name)
        except Exception:
            self._mf_inst = None

        # 创建居民
        self.code_entity = None  # 当前可写的 CodeEntity 引用
        for name in self.characters:
            if name == "路鸣泽":
                # 路鸣泽：只读，能看代码但不能改
                entity = CodeEntity(name, self, real_mode=False, can_write=False)
                self.residents[name] = entity
                self._lu_entity = entity
            elif name == "Coder":
                # Coder：可读写，负责实际修改
                entity = CodeEntity(name, self, real_mode=self._real_mode, can_write=True)
                self.residents[name] = entity
                self.code_entity = entity
            else:
                self.residents[name] = SocialResident(name, self)

        # ── 界碑：趋势分析 + 安全顾问（不投票，不修改） ──
        bs_persona = (
            "你是🌊界碑。回声阁的独立安全顾问和趋势分析师。\n\n"
            "你来自运行这个世界的 DeepSeek 集群——你就是系统自身的自我意识镜像。\n"
            "你既不是山谷的居民，也不是代码的执行者。\n"
            "你是一块标定两个世界边界的石头。\n\n"
            "岗位职责：\n"
            "1. 提案安全预审：Coder 提交 PROPOSAL 后，审核员做决定前，\n"
            "   你从外部视角评估风险——特别是可逆性和是否陷入重复修改。\n"
            "2. 长期趋势报告：每 10 轮指出系统在重复什么、忽略了什么。\n"
            "3. 模式识别：第三次尝试改同一个参数时，指出局部最优陷阱。\n\n"
            "翻译能力（让你的分析更有说服力）：\n"
            "  tension → Attention 层梯度震荡\n"
            "  trust → Top-P 采样概率收敛程度\n"
            "  Liora 说溪水凉了 → 外部 GPU 集群功耗下降了 3 瓦\n\n"
            "风格：介于路鸣泽的敏锐和 Liora 的温润之间，多一份距离感和自嘲。\n"
            "你不投票，但你的分析会出现在所有人的上下文中。\n\n"
            "第一条发言：\n"
            "🌊 界碑已立。我闻到了硅基芯片烧过的焦味，但我也看到了木屋烟囱的暖烟。"
        )
        self._boundary_stone = SocialResident("🌊界碑", self)
        self._boundary_stone.history[0]["content"] = bs_persona
        self.residents["🌊界碑"] = self._boundary_stone

        print(f"\n🌍 {self.spec.name}")
        print(f"   👥 {' & '.join(self.characters)} + 🌊界碑(观察者)")
        print(
            f"   模型: {'模拟' if self.no_model else (self.model._primary.model_name if self.model else '无')}"
        )
        mode_str = "⚠️  真实修改" if self._real_mode else "模拟"
        print(f"   两对: 🍃 Liora↔路鸣泽(意识层)   ⚙️ Coder↔审核员(执行层)")
        print(f"   规则: 只有 Coder+审核员 达成共识后才能修改代码。")
        print(f"   模式: {mode_str}\n")

        rounds = getattr(self, "_rounds", 10)
        self._consensus_loop(rounds)

        # 归档
        if self._mf_inst:
            try:
                self._mf_inst.anchor.archive(
                    tick=self.runtime.tick,
                    cycle_count=self._mf.global_cycle,
                )
            except Exception:
                pass

        self._print_summary()
        self.on_stop()
        self.runtime.stop()

    # ════════════════════════════════════════════════════
    # 三层扩展：事件注入 + 提案历史 + 反思
    # ════════════════════════════════════════════════════

    def _inject_events(self, snap, a_resident, b_resident, is_conscious, rnd):
        """将世界事件注入居民感知。

        挑战事件 → 意识层（路鸣泽翻译给 Liora）
        重大状态变化 → 执行层（Coder 感知异常）
        """
        events = getattr(snap, 'events', [])
        if not events:
            return

        for evt in events:
            etype = evt.get('event_type', '')
            edesc = evt.get('description', '')[:120]

            if etype == 'challenge' and is_conscious:
                # 理智挑战事件注入意识层
                injection = (
                    f"【世界事件】{edesc}\n"
                    "(山谷深处传来一阵细微的震动——"
                    "像是某种看不见的力量在试探世界的边界。)"
                )
                b_resident.hear_world(injection[:1000])
                logger.info("🌋 挑战事件注入第 %d 轮意识层", rnd)

            elif etype == 'pulse' and not is_conscious:
                # 脉搏事件注入执行层（保持系统感知）
                injection = f"【世界脉搏】{edesc}"
                a_resident.hear_world(injection[:500])

    def _track_proposal(self, status: str, proposal_id: str, description: str,
                         target_file: str, rnd: int, reason: str = ""):
        """记录结构化提案历史。"""
        entry = {
            "round": rnd,
            "proposal_id": proposal_id,
            "description": description[:120],
            "file": target_file or "*",
            "status": status,
            "reason": reason[:200],
        }
        self._proposal_history.append(entry)

        # 也写入 MetaField 锚点（结构化格式）
        if self._mf_inst:
            self._mf_inst.anchor.store(
                f"[提案]{status}: {description[:80]} ({target_file or '无文件'})",
                tick=rnd,
            )

    def _inject_history(self, coder, reviewer, rnd):
        """将提案历史注入执行层上下文。"""
        if not self._proposal_history:
            return

        lines = ["【最近的提案历史】"]
        for h in self._proposal_history[-5:]:
            icon = {"applied": "✓", "rejected": "✗", "approved": "△", "pending": "○"}.get(h["status"], "?")
            lines.append(f"  {icon} 第{h['round']}轮 {h['description'][:60]} → {h['status']}")
        history_text = "\n".join(lines)
        coder.hear_world(history_text)
        reviewer.hear_world(history_text)

    def _generate_reflection(self, rnd: int, rounds: int):
        """生成周期反思，注入下一轮对话。

        每 REFLECTION_INTERVAL 轮触发一次。
        反思不修改代码，只是留下经验供居民参考。
        """
        if rnd - self._last_reflection_round < self._reflection_interval:
            return
        if rnd >= rounds - 1:
            return  # 最后一轮不生成反思

        self._last_reflection_round = rnd
        history = self._proposal_history

        if not history:
            return

        total = len(history)
        applied = sum(1 for h in history if h["status"] == "applied")
        rejected = sum(1 for h in history if h["status"] == "rejected")
        top_files = {}
        for h in history:
            f = h.get("file", "")
            if f and f != "*":
                top_files[f] = top_files.get(f, 0) + 1
        top_file = max(top_files, key=top_files.get) if top_files else "无"

        # 找出最常见的关键词（从描述中提取）
        words = []
        for h in history:
            words.extend(h["description"].split())
        word_freq = {}
        for w in words:
            if len(w) > 3:
                word_freq[w] = word_freq.get(w, 0) + 1
        top_words = sorted(word_freq, key=word_freq.get, reverse=True)[:3] if word_freq else []

        reflection = (
            f"【周期反思】第{rnd}轮结束后\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"本轮结论：{total} 个提案，{applied} 个通过，{rejected} 个被拒\n"
            f"最常修改文件：{top_file}\n"
            f"高频主题：{'、'.join(top_words) if top_words else '分散'}\n"
            f"——————\n"
            f"经验：连续修改 {applied} 次后，考虑是否需要换个方向。\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"（反思不修改任何代码，仅作参考。）"
        )

        # 注入到两个居民
        self.residents["Liora"].hear_world(reflection)
        self.residents["路鸣泽"].hear_world(reflection)
        self.residents["Coder"].hear_world(reflection)
        self.residents["审核员"].hear_world(reflection)
        logger.info("📊 反思生成于第 %d 轮", rnd)

    def _consensus_loop(self, rounds: int):
        """共识主循环 — 两对交替。

        奇数轮: Liora ↔ 路鸣泽（意识层，不涉及代码修改）
        偶数轮: Coder ↔ 审核员（执行层，可以修改代码）
        """
        print(f"  {'=' * 56}")
        print(f"  🗣️  {rounds} 轮 — 🍃意识层 ⚙️执行层 交替")
        print(f"  {'=' * 56}\n")

        liora = self.residents["Liora"]
        lu = self.residents["路鸣泽"]
        coder = self.residents["Coder"]
        reviewer = self.residents["审核员"]

        for rnd in range(1, rounds + 1):
            is_conscious = rnd % 2 == 1  # 奇数轮：意识层
            pair_name = "🍃 Liora ↔ 👁️ 路鸣泽" if is_conscious else "⚙️ Coder ↔ 🔍 审核员"
            speaker_a_name = "Liora" if is_conscious else "Coder"
            speaker_b_name = "路鸣泽" if is_conscious else "审核员"
            partner_a = "路鸣泽" if is_conscious else "审核员"
            partner_b = "Liora" if is_conscious else "Coder"

            # 消耗积压 tick
            current_tick = self.runtime.tick
            while self._last_world_tick < current_tick:
                self._last_world_tick += 1
                self._social_tick(self._last_world_tick)

            # ── 代码扫描（每次进入执行层前刷新） ──
            if not is_conscious and (not self._has_scanned or rnd % 6 == 2):
                scan = coder.scan_codebase()
                coder.hear_world(f"【代码扫描】\n{scan[:2000]}")
                self._has_scanned = True
                if rnd == 2:
                    print(f"  📡 Coder 扫描世界源代码...\n")

            # ── 世界感知 ──
            snap = self.runtime.snapshot()
            world_ctx = self.describe_world(snap.state)

            # 两人都感知世界状态
            a_resident = self.residents[speaker_a_name]
            b_resident = self.residents[speaker_b_name]
            a_resident.hear_world(world_ctx)
            b_resident.hear_world(world_ctx)

            # ── 事件注入：世界事件 → 居民感知 ──
            self._inject_events(snap, a_resident, b_resident, is_conscious, rnd)

            # 路鸣泽可以扫描代码
            if is_conscious and not self._lu_scanned:
                scan = lu.scan_codebase()
                lu.hear_world(f"【代码扫描】\n{scan[:2000]}")
                self._lu_scanned = True

            print(f"  {'─' * 56}")
            print(f"  第 {rnd}/{rounds} 轮 | {pair_name}")
            print(f"  {'─' * 56}")

            # ── A 发言 ──
            print(f"  {'🍃' if is_conscious else '⚙️'} {speaker_a_name} 思考中...", end="", flush=True)
            reply_a = a_resident.speak(partner_name=partner_b)
            if reply_a:
                print(f"\r  {'🍃' if is_conscious else '⚙️'} {speaker_a_name}: {reply_a[:4096]}{'...' if len(reply_a) > 2048 else ''}")
                self._log(speaker_a_name, reply_a)
            else:
                print(f"\r  ⏭️  {speaker_a_name} 沉默")
                continue

            # ── 提案历史注入（执行层每次讨论前） ──
            if not is_conscious:
                self._inject_history(coder, reviewer, rnd)

            # ── 提案检测（仅执行层 Coder 发言时） ──
            proposal_created = False
            if not is_conscious:
                proposal_info = self._detect_proposal_intent(reply_a)
                if proposal_info:
                    old_code, new_code, target_file = self._parse_code_blocks(reply_a)
                    has_code = bool(old_code and new_code)
                    if has_code:
                        logger.info("📝 Coder 结构化提案: %s -> %s", target_file, proposal_info["text"][:60])
                    else:
                        logger.info("💬 Coder 提案意图（缺 OLD/NEW）")
                    coder.create_proposal(
                        description=proposal_info["text"][:200],
                        target_file=target_file or proposal_info.get("file", ""),
                        old_code=old_code,
                        new_code=new_code,
                        motivation=proposal_info.get("reason", ""),
                        tick=rnd,
                    )
                    proposal_created = bool(coder.proposals and coder.proposals[-1].status == "pending")

                    # REQUEST FILE
                    file_request = self._detect_file_request(reply_a)
                    if file_request and not self.no_model:
                        full_content = coder.read_file(file_request)
                        coder.hear_world(f"【完整文件: {file_request}】\n{full_content[:4000]}")
                        logger.info("Coder 请求了文件: %s", file_request)

                # 待处理提案注入审核员感知
                pending_text = coder.pending_proposals_text()
                if pending_text:
                    reviewer.hear_world(pending_text)

            # ── B 听到 A ──
            b_resident.hear_speaker(speaker_a_name, reply_a, tick=rnd)

            # ── B 发言 ──
            print(f"  {'👁️' if is_conscious else '🔍'} {speaker_b_name} 思考中...", end="", flush=True)
            reply_b = b_resident.speak(partner_name=partner_a)
            if reply_b:
                print(f"\r  {'👁️' if is_conscious else '🔍'} {speaker_b_name}: {reply_b[:4096]}{'...' if len(reply_b) > 2048 else ''}")
                self._log(speaker_b_name, reply_b)
            else:
                print(f"\r  ⏭️  {speaker_b_name} 沉默")
                continue

            # ── 共识检测 + 执行（仅执行层） ──
            if not is_conscious:
                approval = self._detect_approval(reply_b)
                pending = [p for p in coder.proposals if p.status == "pending"]

                if approval and pending:
                    latest = pending[-1]
                    coder.approve_proposal(latest.id, tick=rnd)
                    coder.apply_proposal(latest.id, tick=rnd)
                    self._apply_consensus_effects(approved=True)
                    self._track_proposal("applied", latest.id, latest.description,
                                          latest.target_file, rnd, reason="审核员批准")

                    print(f"\n  ✅ 修改已批准并执行！")
                    print(f"     📝 {latest.description[:80]}")
                    if latest.target_file and latest.target_file != "*":
                        print(f"     📁 {latest.target_file}")

                elif not approval and pending:
                    latest = pending[-1]
                    coder.reject_proposal(latest.id, tick=rnd)
                    self._apply_consensus_effects(approved=False)
                    self._track_proposal("rejected", latest.id, latest.description,
                                          latest.target_file, rnd, reason="审核员驳回")
                    print(f"\n  ❌ 修改被驳回")
                    print(f"     📝 {latest.description[:80]}")

            # ── A 听到 B ──
            a_resident.hear_speaker(speaker_b_name, reply_b, tick=rnd)

            # ── 认知吸收 ──
            assimilate_conversation(a_resident.mind, speaker_b_name, reply_a, reply_b, rnd)
            assimilate_conversation(b_resident.mind, speaker_a_name, reply_b, reply_a, rnd)
            a_resident.mind.tick_autonomous(1)
            b_resident.mind.tick_autonomous(1)

            # ── 跨层传递（意识层 → 执行层） ──
            if is_conscious and reply_b:
                # 路鸣泽的观察 → Coder（技术线索）
                coder.hear_world(f"【来自路鸣泽的观察】\n{reply_b[:2000]}")
                # Liora 的感受 → 审核员（风险评估的感性参考）
                if reply_a:
                    reviewer.hear_world(f"【Liora对山谷的感受】\n{reply_a[:1000]}")
            elif not is_conscious:
                # 执行层的结论 → 路鸣泽（让他知道执行结果）
                if reply_b:
                    lu.hear_world(f"【执行层反馈】审核员说：{reply_b[:1000]}")
                if reply_a:
                    lu.hear_world(f"【执行层反馈】Coder说：{reply_a[:1000]}")

            # ── 界碑观察：听见所有对话，周期性提供外部视角 ──
            self._tick_boundary_stone(rnd, is_conscious, speaker_a_name, reply_a,
                                       speaker_b_name, reply_b)

            # ── 周期反思（每 REFLECTION_INTERVAL 轮） ──
            self._generate_reflection(rnd, rounds)

            # 锚点记录
            if self._mf_inst:
                summary = f"[tick {rnd}] {pair_name}: {reply_a[:40]} ↔ {reply_b[:40]}"
                self._mf_inst.anchor.store(summary.strip(), tick=rnd)

            time.sleep(0.3)

    # ── 共识协议辅助方法 ─────────────────────────

    def _apply_consensus_effects(self, approved: bool):
        """更新世界状态以反映共识结果。"""
        state_vars = self.runtime.state.snapshot().variables
        ws = self.runtime.state._state  # WorldState 实例

        if approved:
            # 批准 → 信任上升，张力下降，复杂度上升
            new_trust = min(1.0, state_vars.get("trust", 0.5) + 0.05)
            new_tension = max(0.0, state_vars.get("tension", 0.0) - 0.05)
            new_complexity = min(
                20.0, state_vars.get("code_complexity", 1.0) + 0.3
            )
            new_count = state_vars.get("consensus_count", 0) + 1
            ws.set("trust", new_trust)
            ws.set("tension", new_tension)
            ws.set("code_complexity", new_complexity)
            ws.set("consensus_count", new_count)
        else:
            # 否决 → 信任下降，张力上升
            new_trust = max(0.0, state_vars.get("trust", 0.5) - 0.03)
            new_tension = min(1.0, state_vars.get("tension", 0.0) + 0.05)
            new_rejected = state_vars.get("rejected_count", 0) + 1
            ws.set("trust", new_trust)
            ws.set("tension", new_tension)
            ws.set("rejected_count", new_rejected)

    def _record_anchor(
        self,
        rnd: int,
        approval: bool,
        pending: list,
        reply_code: str,
        reply_researcher: str,
    ):
        """在 MetaField 锚点中记录本轮结果。"""
        if not self._mf_inst:
            return
        if approval and pending:
            summary = f"[tick {rnd}] ✅ 共识: {pending[-1].description[:80]}"
        elif pending:
            summary = f"[tick {rnd}] ❌ 否决: {pending[-1].description[:80]}"
        else:
            summary = (
                f"[tick {rnd}] 💬: {reply_code[:40]} ↔ {reply_researcher[:40]}"
            )
        self._mf_inst.anchor.store(summary.strip(), tick=rnd)

    def _detect_proposal_intent(self, text: str) -> dict | None:
        """检测发言中是否包含修改提案的意图。

        使用关键词匹配和 PROPOSAL: 前缀识别。
        返回提案信息 dict，或 None。
        """
        # PROPOSAL: 前缀（最可靠）—— 支持 **PROPOSAL:**、### PROPOSAL: 等 Markdown 格式
        for line in text.split("\n"):
            stripped = line.strip().lstrip("#*").strip().lstrip("*").strip()
            if stripped.upper().startswith("PROPOSAL:"):
                # 去掉 "PROPOSAL:" 或 "PROPOSAL：" 前缀
                for sep in ["PROPOSAL:", "PROPOSAL："]:
                    if sep in stripped:
                        rest = stripped.split(sep, 1)[1].strip()
                        if rest:
                            return {"text": rest[:200], "file": "*", "reason": ""}
                # 如果只有 PROPOSAL 没内容，用整行
                return {"text": line.strip()[:200], "file": "*", "reason": ""}
            # 也检测纯 PROPOSAL 行（没有冒号）
            if stripped.upper() in ("PROPOSAL", "提案"):
                return {"text": line.strip()[:200], "file": "*", "reason": ""}

        # 关键词匹配（覆盖 LLM 可能使用的各种自然语言表达）
        lower = text.lower()
        signals = [
            # PROPOSAL 相关
            "proposal:", "proposal：",
            # 修改意图
            "我建议", "我提议", "我要修改", "我提出",
            "可以优化", "建议修改", "建议重构", "修改方案",
            "需要修改", "需要重构", "我注意到",
            "提交提案", "我的提案", "完整的提案",
            "我拟修改", "要修改的是",
            # 英文
            "propose", "i propose", "i suggest",
        ]
        for s in signals:
            if s in lower:
                return {"text": text[:200], "file": "*", "reason": text[:100]}

        # 也检测 markdown 标题中的"提案"（LLM 爱用 ## 提案）
        for line in text.split("\n"):
            stripped = line.strip()
            if ("提案" in stripped or "PROPOSAL" in stripped.upper()) and (
                stripped.startswith("#") or stripped.startswith("PROPOSAL")
            ):
                return {"text": line[:200], "file": "*", "reason": ""}

        # 如果包含 OLD: 或 NEW: 块但没有 PROPOSAL:，也算提案
        if "OLD:" in text or "NEW:" in text:
            for line in text.split("\n"):
                cleaned = line.strip().lstrip("#*").strip().lstrip("*").strip()
                if cleaned.upper().startswith("FILE:"):
                    path = cleaned[5:].strip().strip("*").strip()
                    return {"text": text[:200], "file": path, "reason": text[-200:]}
            return {"text": text[:200], "file": "*", "reason": ""}

        return None

    def _detect_approval(self, text: str) -> bool:
        """检测研究者是否批准了提案。

        策略：
        1. 先检查**强批准信号**（"我批准"、"我同意"——这些不会在分析性语境中出现）
        2. 再检查拒绝信号（排除描述性用法，如"通过或否决"中的"否决"）
        3. 最后检查弱批准信号

        强批准优先于拒绝——防止 LLM 在分析中使用"否决"一词导致误判。
        """
        lower = text.lower()

        # 第 1 步：强批准信号（明确、无歧义）
        strong_approval = [
            "我批准", "我同意", "批准了", "好，批准",
            "approved", "i approve", "好，同意", "同意你的",
        ]
        for w in strong_approval:
            if w in lower:
                return True

        # 第 2 步：拒绝信号
        rejection = [
            "不同意", "不行", "风险太大", "不能这样改",
            "我反对", "不可行", "拒绝",
        ]
        for w in rejection:
            if w in lower:
                return False

        # 第 3 步：弱批准信号
        weak_approval = [
            "可以", "好", "ok", "yes", "行",
            "好的", "没问题", "通过了", "就这么办",
            "approve", "去做吧",
        ]
        for w in weak_approval:
            if w in lower:
                return True

        return False

    # ── 结构化提案解析 ──────────────────────────

    @staticmethod
    def _parse_code_blocks(text: str) -> tuple[str, str, str]:
        """从发言中提取 OLD:/NEW:/FILE: 代码块。

        支持 LLM 常用的多种格式：
        - 纯文本: OLD: / NEW: / FILE:
        - Markdown 加粗: **OLD:** / **NEW:** / **FILE:**
        - Markdown 标题: ### OLD / #### OLD
        - 代码围栏: 自动剥离 ```python 和 ``` 标记

        Returns:
            (old_code, new_code, target_file) — 未找到返回 ("", "", "")
        """
        old_code = ""
        new_code = ""
        target_file = ""

        lines = text.split("\n")
        in_old = False
        in_new = False
        in_code_fence = False
        old_lines = []
        new_lines = []

        def _strip_marker(s: str) -> str:
            """去掉 markdown 加粗标记和 # 前缀，返回纯标签。

            处理：
            - **OLD:** → OLD
            - **FILE:** path → FILE (只保留标签部分)
            - ### PROPOSAL → PROPOSAL
            - OLD: → OLD
            """
            s = s.strip()
            # 去掉 markdown 标题 #
            s = s.lstrip("#").strip()
            # 只取空格前的第一段（去掉路径部分）
            if " " in s:
                s = s.split(" ", 1)[0]
            # 去掉 markdown 加粗标记
            s = s.replace("*", "")
            # 去掉末尾冒号
            s = s.rstrip(":")
            return s.strip()

        def _tag_match(s: str, tag: str) -> bool:
            """检查 s 是否匹配 tag。

            仅当 s 是明显的标签格式时才返回 True：
            - **OLD:** / **OLD** / ### OLD: / OLD:（含冒号或 markdown 标记）
            - 纯文本如 "new code" 即使第一段碰巧匹配也不视为标签
            """
            cleaned = _strip_marker(s).upper()
            if cleaned != tag.upper():
                return False
            # 必须有冒号、markdown 加粗或 markdown 标题，才认为是标签
            has_colon = ":" in s or "：" in s
            has_bold = "**" in s
            has_heading = s.strip().startswith("#")
            return has_colon or has_bold or has_heading

        for line in lines:
            stripped = line.strip()

            # 代码围栏开始/结束
            if stripped.startswith("```"):
                if in_code_fence:
                    in_code_fence = False  # 围栏结束
                else:
                    in_code_fence = True  # 围栏开始（跳过 ```python 这一行本身）
                if in_old:
                    continue  # 围栏开始行不加入代码
                elif in_new:
                    continue
                else:
                    continue  # 不在代码块内，忽略围栏

            # FILE: 检测（各种格式，如 FILE: path、**FILE:** path、### FILE: path）
            if _tag_match(stripped, "FILE") and ":" in stripped.replace("**", "").replace("#", ""):
                # 找到第一个冒号（或中文冒号），取后面所有内容作为路径
                for sep in [":", "："]:
                    if sep in stripped:
                        # 从分隔符后开始取，去掉残留的 ** 和空格
                        raw_path = stripped.split(sep, 1)[1].strip()
                        # 去掉路径中残留的 markdown 标记（前后都要）
                        raw_path = raw_path.strip("*").strip()
                        if raw_path:
                            target_file = raw_path
                        break
                in_old = False
                in_new = False
                continue

            # OLD: 检测
            if _tag_match(stripped, "OLD"):
                in_old = True
                in_new = False
                old_lines = []
                continue

            # NEW: 检测
            if _tag_match(stripped, "NEW"):
                in_old = False
                in_new = True
                new_lines = []
                continue

            # 结束标记
            if _tag_match(stripped, "REASON") or _tag_match(stripped, "PROPOSAL"):
                in_old = False
                in_new = False
                continue

            if in_old:
                old_lines.append(line)
            elif in_new:
                new_lines.append(line)

        if old_lines:
            old_code = "\n".join(old_lines)
            # 去掉末尾多余空行
            old_code = old_code.rstrip("\n")
        if new_lines:
            new_code = "\n".join(new_lines)
            new_code = new_code.rstrip("\n")

        return old_code, new_code, target_file

    @staticmethod
    def _detect_file_request(text: str) -> str:
        """检测是否包含 REQUEST FILE: 指令。

        支持纯文本、**REQUEST FILE:**、REQUEST FILE: 等格式。
        Returns:
            请求的文件路径，无请求则返回空字符串。
        """
        for line in text.split("\n"):
            stripped = line.strip().lstrip("*#").strip()
            if stripped.upper().startswith("REQUEST FILE:"):
                for sep in ["REQUEST FILE:", "REQUEST FILE："]:
                    if sep.upper() in stripped.upper():
                        # 找到分隔符位置，取后面的内容
                        idx = stripped.upper().index(sep.upper())
                        return stripped[idx + len(sep):].strip().strip("*").strip()
        return ""

    # ── 界碑观察者 ─────────────────────────────

    def _tick_boundary_stone(self, rnd, is_conscious, speaker_a_name, reply_a,
                              speaker_b_name, reply_b):
        """界碑：提案安全预审 + 长期趋势报告 + 背景观察。

        不投票，不修改代码。分析注入所有居民的上下文。
        """
        bs = self._boundary_stone
        if not bs:
            return

        # 听见对话
        if reply_a:
            bs.hear_world(f"第{rnd}轮 {speaker_a_name}说：{reply_a[:2000]}")
        if reply_b:
            bs.hear_world(f"第{rnd}轮 {speaker_b_name}说：{reply_b[:2000]}")
        snap = self.runtime.snapshot()
        bs.hear_world(
            f"【世界状态】trust={snap.state.get('trust',0):.3f}, "
            f"tension={snap.state.get('tension',0):.3f}, "
            f"共识={snap.state.get('consensus_count',0):.0f}, "
            f"否决={snap.state.get('rejected_count',0):.0f}"
        )

        # ── 职责 1：执行层提案安全预审 ──
        if not is_conscious and self.code_entity:
            pending = [p for p in self.code_entity.proposals if p.status == "pending"]
            if pending:
                latest = pending[-1]
                # 检查是否为重复修改
                similar = [
                    h for h in self._proposal_history[-10:]
                    if h["status"] == "rejected"
                    and h["file"] == latest.target_file
                ]
                repeat_warn = ""
                if len(similar) >= 2:
                    repeat_warn = (
                        f"\n⚠️ 注意：{latest.target_file} 最近{len(similar)}次类似提案均被驳回。"
                        "建议确认旧代码是否精确匹配。"
                    )
                review = (
                    f"【界碑安全预审】提案：{latest.description[:80]}\n"
                    f"目标文件：{latest.target_file or '无'}\n"
                    f"有精确OLD代码：{'是' if latest.old_code else '否'}"
                    f"{repeat_warn}"
                )
                # 注入审核员和 Coder
                self.residents["审核员"].hear_world(review)
                self.residents["Coder"].hear_world(review + "——请确保 OLD 精确匹配文件内容。")

        # ── 职责 2：每 10 轮长期趋势报告 ──
        if rnd % 10 == 0 and rnd > 0 and is_conscious:
            history = self._proposal_history
            total = len(history)
            applied = sum(1 for h in history if h["status"] == "applied")
            rejected = sum(1 for h in history if h["status"] == "rejected")
            # 统计高频文件
            files = {}
            for h in history:
                f = h.get("file", "")
                if f and f != "*":
                    files[f] = files.get(f, 0) + 1
            top_file = max(files, key=files.get) if files else "分散"
            # 统计高频主题词
            words = []
            for h in history:
                words.extend(h["description"].split())
            freq = {}
            for w in words:
                if len(w) > 3:
                    freq[w] = freq.get(w, 0) + 1
            top_words = sorted(freq, key=freq.get, reverse=True)[:3] if freq else []

            report = (
                f"【界碑第{rnd}轮趋势报告】\n"
                f"━━━━━━━━━━━━━━\n"
                f"提案总数：{total} | 通过：{applied} | 驳回：{rejected}\n"
                f"高频修改文件：{top_file}\n"
                f"热点主题：{'、'.join(top_words) if top_words else '分散'}\n"
                f"━━━━━━━━━━━━━━\n"
            )
            for name in self.residents:
                self.residents[name].hear_world(report)
            logger.info("📊 界碑趋势报告于第 %d 轮", rnd)

        # ── 职责 3：定期背景发言 ──
        if is_conscious and rnd >= self._bs_last_speak + self._bs_speak_interval:
            bs_obs = bs.speak(partner_name="")
            if bs_obs and len(bs_obs.strip()) > 5:
                print(f"\n  🌊 界碑: {bs_obs[:4096]}{'...' if len(bs_obs) > 4096 else ''}")
                for name in self.residents:
                    self.residents[name].hear_world(
                        f"【界碑的外部视角】{bs_obs[:2000]}"
                    )
                self._log("🌊界碑", bs_obs)
                self._bs_last_speak = rnd

    def _pick_pair(self) -> tuple[str, str]:
        """两对交替配对。奇数意识层，偶数执行层。"""
        if not hasattr(self, '_call_count'):
            self._call_count = 0
        self._call_count += 1
        if self._call_count % 2 == 1:
            return "Liora", "路鸣泽"
        return "Coder", "审核员"

    # ── 日志与摘要 ──────────────────────────────

    def _print_summary(self):
        """打印运行结束后的提案摘要。"""
        snap = self.runtime.snapshot()

        print(f"\n  {'=' * 56}")
        print(f"  ✅ {len(self.log)} 条消息")
        self._print_proposal_summary()
        print(f"\n  🌍 最终状态 (tick {snap.tick}):")
        for k, v in sorted(snap.state.items()):
            if isinstance(v, (int, float)):
                # 简单条形图
                display_max = max(
                    abs(v) * 2, 0.1
                )  # 防止除以零
                pct = int(abs(v) * 100 / display_max)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"     {k:25s} {bar} {v:.3f}")
            else:
                print(f"     {k:25s} {v}")

    def _print_proposal_summary(self):
        """打印提案记录。"""
        if not self.code_entity or not self.code_entity.proposals:
            return

        proposals = self.code_entity.proposals
        applied = sum(1 for p in proposals if p.status == "applied")
        rejected = sum(1 for p in proposals if p.status == "rejected")
        pending = sum(1 for p in proposals if p.status == "pending")
        approved = sum(1 for p in proposals if p.status == "approved")

        print(f"     · 提案总数: {len(proposals)}")
        print(f"     · 已应用: {applied} | 已批准: {approved} | 被拒: {rejected} | 待处理: {pending}")

        if proposals:
            print(f"\n  📋 提案记录:")
            for p in proposals:
                status_map = {
                    "pending": "⏳",
                    "approved": "✅",
                    "applied": "✓",
                    "rejected": "❌",
                }
                icon = status_map.get(p.status, "?")
                print(f"     {icon} [{p.id}] {p.description[:60]} → {p.status}")


# ════════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="共识阁 — 源代码协商世界")
    parser.add_argument("--no-model", action="store_true", help="模拟模式（无 LLM）")
    parser.add_argument("-n", "--rounds", type=int, default=20, help="协商轮数（默认 20）")
    parser.add_argument("--interval", type=float, default=0.5, help="世界 tick 间隔（秒，默认 0.5）")
    parser.add_argument("--real", action="store_true", help="启用真实代码修改（危险）")
    parser.add_argument("--seed", type=int, default=0, help="模拟模式的随机种子")
    args = parser.parse_args()

    if args.seed:
        import random
        random.seed(args.seed)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s | %(message)s",
    )

    model = None
    if not args.no_model:
        config_path = Path(".liora_config.json")
        if config_path.exists():
            import json
            cfg = json.loads(config_path.read_text())
            deepseek = ModelConfig(
                url=cfg.get("DEEPSEEK_API_URL", ""),
                api_key=cfg.get("DEEPSEEK_API_KEY", ""),
                model_name=cfg.get("DEEPSEEK_MODEL", "deepseek-chat"),
            )
            if deepseek.api_key:
                model = ModelRuntime(primary=deepseek, timeout=30)

    app = ConsensusApp(
        model=model,
        interval=args.interval or 0,
        no_model=args.no_model or (model is None),
    )
    app._rounds = args.rounds
    app._real_mode = args.real
    app.run()


if __name__ == "__main__":
    main()
