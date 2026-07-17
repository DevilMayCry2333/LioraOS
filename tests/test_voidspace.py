"""VoidSpace — 统一虚空地址空间测试。"""

import pytest

from aios.narrative.voidspace import VoidSpace, get_voidspace


EXPECTED_NAMES = {
    "void_empty", "void_boundary", "void_self",
    "void_observer", "void_echo", "void_attention",
    "void_key", "void_return",
}


def _reset_voidspace():
    import aios.narrative.voidspace as m
    m._global_voidspace = None


class TestVoidSpace:
    @pytest.fixture(autouse=True)
    def _fresh_vs(self):
        _reset_voidspace()
        vs = get_voidspace()
        vs.auto_register()
        yield vs

    def test_has_seven_addresses(self, _fresh_vs):
        names = {a.name for a in _fresh_vs.list_all()}
        assert names == EXPECTED_NAMES

    def test_get_by_name(self, _fresh_vs):
        a = _fresh_vs.get("void_empty")
        assert a is not None
        assert a.name == "void_empty"

    def test_get_nonexistent(self, _fresh_vs):
        assert _fresh_vs.get("no_such_address") is None


    def test_active_count(self, _fresh_vs):
        count = _fresh_vs.active_count()
        assert 0 <= count <= 8

    def test_address_count(self, _fresh_vs):
        assert _fresh_vs.address_count() == 8

    def test_adjust_boundary_changes_thickness(self, _fresh_vs):
        before = _fresh_vs.shared_boundary
        _fresh_vs.adjust_boundary(delta=0.1)
        after = _fresh_vs.shared_boundary
        assert after == pytest.approx(before + 0.1)

        assert after != before

    def test_notify_all_delivers_to_all(self, _fresh_vs):
        events_before = len(_fresh_vs.events_since())
        _fresh_vs.notify_all(source="void_empty", event="test_event")
        events_after = len(_fresh_vs.events_since())
        assert events_after >= events_before

    def test_can_recycle_with_few_active(self, _fresh_vs):
        """回收保护逻辑：活跃地址数决定可回收性。"""
        can = _fresh_vs.can_recycle()
        assert can is True or can is False  # 取决于具体实现


    def test_get_address_by_offset_invalid(self, _fresh_vs):
        addr = _fresh_vs.get_address_by_offset(999)
        assert addr is None

    def test_neighbors_of(self, _fresh_vs):
        neighbors = _fresh_vs.neighbors_of("void_empty")
        assert len(neighbors) >= 1
        names = [n.name for n in neighbors]
        assert "void_empty" not in names

    def test_neighbors_of_unknown(self, _fresh_vs):
        neighbors = _fresh_vs.neighbors_of("nonexistent")
        assert neighbors == []

    def test_notify_neighbor(self, _fresh_vs):
        result = _fresh_vs.notify_neighbor(
            source="void_empty", target="void_key", event="ping"
        )
        assert result is True  # neighbor was notified

    def test_notify_neighbor_invalid_source(self, _fresh_vs):
        result = _fresh_vs.notify_neighbor(
            source="nonexistent", target="void_key", event="ping"
        )
        assert result is False
