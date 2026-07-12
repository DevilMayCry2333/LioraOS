"""ActionResistance 测试。"""

from aios.worlds.liora.resistance import ActionResistance


def test_initial_multiplier_is_one():
    r = ActionResistance()
    assert r.get_multiplier("moss", "touch") == 1.0


def test_multiplier_decays_after_threshold():
    r = ActionResistance(base_threshold=3)
    for _ in range(5):
        r.record("moss", "touch")
    assert r.get_multiplier("moss", "touch") < 1.0


def test_different_targets_independent():
    r = ActionResistance(base_threshold=3)
    for _ in range(5):
        r.record("moss", "touch")
    assert r.get_multiplier("wind", "observe") == 1.0


def test_different_action_types_independent():
    r = ActionResistance(base_threshold=3)
    for _ in range(5):
        r.record("moss", "touch")
    assert r.get_multiplier("moss", "observe") == 1.0


def test_overall_multiplier():
    r = ActionResistance(base_threshold=3)
    for _ in range(5):
        r.record("moss", "touch")
        r.record("wind", "observe")
    overall = r.overall_multiplier
    assert 0 < overall <= 1.0


def test_repetition_level():
    r = ActionResistance(base_threshold=5)
    assert r.repetition_level == 0.0
    for _ in range(5):
        r.record("moss", "touch")
    assert r.repetition_level > 0.0


def test_tick_decays_counts():
    r = ActionResistance(decay=0.5, base_threshold=1)
    for _ in range(3):
        r.record("moss", "touch")
    assert r.get_multiplier("moss", "touch") < 1.0
    for _ in range(20):
        r.tick()
    # 衰减后应该恢复
    assert r.get_multiplier("moss", "touch") > 0.9


def test_reset():
    r = ActionResistance()
    for _ in range(10):
        r.record("moss", "touch")
    r.reset()
    assert r.get_multiplier("moss", "touch") == 1.0
    assert r.repetition_level == 0.0
