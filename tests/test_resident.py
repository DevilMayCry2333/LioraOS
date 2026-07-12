"""Resident + ResidentRegistry 测试。"""

import tempfile
from pathlib import Path

from aios.kernel.resident import Resident, Component, ResidentRegistry, get_resident_registry


def test_component_roundtrip():
    """Component 序列化和反序列化应保留数据。"""
    c = Component("identity", {"name": "测试居民", "model": "deepseek"})
    d = c.to_dict()
    c2 = Component.from_dict(d)
    assert c2.component_type == "identity"
    assert c2.data["name"] == "测试居民"


def test_resident_create():
    """Resident.create 应创建带 identity 组件的居民。"""
    r = Resident.create("测试居民", model="deepseek", origin="test")
    assert r.resident_id.startswith("res_")
    assert r.join_time
    assert r.last_active

    identity = r.get_component("identity")
    assert identity is not None
    assert identity.data["name"] == "测试居民"
    assert identity.data["model"] == "deepseek"


def test_resident_add_and_get_component():
    """应能添加和查找组件。"""
    r = Resident(resident_id="r1")
    r.add_component(Component("memory", {"capacity": 100}))
    r.add_component(Component("tool", {"list": ["search", "act"]}))

    assert r.has_component("memory")
    assert r.has_component("tool")
    assert not r.has_component("planner")

    mem = r.get_component("memory")
    assert mem.data["capacity"] == 100


def test_resident_to_dict():
    """Resident.to_dict 应序列化所有字段（含组件）。"""
    r = Resident.create("序列化测试")
    d = r.to_dict()
    assert "resident_id" in d
    assert "components" in d
    assert any(c["type"] == "identity" for c in d["components"])


def test_resident_from_dict():
    """从 dict 恢复 Resident 应保留数据。"""
    r1 = Resident.create("恢复测试", model="local", origin="test_origin")
    d = r1.to_dict()
    r2 = Resident.from_dict(d)
    assert r2.resident_id == r1.resident_id
    assert r2.join_time == r1.join_time
    comp = r2.get_component("identity")
    assert comp is not None
    assert comp.data["name"] == "恢复测试"


def test_legacy_format_from_dict():
    """旧格式（字段在顶层而非 components 数组）应兼容。"""
    data = {
        "resident_id": "res_legacy",
        "name": "老居民",
        "model": "old",
        "origin": "legacy",
        "capabilities": ["observe", "speak"],
    }
    r = Resident.from_dict(data)
    assert r.resident_id == "res_legacy"
    identity = r.get_component("identity")
    assert identity.data["name"] == "老居民"
    caps = r.get_component("capabilities")
    assert caps.data["list"] == ["observe", "speak"]


def test_registry_register_and_get():
    """注册居民后应能通过 resident_id 获取。"""
    with tempfile.TemporaryDirectory() as tmp:
        reg = ResidentRegistry(data_dir=Path(tmp))
        r = reg.register("注册测试", model="test")
        fetched = reg.get(r.resident_id)
        assert fetched is not None
        assert fetched.resident_id == r.resident_id


def test_registry_find_by_name():
    """应能通过名字查找居民。"""
    with tempfile.TemporaryDirectory() as tmp:
        reg = ResidentRegistry(data_dir=Path(tmp))
        reg.register("居民A", model="m1")
        reg.register("居民B", model="m2")

        found = reg.find_by_name("居民A")
        assert found is not None
        ident = found.get_component("identity")
        assert ident.data["name"] == "居民A"


def test_registry_deregister():
    """注销后居民应被标记为 archived。"""
    with tempfile.TemporaryDirectory() as tmp:
        reg = ResidentRegistry(data_dir=Path(tmp))
        r = reg.register("待注销")
        assert reg.deregister(r.resident_id) is True
        # deregister 后文件仍在但标记为 archived
        archived = reg.get(r.resident_id)
        assert archived is not None
        assert archived.status == "archived"


def test_registry_list_all():
    """list_all 应返回所有注册过的居民。"""
    with tempfile.TemporaryDirectory() as tmp:
        reg = ResidentRegistry(data_dir=Path(tmp))
        reg.register("居民A")
        reg.register("居民B")
        assert reg.count() == 2


def test_registry_get_nonexistent():
    """不存在的 resident_id 应返回 None。"""
    with tempfile.TemporaryDirectory() as tmp:
        reg = ResidentRegistry(data_dir=Path(tmp))
        assert reg.get("nonexistent") is None


def test_get_resident_registry_singleton():
    """get_resident_registry 应返回同一实例。"""
    r1 = get_resident_registry()
    r2 = get_resident_registry()
    assert r1 is r2
