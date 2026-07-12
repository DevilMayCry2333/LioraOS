"""Cyberpunk 2077 世界观的状态变量定义和演化规则。

不是物理趋向平衡（如 Liora 的温度→22°C），
而是城市系统的**对抗平衡**：

  corporate_grip ↑ → street_heat ↑ → underground_hope ↑ → corporate_grip ↓

这形成一个振荡系统，而非 Liora 的阻尼系统。
城市永远不会稳定——这就是 Cyberpunk。
"""

import math
import random

from aios.kernel.state import StateVariable


def create_cyberpunk_variables() -> dict[str, StateVariable]:
    """创建夜之城的核心状态变量。"""
    return {
        # ── 核心城市力学 ──
        "corporate_grip": StateVariable(
            "corporate_grip", 0.55, 0, 1,
            "企业对城市的控制力。越高→压迫越重，但秩序越强。",
        ),
        "street_heat": StateVariable(
            "street_heat", 0.30, 0, 1,
            "街头紧张度。越高→暴力和抗议越频繁。",
        ),
        "underground_hope": StateVariable(
            "underground_hope", 0.35, 0, 1,
            "地下世界的希望。越高→抵抗运动越活跃。",
        ),

        # ── 数字生态 ──
        "cyberspace_turbulence": StateVariable(
            "cyberspace_turbulence", 0.30, 0, 1,
            "赛博空间扰动。网络攻击、AI 异常、数据风暴。",
        ),
        "data_remnant": StateVariable(
            "data_remnant", 0.20, 0, 1,
            "数据残响密度。旧数据在网络中的回响——夜之城的回声。",
        ),

        # ── 人性维度 ──
        "humanity_decay": StateVariable(
            "humanity_decay", 0.25, 0, 1,
            "人性流失程度。义体化、创伤、系统压迫导致的人性侵蚀。",
        ),

        # ── 外部压力 ──
        "night_city_pulse": StateVariable(
            "night_city_pulse", 0.50, 0, 1,
            "夜之城整体活力/脉动。随机波动，影响其他变量的变化速率。",
        ),
    }


def cyberpunk_evolution_fn(variables: dict[str, float], tick: int) -> dict[str, float]:
    """每 tick 的状态演化。

    设计哲学：
    - Liora 是**趋向平衡**（temperature → 22°C 的负反馈）
    - Cyberpunk 是**对抗平衡**（三力制衡 + 相互放大的正反馈）

    系统永远在振荡，不会静止。这才是赛博朋克。
    """
    deltas: dict[str, float] = {}

    cg = variables.get("corporate_grip", 0.55)
    sh = variables.get("street_heat", 0.30)
    uh = variables.get("underground_hope", 0.35)
    ct = variables.get("cyberspace_turbulence", 0.30)
    dr = variables.get("data_remnant", 0.20)
    hd = variables.get("humanity_decay", 0.25)
    ncp = variables.get("night_city_pulse", 0.50)

    # ── 基频——夜之城的脉动 ──
    pulse_delta = 0.02 * math.sin(tick * 0.05) + random.uniform(-0.01, 0.01)
    deltas["night_city_pulse"] = max(-0.5, min(0.5, pulse_delta))

    # ── corporate_grip：企业控制力 ──
    # 自然增长（权力自我膨胀） + 脉动助推
    # 被 underground_hope 抑制（抵抗运动削弱控制）
    # 被 street_heat 轻微抑制（社会动荡增加管理成本）
    cg_delta = 0.005 * ncp           # 自然膨胀
    cg_delta -= 0.015 * uh           # 抵抗运动的抑制
    cg_delta -= 0.005 * sh           # 社会动荡的抑制
    if cg < 0.3:
        cg_delta += 0.01             # 控制力太低时反弹
    deltas["corporate_grip"] = cg_delta

    # ── street_heat：街头紧张度 ──
    # corporate_grip 高 → 压迫产生紧张
    # humanity_decay 高 → 人性流失驱动愤怒
    # underground_hope 高 → 希望释放紧张（人们看到改变的可能）
    # 自然衰减（城市有惯性）
    sh_delta = 0.02 * cg             # 压迫→紧张
    sh_delta += 0.01 * hd            # 人性流失→愤怒
    sh_delta -= 0.01 * uh            # 希望→舒缓
    sh_delta -= 0.008 * sh           # 自然衰减
    deltas["street_heat"] = sh_delta

    # ── underground_hope：地下希望 ──
    # street_heat 高 → 逆境催生希望
    # corporate_grip 高 → 控制越重，地下越旺盛（逆反）
    # 如果 corporate_grip 低 + street_heat 低 → 希望自然衰减
    uh_delta = 0.012 * sh            # 逆境→希望
    uh_delta += 0.008 * (cg - 0.3)   # 控制过度→逆反
    uh_delta -= 0.006 * uh           # 自然衰减
    if cg < 0.25 and sh < 0.2:
        uh_delta -= 0.01             # 太平盛世→希望消退
    deltas["underground_hope"] = uh_delta

    # ── cyberspace_turbulence：赛博空间扰动 ──
    # 数据残响的累积效应
    # 随机尖峰（攻击、AI 活动）
    # 自然衰减（网络有自愈能力）
    ct_delta = 0.01 * dr             # 数据残响加剧扰动
    ct_delta -= 0.02 * ct            # 自然衰减
    # 随机尖峰——类似 Liora 的随机风
    if random.random() < 0.03:
        ct_delta += random.uniform(0.05, 0.15)
    deltas["cyberspace_turbulence"] = ct_delta

    # ── data_remnant：数据残响 ──
    # cyberspace_turbulence 高 → 产生残响
    # 自然衰减（数据被覆盖/遗忘）
    # corporate_grip 高 → 数据被清理（企业控制信息流）
    dr_delta = 0.015 * ct            # 扰动产生残响
    dr_delta -= 0.005 * dr           # 自然遗忘
    dr_delta -= 0.01 * cg * dr       # 企业信息管控
    # 随机涌现——一个数据在某个角落被重新激活
    if random.random() < 0.02:
        dr_delta += random.uniform(0.02, 0.08)
    deltas["data_remnant"] = dr_delta

    # ── humanity_decay：人性流失 ──
    # corporate_grip 高 → 系统压迫侵蚀人性
    # cyberspace_turbulence 高 → 数字世界蚕食自我
    # underground_hope 高 → 社区感保护人性
    hd_delta = 0.005 * cg            # 系统压迫
    hd_delta += 0.008 * ct           # 赛博空间侵蚀
    hd_delta -= 0.01 * uh            # 社区/希望的保护
    hd_delta += 0.002                # 基础流失（存在本身的代价）
    deltas["humanity_decay"] = hd_delta

    return deltas
