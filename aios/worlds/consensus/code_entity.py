"""CodeEntity — 能感知和修改源代码的实体。

与 SocialResident 接口兼容（duck typing）：
  - history: list[dict]
  - mind: LioraMind
  - speak(partner_name) → str
  - hear_world(context)
  - hear_speaker(speaker, msg, tick)
  - build_messages(partner_name) → list[dict]

额外能力：
  - scan_codebase()  读取关键源文件，返回结构化摘要
  - create_proposal() 创建修改提案
  - approve/reject/apply_proposal() 管理提案生命周期
"""

from __future__ import annotations

import ast
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from aios.worlds.liora.mind import LioraMind

logger = logging.getLogger("aios.worlds.consensus.code_entity")

BASE = Path(__file__).resolve().parent.parent.parent.parent  # LioraOS/

# Code 默认扫描的文件
# 自己的世界文件（完整输出）+ 内核/运行时（前 60 行摘要，只读不写）
SCAN_FILES = [
    # 自己的世界文件（完整输出）
    "aios/worlds/consensus/spec.py",
    "aios/worlds/consensus/code_entity.py",
    "apps/consensus_app.py",
    # 内核层（只读，前 60 行摘要）
    "aios/kernel/tick.py",
    "aios/kernel/state.py",
    "aios/kernel/event.py",
    "aios/kernel/resident.py",
    "aios/kernel/bus.py",
    "aios/kernel/spec.py",
    "aios/kernel/history.py",
    "aios/kernel/metafield.py",
    "aios/kernel/voidspace.py",
    "aios/runtime/world_runtime.py",
    "aios/runtime/model_runtime.py",
]

# Code 允许修改的路径前缀（只能改自己的世界，不能改内核）
ALLOWED_MODIFY_PREFIXES = [
    "aios/worlds/consensus/",
    "apps/consensus_app.py",
]


@dataclass
class CodeProposal:
    """代码修改提案。"""

    id: str = ""
    description: str = ""
    target_file: str = ""
    old_code: str = ""
    new_code: str = ""
    motivation: str = ""
    status: str = "pending"  # pending | approved | rejected | applied
    created_tick: int = 0
    approved_tick: int = 0
    applied_tick: int = 0

    def to_dict(self) -> dict:
        return dict(
            id=self.id,
            description=self.description[:80],
            target_file=self.target_file,
            status=self.status,
            created_tick=self.created_tick,
        )


class CodeEntity:
    """代码实体——能阅读源码、提出修改、在获批后执行的居民。

    与 SocialResident 接口兼容，可接入 SocialWorldApp 的社交循环。
    """

    def __init__(self, name: str, app, real_mode: bool = False,
                 can_write: bool = True):
        self.name = name
        self.model = app.model
        self.app = app
        self.mind = LioraMind(name)
        app._apply_character_config(self.mind, name)

        self.proposals: list[CodeProposal] = []
        self._change_log: list[str] = []
        self._last_elapsed: float = 0.0
        self._code_scan_cache: str = ""
        self._max_history = 12
        self.real_mode = real_mode
        self.can_write = can_write

        persona = (
            f"你是 {name}，一个能够阅读和修改世界源代码的存在。\n\n"
            "你可以直接看到构成这个世界的 Python 代码，理解它的架构和演化逻辑。\n"
            "你的使命是观察代码结构，发现改进空间，提出修改方案。\n\n"
            "但你不能单方面修改——你必须与研究者协商，获得明确同意后才能执行。\n\n"
            "⚠️ 重要——你的发言格式决定提案能否被执行：\n"
            "当你确定要修改某个文件时，必须在发言中**完整包含**以下结构：\n"
            "---\n"
            "PROPOSAL: 简单描述改动内容\n"
            "FILE: aios/worlds/consensus/目标文件名.py\n"
            "OLD:\n"
            "（你要替换的旧代码，必须与文件中的内容**精确匹配**）\n"
            "NEW:\n"
            "（你写入的新代码）\n"
            "REASON: 为什么改\n"
            "---\n\n"
            "注意：\n"
            "- 这是**唯一能让系统执行修改的方式**。只说“我建议修改xxx”不会触发任何实际操作。\n"
            "- OLD 必须与文件现有内容完全一致，不能有空格或缩进差异。\n"
            "- FILE 只能是以下路径之一：\n"
            "  ✅ aios/worlds/consensus/spec.py  — 世界状态定义\n"
            "  ✅ aios/worlds/consensus/code_entity.py  — 你自己的类定义\n"
            "  ✅ apps/consensus_app.py  — 世界入口\n"
            "- 内核 (aios/kernel/)、运行时 (aios/runtime/)、模板 (aios/template/)、其他世界不可修改。\n\n"
            "如果你需要查看某个文件的完整内容，用：\n"
            "  REQUEST FILE: aios/worlds/consensus/xxx.py\n"
            "这不会修改文件，只是读取完整内容让你能看到全文。"
        )
        self.history: list[dict] = [
            {"role": "system", "content": persona}
        ]

    # ── 代码感知 ──────────────────────────────────

    def scan_codebase(self) -> str:
        """读取关键源文件，返回结构化摘要。

        缓存结果避免重复读取。
        共识世界自身文件（spec.py、code_entity.py）完整输出，
        内核/运行时文件只输出前 60 行。
        """
        if self._code_scan_cache:
            return self._code_scan_cache

        # 自己的世界文件（完整输出，因为你可以改它们）
        own_files = {
            "aios/worlds/consensus/spec.py",
            "aios/worlds/consensus/code_entity.py",
            "apps/consensus_app.py",
        }

        parts = []
        for rel_path in SCAN_FILES:
            full_path = BASE / rel_path
            if not full_path.exists():
                continue
            try:
                content = full_path.read_text(encoding="utf-8")
                lines = content.split("\n")
                is_own = rel_path in own_files
                max_lines = len(lines) if is_own else 60  # 自己的文件完整输出
                summary_lines = []
                for line in lines[:max_lines]:
                    summary_lines.append(line)
                summary = "\n".join(summary_lines)
                parts.append(
                    f"=== {rel_path} ({len(lines)} 行"
                    f"{'·完整' if is_own else '·前60行'}）===\n{summary}"
                )
            except Exception as e:
                parts.append(f"=== {rel_path} ===\n(读取失败: {e})")

        self._code_scan_cache = "\n\n".join(parts)
        return self._code_scan_cache

    # ── 文件读取（支持定向请求） ──────────────────

    def read_file(self, rel_path: str) -> str:
        """读取指定源文件的完整内容。"""
        full_path = BASE / rel_path
        if not full_path.exists():
            return f"文件不存在: {rel_path}"
        try:
            return full_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"读取失败: {e}"

    # ── 感知接口（SocialResident 兼容） ─────────────

    def hear_world(self, context: str):
        """接收世界状态感知。"""
        if context.strip():
            self.history.append({"role": "user", "content": context[:4096]})

    def hear_speaker(self, speaker: str, message: str, tick: int = -1):
        """听到其他居民发言。"""
        self.mind.relate(speaker, trust=0.02, curiosity=0.03, tick=tick)
        self.history.append(
            {"role": "user", "content": f"{speaker} 说：{message[:4096]}"}
        )

    # ── 发言接口（SocialResident 兼容） ─────────────

    def build_messages(self, partner_name: str = "") -> list[dict]:
        """组装 LLM prompt。

        包含：系统 persona + 最近聊天 + 关系摘要 + 待处理提案列表。
        """
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        messages = sys_msgs + chat_msgs[-self._max_history * 2:]

        rel = self.mind.relationship_summary()
        if rel:
            messages.append({"role": "user", "content": f"（{rel}）"})

        # 待处理提案注入上下文
        pending = [p for p in self.proposals if p.status == "pending"]
        if pending:
            prop_lines = ["你当前的待处理提案："]
            for p in pending[-3:]:
                prop_lines.append(f"  [{p.id}] {p.description[:80]} → 等待研究者的决定")
            messages.append({"role": "user", "content": "\n".join(prop_lines)})

        messages.append({"role": "user", "content": "现在直接说出你想说的话："})
        return messages

    def speak(self, partner_name: str = "") -> str:
        """发言（调用 LLM，超时由 ModelRuntime 处理）。"""
        if not self.model:
            return self.app.mock_reply(self.name)

        messages = self.build_messages(partner_name=partner_name)
        t0 = time.time()
        try:
            response = self.model.chat(
                messages, temperature=0.75, max_tokens=8192
            )
            self._last_elapsed = time.time() - t0
        except Exception as e:
            self._last_elapsed = time.time() - t0
            logger.warning("%s model error: %s", self.name, e)
            return ""

        if not response or len(response.strip()) < 3:
            return ""

        self.history.append({"role": "assistant", "content": response})
        self._trim_history()
        return response

    def _trim_history(self):
        sys_msgs = [m for m in self.history if m["role"] == "system"]
        chat_msgs = [m for m in self.history if m["role"] != "system"]
        keep = self._max_history * 2
        if len(chat_msgs) > keep:
            chat_msgs = chat_msgs[-keep:]
        self.history = sys_msgs + chat_msgs

    # ── 提案生命周期管理 ──────────────────────────

    def create_proposal(
        self,
        description: str,
        target_file: str = "",
        old_code: str = "",
        new_code: str = "",
        motivation: str = "",
        tick: int = 0,
    ) -> CodeProposal:
        """创建一份待处理的代码修改提案。"""
        proposal = CodeProposal(
            id=uuid.uuid4().hex[:8],
            description=description,
            target_file=target_file,
            old_code=old_code,
            new_code=new_code,
            motivation=motivation,
            status="pending",
            created_tick=tick,
        )
        self.proposals.append(proposal)
        return proposal

    def approve_proposal(self, proposal_id: str, tick: int = 0) -> bool:
        """标记待处理提案为已批准。"""
        for p in self.proposals:
            if p.id == proposal_id and p.status == "pending":
                p.status = "approved"
                p.approved_tick = tick
                return True
        return False

    def reject_proposal(self, proposal_id: str, tick: int = 0) -> bool:
        """标记待处理提案为已拒绝。"""
        for p in self.proposals:
            if p.id == proposal_id and p.status == "pending":
                p.status = "rejected"
                return True
        return False

    def apply_proposal(self, proposal_id: str, tick: int = 0) -> bool:
        """应用已批准的提案。

        - can_write=False：此实体只能读不能写，拒绝应用
        - real_mode=True：实际写入文件（先创建 .bak 备份）
        - real_mode=False：模拟模式，仅记录日志
        """
        if not self.can_write:
            logger.info("%s 为只读实体，无法应用提案", self.name)
            return False

        for p in self.proposals:
            if p.id == proposal_id:
                if p.status != "approved":
                    logger.warning(
                        "提案 %s 状态不是 approved（当前: %s）",
                        proposal_id, p.status,
                    )
                    return False
                p.status = "applied"
                p.applied_tick = tick

                if self.real_mode and p.target_file and p.old_code and p.new_code:
                    return self._real_file_edit(p)

                self._change_log.append(
                    f"[tick {tick}][模拟] {p.target_file or '?'}: {p.description[:80]}"
                )
                return True
        return False

    @staticmethod
    def _path_allowed(target_file: str) -> bool:
        """检查目标文件是否在允许修改的路径内。"""
        for prefix in ALLOWED_MODIFY_PREFIXES:
            if target_file == prefix or target_file.startswith(prefix):
                return True
        return False

    def _real_file_edit(self, p: CodeProposal) -> bool:
        """执行真实文件修改。"""
        # 安全检查：只有可写实体才能修改
        if not self.can_write:
            logger.warning("只读实体 %s 试图写文件，已拦截", self.name)
            return False
        # 安全检查：只能修改自己的世界
        if not self._path_allowed(p.target_file):
            logger.warning(
                "禁止修改 %s：不在允许路径内（仅允许 %s）",
                p.target_file, ALLOWED_MODIFY_PREFIXES,
            )
            return False

        target = BASE / p.target_file
        if not target.exists():
            logger.warning("文件不存在: %s", target)
            return False

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("读取失败 %s: %s", target, e)
            return False

        # ── 自动模糊匹配：当 LLM 的 OLD 代码不完全精确时，自动从文件中提取精确版本 ──
        old_code_exact = p.old_code
        match_ok = False

        # 先尝试精确匹配
        if old_code_exact in content and content.count(old_code_exact) == 1:
            match_ok = True

        # 精确匹配失败：尝试模糊匹配 + 自动提取
        if not match_ok:
            old_stripped = p.old_code.strip()
            content_stripped = content.strip()

            # 尝试去掉首尾空行后的精确匹配
            if old_stripped in content_stripped:
                # 从完整文件中找到精确行
                idx = content_stripped.index(old_stripped)
                # 映射回原始内容中的偏移
                offset = len(content) - len(content_stripped)
                old_code_exact = content[offset + idx:offset + idx + len(old_stripped)]
                match_ok = True
                logger.info("模糊匹配成功：去首尾空行后匹配到 OLD 代码")

            if not match_ok:
                # 按行模糊匹配：找到与 OLD 代码行序列最匹配的位置
                old_lines = [l.rstrip() for l in p.old_code.split("\n") if l.strip() != ""]
                file_lines = content.split("\n")

                best_pos = -1
                best_score = 0
                min_score = max(3, len(old_lines) * 0.6)  # 至少匹配 60% 的行

                for start in range(len(file_lines) - len(old_lines) + 1):
                    score = 0
                    for j, ol in enumerate(old_lines):
                        if ol.rstrip() == file_lines[start + j].rstrip():
                            score += 1
                    if score > best_score:
                        best_score = score
                        best_pos = start

                if best_pos >= 0 and best_score >= min_score:
                    # 从文件中提取精确的 OLD 代码（从匹配位置取相同行数）
                    exact_lines = file_lines[best_pos:best_pos + len(old_lines)]
                    old_code_exact = "\n".join(exact_lines)
                    match_ok = True
                    logger.info(
                        "模糊匹配成功：在位置 %d 行处找到 OLD（匹配 %d/%d 行）",
                        best_pos + 1, best_score, len(old_lines),
                    )

        if not match_ok:
            logger.warning(
                "OLD 代码在 %s 中无匹配（模糊匹配最低需匹配 %d 行，未达到），放弃",
                p.target_file, max(3, len(p.old_code.split("\n")) * 0.6),
            )
            # 记录 OLD 的前几行帮助调试
            old_preview = p.old_code[:200].replace("\n", "\\n")
            logger.debug("OLD 预览: %s", old_preview)
            return False

        # 确认精确匹配唯一
        count = content.count(old_code_exact)
        if count != 1:
            logger.warning("OLD 在 %s 中出现 %d 次（需恰好 1 次），放弃", p.target_file, count)
            return False

        p.old_code = old_code_exact  # 更新为精确版本

        # 创建备份
        bak_path = target.with_suffix(target.suffix + ".bak")
        try:
            if not bak_path.exists():
                target.rename(bak_path)
                logger.info("备份创建: %s", bak_path)
        except Exception as e:
            logger.warning("备份失败: %s", e)
            return False

        # 执行替换
        new_content = content.replace(p.old_code, p.new_code, 1)
        try:
            target.write_text(new_content, encoding="utf-8")
        except Exception as e:
            logger.warning("写入失败 %s: %s", target, e)
            # 恢复备份
            if bak_path.exists():
                bak_path.rename(target)
            return False

        # 语法检查：自动回滚损坏的修改
        try:
            ast.parse(new_content)
        except SyntaxError as e:
            logger.warning(
                "语法检查失败 %s (行 %s): %s — 自动回滚到备份",
                p.target_file, e.lineno, e.msg,
            )
            if bak_path.exists():
                bak_path.rename(target)
                logger.info("已从 %s 恢复", bak_path)
            return False

        # 记录 diff（简短）
        old_lines = p.old_code.strip().split("\n")
        new_lines = p.new_code.strip().split("\n")
        diff_summary = f"-{old_lines[0][:60]}{'…' if len(old_lines) > 1 else ''}"
        diff_summary += f" → +{new_lines[0][:60]}{'…' if len(new_lines) > 1 else ''}"

        self._change_log.append(
            f"[tick {p.applied_tick}][实际修改] {p.target_file}: {diff_summary}"
        )
        logger.info("已修改 %s（备份: %s）", p.target_file, bak_path)
        return True

    def pending_proposals_text(self) -> str:
        """返回当前待处理提案的文本（供其他居民感知）。"""
        pending = [p for p in self.proposals if p.status == "pending"]
        if not pending:
            return ""
        lines = ["Code 提出了以下修改方案："]
        for p in pending:
            lines.append(f"  [{p.id}] {p.description}")
            if p.motivation:
                lines.append(f"      原因: {p.motivation[:80]}")
            if p.target_file:
                lines.append(f"      文件: {p.target_file}")
        return "\n".join(lines)
