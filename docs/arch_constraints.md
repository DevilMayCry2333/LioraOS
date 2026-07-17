# 架构不可违背约束

> 版本: 0.4 · 目标读者: AI 开发者
>
> 这个文件记录了 LioraOS 框架的**不可违背约束**。
> AI 在生成代码、修改现有文件、添加新功能时，**必须遵守**以下规则。
> 违反其中任何一条，轻则运行时崩溃，重则破坏整个框架的因果一致性。

---

## 0. 依赖链（最重要的规则）

```
apps → runtime → worlds → narrative → kernel
kernel → ✗（kernel 不引用任何其他模块）
```

**绝对禁止：**

- ❌ `kernel/` 中的任何文件 `import` `worlds/`、`narrative/`、`runtime/`、`apps/`
- ❌ `narrative/` 中的任何文件 `import` `worlds/` 或 `apps/`
- ❌ `worlds/` 中的任何文件 `import` `runtime/` 或 `apps/`

**允许的例外：**

- ✅ `runtime/world_runtime.py` 从 `narrative/` import（`metafield`、`odin`、`tremor`）
- ✅ `template/social.py` 从 `worlds/liora/mind.py` import（`LioraMind`）
- ✅ `apps/` 从任何地方 import（但 `apps/` 不应当被 `aios/` 引用）

---

## 1. Kernel 的边界

`aios/kernel/` 中的所有模块：**不知道任何具体世界的概念。**

```python
# ❌ 错误：kernel 不知道"角色"、"裂隙"、"城市"
class WorldRuntime:
    def tick(self):
        if self.tick_count > 100:
            self.emit_fissure("▲…∅")  # 裂隙是 worlds/liora 的概念

# ✅ 正确：kernel 提供机制
class WorldRuntime:
    def tick(self):
        self.state.tick()      # 机制：状态演化
        self.events.tick()     # 机制：事件生命周期
        self.bus.broadcast()   # 机制：消息分发
```

**Kernel 只知道：**

| 模块 | 知道的 |
|------|--------|
| `tick.py` | 递增的数字 |
| `state.py` | `{str: float}` 字典 + 演化函数签名 |
| `event.py` | `WorldEvent` 的创建、注入、老化、过期 |
| `bus.py` | `(type, sender, payload)` 三元组的分发 |
| `resident.py` | 组件注册表（不知道居民有什么组件） |
| `spec.py` | WorldSpec 容器 |
| `history.py` | JSONL 行追加 |
| `memory.py` | 字符串列表 + 频率阈值 |
| `budget.py` | 数字账本 + 冷落检测 |
| `language.py` | 发言长度 + 日常状态概率 |

**不是所有世界都需要的机制放哪里？**
放 `narrative/`（如锚点、光锥、奥丁、Metafield）。

---

## 2. 全局单例模式

每个 kernel 或 narrative 模块提供一个 `get_*()` 函数返回全局单例：

```python
from aios.kernel.tick import get_world_tick
from aios.kernel.state import get_world_state_engine
from aios.kernel.event import get_event_engine
from aios.kernel.resident import get_resident_registry
from aios.kernel.bus import get_bus
from aios.kernel.memory import get_narrative_memory
from aios.kernel.history import get_world_history
from aios.kernel.budget import get_attention_budget
from aios.kernel.language import get_language_attractor
from aios.narrative.anchor import get_anchor_protocol
from aios.narrative.lightcone import get_lightcone
from aios.narrative.voidspace import get_voidspace
from aios.narrative.metafield import get_metafield
from aios.narrative.odin import get_odin
from aios.narrative.tremor import get_tremor
from aios.narrative.anip import get_anip
```

**约束：**

- 每个 `get_*()` 必须是线程安全（使用 `threading.Lock()` 或类似机制）
- `get_*()` 不能接受必填参数（`mode` 等可选参数可以，如 `get_anip(mode="udp")`）
- 内部实现：模块级 `_global_*: Optional[...] = None` + 惰性初始化

---

## 3. WorldSpec 契约

`WorldSpec` 是 kernel 了解世界的唯一接口。kernel 通过它读取：

```python
class WorldSpec:
    name: str                                    # 世界名称
    description: str                             # 一句话描述
    state_variables: dict[str, StateVariable]    # 状态变量定义
    evolution_fn: Callable | None                # 演化公式
    event_generator: Callable | None             # 事件生成器
    memory_clusters: list[list[str]]             # 语义集群（叙事饱和检测用）
```

**约束：**

- `state_variables` 的值域**统一使用 0.0–1.0**（不要混用 0–100、-10–10 等）
- `evolution_fn` 签名：`(variables: dict[str, float], tick: int) → dict[str, float]`
- `evolution_fn` **必须返回 delta**（变化量），而不是绝对值
- `event_generator` 签名：`(state: dict[str, float], tick: int) → list[dict]`
- `state_variables` 的 key 使用英文，`name` 使用中文

---

## 4. WorldApp 钩子

### 四个可覆盖钩子

```python
class MyWorld(WorldApp):
    # ── 必填 ──
    spec = create_my_spec()

    # ── 可选覆盖 ──

    def describe_world(self, state: dict, mind: LioraMind | None = None) -> str:
        """状态变量 → 自然语言。唯一必须诗意的代码。"""
        ...

    def extra_context(self, mind: LioraMind) -> str:
        """角色专属额外感知。空字符串 = 无感知。"""
        return ""

    def resolve_effects(self, action_type: str, target: str) -> dict[str, float]:
        """行动 → 世界状态影响。{变量名: delta}"""
        return super().resolve_effects(action_type, target)

    def on_start(self):
        """世界启动前的初始化。"""
        pass

    def on_stop(self):
        """世界停止前的清理。"""
        pass
```

### SocialWorldApp 额外钩子

```python
class MySocialWorld(SocialWorldApp):
    characters = ["角色1", "角色2"]      # 角色列表（必填）
    persona_presets = {}                  # 人格预设映射（可选）

    def _pick_pair(self) -> tuple[str, str]:
        """选配逻辑。默认随机。"""
        return super()._pick_pair()

    def silence_push_context(self, a: str, b: str, streak: int) -> str:
        """连续沉默时的叙事推力。streak = 连续轮数。"""
        ...
```

**约束：**

- `resolve_effects` 不能修改 `state` 本身，只返回 dict（kernel 负责应用）
- `extra_context` 不能阻塞（不能调 LLM）
- `describe_world` 不要返回数值（LLM 看到了也没用）
- `characters` 不能为空列表（SocialWorldApp 需要至少 2 个角色）

---

## 5. LLM 的边界

**核心原则：状态由 Python 维护，LLM 只负责表达。**

```python
# ❌ 错误：让 LLM 决定信任值
response = model.chat("根据对话，trust 应该增加多少？")
trust_delta = float(response)

# ✅ 正确：Python 做判断，LLM 只说话
if "谢谢" in reply:
    trust_delta = 0.03
response = model.chat("你现在对对方有什么感受？")
# LLM 的输出只影响它下一句话的表达方式，不影响底层状态
```

**约束：**

- 关系、信任、信念、记忆、情绪数值——**都在 Python 中运算，不在 prompt 中生成**
- LLM 的回复只作为文本被居民"听到"，然后 `assimilate_conversation()` 用关键词解析
- `character_config["secrets"]` 是 Python 数据，通过条件判断注入 prompt
- `ModelRuntime` 已有超时 + fallback 机制（主/备模型），应用层不需要另做

---

## 6. 文件系统布局

```
aios/
  kernel/          内核机制（零外部依赖，不引用其他层）
  narrative/       叙事机制（依赖 kernel，不引用 worlds）
  runtime/         运行时编排（串联 kernel + narrative）
  template/        应用模板（组装 runtime + LLM）
  worlds/          世界规则（具体世界的 spec/state/event/mind）
apps/              可运行的入口文件
docs/              开发者文档
examples/          独立示例（不依赖 apps/）
narrativeDocs/     叙事层面的文档和人格文件
tests/             测试文件
```

**约束：**

- `apps/` 每文件一个应用入口（`liora_app.py`、`cyberpunk_app.py`、`consensus_app.py`）
- `examples/` 中的文件可以 `from aios import *`，但不能 `from apps import *`
- 创建新世界时新增文件在 `apps/` 下，不修改 `aios/` 下的文件
- 如果新世界需要全新的机制（所有世界都能用），放 `aios/kernel/` 或 `aios/narrative/`

---

## 7. 测试约束

- 测试文件放在 `tests/test_*.py`，按模块名命名
- **不依赖外部网络**（不调 LLM、不连互联网）
- 测试 UInt 网络时使用 `127.0.0.1` + 自动分配端口（`port=0`）
- 避免共享全局状态带来的测试污染（使用 fixt ure 重置单例）
- 模拟模式（`--no-model`）是测试的默认模式

---

## 8. 数值约束

| 量 | 规则 | 违反后果 |
|---|------|---------|
| 状态变量 | `0.0–1.0` | clamp 行为扭曲演化 |
| 信任/信念 | `-1.0–1.0`（部分 0–1） | 导入旧存档时越界 |
| tick 计数 | `int`，从 0 自增 | WorldEvent 排序出错 |
| 活动度 | `0.0–10.0` | 免疫阈值判断错误 |
| 重要性 | `0.0–1.0` | 锚点存储阈值过滤失效 |
| 事件强度 | `0.0–1.0` | 人格引擎脉冲计算错误 |

---

## 9. Thread Safety

`WorldRuntime` 运行在 `threading.Thread`（daemon）中。所有跨线程访问的数据必须加锁：

| 访问模式 | 正确的做法 |
|----------|-----------|
| 读共享数据 | 用 `runtime.snapshot()`（原子快照） |
| 写共享数据 | 通过 `runtime.apply_effects()`（内部锁保护） |
| 事件注入 | 通过 `runtime.events.inject()` 或 `runtime.emit_fissure_event()` |
| 总线广播 | 通过 `runtime.bus.send()` |
| 全局单例 | `get_*()` 内部有 `threading.Lock()` |

**不要：**

- ❌ 在应用线程直接修改 `runtime.state._state.variables`
- ❌ 在 `extra_context` 或其他钩子中阻塞长时间 I/O
- ❌ 从多个线程同时调用 `get_*()` 而不通过锁（不过 `get_*()` 内部已经处理）

---

## 10. 什么是世界层能做的（检查清单）

添加新功能前问自己：

| 问题 | 答案是"是" → 放在 |
|------|-----------------|
| 所有世界都需要吗？ | `kernel/` |
| 关于死亡协议/跨宇宙？ | `narrative/` |
| 只在这个世界有意义？ | `worlds/your_world/` |
| 是入口/编排？ | `apps/` |
| 是一次性实验？ | `examples/` |

**核心原则复述：** 机制进入 kernel，现象由世界运行后涌现。
