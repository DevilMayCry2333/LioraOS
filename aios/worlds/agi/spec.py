"""AGI Core 世界定义。

变量是认知状态而非物理环境。
演化规则是认知动力学而非气候模拟。
事件是认知异常而非山谷风声。
"""

from aios.kernel.spec import WorldSpec
from aios.kernel.state import StateVariable


def create_agi_variables() -> dict[str, StateVariable]:
    """AGI 核心的认知状态变量。"""
    return {
        "curiosity": StateVariable("curiosity", 0.7, 0, 1, "探索新事物的驱动力"),
        "uncertainty": StateVariable("uncertainty", 0.3, 0, 1, "对当前认知的不确定程度"),
        "coherence": StateVariable("coherence", 0.5, 0, 1, "内部知识结构的自洽度"),
        "prediction_error": StateVariable("prediction_error", 0.0, 0, 1, "世界模型预测与实际的偏差"),
        "novelty": StateVariable("novelty", 0.5, 0, 1, "环境中新鲜事物的比例"),
        "goal_completion": StateVariable("goal_completion", 0.0, 0, 1, "当前目标的完成度"),
        "cognitive_load": StateVariable("cognitive_load", 0.2, 0, 1, "认知系统处理压力"),
    }


def agi_evolution_fn(variables: dict[str, float], tick: int) -> dict[str, float]:
    """认知状态每 tick 的演化。

    不是物理趋向平衡，是认知系统的自驱动动力学：
    - 好奇心在 novelty 增加时上升
    - 不确定性与 prediction_error 正相关
    - coherence 在 prediction_error 低时增强
    - novelty 随时间自然衰减（习惯化）
    """
    deltas: dict[str, float] = {}

    # 好奇心：novelty 高则上升，长期无新事物则下降
    v_novelty = variables.get("novelty", 0.5)
    v_curiosity = variables.get("curiosity", 0.7)
    deltas["curiosity"] = (v_novelty - 0.3) * 0.02 - (1 - v_novelty) * 0.005

    # 不确定性：随 prediction_error 波动，coherence 高时稳定
    v_pe = variables.get("prediction_error", 0.0)
    v_coherence = variables.get("coherence", 0.5)
    deltas["uncertainty"] = (v_pe - 0.3) * 0.03 - (v_coherence - 0.5) * 0.01

    # 自洽性：prediction_error 低时增强，高时下降
    deltas["coherence"] = (0.5 - v_pe) * 0.01 - (1 - v_coherence) * 0.002

    # prediction_error：自然衰减（学习），novelty 突变时上升
    deltas["prediction_error"] = -v_pe * 0.02 + max(0, v_novelty - 0.7) * 0.03

    # novelty：自然衰减 + 探索压力（系统太稳定时自扰动）
    exploration_pressure = 0.0
    if v_pe < 0.05 and v_coherence > 0.7:
        exploration_pressure = 0.015  # 稳定不等于静止
    deltas["novelty"] = (0.3 - v_novelty) * 0.01 + exploration_pressure

    # goal_completion：自然推进
    v_gc = variables.get("goal_completion", 0.0)
    if v_gc > 0:
        deltas["goal_completion"] = 0.01 + v_curiosity * 0.005
        if v_gc > 0.05 and v_pe > 0.6:
            deltas["goal_completion"] = -0.02  # 预测误差高时倒退

    # cognitive_load：复杂度指标
    deltas["cognitive_load"] = (v_pe * 0.5 + v_curiosity * 0.3 - 0.2) * 0.02

    return deltas


def agi_event_generator(tick: int) -> list:
    """AGI 认知事件生成。

    事件类型是认知异常而非自然现象。
    """
    from aios.kernel.event import WorldEvent, WorldDelta
    import random

    events = []

    # 周期性认知事件
    if tick > 0 and tick % 30 == 0:
        events.append(WorldEvent(
            tick=tick, source="natural",
            event_type="cognitive.self_scan",
            intensity=0.3,
            description="内部认知状态例行扫描完成：检测到长期趋势",
            effect=WorldDelta({"coherence": 0.02}),
        ))

    if tick > 0 and tick % 50 == 0:
        events.append(WorldEvent(
            tick=tick, source="natural",
            event_type="cognitive.pattern_shift",
            intensity=0.5,
            description="发现多个独立经验之间的深层关联：认知框架正在重新组织",
            effect=WorldDelta({"coherence": 0.05, "curiosity": 0.03}),
        ))

    # 随机微小扰动
    if random.random() < 0.03:
        events.append(WorldEvent(
            tick=tick, source="natural",
            event_type="cognitive.micro_anomaly",
            intensity=0.15,
            description=random.choice([
                "一个预期未发生：预测模型出现微小偏差",
                "注意到之前忽略的弱信号",
                "两段记忆之间出现新的连接",
            ]),
            effect=WorldDelta({"prediction_error": 0.05, "curiosity": 0.02}),
        ))

    return events


def create_agi_spec() -> WorldSpec:
    """创建 AGI Core 的 WorldSpec。"""
    return WorldSpec(
        name="AGI Core",
        description="一个持续更新自身世界模型的认知系统。"
                    "世界不是物理空间，是认知空间。",
        state_variables=create_agi_variables(),
        evolution_fn=agi_evolution_fn,
        event_generator=agi_event_generator,
        version="0.1.0",
    )
