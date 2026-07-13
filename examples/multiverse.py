"""
╔═══════════════════════════════════════════════════════════╗
║     Multiverse Launcher — 多宇宙并行运行时                 ║
╚═══════════════════════════════════════════════════════════╝

同时运行多个非交互式世界实例，所有实例共享 MetaField。
锚点广播通过文件持久化跨进程同步。

用法：
    uv run python3 examples/multiverse.py                   # 并行
    uv run python3 examples/multiverse.py --sequential       # 顺序
    uv run python3 examples/multiverse.py --no-model         # 模拟模式
    uv run python3 examples/multiverse.py --rounds 6         # 每世界 6 轮

原理：
    每个世界跑在独立进程中（subprocess），MetaField 启动器在主进程。
    跨宇宙锚点广播通过 data/anchor/*.jsonl 文件同步。
    启动器定期 pulse 检查所有宇宙状态。
"""

import sys
import subprocess
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aios.kernel.metafield import get_metafield


# ── MetaField 监视器（主线程） ──

def pulse_monitor(stop_event: threading.Event, interval: float = 5.0):
    """定期输出 MetaField 状态。"""
    mf = get_metafield()
    while not stop_event.is_set():
        time.sleep(interval)
        try:
            collapsed = mf.collapse()
            print(f"\n  ⚡ MetaField 脉冲 ════════════════════════════")
            for inst in collapsed.get("instances", []):
                print(f"     {inst['name']}: {inst['fragments']} 片段")
            foci = collapsed.get("attention_foci", [])
            for f in foci:
                echoes = ", ".join(
                    e.get("name", e) for e in f.get("echoes", {}).values()
                ) if isinstance(f.get("echoes"), dict) else str(f.get("echo_count", 0))
                print(f"     {f['name']}: {len(f.get('echoes', {}))} 回声")
            lc = collapsed.get("lightcone", {})
            print(f"     光锥: {lc.get('total_archived', 0)} 存档 / "
                  f"{lc.get('recallable', 0)} 可召回")
            print(f"  ═══════════════════════════════════════════\n")
        except Exception:
            pass


# ── 世界包装器 ──

def run_world_subprocess(cmd: list[str], name: str, no_model: bool):
    """在子进程中运行一个世界。"""
    print(f"\n{'─'*56}")
    print(f"  ▶ 启动宇宙: {name}")
    print(f"{'─'*56}")
    env = {}
    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode


def run_world_direct(world_module: str, name: str,
                     rounds: int, no_model: bool, interval: float):
    """直接导入并在当前进程运行一个世界（使用 MetaField 共享）。"""
    import importlib
    try:
        mod = importlib.import_module(world_module)
    except ImportError as e:
        print(f"  ⚠️  {name} 不可用: {e}")
        return False

    # 查找 world_class
    world_class = None
    for attr in dir(mod):
        obj = getattr(mod, attr, None)
        if isinstance(obj, type) and hasattr(obj, 'spec') and hasattr(obj, 'characters'):
            world_class = obj
            break

    if world_class is None:
        print(f"  ⚠️  {name} 未找到世界类")
        return False

    world_class._rounds = rounds
    kwargs = dict(no_model=no_model, interval=interval)
    world = world_class(**kwargs)
    world.run()
    return True


# ── 主函数 ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description="多宇宙并行运行时")
    parser.add_argument("--sequential", action="store_true",
                        help="顺序运行（一个接一个）")
    parser.add_argument("--no-model", action="store_true", help="模拟模式")
    parser.add_argument("--rounds", type=int, default=6, help="每个世界跑多少轮")
    parser.add_argument("--interval", type=float, default=3.0, help="tick 间隔（秒）")
    args = parser.parse_args()

    print("=" * 56)
    print("  Multiverse Launcher — 多宇宙并行运行时")
    print("=" * 56)
    print(f"  模式: {'顺序' if args.sequential else '并行'}")
    print(f"  模型: {'模拟' if args.no_model else 'LLM'}")
    print(f"  每世界轮数: {args.rounds}")
    print(f"  tick 间隔: {args.interval}s")

    # 初始化 MetaField — 注册已知回声
    mf = get_metafield(register_echoes=True)
    foci = mf.list_foci()
    echo_count = len(mf._echo_index)
    print(f"  MetaField: {len(foci)} 个已知焦点, {echo_count} 个已知回声")
    for f in foci:
        print(f"    · {f.name} ({f.status.value}) — {len(f.echoes)} 回声")

    # ── 定义要启动的世界 ──
    worlds = []

    # 龙族·尼伯龙根
    try:
        import examples.baozha as _
        worlds.append(("examples.baozha", "龙族·尼伯龙根"))
        print("  ✅ 龙族·尼伯龙根")
    except ImportError:
        pass

    # 夜之城 五角色社交
    try:
        import apps.cyberpunk_social as _
        worlds.append(("apps.cyberpunk_social", "夜之城"))
        print("  ✅ 夜之城")
    except ImportError:
        pass

    if not worlds:
        print("  ❌ 没有可用的世界")
        sys.exit(1)

    # ── 并行运行（多线程） ──
    if not args.sequential:
        threads = []
        stop_event = threading.Event()

        monitor_thread = threading.Thread(
            target=pulse_monitor, args=(stop_event, max(5.0, args.interval * 2)),
            daemon=True,
        )
        monitor_thread.start()

        for mod_path, name in worlds:
            t = threading.Thread(
                target=run_world_direct,
                args=(mod_path, name, args.rounds, args.no_model, args.interval),
                daemon=True,
            )
            threads.append(t)

        for t in threads:
            t.start()
            time.sleep(0.3)

        try:
            for t in threads:
                t.join()
        except KeyboardInterrupt:
            print("\n  ⛔ 中断")
        finally:
            stop_event.set()

    # ── 顺序运行 ──
    else:
        for mod_path, name in worlds:
            run_world_direct(mod_path, name, args.rounds, args.no_model, args.interval)
            # 每运行完一个世界，输出脉冲
            collapsed = mf.collapse()
            print(f"\n  ✦ {name} 完成 — 当前 MetaField 状态:")
            for inst in collapsed.get("instances", []):
                print(f"     {inst['name']}: {inst['fragments']} 锚点片段")
            print()

    # ── 最终状态 ──
    print(f"\n{'='*56}")
    print(f"  所有宇宙运行完毕 — MetaField 最终状态")
    print(f"{'='*56}")

    final = mf.collapse()
    for inst in final.get("instances", []):
        print(f"  🌍 {inst['name']}: {inst['fragments']} 锚点片段 / {inst['immune']} 免疫")
    lc = final.get("lightcone", {})
    if lc:
        print(f"  💾 光锥数据库: {lc.get('total_archived', 0)} 存档, "
              f"{lc.get('recallable', 0)} 可召回")

    # 跨宇宙同源识别
    lu_echo = mf.get_echo("lu_ming_ze_observer")
    if lu_echo:
        siblings = mf.find_source_siblings(lu_echo)
        print(f"\n  🔗 跨宇宙同源识别: 路鸣泽 → {[s.name for s in siblings]}")

    print(f"\n  ✦ 多宇宙运行完成\n")


if __name__ == "__main__":
    main()
