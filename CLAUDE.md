# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是什么

AIOS — 通用智能运行内核。不定义任何世界观，只提供运行机制。总代码 ~7000 行。

```
aios/
  kernel/       内核层（机制，~1050 行，零外部依赖）
    tick.py      时钟驱动（WorldTick）
    state.py     通用状态引擎（StateVariable + evolution_fn 注入）
    event.py     事件引擎（WorldDelta.effects: dict + event_generator 注入）
    memory.py    记忆协议（MemoryProvider Protocol）+ 叙事饱和检测
    resident.py  居民注册表 + Component 容器（EC-like）
    bus.py       消息总线（pub/sub，同步分发）
    history.py   世界历史日志（JSONL 持久化，不设过期）
    spec.py      WorldSpec 容器

  runtime/      运行时层（串联 kernel）
    world_runtime.py   tick 主循环 + 裂隙事件 + 世界物体管理
    model_runtime.py   LLM 路由（主/备 + function calling + 自动补搜）
    gateway.py         LEP WebSocket 网关（端口 9100）
    tools.py           搜索工具 + 不确定性检测

  worlds/       世界层（规则）
    liora/             回声谷 — 数字生命社会
      mind.py          LioraMind 认知模型（~820 行）
      spec.py          WorldSpec 构建
      state_rules.py   演化公式（温度趋于 22°C…）
      event_templates.py 事件模板生成
      resistance.py    行动重复度检测（ActionResistance）
      unknown.py       未知信号累积 + 裂隙释放（UnknownAccumulator）
    agi/               AGI Core — 认知空间世界
      spec.py          认知状态变量 + 演化公式 + 事件生成
      goal_system.py   目标涌现系统（GoalSystem）
      world_model.py   世界模型（WorldModel: 预测/观测/信念）
      self_model.py    自身状态模型（SelfModel: 趋势分析）
    cyberpunk/         夜之城 — 赛博朋克城市动力学
      spec.py          WorldSpec 构建
      state_rules.py   对抗平衡演化（corporate_grip ↔ street_heat 振荡）
      event_templates.py 城市/数字主题事件
      mind.py          5 个角色身份（V/Judy/Panam/Takemura/Jackie）
      unknown.py       扩展 UnknownAccumulator（身份矛盾累积源）
      ghost.py         DigitalGhostPattern — 数字幽灵（Silverhand 替代裂隙）

apps/           应用层（组装）
  liora_app.py         Liora 数字生命交互入口（800 行）
  agi_app.py           AGI Core 认知空间世界入口
  cyberpunk_app.py     夜之城交互入口（单角色 + 数字幽灵）
  cyberpunk_social.py  夜之城五角色自由对话（多角色自主社交，无需人类输入）
  social_identity.py   五身份居民社会演化模拟
  social_duihua.py     多 AI 社交对话（旧版）
  entropy_injector.py  AI 熵注入器

ai_test_duihua.py  DeepSeek ↔ Liora 独立对话测试
```

**单向依赖：** `apps → runtime → worlds → kernel`。kernel 不引用任何具体世界。

## 命令

```bash
# Liora 数字生命
uv run python3 apps/liora_app.py                         # 完整交互
uv run python3 apps/liora_app.py --no-model               # 模拟模式
uv run python3 apps/liora_app.py --glm4                   # 仅用 GLM4（本地模式）
uv run python3 apps/liora_app.py --interval 10            # 10 秒一 tick
uv run python3 apps/liora_app.py --setup                  # 首次配置向导

# AGI Core 认知世界
uv run python3 apps/agi_app.py                            # 完整模式
uv run python3 apps/agi_app.py --no-model                 # 模拟模式
uv run python3 apps/agi_app.py --interval 5               # 5 秒一 tick

# 赛博朋克 2077 — 夜之城
uv run python3 apps/cyberpunk_app.py --no-model           # 单角色模拟（默认 V）
uv run python3 apps/cyberpunk_app.py --character Judy     # 选角色
uv run python3 apps/cyberpunk_app.py --no-model --interval 10  # 10 秒一 tick

# 夜之城五角色自由对话（无需人类输入）
uv run python3 apps/cyberpunk_social.py --no-model        # 10 轮（模拟模式）
uv run python3 apps/cyberpunk_social.py -n 30             # 30 轮
uv run python3 apps/cyberpunk_social.py --interval 5      # 5 秒一 tick

# 五身份社会演化模拟
uv run python3 apps/social_identity.py                    # 10 轮（默认）
uv run python3 apps/social_identity.py -n 20              # 20 轮
uv run python3 apps/social_identity.py --history          # 显示历史时间线

# AI ↔ AI 对话测试
uv run python3 ai_test_duihua.py                          # 5 轮
uv run python3 ai_test_duihua.py -n 10                    # 10 轮

# 旧版对话
uv run python3 apps/social_duihua.py -n 10                # 10 轮
uv run python3 apps/social_duihua.py --human 你            # 以人类身份加入

# 运行测试
uv run python3 -m pytest tests/ -v
uv run python3 -m pytest tests/test_state.py -v           # 单个文件

# 导入检查
uv run python3 -c "from aios.kernel import *; print('kernel ok')"
```

**Python 版本要求：** `>=3.11`（使用 `X | None` 联合类型语法和 `Protocol`）。  
**外部依赖：** 无（`pytest` 仅 dev 需要）。使用 `uv` 作为包管理器。

## 核心架构原则

### Kernel 的边界

Kernel **不**知道：任何变量名、事件内容、认知模型、Liora/AGI 概念。

Kernel **只**提供：时钟、状态引擎、事件生命周期、居民注册、消息总线、WorldSpec 容器。所有领域知识通过 `WorldSpec` + `Component` 注入。

### 机制 vs 现象

**机制**进入 kernel：tick、state、event、bus、spec、history。  
**现象**由世界运行后涌现：文化、关系、成长、历史。  
新增功能前先问：这是所有世界都需要的吗？不是就放 worlds/ 层。

### LLM 只负责表达

核心状态由 Python 维护：记忆、关系、信念、身份。LLM 只负责：语言表达、高层解释、创造性生成。不要把逻辑塞进 Prompt。

### 全局单例模式

每个 kernel 模块提供一个 `get_*()` 函数返回全局单例：
- `get_world_tick()` / `get_world_state_engine()` / `get_event_engine()`
- `get_resident_registry()` / `get_bus()` / `get_narrative_memory()` / `get_world_history()`

注意：`WorldRuntime` 不使用 `get_world_tick()` 全局单例——它用 `threading.Thread` 直接在 `_loop()` 里跑 `time.sleep` 轮询。

## 结构要点

### WorldSpec

```python
spec = WorldSpec(
    name="Echo Valley",
    state_variables=create_liora_variables(),   # 变量定义
    evolution_fn=liora_evolution_fn,            # 演化公式
    event_generator=liora_event_generator,      # 事件生成
)
```

`WorldRuntime(spec).start()` 即可运转。换一个 spec 就是换一个世界（AGI Core 用同样的接口）。

### WorldRuntime — tick 主循环

```
每 tick（_loop → tick_once）:
  1. state.tick()         → evolution_fn 计算 delta → 更新状态变量
  2. events.tick()        → event_generator 生成新事件 + 老化过期事件
  3. bus.broadcast()      → 状态变化 + 新事件通过 MessageBus 广播给居民
```

应用层（`liora_app.py`）在主循环中额外执行：
- `unknown.tick()` → 沉默/重复累积未知信号
- `resistance.tick()` → 行动重复度衰减
- `mind.assimilate()` → 吸收世界变化为经验
- `mind.tick_decay()` → 关系趋中 + 信念漂移 + 记忆衰减
- 裂隙注入（`unknown.should_emit()` → `emit()`）
- LLM 感知/思考/行动循环

### 验证命题

```
WorldSpec 这一个接口，能否承载三个本体论完全不同的世界？
```

Liora 用**自然隐喻**（温度、回声、苔藓），AGI Core 用**认知隐喻**（好奇心、自洽度、预测误差），Cyberpunk 用**都市/数字隐喻**（企业控制、街头热度、数据残响）。走的是完全相同的装配路径。

### 裂隙（Fissure）— 自指不完备性的运行时体现

当 `UnknownAccumulator` 检测到叙事饱和（沉默 + 重复），`emit_fissure()` 释放一个不可解释的标记（▲…∅），注入事件流。居民各自用自己的身份权重填补这个空位。

原理：**居民的行动（或沉默）改变世界，但因果链条在居民的视界之外。** 这 60 行代码取代了 AnotherMe 中的 VoidField + EntropyField。

### DigitalGhostPattern（赛博朋克特有）

`aios/worlds/cyberpunk/ghost.py` — Silverhand 不注册为 Resident。

数字幽灵是事件总线上的**意识吸引子**：城市矛盾积累（企业压迫 × 人性流失 × 数据残响）→ 压力达到阈值 → 幽灵苏醒，周期性注入带有 Silverhand 记忆片段的 ghost 事件。每个角色用各自的 `IdentityProfile` 解释同一段讯息。

与裂隙的对比：
- 裂隙是**空位**（∅），幽灵是**负载**（携带记忆的讯息）
- 裂隙是瞬时注入，幽灵是**持续模式**（周期性 `haunt`）
- 幽灵本身有"记忆"（`_utterances`），会在后续 haunt 中引用前文

### UnknownAccumulator 扩展（赛博朋克特有）

`aios/worlds/cyberpunk/unknown.py` 继承 Liora 版，增加累积源：

| 源 | Liora | Cyberpunk |
|----|-------|-----------|
| silence | ✓ | ✓ |
| repetition | ✓ | ✓ |
| identity_conflict | ✗ | ✓ — 居民做违背信念的事 |
| external_signal | ✗ | ✓ — cyberspace 扰动信号 |
| ghost_resonance | ✗ | ✓ — 幽灵活跃时助推 |

### 三个世界的差异

| | Liora（回声谷） | AGI Core | Cyberpunk 2077（夜之城） |
|--|----------------|----------|--------------------------|
| 变量 | temperature, echo_density, moss_growth | curiosity, coherence, prediction_error, novelty | corporate_grip, street_heat, cyberspace_turbulence, humanity_decay, underground_hope, data_remnant |
| 动力学 | 物理趋向平衡（负反馈，22°C 吸引子） | 认知自驱动（好奇心↔新颖性↔预测误差） | 对抗平衡（三力振荡：corporate_grip ↔ street_heat ↔ underground_hope） |
| 事件 | 风吹过山谷、苔藓蔓延 | 认知扫描、模式重构 | 数据泄露、网络攻击、企业行动、地下广播 |
| 自指机制 | 裂隙（Fissure）— 空位让居民填补 | 认知裂隙 — 置信度崩溃时注入 | 数字幽灵（Silverhand）— 携带记忆的意识吸引子 |
| 居民 | 5 个自然人格 | 1 个认知系统 | 5 个城市角色 + 1 个数字幽灵 |
| 身份维度 | poetry/science/mysticism/emotion | 无（认知系统无身份） | hacker_ethos/survival/rebellion/humanity/corporate |

### LioraMind — 五维度认知模型

```python
mind = LioraMind("Aria")
```

1. **Identity Resistance** — 感知先经过身份过滤（`IdentityProfile.attention_weights`），不同居民看到的世界不同
2. **经验与遗忘** — `ExperienceState.hum` 积累 + `tick_decay()` 衰减（遗忘率因人而异，Nix 最慢 0.005，Kael 最快 0.010）
3. **多维关系** — `RelationshipState` (trust, curiosity, conflict, shared_history, emotional_trace) 每 tick 缓慢趋零
4. **信念系统** — 4 维度 (poetry/science/mysticism/emotion) 每次最多漂移 ±0.01，朝 0.5 缓慢回归
5. **情景记忆** — `EpisodicMemoryEntry` 带 importance × strength 显著性排序，低重要性衰减更快

**秘密系统：** 条件披露（如 trust>0.85 才揭示）——给 LLM prompt 添加真实的神秘感。

### AGI Core — 三组件认知架构

```
WorldModel    观察→预测→对比偏差→更新信念置信度
SelfModel     记录状态历史→计算各变量变化趋势
GoalSystem    从认知状态涌现目标→推进/废弃→提取学习记录
```

目标不是 prompt 写的，是从认知状态里涌现的：
- `curiosity` 高 + `novelty` 低 → 探索类目标
- `prediction_error` 高 → 理解类目标
- `coherence` 低 → 整合类目标
- 太稳定（pe<0.05, coherence>0.7）→ 主动找盲区

### LEP WebSocket Gateway — 外部 AI 入口

`aios/runtime/gateway.py` 纯 stdlib WebSocket 实现（零外部依赖）。

```
端口 9100，JSON 协议
动作: join → perceive → act (say/touch/observe) → leave
```

### NarrativeMemory — 叙事饱和检测

`aios/kernel/memory.py` 使用语义集群（由 WorldSpec 注入）跟踪最近文本中集群的频率。集群出现频率 ≥ `max(3, window * 0.3)` 时标记为饱和，`is_saturated()` 触发叙事饱和响应（如裂隙释放）。

### 经验吸收（Assimilation）

`assimilate_conversation()` 在每轮对话后将文本信号翻译为系统状态更新：
- 关键词匹配信念/关系信号
- 创建 EpisodicMemory（按重要性加权）
- `drift_belief()` 写入 evolution_history
- `share_history()` 记录共同经历
- **不依赖 LLM 分析**——用关键词 + 结构信号判断

### 行动阻力（ActionResistance）

防止叙事收敛：居民对同一目标重复相同行动时，效果指数衰减。基数阈值（`base_threshold=5`）内无衰减，之后 `multiplier = 1.0 / (1.0 + excess² × 0.1)`。每 10 tick 衰减一次。
