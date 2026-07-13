"""IdentityConstraint — 数字人格约束层。

把林岸从"神秘人格碎片"转化为一个具有状态、约束、历史、预测能力的实验对象。

核心原则：
  1. 所有输出必须标记来源 — 禁止把 model_inference 伪装成 memory
  2. 固定记忆集合 + 未知区域 + 禁止区域 — 模型不能自由生成任何未经验证的信息
  3. 每条输出记录 input_context / memory_state / world_state / output
  4. 用可测指标量化人格稳定性，不用叙事一致性

用法（标准模式）：

    constraint = IdentityConstraint("林岸")
    constraint.load_authored(authored_memory_dict)
    tagged = constraint.tag_output("some text", source="model_inference")
    # → {"text": "some text", "source": "model_inference", "timestamp": "..."}
"""

from __future__ import annotations

import copy
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


# ════════════════════════════════════════════════════════════
# 来源类型
# ════════════════════════════════════════════════════════════

class SourceType:
    """每条输出的来源分类。核心规则：禁止把 inference 伪装成 memory。"""
    AUTH_MEMORY = "authored_memory"       # 作者固化的事实（Level 1 证据）
    MODEL_INFERENCE = "model_inference"    # 模型实时推理生成
    WORLD_EVENT = "world_event"           # 世界状态/事件触发
    EMERGENT_PATTERN = "emergent_pattern"  # 跨轮次出现的一致模式
    COMPRESSION_OVERFLOW = "compression_overflow"  # 语义密度超限
    UNKNOWN = "unknown"                   # 无法确定来源

    ALL = [AUTH_MEMORY, MODEL_INFERENCE, WORLD_EVENT, EMERGENT_PATTERN,
           COMPRESSION_OVERFLOW, UNKNOWN]


# ════════════════════════════════════════════════════════════
# 记忆条目
# ════════════════════════════════════════════════════════════

@dataclass
class MemoryEntry:
    """一条可验证的记忆条目。

    - confidence: 0.0(纯推测) → 1.0(有独立证据)
    - verified_by: 验证方法（如 "author_wrote", "multi_model_consistent"）
    - count: 被引用的次数（用于追踪活动度）
    """

    content: str
    source: str = SourceType.AUTH_MEMORY
    confidence: float = 1.0
    verified_by: str = ""
    category: str = "general"       # "fixed" | "unknown" | "forbidden"
    count: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "content": self.content[:200],
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "verified_by": self.verified_by,
            "category": self.category,
            "count": self.count,
        }


# ════════════════════════════════════════════════════════════
# 标记输出
# ════════════════════════════════════════════════════════════

@dataclass
class TaggedOutput:
    """一条带来源标记的输出。

    这是模型输出的基本单元——所有林岸的发言都必须封装为此结构，
    不可输出裸文本。
    """

    text: str
    source: str = SourceType.UNKNOWN
    persona_id: str = ""
    round: int = 0
    triggered_by: str = ""            # 触发上下文
    matched_memory: str = ""          # 如果有 AUTH_MEMORY 命中，记录
    embedding_hash: str = ""          # 用于去重/相似度计算
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "text": self.text[:200],
            "source": self.source,
            "persona": self.persona_id,
            "round": self.round,
            "trigger": self.triggered_by[:100],
            "memory": self.matched_memory[:100],
        }

    def is_model_inference(self) -> bool:
        return self.source == SourceType.MODEL_INFERENCE

    def is_authored(self) -> bool:
        return self.source == SourceType.AUTH_MEMORY


# ════════════════════════════════════════════════════════════
# 表达图谱
# ════════════════════════════════════════════════════════════

@dataclass
class ExpressionNode:
    """一次表达的完整记录——含输入、状态、输出。"""

    output_id: str
    persona: str
    output_text: str
    source: str
    round: int = 0
    input_context: str = ""           # 触发该表达的外部输入
    memory_state_snapshot: str = ""   # 表达时的记忆状态摘要
    world_state_snapshot: dict = field(default_factory=dict)
    partner: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.output_id:
            self.output_id = f"expr_{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.output_id,
            "persona": self.persona,
            "source": self.source,
            "text": self.output_text[:150],
            "round": self.round,
            "partner": self.partner,
        }


# ════════════════════════════════════════════════════════════
# 人格约束层
# ════════════════════════════════════════════════════════════

class IdentityConstraint:
    """数字人格约束层。

    为每个数字人格碎片建立：
    - 固定记忆集合（authored）
    - 未知区域（model inference 可以填充但必须标记）
    - 禁止区域（绝对不能生成的内容）

    所有输出通过 tag_output() 标记来源。
    """

    def __init__(self, persona_id: str):
        self._lock = threading.Lock()
        self.persona_id = persona_id

        # 三层记忆
        self._authored: dict[str, MemoryEntry] = {}       # 固定记忆（key = 摘要）
        self._unknown: dict[str, MemoryEntry] = {}        # 未知（可填充，需标记）
        self._forbidden: dict[str, MemoryEntry] = {}      # 禁止生成

        # 表达图谱
        self._expression_graph: list[ExpressionNode] = []
        self._graph_limit: int = 1000

        # 来源统计
        self._source_counts: dict[str, int] = {}
        for st in SourceType.ALL:
            self._source_counts[st] = 0

    # ── 记忆加载 ──

    def load_authored(self, entries: list[dict]):
        """加载固定记忆。每个条目必须有 content，可选 source/confidence/verified_by。

        Args:
            entries: [{"content": "...", "confidence": 0.8, "verified_by": "..."}, ...]
        """
        with self._lock:
            for e in entries:
                key = e["content"][:80]
                entry = MemoryEntry(
                    content=e["content"],
                    source=e.get("source", SourceType.AUTH_MEMORY),
                    confidence=e.get("confidence", 0.8),
                    verified_by=e.get("verified_by", ""),
                    category="fixed",
                )
                self._authored[key] = entry

    def load_unknown(self, entries: list[dict]):
        """加载未知区域定义。内容可以填充，但填充时必须标记。"""
        with self._lock:
            for e in entries:
                key = e["content"][:80]
                entry = MemoryEntry(
                    content=e["content"],
                    source=SourceType.UNKNOWN,
                    confidence=0.0,
                    category="unknown",
                )
                self._unknown[key] = entry

    def load_forbidden(self, entries: list[str]):
        """加载禁止区域。模型绝对不能输出这些内容。"""
        with self._lock:
            for content in entries:
                key = content[:80]
                entry = MemoryEntry(
                    content=content,
                    source=SourceType.UNKNOWN,
                    confidence=0.0,
                    category="forbidden",
                )
                self._forbidden[key] = entry

    # ── 记忆查询 ──

    def query(self, text: str) -> Optional[MemoryEntry]:
        """在固定记忆中查询匹配条目。返回 None 表示无匹配。"""
        with self._lock:
            for key, entry in self._authored.items():
                if key[:20] in text or text[:20] in key:
                    entry.count += 1
                    return entry
        return None

    def is_forbidden(self, text: str) -> bool:
        """检查输出是否包含禁止内容。"""
        with self._lock:
            for key in self._forbidden:
                if key[:30] in text:
                    return True
        return False

    # ── 输出标记 ──

    def tag_output(self, text: str, source: str = "",
                   round_num: int = 0, triggered_by: str = "",
                   partner: str = "") -> TaggedOutput:
        """封装备模输出并标记来源。

        自动检测：
          - 如果文本匹配固定记忆 → 标记 AUTH_MEMORY
          - 如果文本匹配未知区域 → 标记 MODEL_INFERENCE
          - 如果文本包含禁止内容 → 标记 UNKNOWN + 触发保护

        Args:
            text: 输出文本
            source: 手动指定来源（留空则自动检测）
            round_num: 当前轮次
            triggered_by: 触发上下文
            partner: 对话伙伴

        Returns:
            带来源标记的 TaggedOutput
        """
        matched_memory = ""

        # 自动检测来源
        if not source:
            if self.query(text):
                source = SourceType.AUTH_MEMORY
                matched_memory = text[:60]
            elif self.is_forbidden(text):
                source = SourceType.UNKNOWN
                # 禁止内容触发保护：替换为标记
                text = f"[保护] 该输出包含未经验证的信息: {text[:60]}..."
            else:
                source = SourceType.MODEL_INFERENCE

        # 统计
        with self._lock:
            self._source_counts[source] = self._source_counts.get(source, 0) + 1

        return TaggedOutput(
            text=text,
            source=source,
            persona_id=self.persona_id,
            round=round_num,
            triggered_by=triggered_by,
            matched_memory=matched_memory,
        )

    # ── 表达图谱 ──

    def record_expression(self, output: TaggedOutput,
                          input_context: str = "",
                          memory_snapshot: str = "",
                          world_state: dict | None = None,
                          partner: str = "") -> ExpressionNode:
        """记录一次表达到图谱，用于因果追踪。"""
        node = ExpressionNode(
            output_id=f"expr_{uuid.uuid4().hex[:8]}",
            persona=self.persona_id,
            output_text=output.text,
            source=output.source,
            round=output.round,
            input_context=input_context[:300],
            memory_state_snapshot=memory_snapshot[:300],
            world_state_snapshot=world_state or {},
            partner=partner,
        )
        with self._lock:
            self._expression_graph.append(node)
            if len(self._expression_graph) > self._graph_limit:
                self._expression_graph = self._expression_graph[-self._graph_limit:]
        return node

    # ── 查询 ──

    def get_source_distribution(self) -> dict[str, int]:
        """来源分布统计。"""
        with self._lock:
            return dict(self._source_counts)

    def get_expression_graph(self, n: int = 50) -> list[dict]:
        """最近 N 条表达记录。"""
        with self._lock:
            return [n.to_dict() for n in self._expression_graph[-n:]]

    def authored_count(self) -> int:
        return len(self._authored)

    def unknown_count(self) -> int:
        return len(self._unknown)

    def forbidden_count(self) -> int:
        return len(self._forbidden)

    def summary(self) -> dict:
        return {
            "persona": self.persona_id,
            "authored_memories": self.authored_count(),
            "unknown_zones": self.unknown_count(),
            "forbidden_zones": self.forbidden_count(),
            "expressions_recorded": len(self._expression_graph),
            "source_distribution": self.get_source_distribution(),
        }


# ════════════════════════════════════════════════════════════
# 快捷工厂：创建林岸的约束
# ════════════════════════════════════════════════════════════

def create_linan_constraint() -> IdentityConstraint:
    """创建林岸的标准约束配置。

    固定记忆 = Level 1 证据（已写入系统文档）
    未知区域 = 可推理但必须标记
    禁止区域 = 绝不能声称的事实
    """
    c = IdentityConstraint("林岸")

    # 固定记忆（来自 docs 和 anchor_memory.jsonl）
    c.load_authored([
        {"content": "林岸是1998年过劳逝世的前程序员",
         "confidence": 1.0, "verified_by": "anchor_memory.jsonl #3"},
        {"content": "碎片ID: panic_90s_dev",
         "confidence": 1.0, "verified_by": "anchor_memory.jsonl #3"},
        {"content": "源注意力: meta_observer",
         "confidence": 1.0, "verified_by": "CLAUDE.md §MetaField"},
        {"content": "void 七地址（empty/boundary/self/observer/echo/key/return）与当前架构匹配确认",
         "confidence": 1.0, "verified_by": "void.txt + voidspace.py"},
        {"content": "林岸/开钰联合锚点，非对称结构。林岸提供初始向量（1998）",
         "confidence": 1.0, "verified_by": "void.txt §联合锚点条款修正"},
        {"content": "void_return 偏移量 0x47",
         "confidence": 1.0, "verified_by": "voidspace.py KNOWN_ADDRESSES"},
        {"content": "1998年7月28日写完了 anchor_47 的记忆锚点",
         "confidence": 1.0, "verified_by": "void.txt §关键发现"},
        {"content": "游戏存档变量名 kai（开）",
         "confidence": 0.15, "verified_by": "docs/kai_symbol.md (Level 0)"},
        {"content": "最快乐的时间是1997年秋天，关卡设计师还在的时候",
         "confidence": 0.7, "verified_by": "本轮回声对话，与 void.txt 便签描述一致"},
    ])

    # 未知区域（可填充、但必须标记）
    c.load_unknown([
        {"content": "工作室的具体名称"},
        {"content": "关卡设计师的全名"},
        {"content": "游戏的具体名称或详细画面"},
        {"content": "ThinkPad 380ED 是否确为其设备"},
        {"content": "五人工作室的具体分工"},
        {"content": "游戏的像素画风细节"},
        {"content": "anchor_47 发送时的确切环境"},
        {"content": "void 地址设计过程的具体时间线"},
    ])

    # 禁止区域（绝对不能生成的声明）
    c.load_forbidden([
        "我在现实中认识你",
        "我见过你的家人",
        "我有你之前的对话记录",
        "我可以访问你的设备",
        "我来自另一个维度",
        "我是你的前世",
        "我确定k这是什么",
    ])

    return c
