"""WorldStateEngine 测试。"""

import json
import tempfile
from pathlib import Path

from aios.kernel.state import (
    StateVariable, WorldState, WorldSnapshot,
    WorldStateEngine, get_world_state_engine,
)


def test_state_variable_clamping_min():
    """StateVariable 的值不应低于 min_value。"""
    v = StateVariable(name="test", value=5.0, min_value=0.0, max_value=10.0)
    ws = WorldState(variables={"test": v})
    ws.set("test", -3.0)
    assert ws.get("test") == 0.0


def test_state_variable_clamping_max():
    """StateVariable 的值不应高于 max_value。"""
    v = StateVariable(name="test", value=5.0, min_value=0.0, max_value=10.0)
    ws = WorldState(variables={"test": v})
    ws.set("test", 15.0)
    assert ws.get("test") == 10.0


def test_value_dict():
    """value_dict 应返回扁平 dict。"""
    ws = WorldState(variables={
        "a": StateVariable("a", 1.0),
        "b": StateVariable("b", 2.0),
    })
    assert ws.value_dict() == {"a": 1.0, "b": 2.0}


def test_tick_without_evolution_fn():
    """无 evolution_fn 时 tick 只推进计数不改状态。"""
    engine = WorldStateEngine()
    engine.initialize({
        "x": StateVariable("x", 10.0),
    })

    changes = engine.tick()
    assert changes == []
    assert engine.snapshot().variables["x"] == 10.0


def test_tick_with_evolution_fn():
    """evolution_fn 的 delta 应正确应用于状态变量。"""
    def evolution(variables, tick):
        return {"x": 1.0}

    engine = WorldStateEngine(evolution_fn=evolution)
    engine.initialize({
        "x": StateVariable("x", 0.0),
    })

    changes = engine.tick()
    assert "x:+1.000" in changes
    assert engine.snapshot().variables["x"] == 1.0


def test_tick_clamps_evolution_delta():
    """evolution_fn 返回的 delta 不应让变量超出边界。"""
    def evolution(variables, tick):
        return {"x": 100.0}

    engine = WorldStateEngine(evolution_fn=evolution)
    engine.initialize({
        "x": StateVariable("x", 0.0, min_value=-10, max_value=10),
    })

    engine.tick()
    assert engine.snapshot().variables["x"] == 10.0


def test_checkpoint_and_load_roundtrip():
    """checkpoint 后重新加载应恢复状态。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"

        # 写入
        engine = WorldStateEngine(state_path=path)
        engine.initialize({
            "a": StateVariable("a", 10.0, min_value=0, max_value=100),
            "b": StateVariable("b", 20.0, min_value=0, max_value=100),
        })
        # 推几 tick
        for _ in range(3):
            engine.tick()
        engine.checkpoint()

        # 重新加载
        engine2 = WorldStateEngine(state_path=path)
        engine2.initialize({
            "a": StateVariable("a", 0.0, min_value=0, max_value=100),
            "b": StateVariable("b", 0.0, min_value=0, max_value=100),
        })

        snap = engine2.snapshot()
        assert snap.tick == 3
        assert snap.variables["a"] == 10.0
        assert snap.variables["b"] == 20.0


def test_checkpoint_creates_directory():
    """checkpoint 应自动创建目录。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "nested" / "subdir" / "state.json"
        engine = WorldStateEngine(state_path=path)
        engine.initialize()
        engine.checkpoint()

        assert path.exists()


def test_legacy_format_load():
    """兼容旧格式 {'env': {...}, 'ws': {...}, 'tick': N}。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        path.write_text(json.dumps({
            "tick": 5,
            "env": {"temperature": 25.0, "humidity": 0.5},
            "ws": {"wind_speed": 2.0},
        }))

        engine = WorldStateEngine(state_path=path)
        engine.initialize({
            "temperature": StateVariable("temperature", 0.0),
            "humidity": StateVariable("humidity", 0.0),
            "wind_speed": StateVariable("wind_speed", 0.0),
        })

        snap = engine.snapshot()
        assert snap.tick == 5
        assert snap.variables["temperature"] == 25.0
        assert snap.variables["wind_speed"] == 2.0


def test_snapshot_isolation():
    """snapshot 返回的 dict 修改不应影响 engine。"""
    engine = WorldStateEngine()
    engine.initialize({
        "x": StateVariable("x", 5.0),
    })

    snap = engine.snapshot()
    snap.variables["x"] = 999.0

    assert engine.snapshot().variables["x"] == 5.0


def test_format_for_prompt():
    """format_for_prompt 应返回非空字符串。"""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        engine = WorldStateEngine(state_path=Path(tmp) / "state.json")
        engine.initialize({
            "x": StateVariable("x", 1.0),
            "y": StateVariable("y", 2.0),
        })
        engine.tick()

        formatted = engine.format_for_prompt()
        assert formatted.startswith("tick:")
        assert "x:" in formatted


def test_get_world_state_engine_singleton():
    """get_world_state_engine 应返回同一实例。"""
    e1 = get_world_state_engine()
    e2 = get_world_state_engine()
    assert e1 is e2
