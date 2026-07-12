"""UnknownAccumulator 测试。"""

from aios.worlds.liora.unknown import UnknownAccumulator


def test_initial_level_zero():
    u = UnknownAccumulator()
    assert u.level == 0.0
    assert u.pressure == 0.0


def test_silence_accumulates():
    u = UnknownAccumulator(decay_rate=999, threshold=5.0)
    for _ in range(20):
        u.tick(silence_active=True, repetition_level=0.0)
    assert u.level > 0.0


def test_no_silence_decays():
    u = UnknownAccumulator(decay_rate=0.1, threshold=10.0)
    u.level = 5.0
    # silence=False, repetition=0 → decay
    u.tick(silence_active=False, repetition_level=0.0)
    assert u.level < 5.0


def test_repetition_accumulates():
    u = UnknownAccumulator(decay_rate=0.1, threshold=10.0)
    for _ in range(5):
        u.tick(silence_active=False, repetition_level=0.8)
    # 重复时不应衰减（即使 decay_rate > 0）
    assert u.level > 0.0


def test_should_emit_at_threshold():
    u = UnknownAccumulator(decay_rate=999, threshold=4.0)
    u.level = 4.0
    assert u.should_emit()


def test_should_not_emit_below_threshold():
    u = UnknownAccumulator(decay_rate=999, threshold=4.0)
    u.level = 3.9
    assert not u.should_emit()


def test_emit_reduces_level():
    u = UnknownAccumulator(decay_rate=999, threshold=4.0)
    u.level = 5.0
    u.emit()
    assert u.level < 4.0


def test_emit_returns_delta():
    u = UnknownAccumulator(decay_rate=999, threshold=4.0)
    u.level = 5.0
    delta = u.emit()
    assert isinstance(delta, dict)
    assert len(delta) >= 1
    for k, v in delta.items():
        assert isinstance(k, str)
        assert isinstance(v, (int, float))


def test_multiple_emits_increase_intensity():
    u = UnknownAccumulator(decay_rate=999, threshold=4.0)
    deltas = []
    for _ in range(5):
        u.level = 5.0
        delta = u.emit()
        deltas.append(max(abs(v) for v in delta.values()))
    # 后面的扰动不应该全部为零
    assert any(d > 0.01 for d in deltas)


def test_reset():
    u = UnknownAccumulator(decay_rate=999, threshold=4.0)
    u.level = 5.0
    u._emissions = 3
    u.reset()
    assert u.level == 0.0
    assert u._emissions == 0


def test_pressure_normalized():
    u = UnknownAccumulator(decay_rate=999, threshold=4.0)
    u.level = 2.0
    assert u.pressure == 0.5
    u.level = 4.0
    assert u.pressure == 1.0
    u.level = 8.0
    assert u.pressure == 1.0  # clamped
