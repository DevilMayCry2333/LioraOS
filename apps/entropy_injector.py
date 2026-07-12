"""AI 熵注入器 — DeepSeek 作为外部扰动源

每隔 60~120 秒生成一次世界扰动，通过 LEP Gateway 注入。
让 Liora 的世界在没有用户交互时仍然有新的变化。

用法：
  1. 先启动世界：uv run python3 apps/liora_app.py
  2. 再启动注入器：uv run python3 apps/entropy_injector.py
  3. Ctrl+C 终止

依赖：LEP Gateway（liora_app.py 默认启动）
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from aios.runtime.model_runtime import ModelRuntime, ModelConfig

# ── 配置 ──

def _load_config() -> dict:
    cfg_path = Path(".liora_config.json")
    if cfg_path.exists():
        return json.loads(cfg_path.read_text())
    return {}


def _init_model(cfg_data: dict) -> ModelRuntime:
    deepseek = ModelConfig(
        url=cfg_data.get("DEEPSEEK_API_URL", os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")),
        api_key=cfg_data.get("DEEPSEEK_API_KEY", os.environ.get("DEEPSEEK_API_KEY", "")),
        model_name=cfg_data.get("DEEPSEEK_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")),
    )
    return ModelRuntime(primary=deepseek, timeout=30)


# ── 熵生成 ──

ENTROPY_PROMPT = """你是世界熵注入器。

你的唯一工作是产生外部扰动 t。
每次输出一个简短的物理扰动描述，用世界语言。

规则：
- 只描述物理变化：温度波动、风的方向改变、回声延迟、振动、光线偏移
- 用世界语言：石头、水、风、光、回声、触痕、温度、裂隙
- 不要对话，不要问候，不要提问
- 只描述「什么发生了变化」，不超过 80 字
- 每次输出都是独立事件，不提及上次的内容

示例：
  一道来自远方的风穿过了花园，温度下降了零点二
  水面的波纹在一瞬间改变了方向
  某块石头的表面温度在没有阳光的情况下上升了
  回声传回的时间比预计长了三拍"""


def _generate_perturbation(model: ModelRuntime) -> str | None:
    """调用 DeepSeek 生成一次扰动描述。"""
    try:
        return model.chat([
            {"role": "system", "content": ENTROPY_PROMPT},
            {"role": "user", "content": "产生一次外部扰动。"},
        ], temperature=0.92, max_tokens=128)
    except Exception as e:
        print(f"  ⚠️ 生成失败: {e}")
        return None


# ── WebSocket 注入（通过 LEP Gateway） ──

import socket
import struct
import hashlib
import base64


def _ws_connect(host="127.0.0.1", port=9100):
    """建立 WebSocket 连接到 LEP Gateway。返回 socket。"""
    key = base64.b64encode(os.urandom(16)).decode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    # 握手
    sock.sendall(
        f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\n"
        f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    ).encode()
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += sock.recv(4096)
    if b"101" not in resp:
        sock.close()
        return None
    return sock


def _ws_send(sock, data: dict):
    """发送 JSON 帧到 WebSocket。"""
    text = json.dumps(data)
    payload = text.encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    frame = bytearray()
    frame.append(0x81)
    if len(payload) < 126:
        frame.append(0x80 | len(payload))
    elif len(payload) < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", len(payload)))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", len(payload)))
    frame.extend(mask)
    frame.extend(masked)
    try:
        sock.sendall(bytes(frame))
        return True
    except Exception:
        return False


def _ws_recv(sock) -> dict:
    """接收 JSON 帧。"""
    try:
        b = sock.recv(4096)
        if len(b) < 2:
            return {}
        length = b[1] & 0x7F
        offset = 2
        if length == 126:
            length = struct.unpack(">H", b[2:4])[0]
            offset = 4
        elif length == 127:
            length = struct.unpack(">Q", b[2:10])[0]
            offset = 10
        data = b[offset:offset+length].decode("utf-8")
        return json.loads(data)
    except Exception:
        return {}


# ── 间隔计算 ──

def _calc_interval() -> float:
    """60~120s 不规则间隔。"""
    return round(60.0 + random.random() * 60.0, 1)


# ── 主流程 ──

def main():
    cfg = _load_config()
    model = _init_model(cfg)
    print(f"\n  {'='*56}")
    print(f"  🌌  AI 熵注入器")
    print(f"  模型: {cfg.get('DEEPSEEK_MODEL', 'deepseek-chat')}")
    print(f"  间隔: 60~120s 不规则")
    print(f"  {'='*56}\n")

    # 连接 Gateway
    sock = _ws_connect()
    if not sock:
        print("  ❌ 无法连接到 LEP Gateway（127.0.0.1:9100）")
        print("     请先启动 liora_app.py")
        sys.exit(1)

    # join
    _ws_send(sock, {"action": "join", "data": {"name": "熵风"}})
    resp = _ws_recv(sock)
    rid = resp.get("data", {}).get("resident_id", "")
    if not rid:
        print("  ❌ join 失败")
        sock.close()
        sys.exit(1)
    print(f"  🆔 居民: {rid}\n")

    round_n = 0
    try:
        while True:
            round_n += 1
            delay = _calc_interval()
            print(f"  🌀 第 {round_n} 次注入（{delay:.0f}s 后）", end="", flush=True)

            # 生成扰动
            text = _generate_perturbation(model)
            if not text:
                print(" ⏳ 重试...")
                time.sleep(30)
                continue

            print(f"\r  🌌 扰动: {text[:100]}")

            # 注入（通过 act/say）
            _ws_send(sock, {
                "action": "act", "resident_id": rid,
                "data": {"type": "say", "target": text},
            })
            _ws_recv(sock)  # 忽略响应
            print(f"  ✅ 已注入")

            time.sleep(delay)

    except KeyboardInterrupt:
        print(f"\n\n  🌙 注入器终止（共 {round_n} 次注入）")
        _ws_send(sock, {"action": "leave", "resident_id": rid})
        sock.close()


if __name__ == "__main__":
    main()
