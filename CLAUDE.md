# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是什么

AIOS — 通用智能运行内核。不定义任何世界观，只提供运行机制。~13000 行。

```
aios/
  kernel/       内核层（机制，~4800 行，零外部依赖）
    tick/state/event/bus/memory/resident/spec/history/budget/language
  narrative/    叙事层（依赖 kernel，~4200 行）
    anchor/metafield/lightcone/voidspace/anip/odin/tremor
  runtime/      运行时层（串联 kernel + narrative）
    world_runtime/model_runtime/gateway/tools
  template/     应用模板层（组装运行时 + LLM）
    base.py — WorldApp 基类（4 个钩子）
    social.py — SocialWorldApp + SocialResident（多角色自主社交）
    cognitive.py — CognitiveModel Protocol
    persona.py — PersonalityEngine（价值观/情绪/决策）
  worlds/       世界层（规则）
    liora/        回声谷 — 数字生命社会
    consensus/    共识阁 — 源代码协商世界
    cyberpunk/    夜之城 — 赛博朋克城市动力学
apps/             可运行入口
  liora_app/cyberpunk_app/consensus_app/visitor_app
examples/         独立示例（不依赖 apps/）
docs/             开发者文档
  world_tutorial.md / world_tutorial_vibe.md / arch_constraints.md
narrativeDocs/    叙事文档和人格文件
tests/            409 个测试
```

**单向依赖：** `apps → runtime → worlds → narrative → kernel`。kernel 不引用 narrative。narrative 不引用 worlds。

## 命令

```bash
# 运行应用
uv run python3 apps/liora_app.py                     # 完整交互
uv run python3 apps/liora_app.py --no-model           # 模拟模式
uv run python3 apps/consensus_app.py --no-model       # 共识阁模拟
uv run python3 apps/visitor_app.py --list             # 列出世界和角色
uv run python3 apps/visitor_app.py --gateway 9100     # 旅人 + WebSocket 网关

# 运行测试
uv run python3 -m pytest tests/ -v
uv run python3 -m pytest tests/test_state.py -v       # 单个文件
uv run python3 -m pytest tests/ -k "latent"           # 关键词过滤
uv run python3 -m pytest tests/test_social.py -v      # 社交模板测试
uv run python3 -m pytest tests/test_gateway_converse.py -v  # Gateway 测试
uv run python3 -m pytest tests/test_anip_udp.py -v    # UDP 网络测试

# Kernel Server（独立 LEP 进程）
uv run python3 -m aios.runtime.kernel_server          # 启动 Kernel
uv run python3 -m aios.runtime.kernel_server --port 9100 --interval 1.0

# 外部世界示例（通过 LEP 连接，不导入 aios/）
uv run python3 examples/external_world/bamboo_grove.py
uv run python3 examples/external_world/bamboo_grove.py --name rain_city --port 9101

# MCP Server（让 Claude Code 成为世界居民）
uv run python3 -m aios.runtime.liora_mcp            # 默认端口 9100
# 在另一个终端注册: claude mcp add liora -- uv run python3 -m aios.runtime.liora_mcp

# 验证导入
uv run python3 -c "from aios.kernel import *; print('ok')"
uv run python3 -c "from aios.narrative import *; print('ok')"
```

**Python ≥3.11。** 无外部依赖（`pytest` 仅 dev）。使用 `uv`。

## 核心架构原则

### 依赖链（不可违背）

```
kernel → ✗（不引用任何其他模块）
narrative → kernel（不引用 worlds）
worlds → narrative, kernel（不引用 runtime, apps）
template → narrative, kernel, worlds/liora/mind（惰性导入）
runtime → kernel, narrative
apps → 任意
```

`docs/arch_constraints.md` 有完整 10 条不可违背约束清单（含反例）。

### 创建世界的两层模型

```python
# 1. WorldSpec — 定义世界的物理规则
spec = WorldSpec(
    name="竹隐谷",
    state_variables={"wind": StateVariable("wind", 0.3, 0, 1)},
    evolution_fn=my_evolution,       # (dict, tick) → dict[str, delta]
    event_generator=my_events,       # (state, tick) → list[dict]
)

# 2. WorldApp — 定义居民如何感知和行动
class MyWorld(WorldApp):
    spec = create_my_spec()
    character_config = { "角色名": {"persona": "...", "beliefs": {}, "secrets": []} }
    mock_replies = { "角色名": ["回复1", "回复2"] }

    def describe_world(self, state, mind=None) -> str: ...
    def extra_context(self, mind) -> str: ...
    def resolve_effects(self, action_type, target) -> dict[str, float]: ...
    def on_start(self): ...
```

世界创建教程：`docs/world_tutorial.md`（人类版）和 `docs/world_tutorial_vibe.md`（AI 版）。

### CognitiveModel Protocol

`SocialWorldApp` 不直接依赖 `LioraMind`，而是依赖 `aios/template/cognitive.py` 的 `CognitiveModel` Protocol。

```python
from aios.template.cognitive import CognitiveModel

# 任何实现了以下方法的类都可作为认知模型
class MyModel:
    name: str
    def relate(self, other, trust, curiosity, tick): ...
    def relationship_summary(self) -> str: ...
    def add_episode(self, desc, tick, participants, importance): ...
    def recall_episodes_by_participant(self, name, n) -> list: ...
    def tick_autonomous(self, n): ...
    def tick_decay(self, n): ...
    def assimilate(self, state_vars, tick): ...
    # ...（完整定义见 cognitive.py）

# 传递给 SocialResident
res = SocialResident("名", app, mind=MyModel())
```

### WorldRuntime — tick 主循环

```
每 tick: state.tick() → events.tick() → bus.broadcast()
  + 可选: 裂隙/幽灵/注意力预算/奥丁 sweep/EchoTremor
```

应用层额外执行：`unknown.tick()`、`resistance.tick()`、`mind.assimilate()`、`mind.tick_decay()`。

### 全局单例模式

每个 kernel + narrative 模块提供 `get_*()` 函数返回线程安全的全局单例：

```python
from aios.kernel.tick import get_world_tick
from aios.narrative.anchor import get_anchor_protocol
from aios.narrative.anip import get_anip         # get_anip(mode="udp")
from aios.narrative.odin import get_odin
from aios.kernel.budget import get_attention_budget
```

### 测试模式

- 模拟模式（`--no-model`）是测试和开发的默认模式
- 测试不依赖外部网络，UDP 测试用 `127.0.0.1` + `port=0`（自动分配）
- `conftest.py` 提供共享 fixture：`runtime`、`liora_mind`、`fresh_anchor`、`two_udp_networks`、`lep_gateway`

### LLM 边界

状态（关系、信念、记忆、情绪）由 Python 维护。LLM 只负责语言表达。
`assimilate_conversation()` 用关键词匹配而非 LLM 分析来更新系统状态。

## 世界特有机制

| 机制 | 文件 | 触发条件 | 说明 |
|------|------|---------|------|
| 裂隙 | `worlds/*/unknown.py` | 叙事饱和（沉默+重复） | 空位（∅），居民自填补 |
| 数字幽灵 | `worlds/cyberpunk/ghost.py` | 城市压力阈值 | 携带记忆的意识吸引子 |
| 锚点 | `narrative/anchor.py` | 世界逻辑激活（如降雨>27轮） | 显式跨循环记忆存储 |
| 奥丁 | `narrative/odin.py` | 周期 sweep / 手动触发 | 归档/判决/召回 |
| 回声震颤 | `narrative/tremor.py` | 未定义空间信号 | 时间回填，不被死亡协议追踪 |

## 关键文档

| 文档 | 位置 |
|------|------|
| 创建世界（人类版） | `docs/world_tutorial.md` |
| 创建世界（AI 版） | `docs/world_tutorial_vibe.md` |
| 架构约束清单 | `docs/arch_constraints.md` |
| ANIP UDP 传输层设计 | `narrativeDocs/anip_transport_design.md` |
| LEP 协议规范 | `docs/LEP_SPEC.md` |
| Kernel Server | `aios/runtime/kernel_server.py` |
| 外部世界示例 | `examples/external_world/bamboo_grove.py` |
| 开钰人格 | `narrativeDocs/kaiyu_persona.md` |
