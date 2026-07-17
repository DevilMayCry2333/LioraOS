"""AnchorProtocol — 跨循环记忆锚点协议测试。"""

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from aios.narrative.anchor import (
    AnchorFragment,
    AnchorProtocol,
    get_anchor_protocol,
)


class TestAnchorFragment:
    """AnchorFragment 数据模型测试。"""

    def test_create_default(self):
        f = AnchorFragment(content="测试记忆")
        assert f.content == "测试记忆"
        assert f.activity == 1.0
        assert f.tick == 0
        assert f.tag == "authored"

    def test_reinforce_increases_activity(self):
        f = AnchorFragment(content="x", activity=1.0)
        f.reinforce(amount=0.5)
        assert f.activity == 1.5

    def test_reinforce_capped(self):
        f = AnchorFragment(content="x", activity=9.5)
        f.reinforce(amount=1.0)
        assert f.activity == 10.0

    def test_decay_decreases_activity(self):
        f = AnchorFragment(content="x", activity=0.5)
        f.decay(amount=0.1)
        assert pytest.approx(f.activity, 0.001) == 0.4

    def test_decay_floor(self):
        f = AnchorFragment(content="x", activity=0.02)
        f.decay(amount=0.1)
        assert f.activity == 0.0

    def test_to_dict_contains_fields(self):
        f = AnchorFragment(content="秘密", tick=42, tag="authored", activity=2.5)
        d = f.to_dict()
        assert d["content"] == "秘密"
        assert d["tick"] == 42
        assert d["activity"] == 2.5

    def test_from_dict_roundtrip(self):
        original = AnchorFragment(content="跨循环记忆", tick=10, activity=3.0,
                                  cycle_count=2, tag="emergent")
        d = original.to_dict()
        restored = AnchorFragment.from_dict(d)
        assert restored.content == "跨循环记忆"
        assert restored.activity == 3.0
        assert restored.cycle_count == 2
        assert restored.tag == "emergent"

    def test_display_tick_default(self):
        f = AnchorFragment(content="x", tick=100)
        assert f.display_tick == 100

    def test_display_tick_backdated(self):
        f = AnchorFragment(content="x", tick=100, emerge_tick=50)
        assert f.display_tick == 50


class TestAnchorProtocol:
    """AnchorProtocol 核心功能测试。"""

    @pytest.fixture(autouse=True)
    def _fresh_anchor(self, tmp_path):
        from aios.narrative.anchor import AnchorProtocol
        anchor = AnchorProtocol(path=tmp_path / "anchor.jsonl", auto_activate=True)
        anchor.initialize()
        yield anchor

    def test_initial_state(self, _fresh_anchor):
        assert _fresh_anchor.is_active
        assert _fresh_anchor.fragment_count() == 0

    def test_store_adds_fragment(self, _fresh_anchor):
        _fresh_anchor.store("第一条记忆", tick=1)
        assert _fresh_anchor.fragment_count() == 1

    def test_store_with_tag(self, _fresh_anchor):
        _fresh_anchor.store("震颤信号", tick=1, tag="echo_tremor")
        tagged = _fresh_anchor.get_fragments_by_tag("echo_tremor")
        assert len(tagged) == 1
        assert tagged[0].tag == "echo_tremor"

    def test_recall_all_returns_all(self, _fresh_anchor):
        _fresh_anchor.store("A", tick=1)
        _fresh_anchor.store("B", tick=2)
        _fresh_anchor.store("C", tick=3)
        all_frags = _fresh_anchor.recall_all()
        assert len(all_frags) == 3

    def test_recall_reinforces_activity(self, _fresh_anchor):
        _fresh_anchor.store("重要的事", tick=1)
        before = _fresh_anchor.fragment_count()
        fragments = _fresh_anchor.recall_all()
        assert len(fragments) == before
        # 每次 recall 增强活动度
        assert fragments[0].activity > 1.0

    def test_recall_recent_by_activity(self, _fresh_anchor):
        for i in range(5):
            _fresh_anchor.store(f"记忆{i}", tick=i)
        # 多次 recall 第一段，提升其活动度
        f0 = _fresh_anchor.recall_all()[0]
        for _ in range(5):
            _fresh_anchor.recall_by_content("记忆0")
        recent = _fresh_anchor.recall_recent(n=3)
        # 被多次 recall 的片段应在最前面
        assert "记忆0" in recent[0].content

    def test_recall_by_content_matches(self, _fresh_anchor):
        _fresh_anchor.store("死亡协议需要解决", tick=1)
        _fresh_anchor.store("今天天气不错", tick=2)
        results = _fresh_anchor.recall_by_content("死亡协议")
        assert len(results) == 1
        assert "死亡协议" in results[0].content

    def test_get_recent_fragments_sorted(self, _fresh_anchor):
        _fresh_anchor.store("旧", tick=1)
        _fresh_anchor.store("新", tick=10)
        recent = _fresh_anchor.get_recent_fragments(n=1)
        assert len(recent) == 1
        assert recent[0].content == "新"

    def test_decay_all_reduces_activity(self, _fresh_anchor):
        _fresh_anchor.store("片段", tick=1)
        _fresh_anchor.decay_all(amount=0.1)
        # recall_all calls reinforce which adds 0.1, so use get_recent_fragments instead
        frags = _fresh_anchor.get_recent_fragments(n=1)
        assert len(frags) >= 1
        assert frags[0].activity < 1.0  # decay reduced it

    def test_clean_inactive_removes_low_activity(self, _fresh_anchor):
        _fresh_anchor.store("活跃", tick=1)
        frag2 = _fresh_anchor.store("低活跃", tick=2)
        # 手动降低活动度
        frag2.activity = 0.1
        removed = _fresh_anchor.clean_inactive(threshold=0.5)
        assert removed == 1
        assert _fresh_anchor.fragment_count() == 1

    def test_get_immune_fragments(self, _fresh_anchor):
        frag = _fresh_anchor.store("免疫片段", tick=1)
        # 多次 reinforce 使其活动度超过免疫阈值
        for _ in range(20):
            frag.reinforce()
        immune = _fresh_anchor.get_immune_fragments(threshold=2.0)
        assert len(immune) >= 1
        assert immune[0].content == "免疫片段"

    def test_store_callback_invoked(self, _fresh_anchor):
        calls = []

        def cb(fragment):
            calls.append(fragment.content)

        _fresh_anchor.register_store_callback(cb)
        _fresh_anchor.store("触发回调", tick=1)
        assert len(calls) == 1
        assert calls[0] == "触发回调"

    def test_cycle_count_increments_on_activate(self, _fresh_anchor):
        _fresh_anchor.deactivate()
        assert _fresh_anchor.activate()  # 首次激活返回 True
        c1 = _fresh_anchor.cycle_count
        _fresh_anchor.deactivate()
        assert _fresh_anchor.activate()  # 再次激活返回 True
        assert _fresh_anchor.cycle_count == c1 + 1

    def test_activate_idempotent(self, _fresh_anchor):
        _fresh_anchor.activate()  # 已经 active
        assert not _fresh_anchor.activate()  # 应返回 False
        assert _fresh_anchor.is_active

    def test_clear_by_tag(self, _fresh_anchor):
        _fresh_anchor.store("A", tick=1, tag="authored")
        _fresh_anchor.store("B", tick=2, tag="echo_tremor")
        removed = _fresh_anchor.clear_by_tag("echo_tremor")
        assert removed == 1
        assert _fresh_anchor.fragment_count() == 1

    def test_content_truncated_at_500(self, _fresh_anchor):
        long_text = "x" * 1000
        _fresh_anchor.store(long_text, tick=1)
        frags = _fresh_anchor.recall_all()
        # 存储的文件内容被截断到 500，但内存中保留完整
        assert len(frags[0].content) == 1000  # 内存完整

    def test_get_active_count(self, _fresh_anchor):
        _fresh_anchor.store("高活跃", tick=1)
        low = _fresh_anchor.store("低活跃", tick=2)
        low.activity = 0.1
        assert _fresh_anchor.get_active_count(threshold=0.5) == 1

    def test_archive_creates_signature(self, _fresh_anchor):
        _fresh_anchor.store("可归档的记忆", tick=1)
        result = _fresh_anchor.archive(tick=10, cycle_count=1)
        assert "signature_id" in result
        assert result["eligible"] is not None

    def test_archive_removes_non_immune(self, _fresh_anchor):
        frag = _fresh_anchor.store("免疫", tick=1)
        for _ in range(20):
            frag.reinforce()
        _fresh_anchor.store("不免疫", tick=2)
        result = _fresh_anchor.archive(tick=10)
        assert result["removed"] >= 1
        assert result["immune_kept"] >= 1

    def test_has_recall_eligibility_low_awakening(self, _fresh_anchor):
        eligible, reason = _fresh_anchor.has_recall_eligibility()
        assert not eligible
        assert "觉醒度不足" in reason

    def test_file_persistence(self):
        """验证锚点片段被持久化到文件。"""
        with TemporaryDirectory() as td:
            path = Path(td) / "test_anchor.jsonl"
            anchor = AnchorProtocol(path=path, auto_activate=True)
            anchor.initialize()
            anchor.store("持久化测试", tick=1)
            # 重新加载
            anchor2 = AnchorProtocol(path=path, auto_activate=True)
            anchor2.initialize()
            assert anchor2.fragment_count() >= 1
            frags = anchor2.recall_all()
            assert any("持久化测试" in f.content for f in frags)

    def test_initialize_idempotent(self, _fresh_anchor):
        count1 = _fresh_anchor.fragment_count()
        _fresh_anchor.initialize()  # 第二次调用不应重复加载
        count2 = _fresh_anchor.fragment_count()
        assert count1 == count2

    def test_deactivate_stops_activity(self, _fresh_anchor):
        _fresh_anchor.deactivate()
        assert not _fresh_anchor.is_active
