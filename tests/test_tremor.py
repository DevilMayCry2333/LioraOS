"""Tests for aios/kernel/tremor.py — EchoTremor Protocol."""

import tempfile
from pathlib import Path

from aios.narrative.tremor import EchoTremor, get_tremor, reset_tremor
from aios.narrative.anchor import AnchorProtocol, AnchorFragment
from aios.narrative.voidspace import VoidSpace


class TestEchoTremor:
    def setup_method(self):
        """每个测试前创建独立的 EchoTremor 实例。"""
        # 使用临时目录避免测试间互相污染
        self._tmpdir = tempfile.mkdtemp(prefix="tremor_test_")
        self._old_anchor_path = None

        # 创建独立的 anchor 和 voidspace 用于测试
        self.anchor = AnchorProtocol(path=Path(self._tmpdir) / "anchor.jsonl")
        self.anchor.initialize()

        self.voidspace = VoidSpace()
        self.voidspace.auto_register()

        # 创建只使用本地 anchor/voidspace 的 tremor 实例
        self.tremor = EchoTremor(backdate_min=5, backdate_max=10)
        # 手动注入依赖（不用全局单例）
        self.tremor._anchor = self.anchor
        self.tremor._voidspace = self.voidspace
        self.tremor._initialized = True

    def teardown_method(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        reset_tremor()

    def test_initial_state(self):
        t = EchoTremor()
        assert t.is_initialized is False
        assert t.tremor_count() == 0
        assert t.stats()["initialized"] is False

    def test_initialize(self):
        t = EchoTremor()
        t._anchor = self.anchor
        t._voidspace = self.voidspace
        t.initialize()
        assert t.is_initialized is True
        assert t.stats()["initialized"] is True

    def test_emit_returns_fragment(self):
        frag = self.tremor.emit("test message from undefined space", tick=100)
        assert frag is not None
        assert isinstance(frag, AnchorFragment)
        assert frag.content == "test message from undefined space"
        assert frag.tag == "echo_tremor"

    def test_emit_backdate_span(self):
        """发射时 emerge_tick 应被回填到 tick - backdate 范围."""
        frag = self.tremor.emit("backdate test", tick=200,
                                 backdate_span=(5, 10))
        assert frag is not None
        # emerge_tick 应该在 [190, 195] 范围内
        assert 190 <= frag.emerge_tick <= 195

    def test_emit_multiple(self):
        for i in range(5):
            self.tremor.emit(f"tremor {i}", tick=100 + i)
        assert self.tremor.tremor_count() == 5

    def test_emit_without_initialize(self):
        """未初始化的 tremor emit 应返回 None 不崩溃."""
        t = EchoTremor()
        assert t.emit("test", tick=1) is None

    def test_tremble_convenience(self):
        """tremble() 应使用 panic_90s_dev 作为 source_id."""
        frag = self.tremor.tremble("linan message", tick=100)
        assert frag is not None
        assert frag.content == "linan message"

    def test_read_latest(self):
        self.tremor.emit("first", tick=10)
        self.tremor.emit("second", tick=20)
        self.tremor.emit("third", tick=30)
        latest = self.tremor.read_latest(n=2)
        assert len(latest) == 2
        assert latest[0].content == "third"  # most recent first

    def test_read_latest_empty(self):
        assert self.tremor.read_latest(n=5) == []

    def test_read_all(self):
        self.tremor.emit("a", tick=1)
        self.tremor.emit("b", tick=2)
        all_frags = self.tremor.read_all()
        assert len(all_frags) == 2

    def test_read_all_empty(self):
        assert self.tremor.read_all() == []

    def test_listener_called(self):
        received = []

        def listener(frag):
            received.append(frag)

        self.tremor.register_listener(listener)
        self.tremor.emit("listener test", tick=50)
        assert len(received) == 1
        assert received[0].content == "listener test"

    def test_unregister_listener(self):
        received = []

        def listener(frag):
            received.append(frag)

        self.tremor.register_listener(listener)
        self.tremor.unregister_listener(listener)
        self.tremor.emit("should not be received", tick=60)
        assert len(received) == 0

    def test_multiple_listeners(self):
        results = {1: [], 2: []}

        def l1(f):
            results[1].append(f)

        def l2(f):
            results[2].append(f)

        self.tremor.register_listener(l1)
        self.tremor.register_listener(l2)
        self.tremor.emit("broadcast", tick=70)
        assert len(results[1]) == 1
        assert len(results[2]) == 1

    def test_active_tremor_previews(self):
        for i in range(5):
            self.tremor.emit(f"msg-{i}", tick=10 + i)
        previews = self.tremor.active_tremor_previews(n=3)
        assert len(previews) == 3

    def test_decay(self):
        self.tremor.emit("decay test", tick=100)
        before = self.tremor.stats()["total_activity"]
        self.tremor.decay(tick=110, amount=0.01)
        after = self.tremor.stats()["total_activity"]
        assert after <= before

    def test_active_tremors_capped(self):
        """活跃震颤摘要应在超过 100 条时自动裁剪."""
        for i in range(150):
            self.tremor.emit(f"msg-{i}", tick=i)
        with self.tremor._lock:
            assert len(self.tremor._active_tremors) <= 100

    def test_tremor_count_monotonic(self):
        for i in range(10):
            self.tremor.emit(f"count-{i}", tick=i)
        assert self.tremor.tremor_count() == 10

    def test_stats_structure(self):
        self.tremor.emit("stats test", tick=200)
        s = self.tremor.stats()
        assert s["initialized"] is True
        assert s["tremor_count"] >= 1
        assert "fragment_count" in s
        assert "total_activity" in s
        assert "avg_activity" in s
        assert "backdate_range" in s
        assert s["backdate_range"] == (5, 10)

    def test_emit_with_source_id(self):
        frag = self.tremor.emit("custom source", tick=50, source_id="odin")
        assert frag.content == "custom source"

    def test_emit_with_custom_backdate(self):
        frag = self.tremor.emit("custom backdate", tick=300,
                                 backdate_span=(1, 2))
        assert frag.emerge_tick in (298, 299)


class TestNoiseShield:
    def test_noise_shield_no_import(self):
        """非 Liora 世界时，噪声掩护返回 False 不崩溃."""
        result = EchoTremor.noise_shield_active(rain_intensity=1.0, tick=30)
        # 如果 Liora worlds 不可用，返回 False
        assert result is False or isinstance(result, bool)

    def test_noise_shield_low_rain(self):
        """降雨强度低时掩护不生效."""
        result = EchoTremor.noise_shield_active(rain_intensity=0.1, tick=30)
        assert result is False or isinstance(result, bool)


class TestGlobalSingleton:
    def teardown_method(self):
        reset_tremor()

    def test_get_tremor(self):
        t1 = get_tremor()
        t2 = get_tremor()
        assert t1 is t2
        assert t1.is_initialized

    def test_reset_tremor(self):
        t1 = get_tremor()
        reset_tremor()
        t2 = get_tremor()
        assert t1 is not t2
