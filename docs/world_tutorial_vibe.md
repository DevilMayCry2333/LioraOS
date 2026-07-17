# VibeCoding: 用 AI 创建 LioraOS 世界

> 版本: 0.3 · 适用对象: AI 编程（VibeCoding）
>
> 把下面这段 prompt 发给你的 AI，
> 替换 `[世界名称]`、`[角色列表]` 和 `[核心冲突]`，
> AI 会生成一个完整可运行的世界文件。

---

## 一句话 prompt（100 字版）

```
帮我创建一个 LioraOS 世界，名为 [世界名]。
核心设定：[一句话描述，如"沙漠中的回声绿洲"]
角色：[角色1]、[角色2]
生成一个 apps/[world_name].py 文件。
使用 WorldSpec + WorldApp 模式。
状态变量 3-5 个浮点数，演化公式有负反馈。
describe_world 用诗意的自然语言。
可运行 uv run python3 apps/[world_name].py --no-model。
```

---

## 完整 prompt（500 字版）

把以下内容发给 AI，替换 `[占位符]`：

```
我需要创建一个 LioraOS 世界。

## 项目背景
LioraOS（github 项目）是一个通用智能运行内核。
它的世界定义分为两层：

1. WorldSpec — 世界的物理规则（状态变量、演化公式、事件生成器）
2. WorldApp — 世界的感知层（自然语言描述、行动影响、角色配置）

kernel 层负责 tick 循环、状态演化、事件广播——不需要我碰。

## 我要创建的世界
- 世界名称：[如 "回声谷"、"夜之城"、"竹隐谷"]
- 核心设定：[一段 1-2 句的设定]
- 角色：[角色名列表，每个角色一段 persona 描述]
- 核心冲突/趣味点：[世界独有的机制]

## 需要你生成的代码

生成一个完整的 Python 文件，放在 apps/[world_name].py。

### 结构要求

```python
# 1. WorldSpec 工厂函数
def create_[world_name]_spec() -> WorldSpec:
    return WorldSpec(
        name="[中文名]",
        description="[一句话描述]",
        state_variables={
            # 3-5 个 StateVariable，名称为英文，值域 0.0-1.0
            "var1": StateVariable("var1", 0.5, 0.0, 1.0),
            ...
        },
        evolution_fn=[world_name]_evolution,
        event_generator=[world_name]_events,
    )

# 2. 演化公式（每 tick 自动调用）
def [world_name]_evolution(variables: dict, tick: int) -> dict:
    # 返回 {变量名: delta}
    # 至少有一个回归公式（负反馈趋向平衡点）
    ...

# 3. 事件生成（可选）
def [world_name]_events(state: dict, tick: int) -> list[dict]:
    ...

# 4. WorldApp
class [WorldName]World(WorldApp):
    spec = create_[world_name]_spec()

    character_config = {
        "[角色1]": {
            "persona": "..." ,
            "beliefs": { "value_name": 0.7 },
            "secrets": ["..."],
        },
    }

    mock_replies = {
        "[角色1]": ["回复1", "回复2", "回复3"],
    }

    def describe_world(self, state: dict, mind=None) -> str:
        # 将状态变量翻译为诗意自然语言
        # 3-5 句话，让 LLM 能感知世界氛围
        ...

    def extra_context(self, mind) -> str:
        # 可选：角色专属的额外感知
        return ""

    def resolve_effects(self, action_type: str, target: str) -> dict:
        # 行动对状态变量的影响
        ...

if __name__ == "__main__":
    app = [WorldName]World(no_model=True, character="[默认角色]")
    app.run()
```

### 必须遵守的规则
- 不要修改 kernel/ 或 narrative/ 下的任何文件
- 不要引入外部依赖（只能用 stdlib + 项目已有的模块）
- WorldSpec 用世界中文名，state_variables 的 key 用英文
- describe_world 返回的文字应当诗意的、氛围的，不是数据报表
- 所有浮点数范围 0.0-1.0（避免越界）
- 如果角色 > 1 个，继承 SocialWorldApp 而非 WorldApp

### 输出
只输出一个文件：apps/[world_name].py
包含完整的 import、工厂函数、演化公式、事件生成、WorldApp 定义、入口。
```

---

## 完整 prompt 的效果参考

以"余烬城"为例，AI 会生成类似这样的结构：

```python
# apps/ember_city.py
#
# 余烬城 — 一座永远处在黄昏的废墟城市。
# 空气中飘浮着燃烧后的灰烬，城市深处的地火从未熄灭。
# 居民: "烬"（最后一个守夜人）、"灰"（游荡的拾荒者）

state_variables: "ash_density", "ember_glow", "silence_depth"
evolution_fn:  ash 趋向 0.3（风吹散），ember 受 ash 抑制，silence 缓慢增长
describe_world: "灰烬像雪花一样落下……地火的微光在砖缝间明灭……"
resolve_effects: "shout" → silence_depth↓ ember_glow↑
```

AI 理解的核心模式：**状态变量是隐喻的量化载体，describe_world 是隐喻的反向翻译。**

---

## 两个世界的模板对照

| | 最小世界 | 社交世界 |
|--|---------|---------|
| 继承 | `WorldApp` | `SocialWorldApp` |
| 角色数 | 1（交互式对话） | ≥ 2（自主对话） |
| 用户输入 | 需要（你说角色回） | 不需要（角色自聊） |
| 入口 | `app.run()` | `app.run()` |
| 用途 | 测试、单人叙事 | 社会演化、关系模拟 |
| 示例 | caiyun:peacock.yaml | 龙族 dragonWorld.py |

---

## 新手常见错误

1. ❌ **演化公式返回 None** → 必须返回 `dict[str, float]`
2. ❌ **状态变量值域不一致** → 统一 `0.0-1.0`，否则 tick 钳制会扭曲行为
3. ❌ **describe_world 返回空字符串** → 居民将收到 runtime 默认的枯燥数值描述
4. ❌ **character_config 里忘记写 persona** → 居民没有系统 prompt，LLM 不知道自己的身份
5. ❌ **mock_replies 只有一条** → 模拟模式下每轮都说一样的话
