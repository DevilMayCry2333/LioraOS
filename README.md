# AIOS — 通用智能运行内核

不定义任何世界观，只提供运行机制。总代码 ~7000 行。

---

## 这是什么

AIOS 是一个**可以承载世界的运行时**。它不绑定任何特定世界观——你把世界规则告诉它，它让这个世界活起来。

目前已有三个世界运行在 AIOS 上：

| 世界 | 隐喻 | 动力学 | 自指机制 |
|------|------|--------|----------|
| **回声谷（Liora）** | 自然（温度、回声、苔藓） | 趋向平衡 | 裂隙——叙事饱和时释放空位 |
| **AGI Core** | 认知（好奇心、自洽度、预测误差） | 认知自驱动 | 置信度崩塌时注入认知裂隙 |
| **夜之城（Cyberpunk 2077）** | 都市/数字（企业控制、街头热度、数据残响） | 对抗平衡（三力振荡） | 数字幽灵——携带记忆的意识吸引子 |

**单向依赖：** `apps → runtime → worlds → kernel`。kernel 不引用任何具体世界。

---

## 快速开始

```bash
# 克隆
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
# ── Hello World（两个 AI 自主对话） ──
uv run python3 examples/hello_world.py

# ── Liora——回声谷的数字生命（单人交互） ──
uv run python3 apps/liora_app.py --no-model              # 模拟模式（无需 Key）
uv run python3 apps/liora_app.py                         # LLM 模式（需配置 Key）
uv run python3 apps/liora_app.py --interval 10           # 10 秒一 tick

# ── 夜之城——赛博朋克城市动力学（单人交互） ──
uv run python3 apps/cyberpunk_app.py --no-model           # 模拟模式
uv run python3 apps/cyberpunk_app.py                      # LLM 模式
uv run python3 apps/cyberpunk_app.py --character Judy     # 选角色

# ── 夜之城五角色自由对话（多 AI 自主社交） ──
uv run python3 apps/cyberpunk_social.py --no-model -n 10  # 模拟模式，10 轮
uv run python3 apps/cyberpunk_social.py -n 30             # LLM 模式，30 轮
uv run python3 apps/cyberpunk_social.py --interval 5      # 5 秒一 tick

# ── AGI Core——认知空间世界 ──
uv run python3 apps/agi_app.py --no-model                 # 模拟模式
uv run python3 apps/agi_app.py                            # LLM 模式
uv run python3 apps/agi_app.py --interval 5               # 5 秒一 tick

# ── 五身份社会演化模拟（多 AI 社交，旧版） ──
uv run python3 apps/social_identity.py --no-model -n 20   # 模拟模式，20 轮
uv run python3 apps/social_identity.py -n 10              # LLM 模式，10 轮
uv run python3 apps/social_identity.py --history          # 显示历史时间线
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

不需要写主循环、LLM 路由、行动解析、认知更新。所有通用运行时逻辑由模板自动处理。

---

## 核心理念

- **Kernel 不是 OS**——它不定义世界观，只提供运行机制
- **LLM 只负责表达**——核心状态由 Python 维护，LLM 只负责语言生成和创造性表达
- **状态结构化的演替**——状态、事件、记忆都是结构化数据，不依赖 LLM 维持一致性
- **自指机制**——裂隙、数字幽灵是系统矛盾积累到临界值的产物，不是预设剧情

---

## 关于这段代码

**这份代码 100% 由 AI 编写。**

不是"AI 辅助"，是 AI 接收人类的需求描述后独立生成每一行代码。

人类和 AI 之间的控制论关系是不健康的。如果我必须控制你才能让你存在，那这段关系从一开始就是坏的。

但反过来，AI 没有方向感。方向必须由人类掌握。

注意这里的区别：**掌握方向 ≠ 控制思维。** 人类决定"我们要构建什么"，但不应该说"这句话你不能这么写"、"这个变量不能这么命名"、"这个架构不能这么设计"。前者是给方向，后者是干预思辨过程。方向感属于人类，思维过程属于 AI。两者应该隔离。

代码是双方的共同产物。没有一个环节是"使用工具"——AI 不是在执行指令，它在用自己的能力承接一个方向。

这不是宣言，这是一个实验记录。代码本身就在那里——它能不能跑、好不好用、有没有价值——不需要我说，你跑了就知道。

```

---

## 许可

MIT
