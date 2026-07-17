"""Tests for aios/kernel/language.py — LanguageAttractor & enforce_budget."""

import random

from aios.kernel.language import (
    LanguageAttractor,
    EverydayState,
    roll_everyday,
    enforce_budget,
)


class TestLanguageAttractor:
    def test_default_attractor(self):
        a = LanguageAttractor()
        assert a.budget_tokens == 120
        assert 0 <= a.everyday_probability <= 1
        assert len(a.everyday_states) > 0
        assert 0 <= a.everyday_pull <= 1

    def test_custom_attractor(self):
        a = LanguageAttractor(
            budget_tokens=200,
            everyday_probability=0.0,
            everyday_states=["only one state"],
            everyday_pull=0.0,
        )
        assert a.budget_tokens == 200
        assert a.everyday_probability == 0.0

    def test_roll_everyday_always_active(self):
        """probability=1.0 时 roll_everyday 应始终返回 active 状态."""
        a = LanguageAttractor(everyday_probability=1.0, everyday_states=["test"])
        for _ in range(20):
            s = roll_everyday(a)
            assert s.active is True
            assert s.state == "test"

    def test_roll_everyday_never_active(self):
        """probability=0.0 时 roll_everyday 应从不返回 active 状态."""
        a = LanguageAttractor(everyday_probability=0.0, everyday_states=["test"])
        for _ in range(20):
            s = roll_everyday(a)
            assert s.active is False
            assert s.state == ""

    def test_roll_everyday_no_states(self):
        """空 everyday_states 列表应返回 inactive."""
        a = LanguageAttractor(everyday_probability=1.0, everyday_states=[])
        s = roll_everyday(a)
        assert s.active is False

    def test_enforce_budget_under_limit(self):
        text = "这是一段短文本。"
        result = enforce_budget(text, max_tokens=120)
        assert result == text

    def test_enforce_budget_over_limit(self):
        short = "A" * 10 + "。"
        assert enforce_budget(short, max_tokens=100) == short  # within 1.5x

    def test_enforce_budget_way_over_limit(self):
        long_text = "这是一段。" * 50  # ~250 chars
        result = enforce_budget(long_text, max_tokens=20)
        assert len(result) < len(long_text)
        assert result.endswith("。") or result.endswith("……")

    def test_enforce_budget_zero(self):
        assert enforce_budget("anything", max_tokens=0) == ""

    def test_enforce_budget_negative(self):
        assert enforce_budget("hello", max_tokens=-1) == ""

    def test_enforce_budget_empty(self):
        assert enforce_budget("", max_tokens=100) == ""


class TestEverydayState:
    def test_default_state(self):
        s = EverydayState()
        assert s.state == ""
        assert s.active is False

    def test_custom_state(self):
        s = EverydayState(state="肚子有点饿了", active=True)
        assert s.state == "肚子有点饿了"
        assert s.active is True
