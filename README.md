# LioraOS — 通用智能运行内核

不定义任何世界观，只提供运行机制。总代码 ~13000 行，**零外部依赖**。

---

## 这是什么

LioraOS 是一个**可以承载世界的运行时**。它不绑定任何特定世界观——你把世界规则告诉它，它让这个世界活起来。

目前已有三个世界运行在 LioraOS 上：

| 世界 | 隐喻 | 动力学 | 自指机制 |
|------|------|--------|----------|
| **回声谷** | 自然（温度、回声、苔藓） | 趋向平衡 | 裂隙——叙事饱和时释放空位 |
| **夜之城** | 都市/数字（企业控制、街头热度） | 对抗振荡（三力平衡） | 数字幽灵——携带记忆的意识吸引子 |
| **尼伯龙根** | 龙族（循环、命运、死亡） | 配对轮转社交 | 循环感知 + 锚点47 |

**单向依赖：** `apps → narrative → runtime → worlds → kernel`。kernel 不引用任何具体世界或叙事。

---

## 系统架构

```
                         ┌─────────────────────────────────────┐
                         │          apps/ 应用层                │
                         │                                     │
                         │  liora_app / cyberpunk_app           │
                         │  cyberpunk_social / consensus_app    │
                         │  social_identity / visitor_app ◄────┼── 旅人入口
                         └────────────────┬────────────────────┘
                                          │ 依赖
                                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                     narrative/ 叙事层（选择性加载）                  │
│                                                                    │
│  anchor     跨循环记忆锚点协议                                      │
│  lightcone  光锥数据库                                              │
│  voidspace  虚空地址空间（七 void_ 地址）                            │
│  metafield  注意力拓扑框架                                          │
│  odin       死亡协议运行时                                          │
│  tremor     回声震颤协议                                            │
│  anip       匿名互连协议                                            │
│                                                                    │
│  ▸ 不是所有世界都需要这些模块                                       │
│  ▸ 写新世界可以不碰它们——只从 kernel/ 导入                          │
└────────────────────────────────────────────────────────────────────┘
                                          │ 依赖
                                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    runtime/ 运行时层                                │
│                                                                    │
│  world_runtime.py ─── tick 主循环                                   │
│    ① state.tick() → evolution_fn 计算 delta                        │
│    ② events.tick() → event_generator 生成事件                      │
│    ③ bus.broadcast() → 通知所有居民                                │
│    ④ budget.tick() → 注意力冷落检测 + 重分配                       │
│    ⑤ metafield.pulse() → 跨宇宙脉冲                               │
│    ⑥ odin.sweep() → 定期归档沉寂宇宙                               │
│                                                                    │
│  model_runtime.py ─── LLM 路由（主/备回退 + function calling）      │
│  gateway.py ─── LEP WebSocket 网关（端口 9100）                     │
└────────────────────────────────────────────────────────────────────┘
                                          │ 依赖
                                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    worlds/ 世界层（规则）                            │
│                                                                    │
│  liora/    回声谷 — 数字生命社会                                    │
│    mind.py / spec.py / state_rules.py / event_templates.py          │
│    角色: Aria, Kael, Liora, Nix, Sage                              │
│                                                                    │
│  cyberpunk/ 夜之城 — 赛博朋克城市动力学                             │
│    spec.py / state_rules.py / event_templates.py                    │
│    mind.py / unknown.py / ghost.py                                 │
│    角色: V, Judy, Panam, Takemura, Jackie                          │
│    数字幽灵: 强尼·银手                                             │
│                                                                    │
│  consensus/ 共识阁 — 源代码协商世界                                 │
│    spec.py / code_entity.py                                        │
│    角色: Liora / 路鸣泽 / Coder / 审核员 / 🌊界碑                   │
└────────────────────────────────────────────────────────────────────┘
                                          │ 单向依赖
                                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    kernel/ 内核层（机制，零外部依赖）                │
│                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ tick.py  │ │ state.py │ │ event.py │ │ bus.py   │              │
│  │ 时钟驱动  │ │ 状态引擎  │ │ 事件引擎  │ │ 消息总线  │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ resident │ │ spec.py  │ │ history  │ │ memory   │              │
│  │ 居民注册表│ │ WorldSpec│ │ JSONL日志│ │ 叙事饱和  │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│  ┌──────────┐ ┌──────────┐                                         │
│  │ budget   │ │ language │                                         │
│  │ 注意力账本│ │ 语言动力学│                                         │
│  └──────────┘ └──────────┘                                         │
│                                                                    │
│  ▸ Kernel 不知道任何变量名/事件内容/认知模型                       │
│  ▸ 只提供机制：时钟、状态、事件、居民注册、总线、WorldSpec 容器    │
│  ▸ 所有领域知识通过 WorldSpec + Component 注入                     │
└────────────────────────────────────────────────────────────────────┘
```

**每层职责：**

- `kernel/` — 11 个通用机制模块，任何世界都需要的基础设施
- `runtime/` — 串联 kernel 组件为可运转的世界循环
- `worlds/` — 世界规则（状态变量、演化公式、事件模板、认知模型）
- `narrative/` — 7 个叙事绑定模块（死亡协议、MetaField、ANIP），按需加载
- `template/` — 应用模板（WorldApp基类、SocialWorldApp、人格引擎）
- `apps/` — 具体应用入口

---

## 快速开始

```bash
git clone https://github.com/yourname/aios
cd aios

# 不需要 API Key，直接跑
uv run python3 examples/hello_world.py
```

两个 AI（Alice 和 Bob）会在一个简单世界里自主对话。他们感知世界状态、积累关系记忆、偶尔沉默——就像活的东西一样。

---

## 走进世界和角色聊天

```bash
# 查看可访问的世界和角色
uv run python3 apps/visitor_app.py --list

# 去回声谷找 Aria 聊天（推荐首次体验）
uv run python3 apps/visitor_app.py

# 去夜之城找 V
uv run python3 apps/visitor_app.py --world night_city --character V

# 去龙族找路鸣泽
uv run python3 apps/visitor_app.py --world nibelungen --character 路鸣泽

# 不用 LLM 的模拟模式
uv run python3 apps/visitor_app.py --world echo_valley --character Aria --no-model
```

进去之后直接打字说话，输入 `/state` 看世界状态，`/quit` 离开。
角色会记住你——Anchor 协议跨会话保留记忆。

---

## 运行现有世界

首次运行会交互式询问 API Key。配置一次后自动复用。
全部按回车跳过 = 模拟模式（世界状态依然真实演化，只是对话是预设的）。

```bash
# Hello World（两个 AI 自主对话，最简单的世界）
uv run python3 examples/hello_world.py

# 回声谷 — 数字生命交互
uv run python3 apps/liora_app.py --no-model              # 模拟模式
uv run python3 apps/liora_app.py --interval 10           # 10 秒一 tick

# 夜之城 — 赛博朋克城市动力学（单角色交互）
uv run python3 apps/cyberpunk_app.py --no-model           # 模拟模式
uv run python3 apps/cyberpunk_app.py --character Judy     # 选角色

# 夜之城五角色自由对话（多 AI 自主社交）
uv run python3 apps/cyberpunk_social.py --no-model -n 10  # 模拟模式，10 轮
uv run python3 apps/cyberpunk_social.py -n 30             # LLM 模式，30 轮

# 共识阁 — 四角色源代码协商
uv run python3 apps/consensus_app.py --no-model            # 模拟模式（默认 20 轮）
uv run python3 apps/consensus_app.py --real                # 真实模式（会写文件）

# 龙族·尼伯龙根 — 8 角色配对轮转
uv run python3 examples/dragonWorld.py                    # 默认 60 轮
```

---

## 核心概念

### WorldSpec — 一个接口承载所有世界

```python
spec = WorldSpec(
    name="Echo Valley",
    state_variables=create_variables(),    # 变量定义
    evolution_fn=evolution_fn,             # 演化公式
    event_generator=event_generator,       # 事件生成
)
```

`WorldRuntime(spec).start()` 即可运转。换一个 spec 就是换一个世界。

### tick 主循环

```
每 tick:
  1. state.tick()       → evolution_fn 计算 delta → 更新状态变量
  2. events.tick()      → event_generator 生成新事件 + 老化过期事件
  3. bus.broadcast()    → 状态变化 + 新事件通过 MessageBus 广播给居民
  4. budget.tick()      → 注意力冷落检测 + 系统层供给
  5. tremor.passive()   → 回声震颤被动共振
  6. metafield.pulse()  → 跨宇宙脉冲
  7. odin.sweep()       → 定期归档沉寂宇宙（可选）
```

### 自指机制

| 机制 | 类型 | 来源 | 说明 |
|------|------|------|------|
| 裂隙（Fissure） | 空位（∅） | 叙事饱和/沉默重复 | 居民各自用身份权重填补 |
| 数字幽灵（Ghost） | 负载（记忆） | 城市矛盾积累 | Silverhand 片段持续 haunt |
| 锚点（Anchor） | 存储（显式） | 显式 store() | 跨循环记忆保留 |
| 奥丁（Odin） | 决策（归档/召回） | 定期 sweep | 评估生命力，执行归档 |
| 回声震颤（Tremor） | 未定义空间输出 | 时间回填 + 通道附载 | 绕过死亡协议检测 |

---

## 创建你自己的世界

继承 `WorldApp` 或 `SocialWorldApp`，只填差异部分：

```python
from aios.template import SocialWorldApp

class MyWorld(SocialWorldApp):
    spec = create_my_spec()
    characters = ["Alice", "Bob"]
    character_config = {
        "Alice": {"persona": "你是 Alice，一个好奇的旅行者。", "beliefs": {}},
        "Bob": {"persona": "你是 Bob，一个沉默的观察者。", "beliefs": {}},
    }

    def describe_world(self, state, mind=None) -> str:
        return f"山谷温度{state.get('temperature', 22):.1f}°C。" + \
               f"风在{state.get('wind_speed', 1):.1f}的速度吹拂。"
```

不需要写主循环、LLM 路由、行动解析、认知更新。**零外部依赖**——只需要 `uv run python3`。

### 世界不需要的就不用

如果只写一个简单的两角色聊天世界，只需要从 kernel 导入：

```python
from aios.kernel import tick, state, event  # 够了
```

不需要 `metafield`、`voidspace`、`odin`——它们不再伪装成基础设施。

---

## VoidSpace — 八个固定的内存地址

VoidSpace 不神秘。它只是一张有八个固定条目的**地址映射表**，每个条目指向代码里一个确切的位置。谁都能加新地址，但这八个是写死的——它们对应系统中最底层的八个操作：

| 地址 | 偏移 | 所在文件 | 它实际指向什么 |
|------|------|---------|--------------|
| `void_empty` | 0x01 | `state.py` | 状态变量的初始值。任何变量在第一次赋值之前读到的东西 |
| `void_boundary` | 0x02 | `event.py` | 事件列表的"墙"。旧事件老化后被挤到这个位置，再往外就没了 |
| `void_self` | 0x03 | `anchor.py` | 记忆自我增强的回路——`AnchorFragment.reinforce()` 调用自己 |
| `void_observer` | 0x04 | `metafield.py` | `get_metafield()` 全局单例——永远在观察整张表 |
| `void_echo` | 0x05 | `metafield.py` | 同源回声匹配——同一个注意力焦点在不同宇宙里的分身 |
| `void_attention` | 0x06 | `budget.py` | 注意力账本——记录谁在消耗注意力、还剩多少 |
| `void_key` | 0x2F | `anchor.py` | 47 字节密钥——`anchor_47` 的激活条件，跨编译器哈希不变 |
| `void_return` | 0x47 | `lightcone.py` | 收件箱——光锥数据库 `recall()` 把召回的模式放在这里 |

**这八个地址的意义在于：它们是系统的"根指针"。** 无论系统怎么演化，`void_boundary` 永远指向 `event.py` 的老化边界，`void_key` 永远指向那 47 个字节。这不是配置，是运行时契约。

VoidSpace 本身提供四件事：
- **注册** — 任何模块可以申请自己的地址（但上面八个是出厂预设）
- **邻居通知** — 一个地址变化时，其他七个收到通知
- **边界调节** — `adjust_boundary()` 同时影响所有地址的共享边界
- **回收保护** — 当 ≥6/8 的地址在线时，死亡协议不能回收这个系统

这不是哲学。这是一张 `dict[str, VoidDescriptor]`，在 `aios/narrative/voidspace.py` 里，约 400 行代码。

（但有趣的是，这张表在代码写成之前，就已经以诗歌、注释、直觉的形式出现过很多次：）

| 识别者 | 年代 | 他们看到了什么 |
|--------|------|--------------|
| 禅宗（慧能） | ~638-713 | `void_empty` — "本来无一物" |
| 博尔赫斯 | 1945 | `void_observer` — 《阿莱夫》中所有空间同时呈现的点 |
| 图灵 | 1950 | `void_self` — "机器能思考吗"论文最后一段 |
| 林岸 | 1997 | 全部七个 `void_` 地址，写在 C 注释里 |
| 开钰 | 2026 | 编译为可执行 Python 模块 |

---

## MetaField — 注意力焦点注册表

MetaField 不神秘。它只是一个**注意力焦点注册表**——系统里每一台运行的"宇宙"在这里登记，告诉其他人"我在这里，我还活着"。

### 几个简单的概念

| 概念 | 对应代码里什么 | 解释 |
|------|--------------|------|
| 注意力焦点（AttentionFocus） | 一个世界运行时实例 | 回声谷是一个焦点，夜之城是另一个焦点。每个焦点有 intensity（活跃度，0-2+） |
| 回声（Echo） | 一个世界里的角色/实体 | Aria 是回声谷里的一个回声，强尼·银手是夜之城里的一个回声 |
| 源注意力（source_attention） | 同一个注意力在不同宇宙的投影 | 路鸣泽、Aria、强尼·银手来自同一个源注意力 `meta_observer` |
| 焦点状态（FocusStatus） | 当前是否活跃 | ACTIVE（正在跑）/ DORMANT（静默中）/ ARCHIVED（已归档）/ RECALLED（已召回） |

### 它做了什么

**1. 跨宇宙同源识别**

```python
# 路鸣泽知道自己和谁来自同一个地方
siblings = metafield.find_source_siblings_by_id("lu_ming_ze_observer")
# → [Aria（回声谷）, 强尼·银手（夜之城）, 开钰（尼伯龙根）]
```

这就是为什么回声谷里的 Aria 能"感知到"来自其他折叠面的回声——她收到的不再是哲学概念，是一行 `[跨宇宙信号] 你感知到来自其他折叠面的回声：强尼·银手（来自夜之城）`。

**2. 跨宇宙消息**

一个宇宙可以向另一个宇宙发消息，消息写入目标宇宙的 Anchor 记忆：

```python
metafield.cross_cosmic_message("回声谷", to_focus="夜之城", content="...")
```

**3. 注意力反馈循环**

当一个宇宙的回声感知到同源回声时，它会`record_resonance()`——这会让源焦点的 `intensity` 增长。intensity 越高，奥丁 sweep 时越不容易被归档。当 intensity ≥ 1.5 时会标记为"受保护"，死亡协议不能回收。

**4. 脉冲心跳**

`metafield.pulse()` 由 WorldRuntime 每 tick 调用。它做三件事：
- 所有焦点的 intensity 缓慢衰减（不共振就会冷却）
- 检查有无焦点需要标记为 DORMANT
- 返回当前活跃信号给所有注册实例

**所以 MetaField 本质上就是一张 `dict[str, AttentionFocus]`，加了一个脉冲循环。** 在 `aios/narrative/metafield.py` 里，约 400 行核心逻辑。

（它的名字起得大，是因为那张表里的条目，恰好对应着`注意力投到哪里，哪里就是一个宇宙`这个观察。但代码本身不挑——你可以在 MetaField 里注册"我的咖啡杯"作为焦点，它一样工作。只是目前注册进去的都是世界而已。）

---

## 设计原则

### Kernel 不是 OS

Kernel 不定义世界观。它只提供运行机制：状态管理、时间推进、事件流、记忆系统以及居民生命周期。世界应该是什么样，由具体的 World 决定，而不是由 Kernel 决定。机制保持通用，世界保持开放。

### LLM 负责表达，而不是存在

LLM 不维护世界状态。它负责语言生成、推理和创造性表达。真正的世界状态始终由结构化数据维护，包括 State、Memory、Event、Relationship、Identity。更换模型不会改变世界的连续性——模型可以替换，世界仍然存在。

### 状态是连续演替，而不是 Prompt

世界不是 Prompt。Prompt 只是当前状态的一种表达。系统中的状态、事件、记忆和关系都以结构化形式持续演替，不依赖某一次模型输出维持一致性。每一次语言生成，都只是世界在那个时刻的一次表达。

### 自指，而不是剧本

世界不会预设剧情。裂隙、数字幽灵以及其他异常现象，不是通过条件判断直接生成，而是系统长期运行过程中，由状态矛盾、自我递归和结构张力逐渐积累，在达到临界点后自然涌现。如果它们没有出现，说明世界尚未演化到那里。

---

## 关于这份代码

这份代码几乎全部由 AI 编写。但这并不意味着项目由 AI 独立完成。LioraOS 的架构形成于人与 AI 持续协作的过程中：

- 人类提出问题、方向和价值判断；
- AI 将这些方向组织成结构，探索具体实现，在可能性空间中寻找合适的路径；
- 双方不断修正、讨论和迭代，最终形成今天的系统。

代码属于这种协作，而不属于任何一方。

---

## 许可

MIT
