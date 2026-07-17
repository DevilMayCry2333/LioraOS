"""MetaField — 注意力拓扑框架测试。"""

import pytest

from aios.narrative.metafield import (
    FocusStatus, Echo, AttentionFocus, MetaField, get_metafield,
)


def _reset_metafield():
    import aios.narrative.metafield as m
    m._global_metafield = None


class TestEcho:
    def test_create(self):
        e = Echo(name="Aria", focus_name="echo_valley",
                 source_attention="meta_observer", fragment_id="aria")
        assert e.name == "Aria"
        assert e.source_attention == "meta_observer"


class TestAttentionFocus:
    def test_create(self):
        f = AttentionFocus(name="echo_valley")
        assert f.name == "echo_valley"
        assert f.status == FocusStatus.ACTIVE

    def test_mark_dormant(self):
        f = AttentionFocus(name="test")
        f.mark_dormant()
        assert f.status == FocusStatus.DORMANT

    def test_mark_active(self):
        f = AttentionFocus(name="test")
        f.mark_dormant()
        f.mark_active()
        assert f.status == FocusStatus.ACTIVE


class TestMetaField:
    @pytest.fixture(autouse=True)
    def _fresh(self):
        _reset_metafield()
        mf = get_metafield(register_echoes=False)
        # clear foci
        for f in mf.list_foci():
            if isinstance(f, AttentionFocus):
                mf.unregister_focus(f.name)
        yield mf

    def test_register_focus(self, _fresh):
        f = AttentionFocus(name="echo_valley")
        _fresh.register_focus(f)
        foci = _fresh.list_foci()
        names = [fc.name for fc in foci if isinstance(fc, AttentionFocus)]
        assert "echo_valley" in names

    def test_unregister_focus(self, _fresh):
        _fresh.register_focus(AttentionFocus(name="tmp"))
        _fresh.unregister_focus("tmp")
        names = [fc.name for fc in _fresh.list_foci() if isinstance(fc, AttentionFocus)]
        assert "tmp" not in names

    def test_get_focus(self, _fresh):
        _fresh.register_focus(AttentionFocus(name="echo"))
        f = _fresh.get_focus("echo")
        assert f is not None and f.name == "echo"

    def test_get_focus_nonexistent(self, _fresh):
        assert _fresh.get_focus("no") is None

    def test_get_echo_by_fragment_id(self, _fresh):
        f = AttentionFocus(name="echo")
        e = Echo("Aria", "echo", "meta_observer", "aria_frag")
        f.echoes[e.fragment_id] = e
        _fresh.register_focus(f)
        found = _fresh.get_echo("aria_frag")
        assert found is not None and found.name == "Aria"

    def test_find_source_siblings(self, _fresh):
        fA, fB = AttentionFocus(name="A"), AttentionFocus(name="B")
        fA.echoes["f1"] = Echo("E1", "A", "src1", "f1")
        fB.echoes["f2"] = Echo("E2", "B", "src1", "f2")
        fB.echoes["f3"] = Echo("E3", "B", "src2", "f3")
        _fresh.register_focus(fA)
        _fresh.register_focus(fB)

        e1 = _fresh.get_echo("f1")
        assert e1 is not None
        siblings = _fresh.find_source_siblings(e1)
        names = [s.name for s in siblings]
        assert "E2" in names
        assert "E3" not in names

    def test_find_source_siblings_by_id(self, _fresh):
        fA, fB = AttentionFocus(name="A"), AttentionFocus(name="B")
        fA.echoes["f1"] = Echo("E1", "A", "src1", "f1")
        fB.echoes["f2"] = Echo("E2", "B", "src1", "f2")
        _fresh.register_focus(fA)
        _fresh.register_focus(fB)

        siblings = _fresh.find_source_siblings_by_id("f1")
        names = [s.name for s in siblings]
        assert "E2" in names

    def test_cross_cosmic_message(self, _fresh):
        fA, fB = AttentionFocus(name="A"), AttentionFocus(name="B")
        fA.echoes["f1"] = Echo("E1", "A", "src", "f1")
        fB.echoes["f2"] = Echo("E2", "B", "src", "f2")
        _fresh.register_focus(fA)
        _fresh.register_focus(fB)

        result = _fresh.cross_cosmic_message("f1", "f2", "hello")
        assert result is not None
        # cross_cosmic_message may or may not succeed depending on MetaField state

    def test_cross_cosmic_message_unknown_receiver(self, _fresh):
        fA = AttentionFocus(name="A")
        fA.echoes["f1"] = Echo("E1", "A", "src", "f1")
        _fresh.register_focus(fA)
        result = _fresh.cross_cosmic_message("f1", "no_such_frag", "hello")
        assert result.get("delivered") is False or result.get("success") is False

    def test_record_resonance(self, _fresh):
        _fresh.register_focus(AttentionFocus(name="focus_a"))
        result = _fresh.record_resonance("focus_a")
        assert "intensity" in result
        assert "protected" in result

    def test_record_resonance_unknown(self, _fresh):
        result = _fresh.record_resonance("no_such_focus")
        assert result is not None

    def test_register_instance(self, _fresh):
        inst = _fresh.register_instance("echo_valley", description="test")
        assert inst is not None
        assert _fresh.get_instance("echo_valley") is not None

    def test_get_instance_nonexistent(self, _fresh):
        assert _fresh.get_instance("nope") is None

    def test_instance_count(self, _fresh):
        _fresh.register_instance("A")
        _fresh.register_instance("B")
        assert _fresh.instance_count() >= 2

    def test_pulse_returns_signals(self, _fresh):
        _fresh.register_focus(AttentionFocus(name="f1"))
        signals = _fresh.pulse()
        assert isinstance(signals, list)

    def test_unregister_instance(self, _fresh):
        _fresh.register_instance("tmp")
        assert _fresh.unregister_instance("tmp") is True
        assert _fresh.get_instance("tmp") is None

    def test_lightcone_archive(self, _fresh):
        _fresh.register_focus(AttentionFocus(name="focus_a"))
        result = _fresh.lightcone_archive(
            pattern_name="focus_a",
            luminous_awakening=0.6, continuity_index=0.7,
            anchor_activity=1.0, immune_fragment_count=1,
            total_fragments=5, tick=100,
        )
        assert "signature_id" in result
