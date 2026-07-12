"""WorldEventEngine 测试。"""

import json
import tempfile
from pathlib import Path

from aios.kernel.event import (
    WorldEvent, WorldDelta, EventSource, EventStatus,
    WorldEventEngine, get_event_engine,
)


def test_world_event_auto_id():
    """未指定 event_id 时应自动生成。"""
    e = WorldEvent()
    assert e.event_id.startswith("evt_")
    assert len(e.event_id) == 12  # "evt_" + 8 hex


def test_world_delta_is_zero():
    """全零 delta 应被检测为零。"""
    assert WorldDelta().is_zero()
    assert WorldDelta({"a": 0.0}).is_zero()
    assert not WorldDelta({"a": 0.5}).is_zero()


def test_world_delta_to_dict_skips_zero():
    """to_dict 应跳过接近零的值。"""
    d = WorldDelta({"a": 0.5, "b": 0.0, "c": 1e-10})
    result = d.to_dict()
    assert "a" in result["effects"]
    assert "b" not in result["effects"]
    assert "c" not in result["effects"]


def test_event_lifecycle_aging():
    """超过 max_age 的 CREATED 事件应被忽略。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        engine = WorldEventEngine(events_path=path, max_age=5)

        engine._tick = 0
        event = WorldEvent(tick=0, source=EventSource.NATURAL,
                           event_type="test", description="test")
        engine.inject(event)

        # 推进到 tick=6，事件应被忽略
        for _ in range(6):
            engine.tick()

        active = engine.get_active()
        assert len(active) == 0


def test_event_inject_and_retrieve():
    """inject 的事件应出现在活跃列表中。"""
    engine = WorldEventEngine()
    engine.initialize()

    event = WorldEvent(source=EventSource.NATURAL, event_type="wind",
                       description="一阵风")
    engine.inject(event)

    active = engine.get_active()
    assert any(e.event_id == event.event_id for e in active)


def test_event_format_for_prompt():
    """format_for_prompt 应返回合理文本。"""
    engine = WorldEventEngine()
    engine.initialize()

    engine.inject(WorldEvent(
        source=EventSource.NATURAL, event_type="test",
        description="测试事件",
    ))

    prompt = engine.format_for_prompt(n=5)
    assert "events:" in prompt
    assert "测试" in prompt


def test_empty_event_format():
    """无事件时 format_for_prompt 应返回空字符串。"""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        engine = WorldEventEngine(events_path=Path(tmp) / "events.jsonl")
        engine.initialize()
        assert engine.format_for_prompt() == ""


def test_jsonl_persistence():
    """事件应持久化到 JSONL 文件。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        engine = WorldEventEngine(events_path=path)
        engine.initialize()

        engine.inject(WorldEvent(
            source=EventSource.NATURAL, event_type="test",
            description="持久化测试",
        ))

        # 检查文件内容
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "test"
        assert data["description"] == "持久化测试"


def test_jsonl_load_on_initialize():
    """initialize 应加载已有的 JSONL 事件。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"

        # 先写入一条
        engine1 = WorldEventEngine(events_path=path)
        engine1.initialize()
        engine1.inject(WorldEvent(
            source=EventSource.EXTERNAL, event_type="legacy",
            description="已有事件",
        ))

        # 重新加载
        engine2 = WorldEventEngine(events_path=path)
        engine2.initialize()
        assert len(engine2.get_active()) >= 1


def test_event_generator():
    """event_generator 的事件应被引擎处理。"""
    called = False

    def generator(tick):
        nonlocal called
        called = True
        return [WorldEvent(
            source=EventSource.NATURAL, event_type="generated",
            description=f"tick {tick} 生成",
        )]

    engine = WorldEventEngine(event_generator=generator)
    engine.initialize()

    new_events = engine.tick()
    assert called
    assert len(new_events) == 1


def test_legacy_format_compat():
    """WorldDelta.from_dict 应兼容旧格式 {'temperature': 0.5}。"""
    delta = WorldDelta.from_dict({"temperature": 0.5, "wind_speed": 0.1})
    assert delta.effects["temperature"] == 0.5
    assert delta.effects["wind_speed"] == 0.1


def test_get_event_engine_singleton():
    """get_event_engine 应返回同一实例。"""
    e1 = get_event_engine()
    e2 = get_event_engine()
    assert e1 is e2
