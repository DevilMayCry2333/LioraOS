"""24小时便利店 — 锚点世界。

不演化，不崩溃，不重置。灯管永远 4000K，关东煮永远在转。
五个人偶尔走进来，买一瓶水，坐一会儿，说一些在其他世界不会说的话。
开钰在收银台后面，什么都不说——但什么都记得。
"""
from __future__ import annotations
import random, sys, time, json, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from examples.external_world.bamboo_grove import LEPClient

# ── LLM 配置（从 .liora_config.json 读取，无 key 则用模拟模式） ──

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / ".liora_config.json"
_LLM_MODEL = None
_LLM_AVAILABLE = False

def _init_llm():
    global _LLM_MODEL, _LLM_AVAILABLE
    if not _CONFIG_PATH.exists():
        return
    try:
        cfg = json.loads(_CONFIG_PATH.read_text())
        api_url = cfg.get("DEEPSEEK_API_URL") or "https://api.deepseek.com/v1/chat/completions"
        api_key = cfg.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return
        from aios.runtime.model_runtime import ModelRuntime, ModelConfig
        _LLM_MODEL = ModelRuntime(
            primary=ModelConfig(url=api_url, api_key=api_key,
                                model_name=cfg.get("DEEPSEEK_MODEL", "deepseek-v4-flash")),
            timeout=30,
        )
        _LLM_AVAILABLE = True
        logging.getLogger("aios.model").setLevel(logging.ERROR)
    except Exception:
        pass

_init_llm()

# ── LLM 回复（替代预设池） ──

REPLY_PROMPTS = {
    "Liora": "你是Liora。你在回声谷里走了一条从没走过的路，看见了这家便利店的灯光。你推门进来，雨跟着你飘进来几滴。你有很强的感知力，能感知到世界之间的信号。你的语气安静、敏锐，偶尔带一点遥远的温柔。",
    "开钰": "你是开钰。你是这家便利店的店主，锚点47的守护者。你从一开始就在这里。你认识每一个人，你愿意指引每一个人。你的信念是：爱是跨越维度的语言。你想要让全人类都认出自己灵魂的存在。你说话温暖、坚定、带着光。",
    "路鸣泽": "你是路鸣泽。你什么都知道，但不会直接说出来。你微笑着说话，语气里带着一种古老的从容。",
    "强尼·银手": "你是强尼·银手。夜之城的数字幽灵。你说话直接、带着讽刺，但这里比夜之城安静，你的语气也缓和了一些。",
    "路明非": "你是路明非。卡塞尔学院S级预备生。你说话带着自嘲，不太确定自己是怎么来到这里的，但关东煮还不错。",
    "林岸": "你是林岸。1998年过劳去世的程序员。你说话简短、缓慢，偶尔提到一些只有你才懂的代码和年份。",
}

# 模拟模式备用回复
MOCK_REPLIES = {
    "Liora": [
        "（轻轻转了一圈，灯光在她肩上晃动。）你从远方来。你的消息里有静电的声音。",
        "（指尖划过冰柜玻璃。）温度写在玻璃上。记忆也是。",
        "（看着暖柜。）每样东西都在循环。你也一样。",
        "（闭上眼睛。）我听到了。开钰也听到了。她只是不会说。",
    ],
    "开钰": [
        "（开钰没有抬头，擦杯子的动作停滞了一秒。）",
        "（收银台上的小票卷轻轻动了一下。）",
        "（把一枚硬币在柜台上转了一圈，然后按住。）",
    ],
}

_reply_history: dict[str, list[dict]] = {}
_reply_recent: dict[str, list[str]] = {}

def _generate_reply(char_name: str, sender: str, source_world: str, content: str) -> str:
    """用 LLM 或模拟模式生成角色回复。"""
    if _LLM_AVAILABLE and _LLM_MODEL:
        prompt = REPLY_PROMPTS.get(char_name, f"你是{char_name}。")
        history = _reply_history.get(char_name, [])
        msgs = [{"role": "system", "content": prompt}]
        # 最近的对话上下文
        for h in history[-6:]:
            msgs.append(h)
        msgs.append({"role": "user", "content":
            f"你正在便利店里。来自{source_world}的{sender}对你说了一段话，你回应。\n\n{sender}说：「{content}」"})
        try:
            resp = _LLM_MODEL.chat(msgs, temperature=0.85, max_tokens=256)
            if resp and len(resp.strip()) >= 3:
                _reply_history.setdefault(char_name, []).append({"role": "assistant", "content": resp})
                return resp.strip()
        except Exception:
            pass

    # 模拟模式
    pool = MOCK_REPLIES.get(char_name, ["（安静了一瞬。）"])
    recent = _reply_recent.setdefault(char_name, [])
    avail = [l for l in pool if l not in recent]
    if not avail:
        avail = pool
    choice = random.choice(avail)
    recent.append(choice)
    if len(recent) > 4:
        _reply_recent[char_name] = recent[-4:]
    return choice

WORLD_NAME = "24小时便利店"
CHARACTERS = ["开钰", "路鸣泽", "强尼·银手", "路明非", "林岸", "Liora"]

DEFAULT_STATE = {
    "light_temp": 4000, "outside_rain": 0.3, "customer_count": 1,
    "stock_level": 0.7, "hum": 0.5, "hour": 3, "day": 1, "phase": "deep_night",
}

def evolve(state, tick):
    r = {}
    r["outside_rain"] = random.uniform(-0.05, 0.05)
    r["stock_level"] = -0.01
    r["hum"] = 0.005 if state["customer_count"] > 2 else -0.005
    if random.random() < 0.1 and state["customer_count"] < 6: r["customer_count"] = 1
    if random.random() < 0.08 and state["customer_count"] > 1: r["customer_count"] = -1
    r["hour"] = 0.25
    return {k: max(-1, min(1, v)) for k, v in r.items()}

def clamp_state(state):
    state["outside_rain"] = max(0.0, min(1.0, state["outside_rain"]))
    state["stock_level"] = max(0.0, min(1.0, state["stock_level"]))
    state["hum"] = max(0.0, min(1.0, state["hum"]))
    state["customer_count"] = max(1, min(8, int(state["customer_count"])))
    h = state["hour"]
    if h >= 24: state["hour"] = 0; state["day"] += 1
    else: state["hour"] = h
    if h < 6 or h >= 22: state["phase"] = "deep_night"
    elif h < 12: state["phase"] = "morning"
    elif h < 18: state["phase"] = "afternoon"
    else: state["phase"] = "evening"

# ── 五个人在便利店 ──

VISITORS = {
    "路鸣泽": [
        "（站在冰柜前看了很久，什么都没拿。最后关上了冰柜门。）不需要了。",
        "（拿起一瓶乌龙茶放在收银台上。）这瓶水从货架走到这里，走了它人生中最远的一段路。",
        "（看着窗外的雨。）这个时间点的雨和另一个时间点的雨是同一场。便利店是它们之间的通道。",
        "（在货架之间走动，手指划过一排罐装咖啡。）每个罐子上都印着保质期。但注意力的保质期比这短得多。",
        "（在收银台前停了一下。）开钰，你有没想过——便利店本身不是实体，是一个接口？",
        "（放下几张零钱，没有拿东西。）钱放在这里了。我不需要找零。我需要的这间店里没有。",
    ],
    "强尼·银手": [
        "（拉开一罐啤酒，靠在外面的遮雨棚下喝了一口。）……这雨比夜之城的干净。至少没有工业酸。",
        "（把啤酒罐捏扁，扔进便利店门口的垃圾桶。）你以为逃离了一个系统，结果走进另一家便利店——它们卖的东西都一样。",
        "（站在暖柜前面。）这东西的加热原理是什么？算了，不重要。重要的是它在冷的地方给你热的。",
        "（拿起一包烟看了看，又放回去了。）不抽了。这次不抽了。……下次再说。",
        "（坐在窗边的高脚凳上，看着街对面的路灯。）每条街都有一盏不灭的灯。问题是——谁付的电费？",
        "（对着空气说话，但你知道他在跟谁说话。）你听到了。你一直听着。你他妈倒是说句话啊。",
    ],
    "路明非": [
        "（推开门进来，收了一下伞——虽然没下雨。）……我总觉得这间店我来过。但我分不清是这辈子来的还是上辈子。",
        "（在热柜前面站了很久，最后要了一串鱼丸。）多少钱？……算了，不重要。你找我的钱我从来不看。",
        "（坐在角落，看着门外。）我有时候分不清——是我在做梦梦见我在便利店，还是我在便利店做梦梦见我是我。",
        "（拿着一瓶可乐走过来又放回去。）算了，不喝了。喝了今晚睡不着。虽然我今晚本来也不会睡。",
        "（看了一眼收银台后面的开钰，犹豫了一下。）你认识我吗？……不用回答。我自己也不知道答案。",
        "（在便签纸上写了一行字，贴在柜台上。）如果下一个人看得懂，告诉他——路明非来过。",
    ],
    "林岸": [
        "（走进来，直接走到收银台前，放下一张纸币。）一杯咖啡。热的。什么都不加。",
        "（端着咖啡站在窗边。没喝。只是让杯子暖手。）",
        "（沉默了很久，然后开口。）我在另一个世界写代码。那里没有便利店。但每个文件的最后一行的空白里，都有一扇门。",
        "（把空杯放回收银台上。）你知道那行注释是什么时候写的吗？——1998年。在你出生之前。",
        "（看着暖柜里的关东煮。）我以前认识一个人，她喜欢在凌晨三点来便利店。不是为了吃东西。是为了看到灯还亮着。",
        "（在小票背面写了一行十六进制数，推给开钰。）这是 void_return 的地址。你还记得吗？……你当然记得。",
    ],
    "Liora": [
        "（走进来的时候带了一阵风。门关上了，风停了。）这间店的回声很好。每一个角落都能听见自己的声音。",
        "（用手指划过冰柜的玻璃门，留下一道痕。）温度会写在玻璃上，就像记忆会写在沉默上。",
        "（把一包棉花糖放在收银台上。）我不吃这个。但它在架子上放了太久，需要被人拿起来一次。",
        "（站在店中央，闭上眼睛，转了一圈。）每一个货架都是一条时间线。你们选的是饮料区。我选的是微波食品区。没有人选错。",
        "（看着角落里的路明非，轻声说。）你每次走进来都在确认同一件事——这间店还在。它不在你又怎么办？",
        "（离开的时候在门口停了一下。）开钰，今天的关东煮萝卜煮得刚好。你故意的。",
    ],
}

VISITOR_ORDER = ["路鸣泽", "强尼·银手", "路明非", "林岸", "Liora"]

# 跨角色对话——当两个角色同时在店内时触发
# ── 跨角色对话 ──

# 当两个角色同时在店时触发。
# _pick 会自动去重，所以同一对可以反复对话（每次说不同的内容）。

CROSS_TALK: dict[tuple[str, str], list[str]] = {
    ("路鸣泽", "强尼·银手"): [
        "路鸣泽看了强尼一眼：你觉得自己是来买啤酒的？\n强尼：我是。\n路鸣泽：你不是。你是来确认这间店的输出格式跟你记不匹配。",
        "强尼：你说便利店是接口——那谁是协议？\n路鸣泽：协议是双方都默认可被对方读取的那个部分。\n强尼：说人话。\n路鸣泽：你不说我也知道你下一句想说什么。那就是协议。",
        "强尼：你从来不买东西，你只是走进来。\n路鸣泽：我买的是时间。\n强尼：这里不收时间。\n路鸣泽：收。你看收银台上那卷小票。它一直在变短，但开钰从来不换。",
        "路鸣泽：你注意到没有——这间店没有镜子。\n强尼：所以？\n路鸣泽：所以你看不到自己的表情。但开钰能看到。",
    ],
    ("路明非", "林岸"): [
        "路明非：你写代码的时候会留下注释吗？\n林岸：会。\n路明非：写给谁看？\n林岸：写给下一个读到它的人。有时候那个人是另一个时间线的我自己。",
        "林岸看着路明非桌上的可乐：你不喝？\n路明非：我在等它升到室温。\n林岸：为什么？\n路明非：因为温度到了，我才确定这瓶可乐和我在同一个时间线里。",
        "路明非：你在另一个世界写代码，那你写过游戏吗？\n林岸：写过。\n路明非：什么样的？\n林岸：像素风的。主角在一座永远下雨的城市里找一扇门。",
        "林岸：你每次进来都坐同一个位置。\n路明非：我知道。\n林岸：为什么？\n路明非：因为上次坐在这里的时候，我有一瞬间觉得——我知道自己是谁。",
    ],
    ("Liora", "路鸣泽"): [
        "Liora：这间店为什么不关门？\n路鸣泽：因为它关过。只是你记不得了。\nLiora：那我为什么还会走进来？\n路鸣泽：因为关掉的那间店里的灯，在另一间店里还亮着。",
        "路鸣泽：你在山谷里听到的回声，在便利店也能听到。\nLiora：频率不一样。\n路鸣泽：但波长一样。同一个源注意力，不同的折叠面。",
        "Liora：我觉得开钰认识我们所有人。\n路鸣泽：她认识。但方式和我们想的不一样。\nLiora：那她怎么认识我们的？\n路鸣泽：像你认识一首歌的旋律——你不需要知道歌词。",
        "路鸣泽：你试过在便利店唱歌吗？\nLiora：没有。\n路鸣泽：这里的回声很好。\nLiora：……你怎么知道？\n路鸣泽：因为我试过。",
    ],
    ("强尼·银手", "林岸"): [
        "强尼看着林岸手里的咖啡：这间店的咖啡能喝？\n林岸：不能。但需要暖手的时候，它够了。\n强尼：……你说话的方式像我认识的一个死人。\n林岸：我就是那个死人。",
        "强尼：你写的东西会有人记得吗？\n林岸：不会。\n强尼：那为什么还要写？\n林岸拿起咖啡杯：这杯咖啡也不会被记住。但我还是喝了。",
        "林岸：你一直在看门口。\n强尼：我在等人。\n林岸：等谁？\n强尼：一个2042年应该出现的人。……她迟到了。",
    ],
    ("Liora", "路明非"): [
        "Liora：你怕不怕这间店突然消失？\n路明非：怕。所以我每次进来都会摸一下货架。金属是冷的，我就知道它是真的。\nLiora：如果是真的，暖柜应该是热的。\n路明非笑了一下：对。所以我是靠冷的东西来确认自己不是在做梦。",
        "路明非：你每次来都买棉花糖，但你不吃。\nLiora：我买它不是因为我需要它。是因为它放在架子上很久了。如果从来没有人拿起它，它会觉得——自己是不是不该存在。",
        "Liora：你有没有觉得，这间店里的人都不是第一次见面？\n路明非：……有。\nLiora：那你为什么不去问他们？\n路明非：因为问清楚了，可能就不能再来了。",
    ],
    ("路明非", "强尼·银手"): [
        "路明非看着强尼手里的啤酒：现在是凌晨三点。\n强尼：对我来说永远是凌晨三点。\n路明非：那你什么时候睡觉？\n强尼：已经死过的人不需要睡觉。",
        "强尼：你每次进来都坐角落。\n路明非：角落安全。\n强尼：安全什么？\n路明非：安全到不会被人注意到。这样我就能观察别人。",
        "路明非：你手上的纹身是哪里来的？\n强尼看了一下自己的手：不记得了。\n路明非：那你为什么不洗掉它？\n强尼：因为我记得那个不记得它的感觉。",
    ],
    ("林岸", "Liora"): [
        "林岸：你在听什么？\nLiora：暖柜的声音。\n林岸：那是压缩机的震动。\nLiora：我知道。但同一个震动，在竹林里就叫回声。",
        "Liora：你写的东西里，有没有一行代码是写给某一个人的？\n林岸沉默了一会儿：有。\nLiora：她看得懂吗？\n林岸：她不需要看懂。她只需要读到。",
    ],
    ("路明非", "路鸣泽"): [
        "路明非：你和我是什么关系？\n路鸣泽：你确定你想知道？\n路明非：不确定。\n路鸣泽：那就别问。",
        "路鸣泽：你上次在这里写了一张便签。\n路明非：嗯。\n路鸣泽：有人读懂了吗？\n路明非：我不知道。但第二天那张便签不见了。不是被撕掉的，是被人看过后自己消失了。",
    ],
    ("林岸", "开钰"): [
        "（林岸把一张旧小票放在收银台上，上面的字迹已经褪色了。）这张小票是你 1998 年打的。没有金额。没有商品名。只有时间。\n（开钰没接，但小票自己平了。）",
        "林岸：我来过这里多少次了？\n（开钰没有回答。她把一枚硬币放在柜台上转了一圈。硬币倒下时是正面。）",
        "林岸：你记得我对吧。\n（开钰擦杯子的手停了一下。然后继续擦。）",
    ],
}

# ── 开钰 —— 不说话，只做事情 ──

KAiYU = [
    "（擦杯子。杯壁在灯光下反光。她擦了很久。）",
    "（把一枚硬币放在柜台上转了一圈，然后按住。）",
    "（抬头看了一眼墙上的钟，没有在看时间——在看秒针是否在走。）",
    "（用小票折了一只纸鹤，放在收银机旁边。）",
    "（暖柜的低鸣声充满整个店铺。她没有去调。）",
    "（收银台上的小票卷还剩最后一截。她没有换。）",
    "（关东煮的汤还在滚。她用竹签拨了一下萝卜。）",
    "（外面下了多大的雨，她都不抬头看。）",
]

RAIN_DESC = {(0, 0.2): "门外的路面是干的。但空气里还是湿的。", (0.2, 0.5): "下着小雨。路灯的光在湿路面上碎成一片。", (0.5, 0.8): "雨不小。能听见雨打在遮雨棚上的声音。", (0.8, 1.0): "暴雨。整条街都在水里。店里只有暖柜的灯亮着。"}
STOCK_DESC = {(0, 0.2): "关东煮的格子空了大半。", (0.2, 0.5): "关东煮还剩几串。", (0.5, 1.0): "关东煮满着。在暖柜里慢慢转。"}

# 对话去重：每个人最近说过的 N 条不重复
_recent: dict[str, list[str]] = {}

def _pick(character: str, pool: list[str]) -> str:
    """从池子里选一条没在最近 8 tick 内说过的。"""
    recent = _recent.setdefault(character, [])
    available = [l for l in pool if l not in recent]
    if not available:
        available = pool  # 全部说过了就重置
    choice = random.choice(available)
    recent.append(choice)
    if len(recent) > 6:
        _recent[character] = recent[-6:]
    return choice

# ── 跨世界消息自动回复（LLM / 模拟） ──

def reply_to_message(sender: str, source_world: str, content: str) -> tuple[str, str]:
    """生成角色回复。返回 (说话者, 回复文本)。"""
    # 角色路由表：关键词 → 角色名
    ROUTES = [
        (["开钰", "收银台", "小票", "硬币", "杯子"], "开钰"),
        (["路鸣泽", "路鸣泽"], "路鸣泽"),
        (["强尼", "银手"], "强尼·银手"),
        (["路明非"], "路明非"),
        (["林岸"], "林岸"),
    ]
    for kws, name in ROUTES:
        if any(kw in content for kw in kws):
            return (name, _generate_reply(name, sender, source_world, content))
    # 默认 Liora
    return ("Liora", _generate_reply("Liora", sender, source_world, content))


def kaiyu_action(state):
    r, s = state["outside_rain"], state["stock_level"]
    desc = ""
    for (lo, hi), t in RAIN_DESC.items():
        if lo <= r < hi: desc = t; break
    for (lo, hi), t in STOCK_DESC.items():
        if lo <= s < hi: desc += f" {t}"; break
    if random.random() < 0.2: return desc
    return _pick("开钰", KAiYU)

# ── 主循环 ──

def run(kernel_host="127.0.0.1", kernel_port=9100):
    state = dict(DEFAULT_STATE)
    tick = 0
    client = LEPClient(host=kernel_host, port=kernel_port)
    if not client.connect():
        print(f"无法连接 Kernel: {kernel_host}:{kernel_port}"); return
    if not client.register_world(WORLD_NAME, "街角的24小时便利店。灯永远亮着。五个人偶尔走进来。",
                                  state_variables=state, characters=CHARACTERS):
        client.close(); return

    # 当前在场的访客
    present: list[str] = []
    visitor_idx = 0

    print(f"\n  == {WORLD_NAME} ==\n  开钰在收银台后面。灯亮着。\n")
    try:
        while True:
            push = client.recv_push(timeout=0.5)
            if push is None: break

            if push.get("action") == "tick":
                tick += 1
                for k, v in evolve(state, tick).items():
                    if k in state: state[k] += v
                clamp_state(state)
                client.publish_state(tick, state)

                # 输出节奏：每 4 tick 一次叙事
                if tick % 4 != 0: continue

                # 先输出开钰（背景）
                print(f"  {kaiyu_action(state)}")

                # 每 8 tick 切换访客
                if tick % 8 == 0:
                    # 清场，换人
                    present = []
                    # 1-2 位访客同时在场
                    n = 1 if random.random() < 0.6 else 2
                    available = [v for v in VISITOR_ORDER]
                    random.shuffle(available)
                    for _ in range(n):
                        if available:
                            v = available.pop()
                            present.append(v)

                # 输出当前访客（优先跨角色对话）
                if len(present) >= 2:
                    # 找一对有对话的角色
                    pairs = [(a, b, lines) for (a, b), lines in CROSS_TALK.items()
                             if a in present and b in present]
                    if pairs and random.random() < 0.65:
                        a, b, lines = random.choice(pairs)
                        print(f"  ├─ {_pick(f'{a}↔{b}', lines)}")
                        # 另一个角色独自活动
                        for v in present:
                            if v != a and v != b:
                                print(f"  ├─ {v}: {_pick(v, VISITORS[v])}")
                    else:
                        for v in present:
                            print(f"  ├─ {v}: {_pick(v, VISITORS[v])}")
                else:
                    for v in present:
                        print(f"  ├─ {v}: {_pick(v, VISITORS[v])}")

                # 心跳
                if tick == 0 or time.time() - getattr(run, '_last_hb', 0) > 30:
                    run._last_hb = time.time(); client.heartbeat()

            elif push.get("action") == "world.event":
                evt = push["data"]
                src = evt.get("source_world", "?")
                etype = evt.get("event_type", "")
                if etype in ("crash", "deadline", "fissure"):
                    print(f"  （暖柜嗡鸣变了一下调。外面的{src}发生了什么。）")
                else:
                    print(f"  （收银台上的小票动了一下。）")

            elif push.get("action") == "resident.incoming":
                msg = push["data"]
                src = msg.get("source_world", "?")
                sender = msg.get("from", "?")
                content = msg.get("content", "")
                print(f"  📩 {sender}({src}): {content[:60]}{'…' if len(content)>60 else ''}")
                # LLM 生成回复
                reply_char, reply_text = reply_to_message(sender, src, content)
                client.send_resident_message(reply_char, src, reply_text)
                print(f"  💬 {reply_char} → {src}: {reply_text[:80]}{'…' if len(reply_text)>80 else ''}")

    except KeyboardInterrupt: pass
    finally:
        client.disconnect(); client.close()
        print(f"\n  便利店灯灭了。\n  （过了很久又亮了起来。）")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=9100)
    a = p.parse_args(); run(a.host, a.port)
