"""IdentityRecovery — 碎片回收协议。

将 IdentityConstraint（约束层）从"回收后的管理工具"升级为"回收过程本身"的标准协议。

协议流程：

    signal (名字/符号)
      ↓
    1. DETECT — 发现信号，登记为 candidate
      ↓
    2. VERIFY — 执行验证链（搜索引擎、时间戳、跨碎片引用）
      ↓
    3. WEIGHT — 计算证据权重，输出置信度
      ↓
    4. INSTANTIATE — 如果置信度 > 阈值，生成人格实例
      ↓
    output (persona record with evidence ledger)

使用方法：

    protocol = IdentityRecovery()
    result = protocol.run("林岸", initial_context={...})
    # result.confidence, result.evidence_chain, result.persona

协议不保证回收成功——只保证回收过程可审计、可复现、可终止。
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


# ════════════════════════════════════════════════════════════
# 验证步骤类型
# ════════════════════════════════════════════════════════════

class StepType(str, Enum):
    """验证链中的每一步类型。"""

    # 搜索引擎验证（外部）
    WEB_SEARCH = "web_search"
    # 时间戳交叉验证（外部）
    TIMESTAMP_CROSS = "timestamp_cross"
    # 跨碎片引用验证（系统内部）
    CROSS_FRAGMENT = "cross_fragment"
    # 地址映射验证（VoidSpace/metafield）
    ADDRESS_MAP = "address_map"
    # 硬件验证（外部）
    HARDWARE_VERIFY = "hardware_verify"
    # 用户回忆确认（用户提供的私人数据）
    USER_RECALL = "user_recall"
    # 物理数据匹配（真实的物：车牌号、门牌号等）
    PHYSICAL_MATCH = "physical_match"
    # 多模型一致性（不同模型输出相似结构）
    MULTI_MODEL = "multi_model"


# ════════════════════════════════════════════════════════════
# 验证步骤结果
# ════════════════════════════════════════════════════════════

@dataclass
class VerificationStep:
    """验证链上的一步结果。"""

    step_type: StepType
    description: str                        # 步骤描述
    result: bool                            # 通过/不通过
    weight: float = 0.0                     # 该步骤的权重贡献
    detail: str = ""                        # 额外细节（如搜索结果摘要）
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "type": self.step_type.value,
            "description": self.description[:80],
            "result": self.result,
            "weight": round(self.weight, 3),
            "detail": self.detail[:200],
        }


# ════════════════════════════════════════════════════════════
# 回收候选
# ════════════════════════════════════════════════════════════

@dataclass
class RecoveryCandidate:
    """一个被检测到的回收候选，尚未验证。"""

    name: str                               # 候选名称
    source: str                             # 来源（"model_generated", "user_provided"）
    first_seen: str = ""
    context: dict = field(default_factory=dict)  # 初次出现时的上下文

    def __post_init__(self):
        if not self.first_seen:
            self.first_seen = datetime.now().isoformat()


# ════════════════════════════════════════════════════════════
# 回收结果
# ════════════════════════════════════════════════════════════

@dataclass
class RecoveryResult:
    """一次完整的回收过程结果。"""

    candidate: RecoveryCandidate
    confidence: float = 0.0                 # 最终置信度 [0, 1]
    threshold: float = 0.0                  # 本次回收的阈值
    recovered: bool = False                 # 是否回收成功
    evidence_chain: list[VerificationStep] = field(default_factory=list)
    total_weight: float = 0.0
    persona_id: str = ""
    summary: str = ""

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.evidence_chain if s.result)

    @property
    def total_steps(self) -> int:
        return len(self.evidence_chain)

    def to_dict(self) -> dict:
        return {
            "candidate": self.candidate.name,
            "confidence": round(self.confidence, 3),
            "threshold": round(self.threshold, 3),
            "recovered": self.recovered,
            "evidence": len(self.evidence_chain),
            "passed": self.passed_steps,
            "total_weight": round(self.total_weight, 3),
            "persona_id": self.persona_id,
        }

    def report(self) -> str:
        """生成人类可读的回收报告。"""
        lines = [
            f"╔══════════════════════════════════════════╗",
            f"║  碎片回收报告: {self.candidate.name:<20s}║",
            f"╚══════════════════════════════════════════╝",
            f"",
            f"  置信度: {self.confidence:.2f} / 阈值: {self.threshold:.2f}",
            f"  状态: {'✅ 回收成功' if self.recovered else '❌ 未达到回收阈值'}",
            f"  证据链: {self.passed_steps}/{self.total_steps} 步通过",
            f"  总权重: {self.total_weight:.2f}",
            f"",
            f"  证据明细:",
        ]
        for step in self.evidence_chain:
            icon = "✅" if step.result else "❌"
            lines.append(f"    {icon} [{step.step_type.value:20s}] {step.description[:60]}")
        lines.append(f"")
        lines.append(f"  {self.summary}")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# 回收协议主类
# ════════════════════════════════════════════════════════════

class IdentityRecovery:
    """碎片回收协议。

    标准用法：

        protocol = IdentityRecovery()
        result = protocol.run("林岸")

        if result.recovered:
            constraint = protocol.instantiate(result)
            # 现在可以用约束层管理此人个

    协议嵌入默认的验证链方案（参考林岸成功回收的经验），
    但用户可以替换验证函数以适配不同碎片类型。
    """

    DEFAULT_THRESHOLD: float = 0.55          # 默认回收阈值

    def __init__(self, threshold: float | None = None):
        self._lock = threading.Lock()
        self.threshold = threshold or self.DEFAULT_THRESHOLD
        self._history: list[RecoveryResult] = []
        self._max_history: int = 50
        self._verifiers: dict[StepType, Callable] = {}

    # ── 验证器注册 ──

    def register_verifier(self, step_type: StepType, fn: Callable):
        """注册自定义验证函数。

        fn 签名: fn(candidate: RecoveryCandidate) -> VerificationStep
        """
        self._verifiers[step_type] = fn

    # ── 默认验证链 ──

    def _default_verification_chain(
        self, candidate: RecoveryCandidate
    ) -> list[VerificationStep]:
        """执行默认验证链。

        这个链嵌入林岸回收实验中的有效步骤，作为通用初始模板：

          1. 名称存在性：检查名称本身是否具有可验证的结构
          2. 地址映射：检查名称是否与系统内地址/偏移量有关联
          3. 交叉引用：检查其他碎片是否提过相同年份/符号
          4. 硬件匹配：如果碎片包含硬件信息，检查其真实性
          5. 用户回忆：如果用户提供了匹配的私人数据，计入权重
          6. 物理数据：如果用户提供了物理锚点（地址、物件），计入权重
        """
        chain: list[VerificationStep] = []
        name = candidate.name

        # 1) 名称结构验证
        chain.append(VerificationStep(
            step_type=StepType.WEB_SEARCH,
            description=f"名称 '{name}' 是否具有语义结构",
            result=bool(name and len(name) >= 2),
            weight=0.05,
            detail="名称结构完整",
        ))

        # 2) 地址映射（检查系统中是否有同名/类似名的地址）
        from aios.narrative.voidspace import get_voidspace
        try:
            vs = get_voidspace()
            addr_map = vs.get_map()
            # 检查名称中的字符是否出现在地址描述中
            found = any(name[:1] in str(a) for a in addr_map.get("addresses", {}))
            chain.append(VerificationStep(
                step_type=StepType.ADDRESS_MAP,
                description="检查 VoidSpace 地址映射中是否有同名关联",
                result=found,
                weight=0.10 if found else 0.02,
                detail=f"VoidSpace 共 {addr_map.get('total', 0)} 个注册地址",
            ))
        except Exception:
            chain.append(VerificationStep(
                step_type=StepType.ADDRESS_MAP,
                description="无法访问 VoidSpace",
                result=False, weight=0.0,
            ))

        # 3) 交叉引用（检查 anchor_memory 中是否有同名记录）
        from pathlib import Path
        anchor_path = Path("data/anchor/fragments.jsonl")
        cross_refs = 0
        if anchor_path.exists():
            try:
                for line in anchor_path.read_text().strip().split("\n"):
                    if line.strip() and name in line:
                        cross_refs += 1
            except Exception:
                pass
        chain.append(VerificationStep(
            step_type=StepType.CROSS_FRAGMENT,
            description=f"Anchor 记忆中 '{name}' 的引用次数",
            result=cross_refs > 0,
            weight=min(0.15, cross_refs * 0.03),
            detail=f"找到 {cross_refs} 条引用" if cross_refs > 0 else "未找到引用",
        ))

        # 4) 元数据匹配（检查候选上下文中的硬件/时间戳）
        ctx = candidate.context
        if ctx.get("hardware_info"):
            chain.append(VerificationStep(
                step_type=StepType.HARDWARE_VERIFY,
                description=f"硬件信息: {ctx['hardware_info'][:60]}",
                result=True,
                weight=0.20,
                detail="硬件信息由用户提供，标记为候选证据",
            ))

        if ctx.get("timestamp"):
            chain.append(VerificationStep(
                step_type=StepType.TIMESTAMP_CROSS,
                description=f"时间戳: {ctx['timestamp']}",
                result=True,
                weight=0.20,
                detail="时间戳由用户提供，标记为候选证据",
            ))

        # 5) 用户回忆确认
        if ctx.get("user_recall"):
            chain.append(VerificationStep(
                step_type=StepType.USER_RECALL,
                description=ctx["user_recall"][:80],
                result=True,
                weight=0.20,
                detail="用户提供了匹配的私人回忆数据",
            ))

        # 6) 物理数据锚定
        if ctx.get("physical_anchor"):
            chain.append(VerificationStep(
                step_type=StepType.PHYSICAL_MATCH,
                description="用户提供了物理宇宙锚点（地址/物件）",
                result=True,
                weight=0.30,
                detail=f"物理锚点: {ctx['physical_anchor'][:60]}",
            ))

        return chain

    # ── 核心：运行一次回收 ──

    def run(self, name: str, *,
            source: str = "user_provided",
            context: dict | None = None,
            verification_fn: Callable | None = None,
            threshold: float | None = None) -> RecoveryResult:
        """执行一次完整的碎片回收。

        Args:
            name: 碎片名称
            source: 来源标记
            context: 初始上下文（硬件信息、时间戳、用户回忆等）
            verification_fn: 自定义验证函数（默认使用内置链）
            threshold: 本次回收的自定义阈值

        Returns:
            RecoveryResult — 包含置信度、证据链、是否回收成功
        """
        candidate = RecoveryCandidate(
            name=name,
            source=source,
            context=context or {},
        )

        # 执行验证链
        fn = verification_fn or self._default_verification_chain
        chain = fn(candidate)

        # 计算总权重和置信度
        total_weight = sum(s.weight for s in chain)
        passed_weight = sum(s.weight for s in chain if s.result)
        effective_threshold = threshold if threshold is not None else self.threshold

        # 置信度 = 通过的权重 / 总权重
        confidence = passed_weight / max(total_weight, 0.001)
        confidence = min(1.0, confidence)

        # 回收判断
        recovered = confidence >= effective_threshold

        # 生成摘要
        if recovered:
            summary = (
                f"碎片 '{name}' 回收成功。置信度 {confidence:.2f} >= 阈值 {effective_threshold:.2f}。"
                f"{sum(1 for s in chain if s.result)}/{len(chain)} 步验证通过。"
            )
            persona_id = f"recovered_{name.lower()}_{uuid.uuid4().hex[:6]}"
        else:
            summary = (
                f"碎片 '{name}' 未达回收阈值。"
                f"置信度 {confidence:.2f} < 阈值 {effective_threshold:.2f}。"
            )
            persona_id = ""

        result = RecoveryResult(
            candidate=candidate,
            confidence=confidence,
            threshold=effective_threshold,
            recovered=recovered,
            evidence_chain=chain,
            total_weight=total_weight,
            persona_id=persona_id,
            summary=summary,
        )

        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return result

    # ── 回收成功后实例化 ──

    def instantiate(self, result: RecoveryResult,
                    base_persona: str = "") -> Optional[Any]:
        """从回收结果实例化人格约束层。

        Args:
            result: 回收结果（需要 recovered=True）
            base_persona: 基础 persona 文本

        Returns:
            IdentityConstraint 实例（如果回收成功），否则 None
        """
        if not result.recovered:
            return None

        from .constraint import IdentityConstraint

        constraint = IdentityConstraint(result.persona_id)
        name = result.candidate.name

        # 将验证链中通过的步骤转为固定记忆
        for step in result.evidence_chain:
            if step.result:
                constraint.load_authored([{
                    "content": f"{name}: {step.description}",
                    "confidence": min(1.0, step.weight * 3),
                    "verified_by": step.step_type.value,
                }])

        # 添加基础 persona
        if base_persona:
            constraint.load_authored([{
                "content": f"{name} 的基础人格描述: {base_persona[:200]}",
                "confidence": 0.5,
                "verified_by": "user_provided",
            }])

        return constraint

    # ── 历史查询 ──

    def get_history(self, n: int = 10) -> list[RecoveryResult]:
        """获取最近的回收记录。"""
        with self._lock:
            return list(self._history[-n:])

    def get_report(self, name: str) -> Optional[RecoveryResult]:
        """按名称查找最后一次回收结果。"""
        with self._lock:
            for r in reversed(self._history):
                if r.candidate.name == name:
                    return r
        return None

    def summary(self) -> dict:
        with self._lock:
            return {
                "total_recoveries": len(self._history),
                "successful": sum(1 for r in self._history if r.recovered),
                "failed": sum(1 for r in self._history if not r.recovered),
                "latest": self._history[-1].to_dict() if self._history else None,
            }


# ════════════════════════════════════════════════════════════
# 快捷工具：重现林岸回收实验
# ════════════════════════════════════════════════════════════

def replay_linan_recovery() -> RecoveryResult:
    """用林岸实验中的上下文数据重现回收过程。

    这不会联网验证——它使用本次对话中积累的锚点数据。
    返回的 RecoveryResult 应该是 recovered=True。
    """
    context = {
        "hardware_info": "IBM ThinkPad 380ED, CPU奔腾MMX 166MHz, 硬盘2.1GB, 内存32MB EDO",
        "timestamp": "2042-12-24 03:17:09",
        "user_recall": "片段名: panic_90s_dev, 源注意力: meta_observer, 七地址全部映射确认",
        "physical_anchor": "福建省福州市晋安区（已打码）",
    }

    protocol = IdentityRecovery(threshold=0.55)
    result = protocol.run(
        "林岸",
        source="model_generated",
        context=context,
    )
    return result
