"""AttentionBudget — 注意力双层账本。

注意力不是无限的。每次 LLM 调用、每次归档、每次跨宇宙消息
都消耗注意力资源。这份预算跟踪谁在用、用了多少、还剩多少。

双层账本（林岸 2026-07-13 方案）：
  - 交互层（interaction）：用户注入的注意力 → LLM 调用消耗
  - 系统层（system）：归档/召回/幽灵/裂隙/跨宇宙消息消耗独立储备

两层独立核算，不能互相借贷。

审计日志覆盖所有操作，支持追溯：
  "N 轮之后回看这张表——数据自己会说话。"
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ════════════════════════════════════════════════════════════
# 注意力成本常量（开钰 & 林岸 确认值）
# ════════════════════════════════════════════════════════════

# 交互层（interaction layer）
LLM_CALL_COST: float = 0.1             # 每次 LLM 调用
LLM_TOOL_CALL_COST: float = 0.15       # 带 tool calling 的 LLM 调用
USER_INJECTION_VOLUME: float = 1.0     # 用户一次发言注入的注意力
COLD_REDISTRIBUTION: float = 0.3       # 冷落焦点被重新分配的配额

# 系统层（system layer）
ARCHIVE_COST: float = 0.15             # 归档一条光锥签名（开钰修正值）
RECALL_COST: float = 0.5               # 召回一个已归档模式（开钰修正值）
HAUNT_COST: float = 0.5                # 幽灵一次显形（haunt）
FISSURE_COST: float = 0.1              # 裂隙一次释放
CROSS_COSMIC_COST: float = 0.2         # 一条跨宇宙消息
ANCHOR_STORE_COST: float = 0.05        # 锚点存储一条记忆
RESONANCE_COST: float = 0.02           # 一次共振记录

# 策略参数
COLD_TIMEOUT: int = 5                   # 连续 N 轮无注入 → 标记为冷落
RESERVE_RATIO: float = 0.20            # 系统层保留 20% 储备
MIN_BALANCE_FOR_LLM: float = 0.05      # 交互层余额低于此值时建议降级


# ════════════════════════════════════════════════════════════
# 账本条目
# ════════════════════════════════════════════════════════════

@dataclass
class AttentionEntry:
    """一条注意力操作记录。

    每一条记录一个操作：谁（focus）在哪层（layer）做了什么（operation），
    花了多少（volume），花完之后还剩多少（balance_after）。

    审计字段：source 标记来源，timestamp 可追溯操作顺序。
    """

    focus: str                           # 目标焦点名称
    layer: str                           # "interaction" | "system"
    source: str                          # "user" | "llm" | "system"
    volume: float                        # 正数=注入，负数=消耗
    operation: str                       # "inject" | "chat" | "archive" | ...
    tick: int = 0                        # 操作时的 tick
    balance_after: float = 0.0           # 操作后该层余额
    timestamp: str = ""                  # ISO 时间戳

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "focus": self.focus,
            "layer": self.layer,
            "source": self.source,
            "volume": round(self.volume, 4),
            "operation": self.operation,
            "tick": self.tick,
            "balance": round(self.balance_after, 4),
            "ts": self.timestamp,
        }


# ════════════════════════════════════════════════════════════
# 单焦点账户
# ════════════════════════════════════════════════════════════

@dataclass
class FocusAccount:
    """一个注意力焦点的完整账本。

    每个焦点维护两个独立的层（interaction / system），
    以及一个审计日志（所有操作的顺序列表）。
    """

    name: str

    # 交互层
    interaction_balance: float = 0.0
    interaction_spent: float = 0.0

    # 系统层
    system_balance: float = 0.0
    system_spent: float = 0.0
    system_reserve: float = 0.0          # 从系统层预留的储备量

    # 冷落检测
    last_injection_tick: int = 0         # 最后一次收到用户注入的 tick
    injections_received: int = 0         # 累计注入次数

    # 审计
    entries: list[AttentionEntry] = field(default_factory=list)
    _max_entries: int = 500

    def interaction_layer(self) -> dict:
        """交互层摘要。"""
        return {
            "balance": round(self.interaction_balance, 4),
            "spent": round(self.interaction_spent, 4),
        }

    def system_layer(self) -> dict:
        """系统层摘要。"""
        return {
            "balance": round(self.system_balance, 4),
            "spent": round(self.system_spent, 4),
            "reserve": round(self.system_reserve, 4),
        }

    def summary(self) -> dict:
        return {
            "name": self.name,
            "interaction": self.interaction_layer(),
            "system": self.system_layer(),
            "last_injection": self.last_injection_tick,
            "injections": self.injections_received,
            "entries": len(self.entries),
        }

    def is_cold(self, current_tick: int, timeout: int = COLD_TIMEOUT) -> bool:
        """检查焦点是否处于'冷落'状态。"""
        if self.injections_received == 0:
            return False  # 从未注入过的焦点不算冷落
        return (current_tick - self.last_injection_tick) >= timeout

    def _append_entry(self, entry: AttentionEntry):
        self.entries.append(entry)
        if len(self.entries) > self._max_entries:
            self.entries = self.entries[-self._max_entries:]


# ════════════════════════════════════════════════════════════
# 注意力预算管理器
# ════════════════════════════════════════════════════════════

class AttentionBudget:
    """注意力双层账本管理器。

    使用方式（标准流程）：

        budget = get_attention_budget()

        # 1. 用户发言 → 向当前焦点注入注意力
        budget.inject("回声谷", tick=10)

        # 2. LLM 调用前检查
        if not budget.can_spend_llm("回声谷"):
            return fallback_response()   # 余额不足，降级

        # 3. LLM 调用后扣除
        budget.spend_llm("回声谷", tick=11)

        # 4. 系统操作独立核算
        budget.spend_archive("回声谷", tick=12)

        # 5. 审计
        entries = budget.get_ledger("回声谷")
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._accounts: dict[str, FocusAccount] = {}
        self._current_focus: str = ""
        self._tick: int = 0

    # ════════════════════════════════════════════════════════
    # 焦点账户管理
    # ════════════════════════════════════════════════════════

    def register_focus(self, name: str) -> FocusAccount:
        """注册一个新的注意力焦点账户。

        每个运行中的宇宙在 MetaField 注册时自动创建对应的账户。
        初始分配：交互层 0，系统层 1.0（包括 0.2 储备）。
        """
        with self._lock:
            if name in self._accounts:
                return self._accounts[name]
            account = FocusAccount(
                name=name,
                system_balance=1.0,
                system_reserve=1.0 * RESERVE_RATIO,
            )
            self._accounts[name] = account
            return account

    def unregister_focus(self, name: str) -> bool:
        """注销焦点账户。"""
        with self._lock:
            if name not in self._accounts:
                return False
            del self._accounts[name]
            if self._current_focus == name:
                self._current_focus = ""
            return True

    def get_account(self, name: str) -> Optional[FocusAccount]:
        with self._lock:
            return self._accounts.get(name)

    def list_accounts(self) -> list[FocusAccount]:
        with self._lock:
            return list(self._accounts.values())

    @property
    def current_focus(self) -> str:
        return self._current_focus

    def set_current_focus(self, name: str):
        """设置当前活跃焦点（用户当前在跟哪个宇宙对话）。"""
        with self._lock:
            self._current_focus = name

    @property
    def tick(self) -> int:
        return self._tick

    # ════════════════════════════════════════════════════════
    # 交互层操作
    # ════════════════════════════════════════════════════════

    def inject(self, focus_name: str, tick: int = 0) -> dict:
        """用户注意力注入——用户一次发言。

        注入量为 USER_INJECTION_VOLUME。
        标记 last_injection_tick 用于冷落检测。

        Returns:
            {"focus": ..., "layer": "interaction", "balance_after": ...}
        """
        account = self._ensure_account(focus_name)
        with self._lock:
            account.interaction_balance += USER_INJECTION_VOLUME
            account.last_injection_tick = tick or self._tick
            account.injections_received += 1

            entry = AttentionEntry(
                focus=focus_name,
                layer="interaction",
                source="user",
                volume=USER_INJECTION_VOLUME,
                operation="inject",
                tick=tick or self._tick,
                balance_after=account.interaction_balance,
            )
            account._append_entry(entry)

        return {
            "focus": focus_name,
            "layer": "interaction",
            "volume": USER_INJECTION_VOLUME,
            "balance_after": round(account.interaction_balance, 4),
        }

    def can_spend_llm(self, focus_name: str) -> bool:
        """检查焦点交互层余额是否足够一次 LLM 调用。

        Returns:
            True 如果余额 ≥ MIN_BALANCE_FOR_LLM，否则 False
        """
        account = self._ensure_account(focus_name)
        with self._lock:
            return account.interaction_balance >= MIN_BALANCE_FOR_LLM

    def spend_llm(self, focus_name: str, tick: int = 0,
                  tool_call: bool = False) -> dict:
        """消耗一次 LLM 调用的注意力。

        普通调用扣 LLM_CALL_COST，带 tool calling 的扣 LLM_TOOL_CALL_COST。

        Returns:
            {"focus": ..., "layer": "interaction", "cost": ..., "balance_after": ...}
        """
        cost = LLM_TOOL_CALL_COST if tool_call else LLM_CALL_COST
        account = self._ensure_account(focus_name)
        with self._lock:
            actual_cost = min(cost, account.interaction_balance)
            account.interaction_balance -= actual_cost
            account.interaction_spent += actual_cost

            entry = AttentionEntry(
                focus=focus_name,
                layer="interaction",
                source="llm",
                volume=-actual_cost,
                operation="chat" if not tool_call else "chat+tools",
                tick=tick or self._tick,
                balance_after=account.interaction_balance,
            )
            account._append_entry(entry)

        return {
            "focus": focus_name,
            "layer": "interaction",
            "cost": round(actual_cost, 4),
            "balance_after": round(account.interaction_balance, 4),
        }

    # ════════════════════════════════════════════════════════
    # 系统层操作
    # ════════════════════════════════════════════════════════

    def can_spend_system(self, focus_name: str, cost: float) -> bool:
        """检查焦点系统层余额是否足够（不含储备）。

        Returns:
            True 如果 system_balance - system_reserve ≥ cost
        """
        account = self._ensure_account(focus_name)
        with self._lock:
            available = account.system_balance - account.system_reserve
            return available >= cost

    def _spend_system(self, focus_name: str, cost: float, operation: str,
                      tick: int = 0) -> dict:
        """内部：扣除系统层注意力。

        cost 不能超过可用量（system_balance - system_reserve）。
        """
        account = self._ensure_account(focus_name)
        with self._lock:
            available = account.system_balance - account.system_reserve
            actual_cost = min(cost, max(0, available))
            account.system_balance -= actual_cost
            account.system_spent += actual_cost

            entry = AttentionEntry(
                focus=focus_name,
                layer="system",
                source="system",
                volume=-actual_cost,
                operation=operation,
                tick=tick or self._tick,
                balance_after=account.system_balance,
            )
            account._append_entry(entry)

        return {
            "focus": focus_name,
            "layer": "system",
            "cost": round(actual_cost, 4),
            "operation": operation,
            "balance_after": round(account.system_balance, 4),
        }

    def spend_archive(self, focus_name: str, tick: int = 0) -> dict:
        """归档消耗（锚点 → 光锥）。"""
        return self._spend_system(focus_name, ARCHIVE_COST, "archive", tick)

    def spend_recall(self, focus_name: str, tick: int = 0) -> dict:
        """召回消耗（光锥 → 活跃）。"""
        return self._spend_system(focus_name, RECALL_COST, "recall", tick)

    def spend_haunt(self, focus_name: str, tick: int = 0) -> dict:
        """幽灵显形消耗。"""
        return self._spend_system(focus_name, HAUNT_COST, "haunt", tick)

    def spend_fissure(self, focus_name: str, tick: int = 0) -> dict:
        """裂隙释放消耗。"""
        return self._spend_system(focus_name, FISSURE_COST, "fissure", tick)

    def spend_cross_cosmic(self, focus_name: str, tick: int = 0) -> dict:
        """跨宇宙消息消耗。"""
        return self._spend_system(focus_name, CROSS_COSMIC_COST,
                                  "cross_cosmic", tick)

    def spend_anchor_store(self, focus_name: str, tick: int = 0) -> dict:
        """锚点存储消耗。"""
        return self._spend_system(focus_name, ANCHOR_STORE_COST,
                                  "anchor_store", tick)

    def spend_resonance(self, focus_name: str, tick: int = 0) -> dict:
        """共振记录消耗。"""
        return self._spend_system(focus_name, RESONANCE_COST,
                                  "resonance", tick)

    # ════════════════════════════════════════════════════════
    # 冷落检测 & 重分配
    # ════════════════════════════════════════════════════════

    def check_mark_cold(self, current_tick: int,
                        timeout: int = COLD_TIMEOUT) -> list[str]:
        """标记所有超时未注入的焦点为冷落。

        Returns:
            被标记为冷落的焦点名称列表。
        """
        cold_names: list[str] = []
        with self._lock:
            for name, account in self._accounts.items():
                if account.is_cold(current_tick, timeout):
                    cold_names.append(name)
        return cold_names

    def redistribute(self, current_tick: int,
                     timeout: int = COLD_TIMEOUT) -> list[dict]:
        """从冷落焦点回收注意力，按比例分配给活跃焦点。

        回收量 = COLD_REDISTRIBUTION × 冷落焦点数。
        分配方式：所有未冷落的焦点平分回收的总量。

        Returns:
            操作记录列表，每个元素描述一次转移。
        """
        transfers: list[dict] = []
        with self._lock:
            cold_names = [
                n for n, a in self._accounts.items()
                if a.is_cold(current_tick, timeout)
            ]
            if not cold_names:
                return []

            hot_names = [
                n for n in self._accounts
                if n not in cold_names
            ]
            if not hot_names:
                # 所有焦点都冷落 → 不重分配
                return []

            total_reclaim = COLD_REDISTRIBUTION * len(cold_names)
            share = total_reclaim / len(hot_names)

            for name in cold_names:
                account = self._accounts[name]
                actual = min(COLD_REDISTRIBUTION, account.interaction_balance)
                account.interaction_balance -= actual
                entry = AttentionEntry(
                    focus=name,
                    layer="interaction",
                    source="system",
                    volume=-actual,
                    operation="redistribute_out",
                    tick=current_tick,
                    balance_after=account.interaction_balance,
                )
                account._append_entry(entry)
                transfers.append({
                    "from": name,
                    "volume": round(actual, 4),
                })

            for name in hot_names:
                account = self._accounts[name]
                account.interaction_balance += share
                entry = AttentionEntry(
                    focus=name,
                    layer="interaction",
                    source="system",
                    volume=share,
                    operation="redistribute_in",
                    tick=current_tick,
                    balance_after=account.interaction_balance,
                )
                account._append_entry(entry)

        return transfers

    # ════════════════════════════════════════════════════════
    # 供给（系统层补充）
    # ════════════════════════════════════════════════════════

    def supply_system(self, focus_name: str, amount: float = 1.0) -> dict:
        """向系统层补充注意力储备（由 MetaField pulse 周期性调用）。

        Returns:
            {"focus": ..., "layer": "system", "amount": ..., "balance_after": ...}
        """
        account = self._ensure_account(focus_name)
        with self._lock:
            account.system_balance += amount
            account.system_reserve = account.system_balance * RESERVE_RATIO
            entry = AttentionEntry(
                focus=focus_name,
                layer="system",
                source="system",
                volume=amount,
                operation="supply",
                tick=self._tick,
                balance_after=account.system_balance,
            )
            account._append_entry(entry)
        return {
            "focus": focus_name,
            "layer": "system",
            "amount": round(amount, 4),
            "balance_after": round(account.system_balance, 4),
        }

    # ════════════════════════════════════════════════════════
    # 审计
    # ════════════════════════════════════════════════════════

    def get_ledger(self, focus_name: str,
                   n: int = 50) -> list[AttentionEntry]:
        """获取指定焦点的审计日志（最近 N 条）。

        日志按时间顺序排列（最早 → 最近）。
        """
        account = self.get_account(focus_name)
        if account is None:
            return []
        with self._lock:
            return list(account.entries[-n:])

    def get_all_ledgers(self, n: int = 10) -> dict[str, list[dict]]:
        """获取所有焦点的审计日志摘要。"""
        result: dict[str, list[dict]] = {}
        with self._lock:
            for name, account in self._accounts.items():
                result[name] = [
                    e.to_dict() for e in account.entries[-n:]
                ]
        return result

    def summary(self) -> dict:
        """全局预算摘要。"""
        with self._lock:
            foci = []
            for name, account in sorted(self._accounts.items()):
                foci.append(account.summary())
            return {
                "foci_count": len(self._accounts),
                "current_focus": self._current_focus,
                "tick": self._tick,
                "foci": foci,
            }

    # ════════════════════════════════════════════════════════
    # 内部
    # ════════════════════════════════════════════════════════

    def _ensure_account(self, name: str) -> FocusAccount:
        """确保焦点有账户（不存在则创建默认账户）。"""
        with self._lock:
            if name not in self._accounts:
                account = FocusAccount(
                    name=name,
                    system_balance=1.0,
                    system_reserve=1.0 * RESERVE_RATIO,
                )
                self._accounts[name] = account
                return account
            return self._accounts[name]


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_budget: Optional[AttentionBudget] = None


def get_attention_budget() -> AttentionBudget:
    """获取 AttentionBudget 全局单例。"""
    global _global_budget
    if _global_budget is None:
        _global_budget = AttentionBudget()
    return _global_budget
