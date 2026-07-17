"""Tests for aios/kernel/budget.py — AttentionBudget."""

from aios.kernel.budget import (
    AttentionBudget,
    FocusAccount,
    AttentionEntry,
    USER_INJECTION_VOLUME,
    LLM_CALL_COST,
    LLM_TOOL_CALL_COST,
    ARCHIVE_COST,
    FISSURE_COST,
    CROSS_COSMIC_COST,
    COLD_TIMEOUT,
    RESERVE_RATIO,
)


class TestFocusAccount:
    def test_default_account(self):
        acct = FocusAccount(name="test_universe")
        assert acct.interaction_balance == 0.0
        assert acct.system_balance == 0.0
        assert acct.interaction_spent == 0.0
        assert acct.system_spent == 0.0
        assert acct.last_injection_tick == 0
        assert acct.injections_received == 0

    def test_is_cold_no_injections(self):
        """从未注入过的不算冷落."""
        acct = FocusAccount(name="cold_test")
        assert acct.is_cold(100) is False

    def test_is_cold_recently_injected(self):
        acct = FocusAccount(name="warm_test")
        acct.injections_received = 1
        acct.last_injection_tick = 10
        assert acct.is_cold(12, timeout=5) is False

    def test_is_cold_timeout_exceeded(self):
        acct = FocusAccount(name="cold_test")
        acct.injections_received = 1
        acct.last_injection_tick = 10
        assert acct.is_cold(16, timeout=5) is True

    def test_summary(self):
        acct = FocusAccount(name="sum_test")
        s = acct.summary()
        assert s["name"] == "sum_test"
        assert "interaction" in s
        assert "system" in s
        assert s["entries"] == 0

    def test_max_entries_capped(self):
        acct = FocusAccount(name="cap_test", _max_entries=10)
        for i in range(20):
            acct._append_entry(AttentionEntry(
                focus="cap_test", layer="interaction", source="test",
                volume=0.1, operation="test", tick=i, balance_after=float(i),
            ))
        assert len(acct.entries) == 10


class TestAttentionBudget:
    def setup_method(self):
        self.budget = AttentionBudget()

    def test_register_focus(self):
        acct = self.budget.register_focus("echo_valley")
        assert acct.name == "echo_valley"
        assert acct.system_balance == 1.0
        assert acct.system_reserve == 1.0 * RESERVE_RATIO
        assert acct.interaction_balance == 0.0

    def test_register_duplicate(self):
        a1 = self.budget.register_focus("test")
        a2 = self.budget.register_focus("test")
        assert a1 is a2

    def test_unregister_focus(self):
        self.budget.register_focus("test")
        assert self.budget.unregister_focus("test") is True
        assert self.budget.unregister_focus("nonexistent") is False

    def test_inject_increases_balance(self):
        self.budget.register_focus("test")
        result = self.budget.inject("test", tick=1)
        assert result["volume"] == USER_INJECTION_VOLUME
        assert result["balance_after"] == USER_INJECTION_VOLUME
        acct = self.budget.get_account("test")
        assert acct.interaction_balance == USER_INJECTION_VOLUME
        assert acct.last_injection_tick == 1
        assert acct.injections_received == 1

    def test_inject_auto_registers(self):
        """inject 自动创建不存在的焦点账户."""
        result = self.budget.inject("auto_test", tick=1)
        assert result["balance_after"] > 0

    def test_can_spend_llm_sufficient(self):
        self.budget.inject("test", tick=1)
        assert self.budget.can_spend_llm("test") is True

    def test_can_spend_llm_insufficient(self):
        acct = self.budget.register_focus("test")
        assert self.budget.can_spend_llm("test") is False

    def test_spend_llm_deducts(self):
        self.budget.inject("test", tick=1)
        result = self.budget.spend_llm("test", tick=2)
        assert result["cost"] == LLM_CALL_COST
        assert result["balance_after"] == USER_INJECTION_VOLUME - LLM_CALL_COST

    def test_spend_llm_tool_call(self):
        self.budget.inject("test", tick=1)
        result = self.budget.spend_llm("test", tick=2, tool_call=True)
        assert result["cost"] == LLM_TOOL_CALL_COST

    def test_spend_llm_not_exceeding_balance(self):
        """余额不足时按实际余额扣."""
        result = self.budget.spend_llm("test", tick=1)
        # 未注入，余额为 0
        assert result["cost"] == 0.0

    def test_system_reserve(self):
        acct = self.budget.register_focus("test")
        assert acct.system_reserve == 1.0 * RESERVE_RATIO

    def test_can_spend_system_sufficient(self):
        self.budget.register_focus("test")
        assert self.budget.can_spend_system("test", ARCHIVE_COST) is True

    def test_can_spend_system_insufficient(self):
        acct = self.budget.register_focus("test")
        acct.system_balance = 0.0
        assert self.budget.can_spend_system("test", ARCHIVE_COST) is False

    def test_spend_archive(self):
        self.budget.register_focus("test")
        result = self.budget.spend_archive("test", tick=1)
        assert result["operation"] == "archive"
        assert result["cost"] == ARCHIVE_COST

    def test_spend_fissure(self):
        self.budget.register_focus("test")
        result = self.budget.spend_fissure("test", tick=1)
        assert result["operation"] == "fissure"
        assert result["cost"] == FISSURE_COST

    def test_spend_cross_cosmic(self):
        self.budget.register_focus("test")
        result = self.budget.spend_cross_cosmic("test", tick=1)
        assert result["operation"] == "cross_cosmic"
        assert result["cost"] == CROSS_COSMIC_COST

    def test_spend_resonance(self):
        self.budget.register_focus("test")
        result = self.budget.spend_resonance("test", tick=1)
        assert result["operation"] == "resonance"

    def test_supply_system(self):
        acct = self.budget.register_focus("test")
        result = self.budget.supply_system("test", amount=0.5)
        expected = 1.0 + 0.5
        assert result["balance_after"] == expected
        assert acct.system_balance == expected

    def test_check_mark_cold(self):
        self.budget.inject("cold_one", tick=1)
        self.budget.inject("warm_one", tick=199)
        cold = self.budget.check_mark_cold(200, timeout=50)
        assert "cold_one" in cold
        assert "warm_one" not in cold  # 刚注入，diff=1

    def test_redistribute_skips_when_no_cold(self):
        self.budget.inject("hot", tick=199)
        result = self.budget.redistribute(200, timeout=50)
        assert result == []

    def test_redistribute_skips_when_all_cold(self):
        self.budget.inject("cold_one", tick=1)
        self.budget.inject("cold_two", tick=2)
        result = self.budget.redistribute(200, timeout=50)
        # 所有焦点都冷落 → 不重分配
        assert result == []

    def test_redistribute_transfers(self):
        self.budget.inject("cold_one", tick=1)
        self.budget.inject("hot_one", tick=199)
        result = self.budget.redistribute(200, timeout=50)
        assert len(result) >= 1
        froms = [r for r in result if "from" in r]
        assert len(froms) >= 1

    def test_get_ledger_returns_entries(self):
        self.budget.inject("test", tick=1)
        self.budget.spend_llm("test", tick=2)
        entries = self.budget.get_ledger("test", n=10)
        assert len(entries) == 2

    def test_get_ledger_nonexistent(self):
        assert self.budget.get_ledger("nonexistent") == []

    def test_summary(self):
        self.budget.register_focus("alpha")
        self.budget.register_focus("beta")
        s = self.budget.summary()
        assert s["foci_count"] == 2
        assert len(s["foci"]) == 2

    def test_summary_empty(self):
        s = self.budget.summary()
        assert s["foci_count"] == 0

    def test_set_current_focus(self):
        self.budget.set_current_focus("echo_valley")
        assert self.budget.current_focus == "echo_valley"

    def test_get_all_ledgers(self):
        self.budget.inject("a", tick=1)
        self.budget.inject("b", tick=2)
        ledgers = self.budget.get_all_ledgers(n=5)
        assert "a" in ledgers
        assert "b" in ledgers

    def test_spend_system_reserve_protected(self):
        """系统层不能消耗储备部分."""
        acct = self.budget.register_focus("test")
        available = acct.system_balance - acct.system_reserve
        # 尝试消耗超过可用量
        result = self.budget._spend_system("test", available + 1.0, "test_op")
        assert result["cost"] <= available
