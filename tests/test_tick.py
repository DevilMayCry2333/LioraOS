"""WorldTick 测试。"""

import time
import threading
from aios.kernel.tick import WorldTick, get_world_tick


def test_default_tick_count_starts_at_zero():
    """新创建的 WorldTick tick_count 应为 0。"""
    tick = WorldTick(interval=0.5)
    assert tick.tick_count() == 0
    assert not tick.is_active


def test_start_increments_tick():
    """启动后 tick_count 应随时间递增。"""
    tick = WorldTick(interval=0.005)
    tick.start()
    time.sleep(0.02)
    tick.stop(join=True, timeout=1.0)

    assert tick.tick_count() >= 1
    assert not tick.is_active


def test_stop_actually_stops():
    """stop 后 tick_count 应停止增长。"""
    tick = WorldTick(interval=0.005)
    tick.start()
    time.sleep(0.02)
    tick.stop(join=True, timeout=1.0)

    before = tick.tick_count()
    time.sleep(0.03)
    after = tick.tick_count()

    assert before == after, "stop 后 tick_count 不应变化"


def test_start_is_idempotent():
    """多次调用 start 不应启动多个线程。"""
    tick = WorldTick(interval=0.005)
    tick.start()
    tick.start()
    tick.start()

    time.sleep(0.02)
    count = tick.tick_count()
    tick.stop(join=True, timeout=1.0)

    assert count >= 1


def test_multiple_start_stop():
    """可以 stop 后重新 start。"""
    tick = WorldTick(interval=0.005)
    tick.start()
    time.sleep(0.02)
    tick.stop(join=True, timeout=1.0)

    tick.start()
    time.sleep(0.02)
    tick.stop(join=True, timeout=1.0)

    assert tick.tick_count() >= 2


def test_get_world_tick_singleton():
    """get_world_tick 应返回同一实例。"""
    t1 = get_world_tick()
    t2 = get_world_tick()
    assert t1 is t2


def test_thread_safety():
    """多个线程同时读 tick_count 不应报错。"""
    tick = WorldTick(interval=0.001)
    tick.start()

    errors = []

    def reader():
        try:
            for _ in range(50):
                tick.tick_count()
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=1.0)

    tick.stop(join=True, timeout=1.0)
    assert not errors, f"读取 tick_count 时出现异常: {errors}"
