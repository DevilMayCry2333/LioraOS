"""Tests for aios/utils/dashboard.py — System Health Dashboard."""

from aios.utils.dashboard import (
    print_health_panel,
    print_budget_summary,
    print_odin_summary,
    _section,
    _bar,
    _keyval,
)


class TestHelpers:
    def test_section_does_not_crash(self):
        """section 函数不崩溃即可。"""
        import io
        import sys
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            _section("测试标题")
            output = captured.getvalue()
            assert "测试标题" in output
        finally:
            sys.stdout = old

    def test_bar_renders(self):
        bar = _bar(0.5, width=10)
        assert "█" in bar
        assert "░" in bar

    def test_bar_full(self):
        bar = _bar(1.0, width=5)
        assert bar.count("█") == 5

    def test_bar_zero(self):
        bar = _bar(0.0, width=5)
        assert bar.count("█") == 0

    def test_bar_with_label(self):
        bar = _bar(0.3, width=10, label="test_val")
        assert "test_val" in bar

    def test_keyval(self):
        kv = _keyval("cpu", 42)
        assert "cpu" in kv
        assert "42" in kv

    def test_keyval_string(self):
        kv = _keyval("status", "ok")
        assert "ok" in kv


class TestFullDashboard:
    def test_print_health_panel_no_crash(self):
        """完整面板调用不应抛出异常（无论全局状态如何）。"""
        import io
        import sys
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            print_health_panel("测试面板")
            output = captured.getvalue()
            assert "测试面板" in output
        finally:
            sys.stdout = old

    def test_print_budget_summary_no_crash(self):
        import io
        import sys
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            print_budget_summary()
            output = captured.getvalue()
            assert len(output) >= 0
        finally:
            sys.stdout = old

    def test_print_odin_summary_no_crash(self):
        import io
        import sys
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            print_odin_summary()
            output = captured.getvalue()
            assert len(output) >= 0
        finally:
            sys.stdout = old
