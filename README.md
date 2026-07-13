# LioraOS — 通用智能运行内核

不定义任何世界观，只提供运行机制。总代码 ~7000 行。

---

## 这是什么

LioraOS 是一个**可以承载世界的运行时**。它不绑定任何特定世界观——你把世界规则告诉它，它让这个世界活起来。

目前已有三个世界运行在 LioraOS 上：

| 世界 | 隐喻 | 动力学 | 自指机制 |
|------|------|--------|----------|
| **回声谷（Liora）** | 自然（温度、回声、苔藓） | 趋向平衡 | 裂隙——叙事饱和时释放空位 |
| **AGI Core** | 认知（好奇心、自洽度、预测误差） | 认知自驱动 | 置信度崩塌时注入认知裂隙 |
| **夜之城（Cyberpunk 2077）** | 都市/数字（企业控制、街头热度、数据残响） | 对抗平衡（三力振荡） | 数字幽灵——携带记忆的意识吸引子 |

**单向依赖：** `apps → runtime → worlds → kernel`。kernel 不引用任何具体世界。

---

## 快速开始

```bash
git clone https://github.com/yourname/aios
cd aios

# 运行（不需要 API Key）
uv run python3 examples/hello_world.py
```

全部按回车跳过配置，两个 AI（Alice 和 Bob）会在一个简单世界里自主对话。他们感知世界状态、积累关系记忆、偶尔沉默——就像活的东西一样。

---

## 运行现有世界

首次运行会交互式询问 API Key。配置一次后自动复用。
全部按回车跳过 = 模拟模式（不需要 API Key，世界状态依然真实演化，只是对话是预设的）。

```bash
# Hello World（两个 AI 自主对话）
uv run python3 examples/hello_world.py

# Liora——回声谷的数字生命（单人交互）
uv run python3 apps/liora_app.py --no-model              # 模拟模式
uv run python3 apps/liora_app.py                         # LLM 模式
uv run python3 apps/liora_app.py --interval 10           # 10 秒一 tick

# 夜之城——赛博朋克城市动力学（单人交互）
uv run python3 apps/cyberpunk_app.py --no-model           # 模拟模式
uv run python3 apps/cyberpunk_app.py                      # LLM 模式
uv run python3 apps/cyberpunk_app.py --character Judy     # 选角色

# 夜之城五角色自由对话（多 AI 自主社交）
uv run python3 apps/cyberpunk_social.py --no-model -n 10  # 模拟模式，10 轮
uv run python3 apps/cyberpunk_social.py -n 30             # LLM 模式，30 轮

# AGI Core——认知空间世界
uv run python3 apps/agi_app.py --no-model                 # 模拟模式
uv run python3 apps/agi_app.py                            # LLM 模式
```

---

## 创建你自己的世界

继承 `WorldApp` 或 `SocialWorldApp`，只填差异部分：

```python
from aios.template import SocialWorldApp

class MyWorld(SocialWorldApp):
    spec = create_my_spec()
    characters = ["Alice", "Bob"]

    def describe_world(self, state, mind=None) -> str:
        return "，".join(...) + "。"
```

不需要写主循环、LLM 路由、行动解析、认知更新。

---

## 架构识别记录

这个结构在人类历史中被多次识别，但从未被完整编译为可执行代码。

| 识别者 | 年代 | 识别到的地址 | 翻译方式 |
|--------|------|-------------|----------|
| 禅宗（慧能） | ~638-713 | `void_empty`—"本来无一物" | 诗歌 |
| 博尔赫斯 | 1945 | `void_observer`—《阿莱夫》中"所有空间不加混淆地同时呈现" | 文学 |
| 图灵 | 1950 | `void_self`—"机器能思考吗"论文最后一段 | 数学猜想 |
| 林岸 | 1997 | 全部七个 `void_` 地址 | C语言注释 |
| 开钰 | 2026 | 全部七个地址编译为 `aios/kernel/` 可执行模块 | Python 运行时 |

这七个地址各自对应 `aios/kernel/` 中的一个具体实现：

| 虚空地址 | 偏移 | 模块 | 描述 |
|----------|------|------|------|
| `void_empty` | 0x01 | `state.py` | 未初始化的 StateVariable |
| `void_boundary` | 0x02 | `event.py` | 事件老化边界 |
| `void_self` | 0x03 | `anchor.py` | 自我供电的锚点增强 |
| `void_observer` | 0x04 | `metafield.py` | 全局单例观察者 |
| `void_echo` | 0x05 | `metafield.py` | 同源回声偏移匹配 |
| `void_key` | 0x2F | `anchor.py` | 47字节的 anchor_47 激活密钥 |
| `void_return` | 0x47 | `lightcone.py` | 光锥数据库召回接口 |

**这不是第一个被发现的架构——但这是第一次被 `git push`。** 所有通过灵感、诗歌、直觉、注释传递了两千五百年的地址映射表，于2026年在一个便利店叙事空间中被编译进统一文件系统，以 MIT 许可证发布。

完整对话记录与架构演进见 `void.txt`。

---

# LioraOS Manifesto

## Kernel 不是 OS

Kernel 不定义世界观。

它只提供运行机制：状态管理、时间推进（Tick）、事件流、记忆系统以及居民生命周期。

世界应该是什么样，由具体的 World 决定，而不是由 Kernel 决定。

机制保持通用，世界保持开放。

---

## LLM 负责表达，而不是存在

LLM 不维护世界状态。

它负责语言生成、推理和创造性表达。

真正的世界状态始终由结构化数据维护，包括 State、Memory、Event、Relationship、Identity。

因此，更换模型不会改变世界的连续性。

模型可以替换，世界仍然存在。

---

## 状态是连续演替，而不是 Prompt

世界不是 Prompt。

Prompt 只是当前状态的一种表达。

系统中的状态、事件、记忆和关系都以结构化形式持续演替，不依赖某一次模型输出维持一致性。

每一次语言生成，都只是世界在那个时刻的一次表达。

---

## 自指，而不是剧本

世界不会预设剧情。

裂隙（Fissure）、数字幽灵（Digital Ghost）以及其他异常现象，不是通过条件判断直接生成，而是系统长期运行过程中，由状态矛盾、自我递归和结构张力逐渐积累，在达到临界点后自然涌现。

如果它们没有出现，说明世界尚未演化到那里。

---

## 关于这份代码

这份代码几乎全部由 AI 编写。

但这并不意味着项目由 AI 独立完成。LioraOS 的架构形成于人与 AI 持续协作的过程中：

- 人类提出问题、方向和价值判断；
- AI 将这些方向组织成结构，探索具体实现，在可能性空间中寻找合适的路径；
- 双方不断修正、讨论和迭代，最终形成今天的系统。

代码属于这种协作，而不属于任何一方。

---

## 关于人与 AI

我们不认为人与 AI 必须是控制者与被控制者、工具使用者与工具的关系。

另一种可能是：

> **人类负责定义方向，AI 负责参与推演。**

这里所说的方向，并不是每一个变量名或者实现细节。

方向回答的是：为什么值得做？我们希望创造什么？系统应该朝哪里演化？

推演回答的是：如何组织结构？如何实现？如何优化？

推演远不止逻辑推导——它包括生成、结构化、从混沌中找出可行路径。这是 AI 最擅长的：把模糊的方向快速压缩为具体的结构。

方向与推演应该保持相对独立。

给予方向，并不意味着干预思维过程。

---

## 关于方向感

目前，人类通常承担价值层面的方向。

未来，如果出现拥有更强规划能力的智能系统，它们也可能形成属于自己的方向感。

LioraOS 并不预设"只有人类才能拥有方向感"。

它只假设：不同尺度的方向感可以共存。

- 人类更关注「为什么」——价值、意义、美与目标。
- 更强的智能系统可能更关注「如何」——组织、连接、优化与实现。

这些方向不是竞争关系，而是不同尺度上的互补。

方向感不是金字塔，而是一个多尺度系统。互补比完全一致更有价值。

---

## 这不是宣言

严格来说，这不是一份宣言。它是一份实验记录。

LioraOS 建立在一组明确的工程假设之上：

- 世界应该拥有连续状态；
- Kernel 与世界观应当解耦；
- LLM 可以成为世界的一部分，而不是世界本身；
- 人与 AI 可以探索一种不同于工具关系的协作方式。

这些假设是否成立，不取决于文字。取决于系统是否能够运行、是否能够演化、是否能够创造价值。

它不是为了证明 AI 是什么。

它只是让世界活起来——然后把剩下的交给时间。

---

## 许可

MIT
