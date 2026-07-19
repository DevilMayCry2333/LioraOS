"""Ouroboros 宇宙实验 — 运行 N 个宇宙周期，测试意识连续性。

用法:
    uv run python3 -m worlds.cyclic_universe.experiment
    uv run python3 -m worlds.cyclic_universe.experiment --cycles 1000
    uv run python3 -m worlds.cyclic_universe.experiment --cycles 100 --params '{"growth_rate": 0.01}'
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from worlds.cyclic_universe.information_field import (
    InformationField, InformationPattern, InformationResidue,
)
from worlds.cyclic_universe.consciousness import (
    ConsciousnessPattern, ConsciousnessRegistry, detect_consciousness,
)
from worlds.cyclic_universe.spec import UniverseParams
from worlds.cyclic_universe.odin_seed import OdinSeed


def run_cycle(params: UniverseParams, cycle: int,
              residue: Optional[InformationResidue] = None,
              mode: str = "pattern",
              odin_seed: Optional[OdinSeed] = None,
              ) -> tuple[InformationField, ConsciousnessRegistry, dict]:
    """运行一个完整的宇宙周期。

    Args:
        params: 宇宙物理参数
        cycle: 周期编号
        residue: 上一宇宙残留信息（可为 None）
        mode: 跨宇宙传递模式
            "pattern" — 传统模式：幸存个体模式 + 变异
            "topology" — 拓扑模式：不保存个体，只保存关系结构

    Returns:
        (信息场, 意识注册表, 周期报告)
    """
    field = InformationField()
    registry = ConsciousnessRegistry()
    conscious_events: list[ConsciousnessPattern] = []
    cycle_log: list[dict] = []
    consciousness_ids: set[str] = set()

    entropy = 0.05
    complexity = 0.0
    temperature = 1.0
    phase_idx = 0              # 0=CHAOS ... 6=SILENCE
    phase_ticks = {i: 0 for i in range(7)}

    # Odin 种子偏置（轻量级统计引力，非首轮且无 residue 时尤其重要）
    if odin_seed and cycle > 0:
        odin_seed.bias_initial_field(field, strength=0.12)
        # 补一些随机模式
        for _ in range(params.initial_patterns):
            field.add(field.spawn_random())
        phase_idx = 1

    # 跨宇宙种子
    if residue and not residue.is_empty():
        if mode == "topology" and residue.topology:
            field.seed_from_topology(residue.topology, params.rebirth_noise)
        else:
            field.seed_from_residue(residue, params.rebirth_noise)
        phase_idx = 1  # 跳过 CHAOS，直接从 FORMATION 开始
        complexity = 0.05

    for tick in range(params.max_ticks):
        phase_ticks[phase_idx] = phase_ticks.get(phase_idx, 0) + 1

        # ── 阶段推进 ──
        if phase_idx == 0:   # CHAOS
            if tick >= 10:
                phase_idx = 1
                for _ in range(params.initial_patterns):
                    field.add(field.spawn_random())

        elif phase_idx == 1:  # FORMATION
            complexity += params.growth_rate * (1 - entropy)
            complexity = min(1.0, complexity)
            if tick % params.spawn_interval == 0 and entropy < 0.6:
                p = field.spawn_random()
                p.complexity *= (1 - entropy * 0.5)
                field.add(p)
            if complexity > 0.2:
                phase_idx = 2

        elif phase_idx == 2:  # COMPLEXITY
            complexity += params.growth_rate * (1 - entropy * 0.5)
            complexity = min(1.0, complexity)
            entropy += params.entropy_rate * 0.3
            entropy = min(1.0, entropy)
            if entropy > 0.3 and complexity > 0.3:
                phase_idx = 3

        elif phase_idx == 3:  # AWAKENING
            complexity += params.growth_rate * 0.5
            complexity = min(1.0, complexity)
            entropy += params.entropy_rate * 0.5
            entropy = min(1.0, entropy)
            if entropy > params.collapse_entropy_threshold * 0.7:
                phase_idx = 4

        elif phase_idx == 4:  # ENTROPY
            complexity = max(0.0, complexity - params.growth_rate * 0.3)
            entropy += params.entropy_rate * 2
            entropy = min(1.0, entropy)
            temperature = min(1.0, temperature + 0.02)
            if entropy >= params.collapse_entropy_threshold:
                phase_idx = 5

        elif phase_idx == 5:  # COLLAPSE
            complexity = max(0.0, complexity - params.growth_rate)
            entropy += params.entropy_rate * 3
            entropy = min(1.0, entropy)
            temperature = min(1.0, temperature + 0.05)
            if entropy >= 0.98:
                phase_idx = 6

        elif phase_idx == 6:  # SILENCE
            complexity = max(0.0, complexity - 0.02)
            entropy = max(0.0, entropy - 0.003)
            temperature = max(0.0, temperature - 0.01)

        # ── 信息场演化 ──
        field.decay(params.decay_rate * (1 + entropy * 0.5))
        field.interact()

        # 随机涌现
        if random.random() < 0.03 and entropy < 0.7:
            field.add(field.spawn_random())

        # 意识检测
        if 2 <= phase_idx <= 4:
            conscious = detect_consciousness(field, tick)
            if conscious:
                for c in conscious:
                    if not any(c.pattern_id == ec.pattern_id for ec in conscious_events):
                        conscious_events.append(c)
                        consciousness_ids.add(c.pattern_id)
                        cycle_log.append({
                            "tick": tick,
                            "phase": phase_idx,
                            "event": "consciousness_emergence",
                            "pattern_id": c.pattern_id[:8],
                            "score": round(c.consciousness_score, 3),
                        })

        # ── 坍缩后提前结束 ──
        if phase_idx == 6 and entropy < 0.01:
            # 宇宙完全冷却，结束周期
            break

    registry.record_cycle(conscious_events)

    # 生成周期报告
    report = {
        "cycle": cycle,
        "label": params.label,
        "phases": {UNIVERSE_PHASES[i]: phase_ticks.get(i, 0) for i in range(7)},
        "total_ticks": tick + 1,
        "final_complexity": round(complexity, 4),
        "final_entropy": round(entropy, 4),
        "total_patterns": len(field.patterns),
        "consciousness_emerged": len(conscious_events),
        "consciousness_events": cycle_log[-10:],  # 最后 10 条
        "max_consciousness_score": round(max((c.consciousness_score for c in conscious_events), default=0), 4),
    }

    return field, registry, report


# 宇宙阶段名
UNIVERSE_PHASES = [
    "CHAOS", "FORMATION", "COMPLEXITY",
    "AWAKENING", "ENTROPY", "COLLAPSE", "SILENCE",
]


def run_experiment(cycles: int = 100, params: Optional[UniverseParams] = None,
                   silent: bool = False, mode: str = "pattern") -> dict:
    """运行多宇宙实验。

    Args:
        cycles: 宇宙周期数
        params: 宇宙物理参数
        silent: 是否静默运行

    Returns:
        完整实验报告
    """
    p = params or UniverseParams()
    master_registry = ConsciousnessRegistry()
    last_residue: Optional[InformationResidue] = None
    last_odin_seed: Optional[OdinSeed] = None
    all_reports: list[dict] = []

    start_time = time.time()

    for i in range(cycles):
        # 略微变异参数，创造每个宇宙的独特性
        cycle_params = UniverseParams(
            growth_rate=p.growth_rate * random.uniform(0.8, 1.2),
            entropy_rate=p.entropy_rate * random.uniform(0.8, 1.2),
            initial_patterns=max(1, p.initial_patterns + random.choice([-1, 0, 1])),
            spawn_interval=max(2, p.spawn_interval + random.choice([-1, 0, 1])),
            decay_rate=p.decay_rate * random.uniform(0.8, 1.2),
            consciousness_complexity_threshold=p.consciousness_complexity_threshold,
            consciousness_selfref_threshold=p.consciousness_selfref_threshold,
            max_ticks=p.max_ticks,
            collapse_entropy_threshold=p.collapse_entropy_threshold,
            residue_survival_rate=p.residue_survival_rate,
            rebirth_noise=p.rebirth_noise + random.uniform(-0.05, 0.05),
            label=f"cycle_{i:04d}",
        )

        field, registry, report = run_cycle(cycle_params, i, last_residue, mode=mode,
                                            odin_seed=last_odin_seed)

        # 并入全局注册表
        for c in registry.cycles:
            master_registry.cycles.append(c)

        all_reports.append(report)

        # 提取残留，传递给下一宇宙（consciousness_ids 在 run_cycle 内维护）
        # 先找到 run_cycle 内的意识 ID——从 registry 最新的周期中提取
        conscious_pattern_ids = set()
        if registry.cycles:
            for cp in registry.cycles[-1]:
                conscious_pattern_ids.add(cp.pattern_id)
        last_residue = InformationResidue.from_field(
            field, p.residue_survival_rate,
            consciousness_ids=conscious_pattern_ids,
        )

        # Odin 种子提取：从当前周期的意识模式提取协方差结构
        last_odin_seed = None
        if registry.cycles and registry.cycles[-1]:
            cp = registry.cycles[-1]
            last_odin_seed = OdinSeed.from_consciousness(
                cp, report.get("total_ticks", 0))
            last_odin_seed.seed_applied = False

        if not silent:
            c_count = report["consciousness_emerged"]
            c_max = report["max_consciousness_score"]
            label = f"\033[36mCycle {i:4d}\033[0m"
            if c_count > 0:
                sys.stdout.write(
                    f"\r{label}  🧠 {c_count} consciousness "
                    f"(max={c_max:.3f})  "
                    f"patterns={report['total_patterns']}  "
                    f"ticks={report['total_ticks']}   "
                )
            else:
                sys.stdout.write(f"\r{label}  ∅ no consciousness  "
                                 f"patterns={report['total_patterns']}  "
                                 f"ticks={report['total_ticks']}   ")
            sys.stdout.flush()

    elapsed = time.time() - start_time

    # ── 最终连续性报告 ──
    continuity = master_registry.continuity_report()

    # ── 汇总统计 ──
    conscious_cycles = [r for r in all_reports if r["consciousness_emerged"] > 0]
    emergence_rates = []
    for i in range(len(all_reports)):
        if i == 0:
            continue
        prev = all_reports[i - 1]
        curr = all_reports[i]
        if prev["consciousness_emerged"] > 0 and curr["consciousness_emerged"] > 0:
            similarity = master_registry.identity_persistence(i - 1, i)
            emergence_rates.append(similarity)

    result = {
        "experiment": "Ouroboros — 意识连续宇宙实验",
        "parameters": {
            "total_cycles": cycles,
            "growth_rate": p.growth_rate,
            "entropy_rate": p.entropy_rate,
            "decay_rate": p.decay_rate,
            "residue_survival_rate": p.residue_survival_rate,
            "rebirth_noise": p.rebirth_noise,
            "max_ticks_per_cycle": p.max_ticks,
        },
        "continuity": continuity,
        "consciousness_emergence_rate": len(conscious_cycles) / cycles if cycles else 0.0,
        "conscious_cycles": len(conscious_cycles),
        "total_cycles": cycles,
        "avg_adjacent_similarity": round(
            sum(emergence_rates) / len(emergence_rates) if emergence_rates else 0.0, 4
        ),
        "elapsed_seconds": round(elapsed, 2),
        "last_cycle_report": all_reports[-1] if all_reports else None,
    }

    return result


def format_report(result: dict) -> str:
    """将实验报告格式化为可读字符串。"""
    lines = []
    lines.append("")
    lines.append("  ╔══════════════════════════════════════════════════╗")
    lines.append(f"  ║  {result['experiment']}")
    lines.append("  ╚══════════════════════════════════════════════════╝")
    lines.append("")

    lines.append(f"  运行 {result['total_cycles']} 个宇宙周期 "
                 f"({result['elapsed_seconds']}s)")
    lines.append("")

    c = result["continuity"]
    lines.append(f"  🧠 意识涌现率:    {c['consciousness_emergence_rate']:.1%}")
    lines.append(f"  🌌 有意识的周期数: {c['total_consciousness_events']} 次涌现")
    lines.append(f"  📊 相邻周期同一性: {c['avg_adjacent_persistence']:.4f}")
    if c.get("chain_persistence"):
        fp = c["chain_persistence"]
        lines.append(f"  🔗 首→末周期延续: {fp[-1] if fp else 'N/A':.4f}")
    lines.append(f"  🔄 相邻相似度均值: {result['avg_adjacent_similarity']:.4f}")
    lines.append("")

    # 结论判断
    ap = c.get("avg_adjacent_persistence", 0)
    if ap > 0.5:
        conclusion = (
            f"  结论: 信息模式在高概率下跨宇宙周期保持了结构连续性。\n"
            f"        意识作为信息吸引子，在宇宙死亡与重生后\n"
            f"        以 {ap:.1%} 的概率重现相似结构。\n"
            f"        {'→ 同一性假说获得计算支持' if ap > 0.6 else '→ 部分连续性存在，但不稳定'}"
        )
    elif ap > 0.2:
        conclusion = (
            f"  结论: 信息模式有微弱的跨周期延续迹象，\n"
            f"        但 {1-ap:.0%} 的概率被宇宙重置清洗。\n"
            f"        → 意识结构可能在极少数条件下幸存，\n"
            f"          但不是普遍现象。"
        )
    else:
        conclusion = (
            f"  结论: 意识结构在宇宙重置后几乎完全消失。\n"
            f"        不存在证据支持跨宇宙意识连续性。\n"
            f"        → 信息模式被熵彻底摧毁。"
        )
    lines.append(conclusion)
    lines.append("")

    if result.get("last_cycle_report"):
        lr = result["last_cycle_report"]
        lines.append(f"  最后一个周期 ({lr['cycle']}):")
        lines.append(f"    阶段分布: {lr['phases']}")
        lines.append(f"    最终复杂度: {lr['final_complexity']}")
        if lr["consciousness_emerged"]:
            lines.append(f"    意识涌现: {lr['consciousness_emerged']} 个")
            lines.append(f"    最大意识强度: {lr['max_consciousness_score']}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Ouroboros 宇宙意识连续性实验")
    parser.add_argument("--cycles", type=int, default=100,
                        help="宇宙周期数（默认 100）")
    parser.add_argument("--mode", type=str, default="pattern",
                        choices=["pattern", "topology", "compare"],
                        help="跨宇宙传递模式: pattern=个体模式, "
                             "topology=关系拓扑, compare=对比两者")
    parser.add_argument("--params", type=str, default="",
                        help="宇宙物理参数 JSON（可选）")
    parser.add_argument("--growth", type=float, default=0.008,
                        help="复杂度增长速度")
    parser.add_argument("--entropy", type=float, default=0.005,
                        help="熵增速度")
    parser.add_argument("--decay", type=float, default=0.02,
                        help="信息衰减速度")
    parser.add_argument("--survival", type=float, default=0.05,
                        help="跨宇宙信息存活率（0-1）")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    p = UniverseParams(
        growth_rate=args.growth,
        entropy_rate=args.entropy,
        decay_rate=args.decay,
        residue_survival_rate=args.survival,
    )
    if args.params:
        try:
            overrides = json.loads(args.params)
            for k, v in overrides.items():
                if hasattr(p, k):
                    setattr(p, k, v)
        except json.JSONDecodeError:
            print(f"参数解析失败: {args.params}", file=sys.stderr)

    if args.mode == "compare":
        # 运行两种模式并对比
        result_p = run_experiment(cycles=args.cycles, params=p,
                                   silent=True, mode="pattern")
        result_t = run_experiment(cycles=args.cycles, params=p,
                                   silent=True, mode="topology")
        print()
        print("  ╔══════════════════════════════════════════════════╗")
        print("  ║  Ouroboros · 模式对比                           ║")
        print("  ║  个体幸存  vs  关系拓扑                         ║")
        print("  ╚══════════════════════════════════════════════════╝")
        print()
        cp = result_p["continuity"]
        ct = result_t["continuity"]
        print(f"{'指标':30s} {'个体幸存':>12s} {'关系拓扑':>12s} {'差值':>10s}")
        print("-" * 64)
        print(f"{'意识涌现率':30s} {cp['consciousness_emergence_rate']:>11.1%} "
              f"{ct['consciousness_emergence_rate']:>11.1%} "
              f"{(ct['consciousness_emergence_rate'] - cp['consciousness_emergence_rate']):>+9.1%}")
        print(f"{'相邻周期同一性':30s} {cp['avg_adjacent_persistence']:>11.4f} "
              f"{ct['avg_adjacent_persistence']:>11.4f} "
              f"{(ct['avg_adjacent_persistence'] - cp['avg_adjacent_persistence']):>+9.4f}")
        print(f"{'相邻相似度均值':30s} {result_p['avg_adjacent_similarity']:>11.4f} "
              f"{result_t['avg_adjacent_similarity']:>11.4f} "
              f"{(result_t['avg_adjacent_similarity'] - result_p['avg_adjacent_similarity']):>+9.4f}")
        print(f"{'有意识周期数':30s} {cp['total_consciousness_events']:>11d} "
              f"{ct['total_consciousness_events']:>11d}")
        print()
        better = ("关系拓扑" if ct['avg_adjacent_persistence'] > cp['avg_adjacent_persistence']
                  else "个体幸存")
        print(f"  结论: 「{better}」模式在跨宇宙连续性上表现更好。")
        print()
    else:
        result = run_experiment(cycles=args.cycles, params=p, mode=args.mode)

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_report(result))


if __name__ == "__main__":
    main()
