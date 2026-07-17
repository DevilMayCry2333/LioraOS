# 创建你的第一个 LioraOS 世界

> 版本: 0.3 · 适用对象: 人类开发者
>
> 10 分钟从零搭建一个可运行的世界。
> 不需要理解 kernel 层实现，只需填写四个钩子。

---

## 认知模型

LioraOS 的世界架构只有两层概念：

```
WorldSpec  — 世界"是什么"（状态变量、演化规律、事件生成）
WorldApp   — 世界"怎么跑"（感知描述、行动影响、角色配置）
```

**WorldSpec 定义世界的物理规则，WorldApp 定义居民如何感知和行动。**
Kernel 层在底下运转 tick → 演化 → 事件 → 广播，你不需要碰它。

---

## Step 1：定义 WorldSpec

### 状态变量

每个世界有一些连续值（0.0–1.0 或 0–100），每 tick 自动演化。

```python
from aios.kernel.spec import WorldSpec
from aios.kernel.state import StateVariable

def create_bamboo_grove_spec() -> WorldSpec:
    return WorldSpec(
        name="竹隐谷",
        description="一片被雾气笼罩的竹林，风穿过竹节时会发出空洞的响声。",

        # ── 状态变量 ──
        # StateVariable(name, initial, min, max)
        state_variables={
            "wind_intensity": StateVariable("wind", 0.3, 0.0, 1.0),   # 风速
            "fog_density":    StateVariable("fog",  0.5, 0.0, 1.0),   # 雾的浓度
            "bamboo_hum":     StateVariable("hum",  0.2, 0.0, 1.0),   # 竹林共振的嗡鸣
        },

        # ── 演化公式 ──
        evolution_fn=_bamboo_evolution,

        # ── 事件生成（可选）──
        event_generator=_bamboo_events,
    )
```

### 演化公式

```python
def _bamboo_evolution(variables: dict[str, float], tick: int) -> dict[str, float]:
    """每 tick 计算变量的变化量。返回 {变量名: delta}。

    规则：
      - 风每 tick 随机浮动 ±0.02，始终朝 0.3 回归
      - 雾被风驱散（风速越高雾越少），缓慢朝 0.5 回归
      - 竹林嗡鸣受风速正反馈（风越大嗡鸣越大）
    """
    wind = variables.get("wind_intensity", 0.3)
    fog = variables.get("fog_density", 0.5)
    hum = variables.get("bamboo_hum", 0.2)

    return {
        "wind_intensity": (0.3 - wind) * 0.02 + random.uniform(-0.02, 0.02),
        "fog_density":    (0.5 - fog) * 0.01 - wind * 0.01,
        "bamboo_hum":     (0.5 - hum) * 0.005 + wind * 0.01,
    }
```

### 事件生成器（可选）

```python
def _bamboo_events(state: dict, tick: int) -> list[dict]:
    """每 tick 返回 0-N 个事件。

    事件会被居民感知。
    返回格式: [{"event_type": "...", "description": "...", "intensity": 0.0-1.0}, ...]
    """
    if tick > 0 and tick % 5 == 0:
        wind = state.get("wind_intensity", 0.3)
        if wind > 0.6:
            return [{
                "event_type": "wind_gust",
                "description": "一阵强风穿过竹林，竹节剧烈碰撞发出空洞的响声。",
                "intensity": wind,
            }]
    return []
```

---

## Step 2：创建 WorldApp

```python
import random
from pathlib import Path
from aios.template.base import WorldApp

class BambooGroveWorld(WorldApp):
    """竹隐谷 - 你的第一个世界。"""

    # ── 关联 WorldSpec ──
    spec = create_bamboo_grove_spec()

    # ── 角色配置（可选）──
    character_config = {
        "竹翁": {
            "persona": "你是竹翁，一位在竹林里住了很久的老人。"
                       "你的话很少，但每句都带着竹叶的味道。",
            "beliefs": {"silence": 0.7, "nature": 0.8},
            "secrets": ["竹林的嗡鸣其实是无数竹节在低声交谈"],
        },
    }

    # ── 模拟回复池（可选）──
    mock_replies = {
        "竹翁": [
            "风在说你的名字。",
            "听，竹节在传话。",
            "雾散了还会回来。",
        ],
    }
```

### 钩子 1：describe_world

世界状态 → 诗意描述。这是世界**隐喻体系**的入口。

```python
    def describe_world(self, state: dict, mind=None) -> str:
        """用自然语言描述当前世界状态。

        Args:
            state: {变量名: 当前值}
            mind: 感知者的认知模型（可以为 None）

        Returns:
            一段文字，作为居民感知世界的上下文
        """
        wind = state.get("wind_intensity", 0.3)
        fog = state.get("fog_density", 0.5)
        hum = state.get("bamboo_hum", 0.2)

        lines = ["你站在一片竹林中。"]

        if fog > 0.7:
            lines.append("雾气浓重，三米外的竹影几乎融进白色里。")
        elif fog > 0.3:
            lines.append("薄雾在林间游弋，竹子的轮廓若隐若现。")
        else:
            lines.append("雾散了，阳光透过竹叶洒下斑驳的光点。")

        if wind > 0.6:
            lines.append("风很大，竹梢剧烈摇摆，发出嘎吱嘎吱的声响。")
        elif wind > 0.3:
            lines.append("微风拂过，竹叶沙沙作响。")
        else:
            lines.append("风停了，竹林陷入寂静。")

        if hum > 0.6:
            lines.append("你感到脚下的泥土在微微颤动——竹林在低语。")

        return "\n".join(lines)
```

### 钩子 2：extra_context

额外感知。用于注入 LLM 自身感知范围之外的信息。

```python
    def extra_context(self, mind) -> str:
        """额外的感知上下文。
        
        返回空字符串表示无额外感知。
        """
        return ""
```

### 钩子 3：resolve_effects

行动 → 世界状态影响。居民 SAY 一个行动，这里决定它对状态变量的影响。

```python
    def resolve_effects(self, action_type: str, target: str) -> dict[str, float]:
        """居民行动对世界状态的影响。

        Args:
            action_type: 行动类型（say / touch / shout / ...）
            target: 行动目标

        Returns:
            {变量名: delta} 影响量
        """
        effects = super().resolve_effects(action_type, target)

        # 喊叫会扰动风速和嗡鸣
        if action_type == "shout":
            effects["wind_intensity"] = effects.get("wind_intensity", 0) + 0.05
            effects["bamboo_hum"] = effects.get("bamboo_hum", 0) + 0.03

        # 触摸竹子会抑制嗡鸣
        if action_type == "touch" and "竹" in target:
            effects["bamboo_hum"] = -0.03

        return effects
```

> 关于 `action_effects` 和 `target_effects`：你可以在类上直接定义静态效果表，
> 避免每次都要写 resolve_effects 方法：
>
> ```python
> action_effects = {"shout": {"wind_intensity": 0.05, "bamboo_hum": 0.03}}
> target_effects = {"touch": {"竹": {"bamboo_hum": -0.03}}}
> ```

---

## Step 3：Run

### 单角色交互模式

```python
if __name__ == "__main__":
    app = BambooGroveWorld(no_model=True, character="竹翁")
    app.run()
```

这是 CLI 模式：你说话 → 竹翁回应 → 你说话 → 竹翁回应 → ...

```
uv run python3 apps/my_bamboo_world.py
uv run python3 apps/my_bamboo_world.py --no-model   # 模拟模式
```

### 多角色自主社交模式（SocialWorldApp）

要让角色们自己对话（不需人类输入），继承 `SocialWorldApp` 而非 `WorldApp`：

```python
from aios.template.social import SocialWorldApp

class BambooGroveSocial(SocialWorldApp):
    spec = create_bamboo_grove_spec()
    characters = ["竹翁", "青鸦", "鹿隐"]
    character_config = { ... }
    mock_replies = { ... }

    def describe_world(self, state, mind=None) -> str:
        # 和上面一样
        ...

    def extra_context(self, mind) -> str:
        return ""

if __name__ == "__main__":
    app = BambooGroveSocial(no_model=True)
    app.run()   # 默认 10 轮自主对话
```

```
uv run python3 apps/bamboo_social.py -n 30      # 30 轮
uv run python3 apps/bamboo_social.py --interval 5  # 5 秒间隔
```

### 排行榜注册

把世界加到 `visitor_app.py` 的 `WORLDS` 注册表中，别人就能通过旅人入口进入：

```python
# 在 visitor_app.py 的 _register_worlds() 里添加：
try:
    from apps.my_bamboo_world import BambooGroveWorld
    WORLDS["bamboo_grove"] = {
        "name": "竹隐谷",
        "spec_fn": create_bamboo_grove_spec,
        "app_class": BambooGroveWorld,
        "characters": ["竹翁", "青鸦", "鹿隐"],
        "description": "一片被雾气笼罩的竹林。",
    }
except Exception as e:
    logger.debug("bamboo_grove 加载失败: %s", e)
```

```
uv run python3 apps/visitor_app.py --world bamboo_grove --character 竹翁
```

---

## 完整文件

新建 `apps/bamboo_world.py`，把上面的块拼起来。完整文件大约 120 行。

运行：

```bash
uv run python3 apps/bamboo_world.py --no-model
```

---

## 世界观对照表

| 概念 | 在哪定义 | 什么作用 |
|------|---------|---------|
| 状态变量 | `WorldSpec.state_variables` | 世界的底层数字骨架 |
| 演化公式 | `WorldSpec.evolution_fn` | 每 tick 如何变化 |
| 事件生成 | `WorldSpec.event_generator` | 什么事件被所有居民感知 |
| 自然语言描述 | `WorldApp.describe_world()` | LLM 理解世界的入口 |
| 行动→影响 | `WorldApp.resolve_effects()` | 行动如何改变世界 |
| 额外感知 | `WorldApp.extra_context()` | 角色专属的隐藏信息 |
| 角色人格 | `WorldApp.character_config` | LLM prompt + 信念系统 |
| 模拟回复 | `WorldApp.mock_replies` | 无模型时的回复池 |

---

## 常见问题

**Q：必须写 evolution_fn 吗？**
如果 state_variables 为空就不需要。但空的世界不会自己变化。

**Q：describe_world 返回的文字有多长？**
没有硬限制，但建议 200-500 字。太长 LLM 记不住，太短缺少氛围。

**Q：可以不用 LLM 跑起来吗？**
`--no-model` 模式会使用 `mock_replies` 池中的回复。适合测试。

**Q：多个角色共享同一个世界观吗？**
是的。`describe_world()` 对所有角色返回相同的世界描述。
`extra_context(mind)` 可以按 `mind.name` 返回不同的内容。
