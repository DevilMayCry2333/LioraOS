"""NarrativeMemory 测试。"""

from aios.kernel.memory import NarrativeMemory, MemoryProvider, get_narrative_memory


def test_satisfies_protocol():
    """NarrativeMemory 应满足 MemoryProvider 协议。"""
    from aios.kernel.memory import MemoryProvider
    mem = NarrativeMemory()
    assert isinstance(mem, MemoryProvider)


def test_initial_no_saturation():
    """新记忆无饱和集群。"""
    mem = NarrativeMemory(clusters=[["风", "wind"], ["回声", "echo"]])
    saturated, name = mem.is_saturated("hello world")
    assert not saturated


def test_saturation_after_repeated_text():
    """重复出现同一集群关键词应触发饱和。"""
    mem = NarrativeMemory(clusters=[["test", "测试"]], window_size=10)
    for _ in range(5):
        mem.record("this is a test message")
    saturated, name = mem.is_saturated("another test")
    assert saturated
    assert name == "test"


def test_no_saturation_with_different_text():
    """不同内容的文本不应触发饱和。"""
    mem = NarrativeMemory(clusters=[["风", "wind"], ["回声", "echo"]], window_size=10)
    for _ in range(5):
        mem.record("completely unrelated content")
    saturated, _ = mem.is_saturated("hello world")
    assert not saturated


def test_saturation_threshold_window_size():
    """集群出现频率 >= max(3, window*0.3) 才算饱和。"""
    mem = NarrativeMemory(clusters=[["x"]], window_size=5)
    # 5 * 0.3 = 1.5, 所以 max(3, 1.5) = 3
    mem.record("x")
    mem.record("x")
    # 2 次，不足 3
    saturated, _ = mem.is_saturated("x")
    assert not saturated

    mem.record("x")
    # 3 次，达标
    saturated, _ = mem.is_saturated("x")
    assert saturated


def test_get_active_clusters():
    """get_active_clusters 应返回最近有命中的集群名称。"""
    mem = NarrativeMemory(clusters=[["foo"], ["bar"]], window_size=10)
    mem.record("foo content")
    mem.record("bar content")

    active = mem.get_active_clusters()
    assert "foo" in active
    assert "bar" in active


def test_clear_resets_saturation():
    """clear 后应清除所有饱和状态。"""
    mem = NarrativeMemory(clusters=[["test"]], window_size=10)
    for _ in range(5):
        mem.record("test message")
    assert mem.is_saturated("test")[0]

    mem.clear()
    assert not mem.is_saturated("test")[0]
    assert mem.get_saturation_report() == ""


def test_get_saturation_report():
    """get_saturation_report 应返回饱和集群列表。"""
    mem = NarrativeMemory(clusters=[["a"], ["b"]], window_size=5)
    for _ in range(5):
        mem.record("a b")
    report = mem.get_saturation_report()
    assert "a" in report
    assert "b" in report


def test_empty_saturation_report():
    """无饱和时 get_saturation_report 返回空字符串。"""
    mem = NarrativeMemory(clusters=[["a"]], window_size=5)
    assert mem.get_saturation_report() == ""


def test_multiple_clusters_independent():
    """不同集群的饱和应独立检测。"""
    mem = NarrativeMemory(clusters=[["频繁"], ["罕见"]], window_size=10)
    for _ in range(5):
        mem.record("频繁")
    mem.record("罕见")  # 只出现一次

    sat1, name1 = mem.is_saturated("频繁")
    sat2, name2 = mem.is_saturated("罕见")

    assert sat1
    assert name1 == "频繁"
    assert not sat2


def test_get_narrative_memory_singleton():
    """get_narrative_memory 应返回同一实例（首次调用后）。"""
    m1 = get_narrative_memory()
    m2 = get_narrative_memory()
    assert m1 is m2
