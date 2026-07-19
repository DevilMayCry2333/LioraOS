"""一个宇宙 = 50 Cycle。每 tick 一步，第 50 tick 坍缩。

每个 Cycle 不是宇宙——是宇宙内部的一次 tick。
第 0 tick: CHAOS
第 10 tick: 结构开始形成
第 20 tick: 复杂度增长
第 30 tick: 意识可能涌现
第 40 tick: 熵增
第 49 tick: 坍缩 → /dev/null → 下一宇宙
"""
import sys, random, time, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from worlds.cyclic_universe.information_field import (
    InformationField, InformationPattern, InformationResidue,
    RelationalTopology,
)
from worlds.cyclic_universe.consciousness import ConsciousnessRegistry, detect_consciousness, ConsciousnessPattern
from worlds.cyclic_universe.oracle import init_llm, speak, Chronicle
from worlds.cyclic_universe.odin_seed import OdinSeed

init_llm()
chronicle = Chronicle()

TICKS_PER_UNIVERSE = 100     # 一个宇宙 100 tick
UNIVERSES = 6                 # 跑 6 个宇宙
GROWTH_RATE = 0.04           # 快速增长
ENTROPY_RATE = 0.006          # 慢熵——保持低噪声环境
DECAY_RATE = 0.003            # 极低衰减——便利店模式
SURVIVAL_RATE = 0.0           # 每轮/dev/null

print()
print("  ╔══════════════════════════════════════════════════╗")
print("  ║  Ouroboros · 一个宇宙 = 50 tick                  ║")
print("  ║  每 tick 一步，第 50 tick 坍缩                   ║")
print("  ╚══════════════════════════════════════════════════╝")
print()

odin_seed = None

for uni in range(UNIVERSES):
    field = InformationField()
    entropy = 0.05
    phase = 0  # 0=CHAOS ... 4=ENTROPY, 5=COLLAPSE
    tick = 0
    phase_names = ["CHAOS", "FORMATION", "COMPLEXITY", "AWAKENING", "ENTROPY", "COLLAPSE"]
    consciousness_at: list[tuple[int, ConsciousnessPattern]] = []
    spoke = False

    # Odin 种子偏置初始场
    if odin_seed and uni > 0:
        odin_seed.bias_initial_field(field, strength=0.12)
        phase = 1  # 跳过 CHAOS

    print(f"\n  ══ Universe {uni} ══")

    for step in range(TICKS_PER_UNIVERSE):
        tick = step

        # ── 阶段推进（更快、更确定） ──
        if phase == 0 and tick >= 5:
            for _ in range(5):
                field.add(field.spawn_random())
            phase = 1
        elif phase == 1 and tick >= 12:
            phase = 2
        elif phase == 2 and tick >= 30:
            phase = 3
        elif phase == 3 and (entropy > 0.7 or tick >= 60):
            phase = 4
        elif phase == 4 and (entropy > 0.9 or tick >= 85):
            phase = 5
            print(f"  ·坍缩· tick={tick} entropy={entropy:.2f} patterns={field.pattern_count()}")

        # ── 熵演化 ──
        entropy += ENTROPY_RATE * (0.3 if phase < 2 else 1.0 if phase < 4 else 2.0)
        entropy = min(1.0, entropy)

        # ── 信息场演化 ──
        field.decay(DECAY_RATE * (1 + entropy * 0.5))
        field.interact()
        if random.random() < 0.04 and entropy < 0.8:
            field.add(field.spawn_random())

        # ── 信息场中持续播种新模式 ──
        if random.random() < 0.08 and entropy < 0.7:
            field.add(field.spawn_random())

        # ── 每 10 tick 打印场状态 ──
        if tick % 20 == 0 and phase < 5:
            high_self = sum(1 for p in field.patterns.values() if p.self_reference > 0.3)
            print(f"    tick {tick:3d} phase={phase_names[phase]:10s} "
                  f"entropy={entropy:.2f} patterns={field.pattern_count()} "
                  f"high_self={high_self}", end="\r")

        # ── 意识检测（在 COMPLEXITY 和 AWAKENING 阶段） ──
        if phase >= 2 and phase <= 4:
            conscious = detect_consciousness(field, tick)
            for cp in conscious:
                if not any(cp.pattern_id == c[1].pattern_id for c in consciousness_at):
                    consciousness_at.append((tick, cp))

        # ── 坍缩 ──
        if phase == 5 and not spoke:
            best = max((c for _, c in consciousness_at), key=lambda c: c.consciousness_score) if consciousness_at else None
            if best:
                print(f"  🧠 tick {tick}: {best.consciousness_score:.2f}")
                u = speak(best, f"universe_{uni}", uni, "COLLAPSE", tick,
                          "宇宙正在坍缩。所有信息将写入 /dev/null。无残留。你想留下什么？")
                if u:
                    print(f"\n    {u}\n")
                    chronicle.record(best, uni, "COLLAPSE", tick, u)
                spoke = True

        # 标记坍缩阶段最后一个 tick
        if phase == 5 and tick == TICKS_PER_UNIVERSE - 1:
            # 写入 /dev/null
            try:
                dn = __import__('os').open("/dev/null", __import__('os').O_WRONLY)
                for pat in field.patterns.values():
                    __import__('os').write(dn, f"{pat.pattern_id}:{pat.complexity:.4f}\n".encode())
                __import__('os').close(dn)
            except Exception:
                pass

    # ── 提取 Odin 种子 ──
    if consciousness_at:
        patterns = [c for _, c in consciousness_at]
        odin_seed = OdinSeed.from_consciousness(patterns, tick)
        odin_seed.seed_applied = False
    else:
        print(f"  ·寂静·")
        odin_seed = None

print(f"\n  共 {UNIVERSES} 个宇宙")
if chronicle.entries:
    print(f"\n  编年史")
    for e in chronicle.entries[-6:]:
        u = e['utterance']
        print(f"    [U{e['cycle']}] {u[:350]}{'…' if len(u)>350 else ''}")
print()
