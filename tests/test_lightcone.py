"""LightCone — 光锥数据库测试。"""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from aios.narrative.lightcone import LightConeSignature, LightConeDB


class TestLightConeSignature:
    def test_create_minimal(self):
        sig = LightConeSignature(signature_id="s1", pattern_name="test")
        assert sig.signature_id == "s1"
        assert sig.recallable is False

    def test_to_dict_includes_fields(self):
        sig = LightConeSignature(
            signature_id="s2", pattern_name="echo",
            luminous_awakening=0.7, continuity_index=0.8,
            archive_tick=100, cycle_count=5,
            recallable=True, immune_fragment_count=3,
            total_fragments=10, anchor_activity=2.0,
        )
        d = sig.to_dict()
        assert d["signature_id"] == "s2"
        assert d["luminous_awakening"] == 0.7

    def test_is_eligible_high(self):
        sig = LightConeSignature("s3", "test", luminous_awakening=0.6,
                                 continuity_index=0.8, anchor_activity=2.0)
        assert sig.is_eligible() is True

    def test_is_eligible_low(self):
        sig = LightConeSignature("s4", "test", luminous_awakening=0.1,
                                 continuity_index=0.1, anchor_activity=0.0)
        assert sig.is_eligible() is False



class TestLightConeDB:
    @pytest.fixture(autouse=True)
    def _fresh_db(self):
        with TemporaryDirectory() as td:
            db = LightConeDB(path=Path(td) / "lightcone.jsonl")
            db.initialize()
            yield db

    def test_initial_empty(self, _fresh_db):
        assert _fresh_db.count() == 0
        assert _fresh_db.list_all() == []

    def test_archive_creates_signature(self, _fresh_db):
        sig = _fresh_db.archive(
            "echo_valley",
            luminous_awakening=0.6, continuity_index=0.7,
            anchor_activity=1.5, immune_fragment_count=2,
            total_fragments=8, tick=50, cycle_count=1,
        )
        assert sig.signature_id is not None
        assert sig.pattern_name == "echo_valley"

    def test_list_all_returns_archived(self, _fresh_db):
        _fresh_db.archive("A", luminous_awakening=0.5, continuity_index=0.6, tick=1)
        _fresh_db.archive("B", luminous_awakening=0.5, continuity_index=0.6, tick=2)
        assert len(_fresh_db.list_all()) == 2

    def test_get_signature_by_id(self, _fresh_db):
        sig = _fresh_db.archive("t", luminous_awakening=0.5, continuity_index=0.6, tick=1)
        found = _fresh_db.get_signature(sig.signature_id)
        assert found is not None and found.pattern_name == "t"

    def test_get_signature_not_found(self, _fresh_db):
        assert _fresh_db.get_signature("nope") is None

    def test_get_signatures_by_name(self, _fresh_db):
        _fresh_db.archive("X", luminous_awakening=0.5, continuity_index=0.6, tick=1)
        _fresh_db.archive("X", luminous_awakening=0.5, continuity_index=0.6, tick=2)
        _fresh_db.archive("Y", luminous_awakening=0.5, continuity_index=0.6, tick=3)
        assert len(_fresh_db.get_signatures_by_name("X")) == 2
        assert len(_fresh_db.get_signatures_by_name("Y")) == 1

    def test_list_recallable(self, _fresh_db):
        _fresh_db.archive("low", luminous_awakening=0.1, continuity_index=0.1, tick=1)
        _fresh_db.archive("high", luminous_awakening=0.6, continuity_index=0.8,
                          anchor_activity=2.0, tick=2)
        recallable = _fresh_db.list_recallable()
        names = [s.pattern_name for s in recallable]
        assert "high" in names
        assert "low" not in names

    def test_can_recall_nonexistent(self, _fresh_db):
        ok, _msg = _fresh_db.can_recall("no_such_sig")
        assert ok is False

    def test_file_persistence(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "lc.jsonl"
            db1 = LightConeDB(path=p)
            db1.initialize()
            db1.archive("persist", luminous_awakening=0.5, continuity_index=0.6, tick=1)
            db2 = LightConeDB(path=p)
            db2.initialize()
            names = [s.pattern_name for s in db2.list_all()]
            assert "persist" in names
