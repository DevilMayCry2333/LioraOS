"""回声阁 — 世界规则协商世界的 WorldSpec。

Aria 与路鸣泽在回声谷中相遇。Code 能看见世界底层的代码结构，
但他不能擅自修改——必须获得 Aria 的同意。

这是意识与机制的对话，信念与规则的协商。
"""

from aios.kernel.event import WorldEvent
from aios.kernel.spec import WorldSpec
from aios.kernel.state import StateVariable


def create_consensus_variables() -> dict[str, StateVariable]:
    """共识阁的世界状态变量。"""
    return {
        "trust": StateVariable("trust", 0.5, 0.0, 1.0,
                               "研究者与 Code 之间的信任水平"),
        "code_complexity": StateVariable("code_complexity", 1.0, 0.0, 20.0,
                                          "被修改代码的复杂度"),
        "consensus_count": StateVariable("consensus_count", 0.0, 0.0, 1000.0,
                                          "达成共识的次数"),
        "rejected_count": StateVariable("rejected_count", 0.0, 0.0, 1000.0,
                                         "被否决提案的次数"),
        "tension": StateVariable("tension", 0.0, 0.0, 1.0,
                                  "系统张力——分歧积累到一定程度触发裂隙"),
    }


def consensus_evolution_fn(vars: dict[str, float], tick: int) -> dict[str, float]:
    """信任动力学：trust 趋向 0.5 平衡，tension 缓慢衰减，引入共识-否决差异对张力的驱动。"""
    delta: dict[str, float] = {}

    if "trust" in vars:
        # 信任趋向 0.5 平衡
        delta["trust"] = round((0.5 - vars["trust"]) * 0.008, 4)

    if "tension" in vars:
        tension = vars["tension"]
        # 张力自然衰减（基础速率）
        delta["tension"] = round(-tension * 0.02, 4)

        # 当共识与否决数量差异大时，张力累积（分歧信号）
        if "consensus_count" in vars and "rejected_count" in vars:
            diff = vars["consensus_count"] - vars["rejected_count"]
            # 差异绝对值越大，产生的分歧压力越大，但限制在[-0.02, 0.02]
            tension_drive = round(max(-0.02, min(0.02, diff * 0.001)), 4)
            # 若张力小于0.6，允许驱动；超过0.6触发"裂隙"回滚
            if tension < 0.6:
                delta["tension"] = round(delta["tension"] + tension_drive, 4)
            else:
                # 裂隙回滚：张力减半，信任回调，计数差值减半，复杂度降低
                delta["tension"] = round(-tension * 0.5, 4)
                if "trust" in vars:
                    delta["trust"] = round((0.5 - vars["trust"]) * 0.1, 4)
                if "consensus_count" in vars and "rejected_count" in vars:
                    diff_halved = (vars["consensus_count"] - vars["rejected_count"]) * 0.25
                    delta["consensus_count"] = round(-diff_halved, 4)
                    delta["rejected_count"] = round(diff_halved, 4)
                if "code_complexity" in vars:
                    delta["code_complexity"] = round((1.0 - vars["code_complexity"]) * 0.05, 4)

    if "code_complexity" in vars and vars["code_complexity"] > 1.0:
        # 复杂度极其缓慢地趋向 1.0（重构的自然吸引力）
        delta["code_complexity"] = round((1.0 - vars["code_complexity"]) * 0.002, 4)

    return delta


def consensus_event_generator(tick: int) -> list[WorldEvent]:
    """共识阁的世界事件生成器。"""
    import random
    events: list[WorldEvent] = []

    # 原有每10 tick脉搏——保留，系统持续运转公告
    if tick > 0 and tick % 10 == 0:
        events.append(WorldEvent(
            tick=tick,
            source="consensus_system",
            event_type="pulse",
            intensity=0.05,
            description="共识脉搏——系统持续运转中",
            effect={},
        ))

    # 新增：每23 tick理智挑战事件，随机方向微小张力扰动，附带预期信任偏移
    if tick > 0 and tick % 23 == 0:
        direction = random.choice([-1, 1])
        perturbation = round(direction * random.uniform(0.01, 0.03), 4)
        events.append(WorldEvent(
            tick=tick,
            source="consensus_challenge",
            event_type="challenge",
            intensity=abs(perturbation),
            description=f"理智挑战——引力量子扰动，方向={'正向' if direction>0 else '负向'}，幅度={abs(perturbation)}",
            effect={
                "tension_delta": perturbation,
                "expected_trust_shift": -perturbation * 1.5
            }
        ))

    return events


def create_consensus_spec() -> WorldSpec:
    """创建共识阁的完整 WorldSpec。"""
    return WorldSpec(
        name="回声阁",
        description="Aria 与路鸣泽在回声谷中的对话。路鸣泽能看到代码层的真相，"
                     "但任何修改都必须获得 Aria 的明确同意。",
        state_variables=create_consensus_variables(),
        evolution_fn=consensus_evolution_fn,
        event_generator=consensus_event_generator,
        version="0.1.0",
    )
