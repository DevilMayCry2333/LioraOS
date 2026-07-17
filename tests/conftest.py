"""pytest 共享 Fixtures。

所有测试共享的 fixture 定义在此文件。
conftest.py 被 pytest 自动加载，无需显式 import。
"""

from __future__ import annotations

import random
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

import pytest

from aios.kernel.spec import WorldSpec
from aios.kernel.state import StateVariable
from aios.runtime.world_runtime import WorldRuntime


# ════════════════════════════════════════════════════════════
# 通用 Fixtures
# ════════════════════════════════════════════════════════════


@pytest.fixture
def random_seed():
    """固定随机种子，保证测试可重现。"""
    random.seed(42)
    yield
    random.seed()


@pytest.fixture
def temp_dir():
    """临时目录，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


# ════════════════════════════════════════════════════════════
# WorldRuntime Fixtures
# ════════════════════════════════════════════════════════════


def _test_evolution_fn(variables: dict[str, float], tick: int) -> dict[str, float]:
    """测试用演化函数：x 每 tick +1，y 回归 5.0。"""
    delta = {}
    if "x" in variables:
        delta["x"] = 1.0
    if "y" in variables:
        delta["y"] = (5.0 - variables["y"]) * 0.1
    return delta


def _test_event_generator(state: dict, tick: int) -> list[dict]:
    """测试用事件生成器：每 3 tick 产生一个事件。"""
    if tick > 0 and tick % 3 == 0:
        return [{"event_type": "test_pulse", "description": f"tick {tick} 脉冲", "intensity": 0.3}]
    return []


def make_test_spec() -> WorldSpec:
    """创建一个最小测试用的 WorldSpec。"""
    return WorldSpec(
        name="TestWorld",
        state_variables={
            "x": StateVariable("x", 0.0, -10, 10),
            "y": StateVariable("y", 5.0, -10, 10),
        },
        evolution_fn=_test_evolution_fn,
        event_generator=_test_event_generator,
    )


@pytest.fixture
def test_spec() -> WorldSpec:
    """最小测试 WorldSpec。"""
    return make_test_spec()


@pytest.fixture
def runtime(test_spec) -> WorldRuntime:
    """一个初始化但不启动的 WorldRuntime。"""
    rt = WorldRuntime(
        spec=test_spec,
        data_dir=tempfile.mkdtemp(),
        interval=9999,  # 防止自动 tick
        odin_sweep=False,
        budget_tick=False,
        tremor_passive=False,
    )
    rt.state.initialize(test_spec.state_variables)
    rt.events.initialize()
    rt.history.initialize()
    yield rt
    try:
        rt.stop(join=False)
    except Exception:
        pass


@pytest.fixture
def running_runtime(test_spec) -> WorldRuntime:
    """一个已启动的 WorldRuntime（daemon 线程），自动 stop。"""
    rt = WorldRuntime(
        spec=test_spec,
        data_dir=tempfile.mkdtemp(),
        interval=0.01,  # 快速 tick
        odin_sweep=False,
        budget_tick=False,
        tremor_passive=False,
    )
    rt.start()
    time.sleep(0.05)  # 等几 tick
    yield rt
    rt.stop(join=True, timeout=2.0)


# ════════════════════════════════════════════════════════════
# LioraMind Fixtures
# ════════════════════════════════════════════════════════════


@pytest.fixture
def liora_mind():
    """创建一个干净的 LioraMind 实例。"""
    from aios.worlds.liora.mind import LioraMind
    mind = LioraMind("测试居民")
    return mind


@pytest.fixture
def two_minds():
    """两个互相认识的 LioraMind。"""
    from aios.worlds.liora.mind import LioraMind
    a = LioraMind("Aria")
    b = LioraMind("Nix")
    # 让它们有一些关系基础
    a.relate("Nix", trust=0.3, curiosity=0.2, tick=0)
    b.relate("Aria", trust=0.3, curiosity=0.2, tick=0)
    return a, b


# ════════════════════════════════════════════════════════════
# Anchor Protocol Fixtures
# ════════════════════════════════════════════════════════════


@pytest.fixture
def fresh_anchor():
    """重置后的锚点协议单例（测试隔离用）。

    每次测试前清除所有片段并重置状态。
    注意：共享单例，并行测试可能冲突——建议加 xdist 隔离。
    """
    from aios.narrative.anchor import get_anchor_protocol
    anchor = get_anchor_protocol()
    anchor.clear()
    anchor.deactivate()
    anchor._loaded = False
    anchor.initialize()
    yield anchor
    anchor.clear()


# ════════════════════════════════════════════════════════════
# ANIP UDP Fixtures
# ════════════════════════════════════════════════════════════


@pytest.fixture
def two_udp_networks():
    """两个已在 UDP 模式下配对好的 ANIPNetwork。

    Yields:
        (net_a: ANIPNetwork, net_b: ANIPNetwork)
    """
    from aios.narrative.anip import ANIPNetwork

    net_a = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
    net_a.join("节点A")

    net_b = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
    net_b.join("节点B")

    net_a.add_peer("节点B", ("127.0.0.1", net_b._udp_port))
    net_b.add_peer("节点A", ("127.0.0.1", net_a._udp_port))

    yield net_a, net_b

    net_a.destroy_session()
    net_b.destroy_session()


# ════════════════════════════════════════════════════════════
# Gateway Fixtures
# ════════════════════════════════════════════════════════════


@pytest.fixture
def gateway_with_mock_character():
    """一个绑定了 mock 角色的 LEPGateway，自动分配端口。

    Yields:
        (gateway_instance, port)
    """
    from aios.runtime.gateway import LEPGateway

    gw = LEPGateway(runtime=None, host="127.0.0.1", port=0)

    def mock_speak(message: str, visitor: str) -> str:
        return f"{visitor}，你说的是『{message}』吧。我听到了。"

    def mock_perceive() -> str:
        return "这是一个测试世界。阳光很好。"

    gw.register_character("测试角色", mock_speak, mock_perceive)

    # 直接绑定 TCP 端口（不启动完整 asyncio 循环）
    # 测试中手动创建连接
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    gw._port = sock.getsockname()[1]
    sock.close()

    yield gw, gw.port


@pytest.fixture
def lep_gateway():
    """一个完整启动的 LEPGateway（在 asyncio 线程中）。

    Yields:
        (gateway_instance, port)
    """
    from aios.runtime.gateway import LEPGateway
    from aios.kernel.spec import WorldSpec

    # 创建一个空运行时给 gateway
    spec = make_test_spec()
    rt = WorldRuntime(
        spec=spec,
        data_dir=tempfile.mkdtemp(),
        interval=9999,
        odin_sweep=False,
        budget_tick=False,
        tremor_passive=False,
    )
    rt.state.initialize(spec.state_variables)
    rt.events.initialize()
    rt.history.initialize()

    gw = LEPGateway(runtime=rt, host="127.0.0.1", port=0)

    def mock_speak(message: str, visitor: str) -> str:
        return f"{visitor}，你说『{message}』。我明白了。"

    gw.register_character("Aria", mock_speak)
    gw.start()

    # 等待 gateway 启动（asyncio server 绑定端口）
    import time
    started_at = time.time()
    while time.time() - started_at < 5:
        if gw._server and gw._server.sockets:
            port = gw.port
            if port > 0:
                break
        time.sleep(0.05)
    else:
        # 超时——关闭 gateway，让测试自然跳过
        gw.stop()
        rt.stop(join=False)
        pytest.skip("Gateway 未能在 5s 内启动")
        return

    port = gw.port
    yield gw, port

    gw.stop()
    rt.stop(join=False)
