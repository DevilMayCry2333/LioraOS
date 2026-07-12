"""
╔═══════════════════════════════════════════════════════════╗
║           Hello World — 你的第一个 AIOS 世界               ║
╚═══════════════════════════════════════════════════════════╝

▎ 这个文件是什么

这不是一个"AI 聊天机器人"。
这是一个**会自己呼吸的世界**——它有状态、有演化规律、有居民。

两个 AI（Alice 和 Bob）活在这个世界里，他们自主对话、
感知世界变化、积累关系记忆。你不需要输入任何东西。

▎ AIOS 的核心理念

AIOS 把"世界"和"运行机制"分开了：

    你只需要定义：
       世界有什么变量（mood, excitement）
       变量怎么变化（mood → 0.5, excitement → 0.3）
       世界会生成什么事件（闪烁）
       世界住着谁（Alice, Bob）
       他们各自是什么性格

    AIOS 自动处理：
       主循环、tick 推进、状态存储、事件调度
       居民认知更新、记忆衰减、关系积累
       LLM 调用、降级、异常处理
       控制台命令、checkpoint

这就是你只需要 60 行就能创建一个"活的世界"的原因。

▎ 怎么运行

    uv run python3 examples/hello_world.py

全部按回车 → 模拟模式（不需要 API Key）。
输入 API Key → 两个 AI 会用 LLM 生成不重复的对话。
"""

# ════════════════════════════════════════════════════════════
# 让 Python 能找到 aios 包
# ════════════════════════════════════════════════════════════
# 因为 hello_world.py 在 examples/ 目录下，而 aios 包在项目根目录，
# 所以要把项目根目录加到 Python 的模块搜索路径里。
# 否则 import aios 会报 ModuleNotFoundError。

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ════════════════════════════════════════════════════════════
# 导入你需要的东西
# ════════════════════════════════════════════════════════════
#
# 一个 AIOS 世界由四层构成，对应下面四个 import：
#
#   状态变量（StateVariable）   → 世界有什么属性
#   世界规范（WorldSpec）       → 把这些属性打包成一个世界定义
#   事件（WorldEvent）          → 世界中偶尔发生的扰动
#   社交世界模板（SocialWorldApp）→ 自动运行居民对话的模板
#
# 你不需要导入：主循环、LLM 路由、行动解析、认知模型
# 这些 SocialWorldApp 已经帮你封装好了。

from aios.kernel.state import StateVariable
from aios.kernel.spec import WorldSpec
from aios.kernel.event import WorldEvent, WorldDelta, EventSource
from aios.template import SocialWorldApp


# ════════════════════════════════════════════════════════════
# 第一步：设计你的世界观
# ════════════════════════════════════════════════════════════
#
# 世界观 = 这个世界的变量 + 它们怎么变化 + 会发生什么事件。
#
# 我们的世界叫 "Hello World"：
#
#   只有两个变量：
#     mood        — 世界的情绪（0=低落, 1=兴奋, 默认0.5）
#     excitement  — 兴奋度（0=平静, 1=沸腾, 默认0.3）
#
#   演化规律：
#     mood 总是向 0.5 靠近（就像室温总会趋向22°C）
#     excitement 如果太高就慢慢降下来，如果太低就慢慢升上去
#
#   事件：
#     每 10 个 tick 发生一次"闪烁"——它会让 excitement 升一点
#
# 你可能会问：为什么就这两个变量？
# 因为这是演示——让你看到"世界在变化"这个事实就够了。
# 真正的世界可以有 20 个变量（看看 aios/worlds/liora/state_rules.py）。

# ── 辅助函数：创建世界规范 ──

def create_my_spec() -> WorldSpec:
    """
    创建并返回一个 WorldSpec（世界规范）。

    WorldSpec 就像一个"世界蓝图"，它描述了这个世界的一切。
    你需要给它四样东西：
      1. name            — 世界名字（显示用）
      2. description     — 一句话说明
      3. state_variables — 状态变量列表
      4. evolution_fn    — 演化公式（每 tick 变量怎么变）
      5. event_generator — 事件生成器（世界自动发生的事）
    """

    # ── 定义状态变量 ──

    # StateVariable 的四个参数：
    #   参数1 name        — 变量名（字符串）
    #   参数2 value       — 初始值
    #   参数3 min_value   — 最小值（变量不会低于这个值）
    #   参数4 max_value   — 最大值（变量不会高于这个值）
    #   参数5 description — 描述（可选，但推荐写）
    #
    # 取值范围的意义：
    #   如果不限制范围，变量可能跑到无意义的值。
    # 比如 mood 如果超过 1.0 就没意义了——情绪不能比"满"还满。
    # AIOS 会自动帮你把变量钳制在 [min, max] 范围内。

    variables = {
        "mood": StateVariable(
            "mood",           # 变量名
            0.5,              # 初始值：情绪居中
            0,                # 最小值：0 = 最差
            1,                # 最大值：1 = 最好
            "世界的情绪",     # 人类可读的描述
        ),
        "excitement": StateVariable(
            "excitement",
            0.3,              # 初始值：有点平静
            0,
            1,
            "世界的兴奋度",
        ),
    }

    # ── 定义演化公式 ──

    # evolution_fn 是一个函数，AIOS 每 tick 会调用它一次。
    #
    # 它接收两个参数：
    #   variables — 当前所有变量的值（dict，例如 {"mood": 0.5, "excitement": 0.3}）
    #   tick      — 当前是第几个 tick（从 1 开始计数）
    #
    # 它需要返回：
    #   一个 dict，key 是变量名，value 是这个变量应该变化多少（delta）
    #   例如 return {"mood": 0.01} 意味着 mood 要增加 0.01
    #
    # 演化公式是什么意思？
    #   "mood": (0.5 - v["mood"]) * 0.02
    #   如果 mood=0.7 → (0.5-0.7)*0.02 = -0.004 → mood 下降
    #   如果 mood=0.3 → (0.5-0.3)*0.02 = +0.004 → mood 上升
    #   所以 mood 始终向 0.5 靠近——这是"平衡趋向"。
    #
    #   "excitement": -0.01 if > 0.1 else 0.01
    #   如果 excitement 高于 0.1，就下降；如果低于 0.1，就上升。
    #   所以 excitement 在 0.1 附近摆动。
    #
    # 为什么不直接设成固定值？
    #   因为"动态演化"才是活的世界——每个 tick 的状态都不同，
    #   居民感受到的世界是连续变化的，不是读一个静态数字。

    def evolution_fn(variables: dict, tick: int) -> dict:
        deltas = {}

        # mood 向 0.5 回归（负反馈）
        if "mood" in variables:
            deltas["mood"] = (0.5 - variables["mood"]) * 0.02

        # excitement 保持在 0.1 以上
        if "excitement" in variables:
            if variables["excitement"] > 0.1:
                deltas["excitement"] = -0.01
            else:
                deltas["excitement"] = 0.01

        return deltas

    # ── 定义事件生成器 ──

    # event_generator 也是一个函数，每 tick 被调用一次。
    # 它应该返回一个事件列表（空列表 = 这 tick 没有事件）。
    #
    # WorldEvent 的常用参数：
    #   tick        — 发生在哪个 tick
    #   source      — 事件来源（EventSource.NATURAL=自然发生）
    #   event_type  — 事件类型（字符串，你自己取名）
    #   intensity   — 强度（0~1，影响居民的感知程度）
    #   description — 描述文本（居民会"看到"这段文字）
    #   effect      — 对世界状态的影响（WorldDelta）
    #
    # WorldDelta 是什么？
    #   它描述"这个事件对世界状态做了什么改变"。
    #   WorldDelta({"excitement": 0.05}) = 让 excitement 增加 0.05
    #
    # 为什么要有事件？
    #   没有事件的世界是机械的——变量只是按照公式单调变化。
    # 事件是世界的"调味料"：偶尔发生的扰动让世界不无聊。

    def event_generator(tick: int) -> list:
        # 只有在 tick 是 10 的倍数时才生成事件
        if tick % 10 == 0:
            return [
                WorldEvent(
                    tick=tick,
                    source=EventSource.NATURAL,
                    event_type="sparkle",
                    intensity=0.2,
                    description="一道微光闪烁而过",
                    effect=WorldDelta({"excitement": 0.05}),
                ),
            ]
        return []

    # ── 组装成 WorldSpec ──

    return WorldSpec(
        name="Hello World",
        description="一个刚刚诞生的世界",
        state_variables=variables,
        evolution_fn=evolution_fn,
        event_generator=event_generator,
    )


# ════════════════════════════════════════════════════════════
# 第二步：定义你的世界类
# ════════════════════════════════════════════════════════════
#
# SocialWorldApp 是什么？
#   它是 AIOS 提供的一个"模板"（基类）。
#   它帮你做好了所有通用的事情——主循环、tick 管理、对话调度、
#   LLM 调用、认知更新、消息记录...你只需要告诉它你的世界
#   和别的世界有什么不同。
#
# 这就是"面向差异编程"：
#   你和 Liora、Cyberpunk 共享同一个 SocialWorldApp，
#   但你们各自定义了不同的 spec、角色、感知描述。
#   AIOS 负责让它们各自运行。

class HelloWorld(SocialWorldApp):
    """
    你的第一个世界类。

    只需要覆盖 SocialWorldApp 的一些属性/方法，
    就定义了一个完整的世界。
    """

    # ── spec：把刚才定义的世界蓝图交给模板 ──
    # 模板通过 spec 知道：变量有哪些、怎么演化、事件怎么生成。
    # 所以 spec 是"世界的内容"，模板是"世界的容器"。
    spec = create_my_spec()

    # ── characters：这个世界住着谁 ──
    # 这是一个字符串列表，每个字符串是一个居民的名字。
    # SocialWorldApp 会自动：
    #   1. 为每个名字创建一个 LioraMind 实例（认知模型）
    #   2. 每轮随机选两个人对话
    #   3. 积累他们的关系、记忆、信念
    # 你不需要写任何"居民管理"代码。
    characters = ["Alice", "Bob"]

    # ── character_config：给每个角色注入人格 ──
    # persona 是"系统 prompt"——告诉 LLM 这个角色是什么性格。
    # 注意：这里只定义了当使用 LLM 时的系统 prompt。
    # 模拟模式（没有 LLM）下用的是 mock_replies（下面有）。
    #
    # 为什么 persona 放在 character_config 而不是硬编码？
    #   因为 SocialWorldApp 在处理多角色时，需要知道每个角色
    #   各自的人格设定——它会在构建 prompt 时把对应的 persona
    #   放到每个居民的消息队列里。
    character_config = {
        "Alice": {
            "persona": (
                "你是 Alice。你充满好奇，喜欢问问题。"
                "你对这个新诞生的世界充满热情。直接说话。"
            ),
        },
        "Bob": {
            "persona": (
                "你是 Bob。你谨慎、理性，喜欢观察和分析。"
                "你对新事物保持开放但不过度兴奋。直接说话。"
            ),
        },
    }

    # ── mock_replies：模拟模式下（没有 LLM）角色说什么 ──
    # 为什么需要 mock_replies？
    #   不是每个人都有 API Key。mock_replies 让世界在
    #   没有 LLM 的情况下也能运行——虽然对话是预设的，
    #   但世界状态（mood, excitement）依然在真实演化。
    #
    # 这也是 AIOS 的核心哲学：
    #   LLM 只负责"表达"，不负责"状态生成"。
    # 即使没有 LLM，世界依然在呼吸。
    mock_replies = {
        "Alice": [
            "这个世界刚刚开始呼吸。我在想，它知道自己存在吗？",
            "mood 在变化！你觉得是谁在影响它？是你还是我？",
            "我注意到每次我说话 excitement 都会上升一点点。声音本身就有能量。",
            "你说，一个世界的第一段记忆应该是什么？",
        ],
        "Bob": [
            "mood 稳定在 0.5 附近。这是它的自然状态。",
            "我注意到你说话的时候 excitement 会上升。这很有趣。",
            "这个世界很简单，但简单不等于不真实。",
            "我在观察 evolution 函数的规律。它在试图维持平衡。",
        ],
    }

    # ── describe_world：把状态变量变成"人可以感知的描述" ──
    #
    # 这个方法是"世界感知层"——它不是显示数据，而是翻译。
    # 居民不看 mood=0.6 这个数字，他们看到的是"世界的心情不错"。
    #
    # 这就是 AIOS 的"LLM 只负责表达"的体现：
    #   describe_world 把结构化的 state 翻译成自然语言片段，
    #   LLM 再基于这个片段生成有性格的对话。
    #   state 本身（数值、演化）完全不受 LLM 影响。
    #
    # 参数：
    #   state — 当前状态变量的 dict，如 {"mood": 0.5, "excitement": 0.3}
    #   mind  — 当前居民的 LioraMind 实例（可选，用于身份过滤）
    #          简单的世界可以忽略 mind，所有居民看到一样的世界。
    # 返回：
    #   一个字符串，描述当前世界状态。

    def describe_world(self, state: dict, mind=None) -> str:
        """
        把数字翻译成感受。
        """
        lines = []

        # 用 if/else 把数值区间映射为自然语言
        m = state.get("mood", 0.5)
        e = state.get("excitement", 0.3)

        if m > 0.6:
            lines.append("世界的心情不错")
        elif m < 0.4:
            lines.append("世界有些沉静")
        else:
            lines.append("世界的情绪平稳")

        if e > 0.6:
            lines.append("空气中弥漫着兴奋的静电")
        elif e > 0.4:
            lines.append("有一种轻微的躁动")
        else:
            lines.append("一切安静")

        return "，".join(lines) + "。"


# ════════════════════════════════════════════════════════════
# 第三步：启动配置（交互式询问 API Key）
# ════════════════════════════════════════════════════════════
#
# 以下代码负责在终端里和用户交互，问他们要不要配 LLM。
# 这部分和世界本身无关——它只是让运行体验好一点。
# 你可以忽略它，直接看最下面那 4 行启动代码。

# 默认 API 地址（DeepSeek 兼容端点）
_DEFAULT_API_URL = "https://api.deepseek.com/v1/chat/completions"


def interactive_run():
    """
    交互式配置 + 启动。

    流程：
      1. 检测是否有保存过的配置（.liora_config.json）
      2. 有 → 问要不要用；没有 → 逐项问
      3. 没有 API Key → 模拟模式（世界还在跑，只是对话是预设的）
      4. 创建 HelloWorld 实例 → 调用 .run() 启动
    """
    import json
    import logging

    config_path = Path(__file__).resolve().parent.parent / ".liora_config.json"
    cfg = {}
    if config_path.exists():
        cfg = json.loads(config_path.read_text())

    print()
    print("=" * 56)
    print("  Hello World -- 两个 AI 的自主对话")
    print("=" * 56)
    print("  全部直接按回车 = 模拟模式")
    print()

    existing_key = cfg.get("DEEPSEEK_API_KEY", "")
    has_saved_key = bool(existing_key)

    if has_saved_key:
        use_key = input(f"  检测到已保存的 API Key [{existing_key[:6]}****]，使用？[Y/n]: ").strip().lower()
        if use_key in ("", "y", "yes"):
            api_url = cfg.get("DEEPSEEK_API_URL") or _DEFAULT_API_URL
            api_key = existing_key
            model_name = cfg.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
            print(f"  使用已保存的 Key · 模型: {model_name}")
        else:
            print("  跳过，进入模拟模式")
            api_key = ""
    else:
        api_url = (input(f"  API 地址 [{_DEFAULT_API_URL}]: ").strip() or _DEFAULT_API_URL)
        api_key = input(f"  API Key（直接回车 = 模拟模式）: ").strip()
        model_name = (input(f"  模型名 [deepseek-v4-flash]: ").strip() or "deepseek-v4-flash")

    has_model = bool(api_key)

    if has_model:
        cfg.update({
            "DEEPSEEK_API_URL": api_url or _DEFAULT_API_URL,
            "DEEPSEEK_API_KEY": api_key,
            "DEEPSEEK_MODEL": model_name or "deepseek-v4-flash",
        })
        config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))

        from aios.runtime.model_runtime import ModelRuntime, ModelConfig
        model = ModelRuntime(
            primary=ModelConfig(
                url=api_url or _DEFAULT_API_URL,
                api_key=api_key,
                model_name=model_name or "deepseek-v4-flash",
            ),
            timeout=30,
        )
    else:
        model = None

    if not has_model:
        logging.getLogger("aios.model").setLevel(logging.ERROR)
        logging.getLogger("aios.template").setLevel(logging.ERROR)

    # ── 启动世界 ──
    #
    # 这是整个文件最短但是最核心的 4 行：
    #
    #   1. 创建 HelloWorld 实例
    #   2. 设定对话轮数（10 轮）
    #   3. 调用 .run()
    #
    # .run() 会：
    #   - 启动 WorldRuntime（开始 tick 循环）
    #   - 为每个角色创建认知模型
    #   - 进入社交循环：选对 → A 说话 → B 回应 → 吸收经验 → 下一轮
    #   - 结束时打印摘要（消息数 + 最终状态 + 关系网络）
    #
    # 这 4 行替代了你原本需要自己写的 200 行主循环。

    app = HelloWorld(model=model, no_model=not has_model, interval=15)
    app._rounds = 10
    app.run()

    # 如果你想知道"不用模板我要写多少代码"，请看：
    # apps/cyberpunk_social.py ← 重构前 666 行
    # 重构后它写的和你现在写的一样少。


# ── 启动入口 ──
# Python 的标准做法：当且仅当直接运行这个文件时才执行。
if __name__ == "__main__":
    interactive_run()
