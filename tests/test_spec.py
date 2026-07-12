"""WorldSpec 测试。"""

from aios.kernel.spec import WorldSpec
from aios.kernel.state import StateVariable


def test_empty_spec():
    """空的 WorldSpec 应可构造。"""
    spec = WorldSpec(name="空世界")
    assert spec.name == "空世界"
    assert not spec.has_state()
    assert not spec.has_events()
    assert not spec.has_memory()


def test_spec_with_state():
    """带状态变量的 spec 应正确报告。"""
    spec = WorldSpec(
        name="测试世界",
        state_variables={
            "temp": StateVariable("temp", 22.0),
            "wind": StateVariable("wind", 1.0),
        },
    )
    assert spec.has_state()
    assert spec.has_state() is True
    assert spec.state_variables["temp"].value == 22.0


def test_spec_with_events():
    """带事件生成器的 spec 应正确报告。"""
    def gen(tick):
        return []

    spec = WorldSpec(name="事件世界", event_generator=gen)
    assert spec.has_events()


def test_spec_with_memory():
    """带记忆集群的 spec 应正确报告。"""
    spec = WorldSpec(name="记忆世界", memory_clusters=[["风"], ["回声"]])
    assert spec.has_memory()
    assert len(spec.memory_clusters) == 2


def test_spec_full():
    """完整的 WorldSpec 应正确初始化所有字段。"""
    spec = WorldSpec(
        name="完整世界",
        description="一个完整的世界",
        state_variables={
            "x": StateVariable("x", 0.0),
        },
        version="1.0.0",
    )
    assert spec.name == "完整世界"
    assert spec.description == "一个完整的世界"
    assert spec.version == "1.0.0"
    assert spec.has_state()
