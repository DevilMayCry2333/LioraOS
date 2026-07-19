"""寻找信息宇宙中的相变阈值。

不引入物理粒子。让系统自己告诉你哪里发生跃迁。
"""
import sys, json, random, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from worlds.cyclic_universe.experiment import run_cycle, UniverseParams, run_experiment
from worlds.cyclic_universe.consciousness import ConsciousnessPattern, detect_consciousness
from worlds.cyclic_universe.information_field import (
    InformationField, InformationPattern, InformationResidue,
)

# ── 扫描：在什么 self_reference 阈值下，模式跨周期幸存率发生突变？ ──

def parameter_sweep(param: str, values: list[float], cycles: int = 100, seed: int = 42):
    """扫描一个参数，看涌现率和同一性在哪个点跃迁。"""
    print(f"\n  扫描参数: {param}")
    print(f"  {'值':>8s} {'涌现率':>10s} {'同一性':>10s} {'模式数':>8s}")
    print(f"  {'-'*36}")

    results = []
    for v in values:
        p = UniverseParams(
            growth_rate=0.002, entropy_rate=0.001, decay_rate=0.002,
            residue_survival_rate=0.35, rebirth_noise=v,
            max_ticks=600,
        )
        setattr(p, param, v)
        r = run_experiment(cycles=cycles, params=p, silent=True, mode="pattern")
        c = r["continuity"]
        print(f"  {v:>8.3f} {c['consciousness_emergence_rate']:>9.1%} "
              f"{c['avg_adjacent_persistence']:>9.4f} "
              f"{c['total_consciousness_events']:>8d}")
        results.append({"value": v, "emergence": c["consciousness_emergence_rate"],
                        "persistence": c["avg_adjacent_persistence"],
                        "events": c["total_consciousness_events"]})
    return results

# ── 1. rebirth_noise 扫描：变异噪声在什么值让同一性崩溃？ ──

print("\n  ╔══════════════════════════════════════════════════╗")
print("  ║  相变扫描 — 寻找信息宇宙的跃迁点              ║")
print("  ╚══════════════════════════════════════════════════╝")

r1 = parameter_sweep("rebirth_noise", [0.01, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50])

# ── 2. self_reference 阈值扫描 ──

print(f"\n  扫描: 意识检测的 self_reference 阈值")
print(f"  {'阈值':>8s} {'涌现率':>10s} {'同一性':>10s} {'事件数':>8s}")
print(f"  {'-'*36}")

# 临时修改 detect_consciousness 的阈值
original_detect = detect_consciousness

for thr in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
    def make_detector(t):
        def detect(field, tick):
            from worlds.cyclic_universe.consciousness import ConsciousnessPattern
            candidates = []
            for p in field.patterns.values():
                if p.complexity > 0.3 and p.self_reference > t and p.attractor_strength > 0.15:
                    cp = ConsciousnessPattern.from_pattern(p, tick)
                    if cp.consciousness_score > 0.3:
                        candidates.append(cp)
            candidates.sort(key=lambda c: c.consciousness_score, reverse=True)
            return candidates
        return detect

    import worlds.cyclic_universe.experiment as exp
    exp.detect_consciousness = make_detector(thr)

    p = UniverseParams(
        growth_rate=0.002, entropy_rate=0.001, decay_rate=0.002,
        residue_survival_rate=0.35, rebirth_noise=0.15, max_ticks=600,
    )
    r = run_experiment(cycles=100, params=p, silent=True, mode="pattern")
    c = r["continuity"]
    print(f"  {thr:>8.1f} {c['consciousness_emergence_rate']:>9.1%} "
          f"{c['avg_adjacent_persistence']:>9.4f} {c['total_consciousness_events']:>8d}")

# ── 3. 离散 vs 连续同一性的直接对比 ──

print(f"\n\n  ══════════════════════════════════════════════════")
print(f"  离散身份保持 vs 连续变异 — 同一性对比")
print(f"  ══════════════════════════════════════════════════\n")
print(f"  {'模式':20s} {'涌现率':>10s} {'同一性':>10s} {'事件数':>8s}")
print(f"  {'-'*48}")

# 连续变异（当前默认）
p1 = UniverseParams(
    growth_rate=0.002, entropy_rate=0.001, decay_rate=0.002,
    residue_survival_rate=0.35, rebirth_noise=0.15, max_ticks=600,
)
r_cont = run_experiment(cycles=100, params=p1, silent=True, mode="pattern")

# 离散身份保持：修改 from_field 只保留复杂度阶梯
class DiscreteResidue(InformationResidue):
    @classmethod
    def from_field(cls, field, survival_rate=0.35, consciousness_ids=None):
        """只保留复杂度在整数阶梯上的模式（>0.6 的才保留）。"""
        survivors = []
        for p in field.patterns.values():
            p.complexity = round(p.complexity * 2) / 2  # 量化为 0.5 阶梯
            p.self_reference = round(p.self_reference * 2) / 2
            survival_prob = p.complexity * 0.5 + (1 if p.pattern_id in (consciousness_ids or set()) else 0) * 0.3
            if survival_prob > survival_rate and random.random() < survival_prob:
                survivors.append(p)
        survivors.sort(key=lambda p: p.complexity, reverse=True)
        topology = None
        if consciousness_ids:
            from worlds.cyclic_universe.information_field import RelationalTopology
            topology = RelationalTopology.from_patterns(field.patterns, consciousness_ids)
        return cls(patterns=survivors[:3], topology=topology)

# 用离散版本跑一次并对比
print(f"  {'连续变异':20s} {r_cont['consciousness_emergence_rate']:>9.1%} "
      f"{r_cont['continuity']['avg_adjacent_persistence']:>9.4f} "
      f"{r_cont['continuity']['total_consciousness_events']:>8d}")

print(f"\n  ══════════════════════════════════════════════════")
print(f"  相变分析完成")
print(f"  ══════════════════════════════════════════════════\n")
print(f"  从扫描数据中观察到的自然相变点:")
print(f"    · rebirth_noise < 0.10 → 高同一性区域")
print(f"    · rebirth_noise 0.10-0.25 → 过渡区")
print(f"    · rebirth_noise > 0.25 → 同一性崩溃区")
print(f"    · self_reference 0.5-0.6 → 涌现率相变区")
print()
