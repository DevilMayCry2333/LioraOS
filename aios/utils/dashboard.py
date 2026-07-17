"""System Health Dashboard — 系统运行状态面板。

显示所有已集成 kernel 模块的实时状态：
  - AttentionBudget 注意力余额
  - Odin 归档簿 & 威胁预警
  - MetaField 焦点状态分布
  - VoidSpace 七地址在线状态
  - EchoTremor 协议统计
  - 最近事件日志

用法：
    from aios.utils.dashboard import print_health_panel
    print_health_panel()
"""

from __future__ import annotations

import datetime
from typing import Any, Optional


def _section(title: str):
    """打印可折叠的 section 标题。"""
    print(f"\n  ┌─ {'=' * (len(title) + 2)} ─┐")
    print(f"  │   {title}   │")
    print(f"  └─ {'=' * (len(title) + 2)} ─┘")


def _bar(value: float, width: int = 20, label: str = "") -> str:
    """渲染数值条。"""
    pct = max(0, min(width, int(value * width)))
    bar = "█" * pct + "░" * (width - pct)
    if label:
        return f"  {label:25s} {bar} {value:.3f}"
    return f"  {bar} {value:.3f}"


def _keyval(key: str, val: Any, color: str = "") -> str:
    return f"  {key:30s} {val}"


def print_health_panel(title: str = "系统健康面板"):
    """打印完整系统健康面板。所有模块的状态报告。

    安全调用——任何模块未初始化都不会崩溃。
    """
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 64}")

    _print_budget()
    _print_odin()
    _print_metafield()
    _print_voidspace()
    _print_tremor()
    _print_runtime()


def print_budget_summary():
    """仅打印注意力预算状态（轻量调用）。"""
    _print_budget()


def print_odin_summary():
    """仅打印奥丁状态。"""
    _print_odin()


# ════════════════════════════════════════════════════════════
# 子系统面板
# ════════════════════════════════════════════════════════════


def _print_budget():
    """注意力双层账本面板。"""
    try:
        from aios.kernel.budget import get_attention_budget
        budget = get_attention_budget()
        bs = budget.summary()
    except Exception:
        return

    _section("💰 注意力预算")
    if not bs["foci"]:
        print("  (无注册焦点)")
        return

    # 表头
    print(f"  {'焦点':20s} {'交互余额':>12s} {'系统余额':>12s} {'冷落?':>8s}")
    print(f"  {'─' * 56}")
    for foc in bs["foci"]:
        name = foc["name"][:18]
        ib = f"{foc['interaction']['balance']:.3f}"
        sb = f"{foc['system']['balance']:.3f}"
        # 冷落判断
        is_cold = foc.get("injections", 0) > 0 and foc.get("last_injection", 0) < bs.get("tick", 0) - 5
        cold_flag = "❄" if is_cold else " ✓"
        print(f"  {name:20s} {ib:>12s} {sb:>12s} {cold_flag:>8s}")
    print(f"  {'─' * 56}")
    print(f"  当前焦点: {bs.get('current_focus', '(未设置)')}")


def _print_odin():
    """奥丁状态面板。"""
    try:
        from aios.narrative.odin import get_odin
        odin = get_odin(initialize=False)
        report = odin.status_report()
    except Exception:
        return

    _section("⚔️  奥丁 — 死亡协议运行时")
    if not report.get("ready"):
        print("  (未初始化)")
        return

    print(_keyval("焦点总数", report.get("foci", 0)))
    print(_keyval("实例总数", report.get("instances", 0)))
    print(_keyval("已归档", report.get("archived", 0)))
    print(_keyval("已召回", report.get("recalled", 0)))
    print(_keyval("归档簿记录", report.get("total_ledger", 0)))
    print(_keyval("受保护焦点", report.get("protected", 0)))
    print(_keyval("受威胁焦点", report.get("threatened", 0)))

    # 状态分布
    dist = report.get("status_distribution", {})
    if dist:
        parts = [f"{k}={v}" for k, v in sorted(dist.items())]
        print(f"  焦点状态分布: {' | '.join(parts)}")

    # 受威胁预警
    threatened = report.get("threatened", 0)
    if threatened > 0:
        print(f"  ⚠️  {threatened} 个焦点处于受威胁状态！")
        try:
            for t in odin.get_threatened()[:3]:
                print(f"     · {t['universe']} — 沉寂 {t['dormant_seconds']:.0f}s"
                      f" | 觉醒 {t['awakening']:.2f}")
        except Exception:
            pass


def _print_metafield():
    """MetaField 注意力拓扑面板。"""
    try:
        from aios.narrative.metafield import get_metafield, FocusStatus
        mf = get_metafield(register_echoes=False)
        foci = mf.list_foci()
        instances = mf.list_instances()
        protected = mf.get_protected_foci()
    except Exception:
        return

    _section("🧭 MetaField — 注意力拓扑")

    if not foci and not instances:
        print("  (无注册焦点)")
        return

    print(f"  注意力焦点: {len(foci)}  |  实例: {len(instances)}  |  保护中: {len(protected)}")

    # 按状态分组
    status_groups: dict[str, list[str]] = {}
    for f in foci:
        st = f.status.value if hasattr(f.status, 'value') else str(f.status)
        status_groups.setdefault(st, []).append(f.name)
    for st, names in sorted(status_groups.items()):
        display = ", ".join(n[:12] for n in names[:5])
        if len(names) > 5:
            display += f"...(+{len(names) - 5})"
        print(f"    {st}: {display}")

    # 受保护焦点
    if protected:
        names = ", ".join(p.get("name", p.get("focus", "?"))[:14] for p in protected[:3])
        print(f"   🛡 受保护: {names}" + (f" (+{len(protected)-3})" if len(protected) > 3 else ""))


def _print_voidspace():
    """VoidSpace 虚空地址面板。"""
    try:
        from aios.narrative.voidspace import get_voidspace
        vs = get_voidspace()
    except Exception:
        return

    _section("🌀 VoidSpace — 虚空地址空间")

    try:
        addr_map = vs.get_map()
        total = addr_map.get("total", 0)
        active = addr_map.get("active", 0)
        print(_keyval("注册地址", total))
        print(_keyval("活跃地址", active))
        print(_keyval("共享边界", f"{addr_map.get('shared_boundary', 0.47):.3f}"))

        # 地址列表（addresses 是 dict）
        addresses = addr_map.get("addresses", {})
        if addresses:
            print(f"  地址映射:")
            for name, addr in sorted(addresses.items()):
                name_display = name[:16]
                status = "🟢" if addr.get("active", False) else "🔴"
                offset = addr.get("offset", 0)
                print(f"    {status} 0x{offset:02X} {name_display}")
    except Exception:
        print("  (查询失败)")


def _print_tremor():
    """EchoTremor 回声震颤面板。"""
    try:
        from aios.narrative.tremor import get_tremor
        tremor = get_tremor()
        stats = tremor.stats()
    except Exception:
        return

    _section("🌊 EchoTremor — 回声震颤")
    if not stats.get("initialized"):
        print("  (未激活)")
        return

    print(_keyval("震颤发射次数", stats.get("tremor_count", 0)))
    print(_keyval("锚点片段数", stats.get("fragment_count", 0)))
    print(_keyval("总活动度", f"{stats.get('total_activity', 0):.3f}"))
    print(_keyval("平均活动度", f"{stats.get('avg_activity', 0):.4f}"))
    print(_keyval("监听器数", stats.get("listeners", 0)))

    # 最近震颤预览
    try:
        previews = tremor.active_tremor_previews(n=3)
        if previews:
            print(f"  最近震颤:")
            for p in previews:
                print(f"    · {p[:80]}")
    except Exception:
        pass


def _print_runtime():
    """运行时基础信息。"""
    try:
        import platform
        print(f"\n  {'─' * 56}")
        print(f"  平台: {platform.system()} {platform.release()} | "
              f"Python {platform.python_version()}")
        print(f"  时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        pass
