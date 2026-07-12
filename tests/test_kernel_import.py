"""Kernel 导入测试。"""


def test_kernel_import():
    """所有内核模块应能正常导入。"""
    from aios.kernel import tick, state, event, memory, resident, bus, spec
    assert tick is not None
    assert state is not None
    assert event is not None
    assert memory is not None
    assert resident is not None
    assert bus is not None
    assert spec is not None


def test_shutdown_function_exists():
    """shutdown 函数应存在且可调用。"""
    from aios.kernel import shutdown
    assert callable(shutdown)
