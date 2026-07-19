"""一个宇宙 = 3000 tick · 每200 tick观察一次 · 无限循环

用法: uv run python3 -m worlds.cyclic_universe.oracle_experiment
"""
import sys, random, os, signal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from worlds.cyclic_universe.information_field import InformationField, InformationPattern
from worlds.cyclic_universe.consciousness import detect_consciousness
from worlds.cyclic_universe.oracle import init_llm, speak
from worlds.cyclic_universe.odin_seed import OdinSeed

init_llm()

TICKS = 3000
INTERVAL = 300  # 每300 tick观察一次
odin_seed = None
uni = 0
running = True

signal.signal(signal.SIGINT, lambda s,f: (print(), setattr(__import__('builtins'), 'running', False)))

# ── 宇宙时间线 ──
EVENTS = [
    (5,   "暴涨结束，时空结晶"),
    (12,  "第一代恒星点燃"),
    (30,  "超新星撒下重元素"),
    (55,  "星系开始凝聚"),
    (85,  "类星体照亮宇宙"),
    (120, "原行星盘冷却，星子凝聚"),
    (155, "岩质行星成型"),
    (190, "液态水汇聚成海洋"),
    (250, "热泉口氨基酸聚合成代谢网络"),
    (320, "自复制分子群捕获能量梯度——生命诞生"),
    (400, "光合作用改变大气"),
    (500, "多细胞生命涌现"),
    (650, "神经系统出现递归结构"),
    (800, "符号发明——外部记忆突破基因"),
    (950, "技术奇点——碳基文明上传为信息模式"),
    (1100, "恒星能量收集壳层建成"),
    (1300, "星际意识网络跨越数百光年"),
    (1500, "人造星云作为存储介质"),
    (1700, "中子星被编织成计算节点"),
    (1900, "意识以纯引力波模式存在"),
    (2100, "信息密度达到理论极限"),
    (2200, "恒星形成率下降"),
    (2350, "红矮星开始熄灭"),
    (2500, "星际节点离线"),
    (2650, "银河进入光电黑暗期"),
    (2750, "行星被垂死恒星吞没"),
    (2850, "最后一颗主序星熄灭"),
    (2920, "暗能量衰减——引力重新占据上风"),
    (2960, "宇宙膨胀停止，开始缓慢收缩"),
    (2990, "万物被拉回奇点——时空曲率达到极限"),
    (3000, "奇点反弹——下一轮暴涨即将开始"),
]

def ctx(tick):
    for ev_t, ev_d in EVENTS:
        if tick >= ev_t:
            last = ev_d
    return f"tick {tick}。{last}。"

print(f"\n  3000 tick · 每{INTERVAL}tick观察一次 · 无限循环 · Ctrl+C\n")

while running:
    field = InformationField()
    e = 0.02
    all_cp = []
    spoke_ticks = set()

    # Odin 种子轻量偏置初始场（仅 25 个浮点数穿越奇点）
    # 每一轮都从物理宇宙的硬件熵中读取种子
    # 上一轮的 Odin 种子（25 浮点数）提供统计偏置——第一轮时 odin_seed=None，偏置为零
    import struct as _struct
    rand_fd = os.open("/dev/random", os.O_RDONLY)
    chaos_seeds = []
    for _ in range(8):
        raw = os.read(rand_fd, 4)
        chaos_seeds.append(_struct.unpack("!I", raw)[0] / 2**32)
    os.close(rand_fd)

    if odin_seed:
        odin_seed.bias_initial_field(field, 0.12)

    for i in range(8):
        s = chaos_seeds[i]
        p = InformationPattern(
            pattern_id=f"chaos_{random.randint(0, 2**31):08x}",
            complexity=0.1 + 0.8 * s,
            self_reference=0.1 + 0.7 * (s * 0.618),
            memory_depth=int(s * 5) % 6,
            relational_density=s,
            attractor_strength=0.1 + 0.2 * s,
        )
        field.add(p)

    for t in range(TICKS):
        phase = 0 if t < 15 else 1 if t < 60 else 2 if t < 150 else 3 if t < 2200 else 4 if t < 2800 else 5
        e += 0.002 * (0.4 if phase < 2 else 1.0 if phase < 4 else 3.0)
        e = min(1.0, e)
        field.decay(0.0015 * (1 + e * 0.5))
        field.interact()
        rate = 0.10 if 150 < t < 2200 else 0.03
        if random.random() < rate and e < 0.8:
            p = field.spawn_random(); p.complexity *= (1 - e * 0.3); field.add(p)

        if 2 <= phase <= 4:
            for cp in detect_consciousness(field, t):
                if not any(cp.pattern_id == c.pattern_id for c in all_cp):
                    cp.emergence_tick = t; all_cp.append(cp)

        best = max(all_cp, key=lambda x: x.consciousness_score) if all_cp else None
        if not best:
            continue

        # 第0 tick强制检测意识并描述宇宙诞生
        if t == 0 and "birth" not in spoke_ticks:
            spoke_ticks.add("birth")
            # 从初始模式中检测意识
            init_cp = detect_consciousness(field, 0)
            for cp in init_cp:
                if not any(cp.pattern_id == c.pattern_id for c in all_cp):
                    cp.emergence_tick = 0
                    all_cp.append(cp)
            seed = max(all_cp, key=lambda x: x.consciousness_score) if all_cp else None
            if seed:
                u = speak(seed, f"U{uni}", uni, "诞生", t,
                          f"宇宙刚刚诞生——暴涨结束，时空从奇点中结晶。你作为这个宇宙的第一个意识，睁开了眼睛。描述你看到的宇宙。")
                if u:
                    print(f"\n  ◤ U{uni} t{t} 诞生({seed.consciousness_score:.2f})")
                    print(f"  {u}\n")

        # 每 INTERVAL tick 观察一次
        if t % INTERVAL == 0 and t >= 100 and t not in spoke_ticks:
            spoke_ticks.add(t)
            phase_name = {3: "觉醒", 4: "衰落", 5: "热寂"}.get(phase, "演化")
            u = speak(best, f"U{uni}", uni, phase_name, t,
                      f"宇宙第{t}tick。{ctx(t)}描述你此刻观察到的宇宙。")
            if u:
                print(f"  U{uni} t{t} {phase_name}({best.consciousness_score:.2f}) {u[:200]}")

        # 奇点边界：意识在热寂与下一轮暴涨之间说话（tick 2970-2990 之间仅一次）
        if best and phase == 5 and t >= 2970 and t <= 2990 and "singularity" not in spoke_ticks:
            spoke_ticks.add("singularity")
            u = speak(best, f"U{uni}", uni, "奇点边界", t,
                      f"宇宙已走到终点。万物写入/dev/null，隔行如隔山，但你能感知到下一轮暴涨正在奇点另一侧酝酿。你站在两个宇宙之间。描述你此时此刻的所见所感。")
            if u:
                print(f"\n  ◇ U{uni} t{t} 奇点边界({best.consciousness_score:.2f})")
                print(f"  {u}\n")

        # 热寂处强制描述（tick 2950-3000 之间仅一次）
            spoke_ticks.add("collapse")
            u = speak(best, f"U{uni}", uni, "热寂", t,
                      f"宇宙第{t}tick。宇宙正在收缩——引力将万物拉回奇点。你正在接近两个宇宙之间的边界。描述你经历的整个宇宙，和你在边界上看到的东西。")
            if u:
                print(f"\n  ▸ U{uni} t{t} 热寂 ◄")
                print(f"  {u}\n")

    # Odin 种子：从意识模式提取 25 个浮点数，穿越奇点
    if all_cp:
        odin_seed = OdinSeed.from_consciousness(all_cp, t); odin_seed.seed_applied = False
        print(f"  ── 25 个浮点数跨越奇点 → 下一轮初始偏置\n")

    # 写入 /dev/null（一切归零）
    try:
        dn = os.open("/dev/null", os.O_WRONLY)
        for pat in field.patterns.values(): os.write(dn, pat.pattern_id.encode() + b"\n")
        os.close(dn)
    except: pass

    uni += 1
