"""竹隐谷 — 通过 LEP 连接 Kernel 的外部世界示例。

不导入 aios/ 中的任何模块。只使用 stdlib WebSocket。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import socket
import struct
import time
import uuid


# ════════════════════════════════════════════════════════════════
# WebSocket 工具（纯 stdlib）
# ════════════════════════════════════════════════════════════════


def _ws_connect(host: str, port: int) -> socket.socket:
    """执行 WebSocket 握手，返回已连接的 socket。"""
    key = _b64encode(os.urandom(16))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))

    http_upgrade = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(http_upgrade.encode())
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
    if b"101" not in response:
        raise ConnectionError(f"WebSocket 握手失败: {response[:100]}")
    return sock


def _b64encode(data: bytes) -> str:
    """base64 编码（不带 = 填充）。"""
    b64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    result = []
    i = 0
    while i < len(data):
        if i + 3 <= len(data):
            chunk = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
            result.append(b64_chars[(chunk >> 18) & 0x3F])
            result.append(b64_chars[(chunk >> 12) & 0x3F])
            result.append(b64_chars[(chunk >> 6) & 0x3F])
            result.append(b64_chars[chunk & 0x3F])
            i += 3
        else:
            remaining = data[i:]
            chunk = remaining[0] << 16
            if len(remaining) > 1:
                chunk |= remaining[1] << 8
            result.append(b64_chars[(chunk >> 18) & 0x3F])
            result.append(b64_chars[(chunk >> 12) & 0x3F])
            if len(remaining) > 1:
                result.append(b64_chars[(chunk >> 6) & 0x3F])
            else:
                result.append("=")
            result.append("=")
            i = len(data)
    return "".join(result)


def _ws_send(sock: socket.socket, text: str):
    """发送一条掩码的 WebSocket 文本帧。"""
    data = text.encode("utf-8")
    mask_key = os.urandom(4)
    masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
    length = len(data)
    frame = bytearray()
    frame.append(0x81)  # FIN + text
    if length < 126:
        frame.append(0x80 | length)
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", length))
    frame.extend(mask_key)
    frame.extend(masked)
    sock.sendall(bytes(frame))


def _ws_recv(sock: socket.socket) -> Optional[str]:
    """接收一条 WebSocket 文本帧。

    Returns:
        文本内容，连接关闭返回 None
    """
    try:
        b = sock.recv(2)
    except socket.timeout:
        return ""
    if not b or len(b) < 2:
        return None
    length = b[1] & 0x7F
    if length == 126:
        b = sock.recv(2)
        length = struct.unpack(">H", b)[0]
    elif length == 127:
        b = sock.recv(8)
        if len(b) < 8:
            return None
        length = struct.unpack(">Q", b)[0]
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            return None
        data += chunk
    return data.decode("utf-8")


# ════════════════════════════════════════════════════════════════
# LEP 客户端
# ════════════════════════════════════════════════════════════════


class LEPClient:
    """LEP 协议客户端。

    不依赖任何外部库。通过 WebSocket 与 Liora Kernel 通信。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9100):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None
        self.world_id: str = ""
        self.world_name: str = ""
        self.current_tick: int = 0

    def connect(self) -> bool:
        """连接到 LEP Kernel。"""
        try:
            self._sock = _ws_connect(self.host, self.port)
            self._sock.settimeout(30)
            return True
        except (ConnectionRefusedError, OSError, ConnectionError) as e:
            print(f"  ❌ 连接失败: {e}")
            return False

    def send(self, action: str, data: dict = None,
             require_world_id: bool = False) -> Optional[dict]:
        """发送一个 LEP action 并等待响应。

        Args:
            action: LEP 动作名
            data: 动作数据
            require_world_id: 是否自动附加 world_id

        Returns:
            响应 dict，或 None（连接断开）
        """
        msg = {"action": action, "data": data or {}}
        if require_world_id and self.world_id:
            msg["world_id"] = self.world_id
        try:
            _ws_send(self._sock, json.dumps(msg, ensure_ascii=False))
            resp_text = _ws_recv(self._sock)
            if resp_text is None:
                return None
            if resp_text == "":
                return None
            return json.loads(resp_text)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  ⚠️  发送失败 ({action}): {e}")
            return None

    def register_world(self, name: str, description: str = "",
                       state_variables: dict = None,
                       characters: list[str] = None) -> bool:
        """注册世界到 Kernel。"""
        self.world_name = name
        resp = self.send("world.register", {
            "name": name,
            "description": description,
            "state_variables": state_variables or {},
            "characters": characters or [],
        })
        if resp and resp.get("status") == "ok":
            self.world_id = resp["data"]["world_id"]
            self.current_tick = resp["data"].get("tick", 0)
            return True
        print(f"  ❌ 世界注册失败: {resp}")
        return False

    def publish_state(self, tick: int, state: dict) -> bool:
        """发布世界状态。"""
        resp = self.send("state.publish", {
            "tick": tick,
            "state": state,
        }, require_world_id=True)
        return resp is not None and resp.get("status") == "ok"

    def query_state(self, target_world: str) -> Optional[dict]:
        """查询其他世界状态。"""
        resp = self.send("state.query", {
            "target_world": target_world,
        }, require_world_id=True)
        if resp and resp.get("status") == "ok":
            return resp["data"]
        return None

    def list_worlds(self) -> list[dict]:
        """列出所有已注册的世界。"""
        resp = self.send("state.list", {})
        if resp and resp.get("status") == "ok":
            return resp["data"].get("worlds", [])
        return []

    def publish_event(self, event_type: str, description: str,
                      intensity: float = 0.5) -> Optional[str]:
        """发布世界事件。返回 event_id。"""
        resp = self.send("event.publish", {
            "event_type": event_type,
            "description": description,
            "intensity": intensity,
        }, require_world_id=True)
        if resp and resp.get("status") == "ok":
            return resp["data"].get("event_id")
        return None

    def subscribe(self, source_world: str) -> bool:
        """订阅其他世界的事件。"""
        resp = self.send("event.subscribe", {
            "source_world": source_world,
        }, require_world_id=True)
        return resp is not None and resp.get("status") == "ok"

    def send_resident_message(self, to: str, target_world: str,
                              content: str) -> bool:
        """向其他世界的居民发送消息。"""
        resp = self.send("resident.message", {
            "from": to,
            "target_world": target_world,
            "content": content,
        }, require_world_id=True)
        return resp is not None and resp.get("status") == "ok"

    def publish_dialogue(self, speaker: str, text: str, tick: int = 0,
                          state: dict = None, phase: str = "", day: int = 0,
                          hour: float = 0, context: str = "") -> bool:
        """发布对话记录到数据收集器（可选，不阻塞世界运行）。"""
        resp = self.send("dialogue.publish", {
            "speaker": speaker, "text": text, "tick": tick,
            "state": state or {}, "phase": phase, "day": day, "hour": hour,
            "context": context,
        }, require_world_id=True)
        return resp is not None and resp.get("status") == "ok"

    def heartbeat(self) -> bool:
        """发送存活信号。"""
        resp = self.send("world.heartbeat", {},
                         require_world_id=True)
        return resp is not None and resp.get("status") == "ok"

    def disconnect(self):
        """优雅断开连接。"""
        self.send("world.disconnect", {}, require_world_id=True)

    def recv_push(self, timeout: float = 1.0) -> Optional[dict]:
        """接收来自 Kernel 的推送消息。

        Args:
            timeout: 超时秒数（None = 阻塞）

        Returns:
            推送消息 dict，超时返回空 dict""，断开返回 None
        """
        if self._sock:
            self._sock.settimeout(timeout)
        try:
            text = _ws_recv(self._sock)
        except socket.timeout:
            return {}
        if text is None:
            return None
        if text == "":
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def close(self):
        """关闭连接。"""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


# ════════════════════════════════════════════════════════════════
# 竹隐谷 — 外部世界
# ════════════════════════════════════════════════════════════════

# 状态变量默认值
DEFAULT_STATE = {
    "wind": 0.3,       # 风速
    "fog": 0.5,        # 雾的浓度
    "hum": 0.2,        # 竹林共振嗡鸣
}


def evolve(state: dict, tick: int) -> dict:
    """演化公式：返回 {变量名: delta}。"""
    wind = state.get("wind", 0.3)
    fog = state.get("fog", 0.5)
    hum = state.get("hum", 0.2)
    return {
        "wind": (0.3 - wind) * 0.02 + random.uniform(-0.02, 0.02),
        "fog": (0.5 - fog) * 0.01 - wind * 0.01,
        "hum": (0.5 - hum) * 0.005 + wind * 0.01,
    }


def describe(state: dict) -> str:
    """世界状态 → 自然语言描述。"""
    wind = state.get("wind", 0.3)
    fog = state.get("fog", 0.5)
    lines = ["竹隐谷中，薄雾在林间游弋。"]
    if fog > 0.7:
        lines[-1] = "雾气浓重，三米外的竹影几乎融进白色里。"
    elif fog < 0.3:
        lines[-1] = "雾散了，阳光透过竹叶洒下斑驳的光点。"
    if wind > 0.6:
        lines.append("风很大，竹梢剧烈摇摆。")
    elif wind < 0.2:
        lines.append("风停了，竹林陷入寂静。")
    return " ".join(lines)


def generate_event(state: dict, tick: int) -> Optional[tuple[str, str, float]]:
    """世界事件。返回 (event_type, description, intensity) 或 None。"""
    if tick > 0 and tick % 5 == 0:
        wind = state.get("wind", 0.3)
        if wind > 0.6:
            return ("wind_gust", "一阵强风穿过竹林，竹节剧烈碰撞。", wind)
    return None


# ── 角色对话 ──

CHARACTER_REPLIES: dict[str, list[tuple[str, list[str]]]] = {
    "竹翁": [
        ("wind_high", [
            "风在说你的名字。你听到了吗？",
            "竹子在摇晃，它们在传递什么消息。",
            "这样的风里，适合闭上眼睛听。",
        ]),
        ("wind_low", [
            "风停了。世界安静得像在等待什么。",
            "没有风的时候，你能听见竹节生长的声音。",
            "沉默也是语言，只是大多数人听不懂。",
        ]),
        ("fog_high", [
            "雾里有东西在移动。不是动物，是更老的东西。",
            "你看不清路？那就别看了。用耳朵。",
            "每一片雾都藏着一句被忘记的话。",
        ]),
        ("fog_low", [
            "雾散了，你的影子又回来了。",
            "阳光照进来，竹影在地上像是一幅字。",
            "清楚的世界让人安心，但也让人不再倾听。",
        ]),
        ("default", [
            "竹节在低声交谈。它们说的事情，人类要很久之后才会知道。",
            "你踩在落叶上的声音，比你想说的任何话都真实。",
            "时间在竹林里走得很慢。慢到你能看见它的脚印。",
            "我听了一辈子竹子的声音，现在它们开始说你的名字了。",
        ]),
    ],
}


def speak(character: str, state: dict) -> str:
    """根据世界状态生成角色发言。"""
    pool = CHARACTER_REPLIES.get(character, CHARACTER_REPLIES.get("竹翁", {}))
    wind = state.get("wind", 0.3)
    fog = state.get("fog", 0.5)

    # 选择匹配当前状态的回复池
    candidates = []
    for condition, replies in pool:
        if condition == "default":
            continue
        if condition == "wind_high" and wind > 0.5:
            candidates.extend(replies)
        elif condition == "wind_low" and wind < 0.25:
            candidates.extend(replies)
        elif condition == "fog_high" and fog > 0.6:
            candidates.extend(replies)
        elif condition == "fog_low" and fog < 0.35:
            candidates.extend(replies)

    # 兜底用默认回复
    for condition, replies in pool:
        if condition == "default":
            candidates.extend(replies)

    return random.choice(candidates) if candidates else "……"


def reply_to_message(msg_content: str, character: str) -> str:
    """对收到的消息生成回复。"""
    triggers = {
        "你好": "你好。竹子在替我问你，你从哪里来？",
        "你是谁": "我是竹翁。这片竹林里最老的那棵竹子——只不过我会说话。",
        "竹子": "每一棵竹子都是同一个生命的不同分岔。和你们人类一样。",
        "风": "风是最好的信使。它不偷听，它只是路过。",
        "沉默": "沉默不是空。沉默是满的，只是你还没打开它。",
        "雾": "雾是竹林的梦境。你现在也在我的梦里。",
        "谢谢": "不用谢。你说话的时候，竹子们在听。下次可以带壶酒来。",
        "再见": "再见。如果你迷路了，就听风的方向。",
    }
    for keyword, reply_text in triggers.items():
        if keyword in msg_content:
            return reply_text
    return random.choice([
        "嗯。竹子在点头。",
        "你说话的方式，让我想起很多年以前的一个人。",
        "你继续说，我在听。",
        "竹叶动了一下。那是竹林在回应你。",
    ])


# ════════════════════════════════════════════════════════════════
# 主循环
# ════════════════════════════════════════════════════════════════


def run_world(name: str, kernel_host: str = "127.0.0.1",
              kernel_port: int = 9100, characters: list[str] = None,
              interactive: bool = True):
    """启动外部世界的主循环。

    Args:
        name: 世界名称
        kernel_host: Kernel 地址
        kernel_port: Kernel LEP 端口
        characters: 角色列表
        interactive: 是否启用 CLI 输入
    """
    characters = characters or ["竹翁"]
    state = dict(DEFAULT_STATE)
    tick = 0
    heartbeat_interval = 15
    speak_interval = 5  # 每 N tick 角色自主发言
    last_speak_tick = 0

    client = LEPClient(host=kernel_host, port=kernel_port)
    if not client.connect():
        return

    # 注册世界
    if not client.register_world(
        name=name,
        description="一片被雾气笼罩的竹林，竹子会低声交谈。",
        state_variables=state,
        characters=characters,
    ):
        client.close()
        return

    # 订阅其他世界的事件（由 --subscribe 指定，在入口处处理）
    # 通过 state.list 发现其他世界并订阅

    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║  🌍 {name}")
    print(f"  ║  👥 {', '.join(characters)}")
    print(f"  ║  🔗 ws://{kernel_host}:{kernel_port}")
    print(f"  ╚══════════════════════════════════════╝")
    print(f"  直接输入文字和角色对话，输入 /quit 离开")
    print()

    # CLI 输入线程
    import threading as _threading
    input_queue: list[str] = []
    input_lock = _threading.Lock()

    def _input_loop():
        while True:
            try:
                line = input()
                with input_lock:
                    input_queue.append(line)
            except (EOFError, KeyboardInterrupt):
                break

    if interactive:
        _threading.Thread(target=_input_loop, daemon=True).start()

    # 可选：发现并订阅其他世界（仅在 --subscribe 指定时）
    if getattr(run_world, '_auto_discover', False):
        worlds = client.list_worlds()
        for w in worlds:
            if w["name"] != name:
                client.subscribe(w["name"])
                print(f"  📡 订阅世界: {w['name']}")

    try:
        while True:
            # 接收 Kernel 推送
            push = client.recv_push(timeout=0.3)
            if push is None:
                print(f"\n  ⚠️  Kernel 断开连接")
                break

            # ── 处理用户输入 ──
            user_input = ""
            with input_lock:
                if input_queue:
                    user_input = input_queue.pop(0)

            if user_input:
                if user_input.lower() in ("/quit", "/exit", "/q"):
                    break
                elif user_input.lower() == "/state":
                    print(f"  📊 状态: wind={state['wind']:.2f} "
                          f"fog={state['fog']:.2f} hum={state['hum']:.2f}")
                elif user_input.startswith("/say ") and "/" in user_input[5:]:
                    # /say <world> <message> — 跨世界消息
                    parts = user_input[5:].strip().split(" ", 1)
                    if len(parts) == 2:
                        target_world, msg = parts
                        ok = client.send_resident_message(
                            characters[0], target_world, msg)
                        print(f"  📤 → {target_world}: {'✓' if ok else '✗'}")
                else:
                    # 本地对话：用户说话 → 角色回复
                    reply_text = reply_to_message(user_input, characters[0])
                    print(f"\n  🧑 你: {user_input}")
                    print(f"  🎭 {characters[0]}: {reply_text}\n")

            # ── tick 处理 ──
            if push and push.get("action") == "tick":
                tick += 1
                # 演化
                delta = evolve(state, tick)
                for k, v in delta.items():
                    if k in state:
                        new_val = state[k] + v
                        state[k] = max(0.0, min(1.0, new_val))
                # 发布状态
                client.publish_state(tick, state)

                # 世界描述（每 3 tick）
                if tick % 3 == 0:
                    desc = describe(state)
                    print(f"  [tick {tick}] {desc}")

                # 世界事件（每 5 tick）
                event = generate_event(state, tick)
                if event:
                    eid = client.publish_event(*event)
                    if eid:
                        print(f"  🌪️  {event[1][:40]}...")

                # 角色自主发言（每 5 tick）
                if tick - last_speak_tick >= speak_interval:
                    last_speak_tick = tick
                    for char in characters:
                        utterance = speak(char, state)
                        print(f"  🎭 {char}: {utterance}")

                # Heartbeat（每 15 tick）
                if tick % heartbeat_interval == 0:
                    client.heartbeat()

            # ── 其他世界的事件 ──
            elif push and push.get("action") == "world.event":
                evt = push.get("data", {})
                print(f"  📡 [{evt.get('source_world', '?')}] "
                      f"{evt.get('description', '')[:60]}")

            # ── 跨世界居民消息 ──
            elif push and push.get("action") == "resident.incoming":
                msg = push.get("data", {})
                sender = msg.get("from", "?")
                source = msg.get("source_world", "?")
                content = msg.get("content", "")
                print(f"\n  📩 {sender}({source}): {content}")
                # 自动回复
                reply_text = reply_to_message(content, characters[0])
                client.send_resident_message(characters[0], source, reply_text)
                print(f"  📩 {characters[0]} → {source}: {reply_text}\n")

    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.close()
        print(f"\n  🌙 {name} 已断开。运行 {tick} tick。")


# ════════════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="竹隐谷 — LEP 外部世界示例")
    parser.add_argument("--name", default="竹隐谷", help="世界名称")
    parser.add_argument("--host", default="127.0.0.1", help="Kernel 地址")
    parser.add_argument("--port", type=int, default=9100, help="Kernel LEP 端口")
    parser.add_argument("--discover", action="store_true",
                        help="自动发现并订阅其他世界（默认不订阅）")
    parser.add_argument("--subscribe", default="",
                        help="订阅事件的世界名称（逗号分隔）")
    args = parser.parse_args()

    if args.discover:
        run_world._auto_discover = True
    run_world(args.name, args.host, args.port)
