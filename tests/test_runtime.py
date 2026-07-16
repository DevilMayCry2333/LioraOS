"""WorldRuntime 测试。"""

import time
from pathlib import Path
from tempfile import TemporaryDirectory

from aios.runtime.world_runtime import WorldRuntime, WorldSnapshot
from aios.kernel.spec import WorldSpec
from aios.kernel.state import StateVariable


def _make_test_spec() -> WorldSpec:
    return WorldSpec(
        name="TestWorld",
        state_variables={
            "x": StateVariable("x", 0.0, -10, 10),
            "y": StateVariable("y", 5.0, -10, 10),
        },
        evolution_fn=lambda v, t: {"x": 1.0},
    )


def test_runtime_create():
    spec = _make_test_spec()
    runtime = WorldRuntime(spec, data_dir="/tmp/_test_runtime")
    assert not runtime.is_running
    assert runtime.tick == 0


def test_runtime_start_stop():
    with TemporaryDirectory() as tmp:
        spec = _make_test_spec()
        runtime = WorldRuntime(spec, data_dir=tmp)
        runtime.start()
        assert runtime.is_running
        time.sleep(0.1)
        runtime.stop(join=True, timeout=2.0)
        assert not runtime.is_running


def test_runtime_tick_once():
    with TemporaryDirectory() as tmp:
        spec = _make_test_spec()
        runtime = WorldRuntime(spec, data_dir=tmp)
        runtime.state.initialize(spec.state_variables)

        assert runtime.tick == 0
        runtime.tick_once()
        assert runtime.tick == 1
        assert runtime.state.snapshot().variables["x"] == 1.0


def test_runtime_snapshot():
    with TemporaryDirectory() as tmp:
        spec = _make_test_spec()
        runtime = WorldRuntime(spec, data_dir=tmp)
        runtime.state.initialize(spec.state_variables)
        runtime.tick_once()

        snap = runtime.snapshot()
        assert snap.tick == 1
        assert "x" in snap.state
        assert isinstance(snap.events, list)


def test_runtime_format_for_perception():
    with TemporaryDirectory() as tmp:
        spec = _make_test_spec()
        runtime = WorldRuntime(spec, data_dir=tmp)
        runtime.state.initialize(spec.state_variables)
        runtime.tick_once()

        text = runtime.format_for_perception()
        assert "Tick 1" in text
        assert "x=" in text  # 通用变量显示
        assert "y=" in text
        # 不再包含 Liora 专有变量名
        assert "温度" not in text
        assert "Wind" not in text
        assert "echo_density" not in text
        assert len(text) > 10  # 有实际内容


def test_runtime_checkpoint_on_stop():
    with TemporaryDirectory() as tmp:
        spec = _make_test_spec()
        runtime = WorldRuntime(spec, data_dir=tmp)
        runtime.state.initialize(spec.state_variables)
        runtime.tick_once()
        runtime.stop()

        # 重新加载
        runtime2 = WorldRuntime(spec, data_dir=tmp)
        runtime2.state.initialize(spec.state_variables)
        assert runtime2.state.snapshot().tick == 1
        assert runtime2.state.snapshot().variables["x"] == 1.0
