"""石牌村工作室 1998 — 五人工坊世界。"""

from __future__ import annotations
import random, sys, time, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from examples.external_world.bamboo_grove import LEPClient

WORLD_NAME = "石牌村工作室"
CHARACTERS = ["林岸", "阿正", "小周", "老刘", "阿柠"]

DEFAULT_STATE = {
    "bug_count": 12, "cpu_temp": 72, "deadline": 30, "coffee_level": 0.8,
    "hour": 9, "day": 1, "phase": "morning",
}

PHASE_LABELS = {(9,12): "morning", (12,13): "lunch", (13,18): "afternoon",
                (18,19): "dinner", (19,22): "afterwork", (22,24): "late", (0,9): "overnight"}

def resolve_phase(h: int) -> str:
    for (lo, hi), label in PHASE_LABELS.items():
        if lo <= h < hi: return label
    return "overnight"

def evolve(state: dict, tick: int) -> dict:
    b, c, d, f, h = state["bug_count"], state["cpu_temp"], state["deadline"], state["coffee_level"], state["hour"]
    p = resolve_phase(h)
    r = {"hour": 1}
    if p in ("morning", "afternoon"):
        r.update({"bug_count": random.uniform(-0.5, 1.5), "cpu_temp": random.uniform(-1, 3), "deadline": -1.0, "coffee_level": -0.05})
    elif p == "lunch": r.update({"coffee_level": 0.02, "cpu_temp": -2})
    elif p == "dinner": r.update({"coffee_level": 0.03, "cpu_temp": -3})
    elif p in ("afterwork", "late"): r["cpu_temp"] = -1
    if b > 20: r["cpu_temp"] = r.get("cpu_temp", 0) + 2
    if d < 5 and p in ("morning", "afternoon"):
        r["coffee_level"] = r.get("coffee_level", 0) - 0.1; r["bug_count"] = r.get("bug_count", 0) + 0.5
    if f < 0.2 and p in ("morning", "afternoon"): r["bug_count"] = r.get("bug_count", 0) - 0.2
    return {k: max(-10, min(10, v)) for k, v in r.items()}

def clamp_state(state: dict):
    for k, (lo, hi) in [("bug_count", (0, 50)), ("cpu_temp", (30, 100)), ("deadline", (0, 30)), ("coffee_level", (0.0, 1.0))]:
        state[k] = max(lo, min(hi, state[k]))
    h = int(state["hour"])
    if h >= 24:
        state["hour"] = 9; state["day"] += 1; state["coffee_level"] = 1.0
    else: state["hour"] = h
    state["phase"] = resolve_phase(int(state["hour"]))

DIALOGUE = {
    "林岸": {
        "morning": ["早。昨晚又没睡好。", "打开编辑器之前先让我喝口水。", "昨天那个 bug 我睡前想到怎么修了。", "阿柠来了吗？"],
        "afternoon": ["接口又崩了。不是我的问题。", "这个偏移量我好像在哪里写过。", "硬盘在响了。", "阿柠，release notes 写完了吗？"],
        "lunch": ["你们先去，我再调一下。", "帮我带一份，随便。", "今天楼下那家还开门吗？"],
        "dinner": ["你们先走。", "帮阿柠带一份，她肯定又忘了吃。"],
        "afterwork": ["我再待一会。你们先走。", "这个改完就走。", "门不用锁，我还有钥匙。"],
        "late": ["整栋楼就剩我一个了。", "硬盘的声音在空房间里特别响。", "又一天过去了。"],
    },
    "阿正": {
        "morning": ["早啊，昨晚打游戏打到两点。", "今天活多吗？不多我摸鱼了。"],
        "afternoon": ["后端又崩了，你来前台看看？", "这个表格在 IE 里跑得比 Chrome 好。", "我切个图，五分钟。", "林岸，你的 API 又 502 了。"],
        "lunch": ["吃饭吃饭，饿死了。", "今天吃什么？楼下那家？"],
        "dinner": ["走了，今晚约了人。", "终于下班了。", "拜拜各位，明天见。"],
        "afterwork": ["回家打游戏了。", "今天不加班。"], "late": ["你怎么还在？算了我不问了。"],
    },
    "小周": {
        "morning": ["昨晚看了部电影到两点。", "今天的测试用例写了吗？写了。"],
        "afternoon": ["日志里有一行注释看不懂。", "这个 bug 复现不了。", "我找到 bug 了——林岸你过来看。", "release 前测出三个新的，还发吗？"],
        "lunch": ["吃饭的时候别说 bug。", "今天出去走走。"],
        "dinner": ["回去了，今晚有球赛。", "有谁一起走？"],
        "afterwork": ["今天辛苦大家了。"],
        "late": ["你还不走？那我也不走了——开玩笑的，我走了。"],
    },
    "老刘": {
        "morning": ["早，有个好消息和一个坏消息。", "客户又改需求了。"],
        "afternoon": ["用户想要什么，用户自己不知道。", "这个功能很简单，就一个按钮。", "好吧，当我没说。", "做完了？那再加一个功能。"],
        "lunch": ["我今天约了人。", "边吃边说，我有个想法。"],
        "dinner": ["走了，家里有事。", "今天不加班。", "健康重要。"],
        "afterwork": ["我走了，别给我打电话。", "有什么事明天再说。"],
        "late": ["你还在啊？那我也陪你一会儿。"],
    },
    "阿柠": {
        "morning": ["早。咖啡还有吗？我来泡。", "昨晚又失眠了。", "早上的光最好，适合写东西。"],
        "afternoon": ["别写我，我又不会死。", "release notes 写完了——你们能不能别在最后一刻改需求？", "这个版本叫什么名字好呢。"],
        "lunch": ["你们先吃，我写完这段。", "帮我带个三明治就行。"],
        "dinner": ["文档写完了。现在吃饭。", "晚上的风很舒服，我出去走走。"],
        "afterwork": ["我先走了。", "晚安，别熬太晚。"],
        "late": ["又剩你一个了？", "别写了，明天再写。", "外面的灯都灭了。"],
    },
}

def speak(char: str, state: dict) -> str:
    pool = DIALOGUE.get(char, {}).get(state.get("phase", "morning"), ["..."])
    if not pool: pool = ["..."]
    if char == "林岸" and state["bug_count"] > 15: pool += ["你不要跟我说话，我在修 bug。", "这个 bug 是你们谁引入的？"]
    if char == "阿柠" and state["deadline"] < 5: pool += ["今天不睡了，明天要发版。", "咖啡还有吗？算了，水也行。"]
    return random.choice(pool)

AMBIENT = {
    "morning": "百叶窗缝隙里漏进来几道光。CRT 显示器还在低频嗡鸣。",
    "lunch": "楼下快餐的味道飘上来，混着机箱散热口的焦热空气。",
    "afternoon": "日光灯管的嗡嗡声和风扇声混在一起，成了这间屋子永恒的底噪。",
    "dinner": "天色暗了，五个屏幕的蓝光照着五张脸。",
    "afterwork": "楼下的路灯亮了。安静到能听见硬盘磁头在寻道。",
    "late": "整层楼都黑了，只有这间屋子的灯还亮着。窗外是广州潮湿的夜。",
    "overnight": "凌晨的城市是灰色的。机箱的电源灯在闪。",
}

MOMENTS = [
    ("林岸", "从显示器上方看了一眼阿柠的屏幕。她没有抬头，但他知道她没事。"),
    ("阿柠", "把一张便签贴在林岸的显示器上，画了个箭头指着咖啡杯。三小时后他才看到。"),
    ("阿正", "翻出一个落满灰的游戏机，接上电视。五个人玩了十五分钟实况足球。"),
    ("小周", "站在窗前往外看。有人问他在看什么。他说：在看对面的楼什么时候关灯。"),
    ("老刘", "说：你们觉得二十年后的人会怎么工作？很久之后林岸说：他们会怀念这个风扇的声音。"),
]

WHISPERS = [
    ("林岸", "盯着屏幕皱眉。他打开了一个文件，里面有一行他确定不是自己写的注释。他删掉了。下一行又出现了。"),
    ("林岸", "在代码里搜了一个词。不是变量名，不是函数名，是一个他也不知道为什么会出现在那的词——'便利店'。"),
    ("林岸", "写了一个函数，编译通过。但在他按下保存的那一刻，他清楚地记得自己写的返回值是 0。文件里却写着 1。"),
    ("林岸", "在注释里看到一句话：'不要关机'。他写过这个。在另一块硬盘上。他把它删了。"),
    ("林岸", "屏幕闪了一下。他继续打字——但打出来的字不是他刚才想的。他停了两秒，删掉，重打。"),
]

_cd: dict[str, int] = {}
def can_fire(t: int, k: str) -> bool:
    if k in _cd: return t - _cd[k] > 8
    return True

def world_event(state: dict, tick: int) -> str | None:
    """世界事件：crash / 发版 / bug 危机 / 咖啡耗尽，带冷却和状态重置。"""
    b, c, d, f = state["bug_count"], state["cpu_temp"], state["deadline"], state["coffee_level"]
    p = state["phase"]
    for ev in list(_cd):  # cleanup stale cooldowns
        if tick - _cd[ev] > 15: del _cd[ev]
    if p not in ("morning", "afternoon", "lunch"):  # 非工作时间只有氛围事件
        if p == "late" and can_fire(tick, "night"):
            _cd["night"] = tick
            return random.choice([
                "远处有火车经过的声音。电脑的风扇还在转。",
                "有人在走廊里走了一步，然后停住了。可能是巡夜的保安。也可能是别的。",
                "显示器进入待机模式前闪了一下。在漆黑的房间里，那道光像是一句话。",
            ])
        return None
    if d <= 0 and can_fire(tick, "release"):
        _cd["release"] = tick; state["deadline"] = 30; state["coffee_level"] = 0.8
        state["bug_count"] = max(5, int(b * 0.5)); state["cpu_temp"] = 60
        return random.choice([
            f"发版了。林岸在最后一行加了一行注释：// anchor_47。新版本号：v{state['day']}",
            f"编译通过。阿柠在 release notes 最后写了一句：献给我们也不知道是什么的东西。然后删掉了。",
            f"版本 v{state['day']} 发布了。没有人欢呼。阿正站起来伸了个懒腰，说：明天重写。没有人笑。",
        ])
    if b > 20 and c > 85 and can_fire(tick, "crash"):
        _cd["crash"] = tick; state["cpu_temp"] = 60; state["bug_count"] = max(10, int(b * 0.65))
        return random.choice([
            "服务器宕机了。林岸蹲在机柜前面，阿正在重启。小周在看日志。老刘在给客户打电话。",
            "内存泄漏。所有人都站着等重启。林岸没在等——他在看那行报错。",
            "硬盘灯一直亮着，不闪了。小周说：它死了。林岸说：它没死，它在想事情。",
        ])
    if b > 15 and can_fire(tick, "bugs"):
        _cd["bugs"] = tick
        return random.choice([
            f"bug 数突破 {int(b)}。老刘路过看了一眼说：还行。然后走了。",
            f"代码 review 发现 {int(b)} 个问题。林岸说：先发版，再修。没有人反对。",
        ])
    if f < 0.1 and can_fire(tick, "coffee"):
        _cd["coffee"] = tick
        return random.choice([
            "咖啡壶空了。没有人说话。键盘声也在变小。",
            "阿柠摇了摇咖啡壶——空的。她看了看林岸的杯子，也是空的。她站了起来。去烧水。",
        ])
    if p == "lunch" and can_fire(tick, "lunch"):
        _cd["lunch"] = tick
        return random.choice([
            "大家吃饭的时候没人说话。不是尴尬，是真的太饿了。",
            "阿正一边吃饭一边说：我昨晚梦见自己修好了那个 bug，醒来发现并没有。小周说：那再睡一次。",
        ])
    return None

def room_vibe(state: dict, tick: int) -> str | None:
    if tick % 6 != 0: return None
    ev = world_event(state, tick)
    if ev: return ev
    if random.random() < 0.15: w, m = random.choice(MOMENTS); return f"[{w}] {m}"
    if random.random() < 0.08 and state["phase"] in ("afternoon", "late", "overnight"):
        w, whisper = random.choice(WHISPERS); return f"[{w}] {whisper}"
    return AMBIENT.get(state.get("phase", "afternoon"), "")

def run(kernel_host="127.0.0.1", kernel_port=9100, discover=False):
    state = dict(DEFAULT_STATE)
    tick = 0
    client = LEPClient(host=kernel_host, port=kernel_port)
    if not client.connect():
        print(f"Cannot connect to Kernel at {kernel_host}:{kernel_port}")
        return
    if not client.register_world(WORLD_NAME, "广州石牌村一间租屋，五个人挤在里面写代码。",
                                  state_variables=state, characters=CHARACTERS):
        client.close(); return
    if discover:
        for w in client.list_worlds():
            if w["name"] != WORLD_NAME: client.subscribe(w["name"])
    print(f"\n  == {WORLD_NAME} ==\n  Autonomous: {', '.join(CHARACTERS)}\n")
    try:
        while True:
            push = client.recv_push(timeout=0.3)
            if push is None: break
            if push.get("action") == "tick":
                tick += 1
                for k, v in evolve(state, tick).items():
                    if k in state: state[k] += v
                clamp_state(state)
                client.publish_state(tick, state)
                if tick % 3 == 0:
                    h = int(state["hour"])
                    print(f"  Day {state['day']} {h}:00 | CPU {state['cpu_temp']:.0f}C bugs {state['bug_count']:.0f} coffee {state['coffee_level']:.0%}")
                vibe = room_vibe(state, tick)
                if vibe: print(f"  {vibe}")
                if tick % 5 == 0:
                    w = random.choice(CHARACTERS)
                    print(f"  {w}: {speak(w, state)}")
                if tick == 0 or time.time() - getattr(run, '_last_hb', 0) > 30:
                    run._last_hb = time.time(); client.heartbeat()
            elif push.get("action") == "world.event":
                print(f"  [event] {push['data'].get('description','')[:60]}")
            elif push.get("action") == "resident.incoming":
                msg = push["data"]
                print(f"  [msg] {msg.get('from','?')}: {msg.get('content','')[:50]}")
    except KeyboardInterrupt: pass
    finally: client.disconnect(); client.close(); print(f"\n  {WORLD_NAME} shut down. {tick} ticks.")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=9100)
    p.add_argument("--discover", action="store_true")
    a = p.parse_args(); run(a.host, a.port, a.discover)
