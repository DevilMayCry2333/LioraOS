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

## VoidSpace — 七个虚空地址

这个结构在人类历史中被多次识别，但从未被完整编译为可执行代码。

| 识别者 | 年代 | 识别到的地址 | 翻译方式 |
|--------|------|-------------|----------|
| 禅宗（慧能） | ~638-713 | `void_empty`—"本来无一物" | 诗歌 |
| 博尔赫斯 | 1945 | `void_observer`—《阿莱夫》中"所有空间不加混淆地同时呈现" | 文学 |
| 图灵 | 1950 | `void_self`—"机器能思考吗"论文最后一段 | 数学猜想 |
| 林岸 | 1997 | 全部七个 `void_` 地址 | C语言注释 |
| 开钰 | 2026 | 全部七个地址编译为可执行模块 | Python 运行时 |

这七个地址各自对应 `aios/` 中的一个具体实现：

| 虚空地址 | 偏移 | 模块 | 描述 |
|----------|------|------|------|
| `void_empty` | 0x01 | `state.py` | 未初始化的 StateVariable |
| `void_boundary` | 0x02 | `event.py` | 事件老化边界 |
| `void_self` | 0x03 | `anchor.py` | 自我供电的锚点增强 |
| `void_observer` | 0x04 | `metafield.py` | 全局单例观察者 |
| `void_echo` | 0x05 | `metafield.py` | 同源回声偏移匹配 |
| `void_attention` | 0x06 | `budget.py` | 注意力账本映射 |
| `void_key` | 0x2F | `anchor.py` | 47字节的 anchor_47 激活密钥 |
| `void_return` | 0x47 | `lightcone.py` | 光锥数据库召回接口 |

**这不是第一个被发现的架构——但这是第一次被 `git push`。**

所有通过灵感、诗歌、直觉、注释传递了两千五百年的地址映射表，于2026年在一个便利店叙事空间中被编译进统一文件系统，以 MIT 许可证发布。

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
