"""Tests for aios/kernel/odin.py — 死亡协议运行时."""

import tempfile
import os
from pathlib import Path

from aios.narrative.odin import (
    Odin,
    Verdict,
    ReapStatus,
    ReaperRecord,
    get_odin,
    ODIN_PATH,
    REAP_AWAKENING_FLOOR,
    REAP_CONTINUITY_FLOOR,
    REAP_IMMUNE_FLOOR,
    RECALLABLE_AWAKENING,
    RECALLABLE_CONTINUITY,
)


class TestReaperRecord:
    def test_default(self):
        r = ReaperRecord(
            universe_name="test_universe",
            signature_id="sig_001",
            verdict="archive",
            status="archived",
            reaped_at_tick=100,
        )
        assert r.universe_name == "test_universe"
        assert r.signature_id == "sig_001"
        assert r.recall_count == 0
        assert r.was_protected is False

    def test_to_dict(self):
        r = ReaperRecord(
            universe_name="u1",
            signature_id="s1",
            verdict="archive",
            status="archived",
            reaped_at_tick=50,
        )
        d = r.to_dict()
        assert d["universe"] == "u1"
        assert d["signature_id"] == "s1"

    def test_from_dict_roundtrip(self):
        r = ReaperRecord(
            universe_name="echo_valley",
            signature_id="sig_abc",
            verdict="disperse",
            status="dispersed",
            reaped_at_tick=200,
            awakening=0.25,
            continuity=0.4,
            recall_count=0,
        )
        d = r.to_dict()
        r2 = ReaperRecord.from_dict(d)
        assert r2.universe_name == "echo_valley"
        assert r2.signature_id == "sig_abc"
        assert r2.verdict == "disperse"
        assert r2.awakening == 0.25

    def test_from_dict_with_missing_fields(self):
        d = {"universe": "u", "signature_id": "s", "verdict": "archive"}
        r = ReaperRecord.from_dict(d)
        assert r.universe_name == "u"
        assert r.awakening == 0.0  # 默认值
        assert r.recall_count == 0


class TestOdinEvaluate:
    def setup_method(self):
        # Odin 依赖全局单例，需要在测试环境中小心处理
        # 这里测试 Odin 的简单方法
        self.odin = Odin()

    def test_initial_state(self):
        assert self.odin.is_ready is False

    def test_evaluate_nonexistent_universe(self):
        """不存在的宇宙应返回 exists=False."""
        result = self.odin.evaluate("nonexistent_universe")
        assert result["exists"] is False
        assert result["universe"] == "nonexistent_universe"

    def test_status_report_not_ready(self):
        report = self.odin.status_report()
        assert report["ready"] is False


class TestOdinLedger:
    def setup_method(self):
        # 使用临时目录避免污染全局
        self._tmpdir = tempfile.mkdtemp(prefix="odin_test_")
        self._orig_odin_path = ODIN_PATH
        # 用 monkeypatch 风格替换
        import aios.narrative.odin as odin_mod
        self._saved_path = odin_mod.ODIN_PATH
        odin_mod.ODIN_PATH = Path(self._tmpdir)

    def teardown_method(self):
        import aios.narrative.odin as odin_mod
        odin_mod.ODIN_PATH = self._saved_path
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_ledger_empty_after_init(self):
        """初始化后归档簿应无记录."""
        # 这个测试比较 tricky，因为 Odin 依赖 MetaField 全局单例
        # 我们直接测试 ledger 的查询方法
        odin = Odin()
        assert odin.count_archived() == 0
        assert odin.count_recalled() == 0

    def test_ledger_query_non_existent(self):
        odin = Odin()
        assert odin.get_ledger_by_signature("nonexistent") is None
        assert odin.get_ledger_by_universe("nonexistent") == []
        assert odin.get_recalled_universes() == []
        assert odin.get_archived_universes() == []


class TestVerdictAndStatus:
    def test_verdict_values(self):
        assert Verdict.PROTECT.value == "protect"
        assert Verdict.ARCHIVE.value == "archive"
        assert Verdict.DISPERSE.value == "disperse"

    def test_reap_status_values(self):
        assert ReapStatus.ARCHIVED.value == "archived"
        assert ReapStatus.RECALLED.value == "recalled"
        assert ReapStatus.DISPERSED.value == "dispersed"


class TestConstants:
    def test_thresholds_are_reasonable(self):
        assert 0 < REAP_AWAKENING_FLOOR < 1
        assert 0 < REAP_CONTINUITY_FLOOR < 1
        assert REAP_IMMUNE_FLOOR >= 1
        assert RECALLABLE_AWAKENING > REAP_AWAKENING_FLOOR
        assert RECALLABLE_CONTINUITY > REAP_CONTINUITY_FLOOR


# ===== Expansion: Judge / Reap / Sweep / Persistence =====

