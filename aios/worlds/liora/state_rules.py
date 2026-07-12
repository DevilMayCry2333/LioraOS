"""Liora 世界观的状态变量定义和演化规则。

从 aios/kernel/state.py 移出，原为硬编码在 WorldStateEngine 中的演化公式。
"""

from aios.kernel.state import StateVariable


def create_liora_variables() -> dict[str, StateVariable]:
    """创建 Liora 世界的默认状态变量注册表。"""
    return {
        "temperature": StateVariable("temperature", 22.0, -50, 100, "气温 (°C)"),
        "wind_speed": StateVariable("wind_speed", 1.0, 0, 50, "风速"),
        "humidity": StateVariable("humidity", 0.6, 0, 1, "相对湿度"),
        "light_level": StateVariable("light_level", 0.7, 0, 1, "光照水平"),
        "pressure": StateVariable("pressure", 1013, 800, 1200, "大气压 (hPa)"),
        "echo_density": StateVariable("echo_density", 0.3, 0, 1, "回声密度"),
        "silence_level": StateVariable("silence_level", 0.2, 0, 1, "寂静水平"),
        "vibration_field": StateVariable("vibration_field", 0.1, 0, 1, "振动场"),
        "crack_network": StateVariable("crack_network", 0.0, 0, 1, "裂隙网络"),
        "moss_growth": StateVariable("moss_growth", 0.1, 0, 1, "苔藓生长"),
        "mint_density": StateVariable("mint_density", 0.3, 0, 1, "薄荷密度"),
    }


def liora_evolution_fn(variables: dict[str, float], tick: int) -> dict[str, float]:
    """Liora 世界每 tick 的状态演化。

    温度趋于 22°C，风速趋于 0.5，回声密度趋于 0.3。
    """
    deltas: dict[str, float] = {}

    if "temperature" in variables:
        deltas["temperature"] = 0.05 * (22.0 - variables["temperature"])

    if "wind_speed" in variables:
        target = 0.5
        deltas["wind_speed"] = max(-0.1, min(0.1, (target - variables["wind_speed"]) * 0.02))

    if "echo_density" in variables:
        deltas["echo_density"] = max(-0.01, min(0.01, (0.3 - variables["echo_density"]) * 0.01))

    if "humidity" in variables:
        deltas["humidity"] = (0.6 - variables["humidity"]) * 0.01

    if "light_level" in variables:
        deltas["light_level"] = (0.7 - variables["light_level"]) * 0.005

    return deltas
