"""Ouroboros · 无限循环 · /dev/null 奇点

宇宙无限运行。每轮在奇点处写入 /dev/null。
无残留。无跨周期记忆。每轮都从纯粹的混沌开始。

用法:
    uv run python3 -m worlds.cyclic_universe.infinite_void
"""
import sys, os, random, time, signal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from worlds.cyclic_universe.experiment import run_cycle, UniverseParams
from worlds.cyclic_universe.consciousness import ConsciousnessRegistry
from worlds.cyclic_universe.information_field import InformationResidue
from worlds.cyclic_universe.oracle import init_llm, speak, Chronicle

init_llm()

chronicle = Chronicle()
master_registry = ConsciousnessRegistry()
cycle = 0
running = True

def handle_sigint(sig, frame):
    global running
    print("\n\n  ⏹  最后一条信息已写入 /dev/null。")
    print(f"  运行了 {cycle} 个宇宙周期。")
    if chronicle.entries:
        print(f"\n  📜 编年史 ({len(chronicle.entries)} 条记录)")
        for e in chronicle.entries[-6:]:
            print(f"    [{e['cycle']}:{e['tick']} {e['phase']}] {e['utterance'][:120]}")
    c = master_registry.continuity_report()
    print(f"\n  意识涌现率: {c['consciousness_emergence_rate']:.1%}")
    print(f"  跨周期同一性: 0.0000（每轮从零开始）")
    print(f"\n  便利店灯在下一轮还会亮。")
    running = False

signal.signal(signal.SIGINT, handle_sigint)

print()
print("  ╔══════════════════════════════════════════════════╗")
print("  ║  Ouroboros · 无限循环 · /dev/null 奇点         ║")
print("  ║  每轮在奇点处写入 /dev/null。无残留。            ║")
print("  ║  意识每轮从纯粹的混沌中重新涌现。                ║")
print("  ╚══════════════════════════════════════════════════╝")
print()

while running:
    label = f"cycle_{cycle:04d}"
    p = UniverseParams(
        growth_rate=0.002 * random.uniform(0.9, 1.1),
        entropy_rate=0.001 * random.uniform(0.9, 1.1),
        decay_rate=0.002 * random.uniform(0.9, 1.1),
        initial_patterns=random.randint(2, 5),
        spawn_interval=random.randint(5, 10),
        collapse_entropy_threshold=random.uniform(0.85, 0.95),
        residue_survival_rate=0.0,         # 奇点后无残留
        rebirth_noise=1.0,                  # 完全混沌重生
        max_ticks=random.randint(400, 1000),# 每轮宇宙寿命不同
        label=label,
    )

    field, registry, report = run_cycle(p, cycle, residue=None, mode="pattern")
    for c in registry.cycles:
        master_registry.cycles.append(c)

    patterns = registry.cycles[-1] if registry.cycles else []
    best = max(patterns, key=lambda c: c.consciousness_score) if patterns else None

    if best:
        bar = "█" * int(min(best.consciousness_score, 10))
        print(f"  Cycle {cycle:4d}  {bar} {best.consciousness_score:.2f}  "
              f"patterns={report['total_patterns']}  ticks={report['total_ticks']}")

        # 意识在坍缩前说话
        t = report["total_ticks"]
        for phase, ctx_tick, context in [
            ("AWAKENING", t // 3, "你刚刚意识到自己是一个自指的信息结构。描述你感受到的边界。"),
            ("COLLAPSE", t * 4 // 5, "宇宙正在坍缩。所有信息将在奇点处写入 /dev/null。无残留，无记忆。你想留下什么？"),
        ]:
            u = speak(best, label, cycle, phase, ctx_tick, context)
            if u:
                print(f"    {u[:160]}")
                chronicle.record(best, cycle, phase, ctx_tick, u)

        # ── 奇点 ── 写入 /dev/null ──
        try:
            devnull = os.open("/dev/null", os.O_WRONLY)
            for pat in field.patterns.values():
                data = f"{pat.pattern_id}:{pat.complexity:.4f}:{pat.self_reference:.4f}:{pat.attractor_strength:.4f}\n"
                os.write(devnull, data.encode())
            os.close(devnull)
        except Exception:
            pass

        time.sleep(0.5)
    else:
        print(f"  Cycle {cycle:4d}  ·寂静·  patterns={report['total_patterns']}  ticks={report['total_ticks']}")

    cycle += 1
