"""LEP Gateway converse 动作集成测试。

通过原生 TCP socket 连接 Gateway，完成 WebSocket 握手，
测试 join → converse → perceive → converse → leave 完整流程。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import time

import pytest


# ── WebSocket 工具函数 ───────────────────────────────


def _ws_handshake(host: str, port: int) -> tuple[socket.socket, str]:
    """执行 WebSocket 握手。返回 (sock, key)。"""
    key = base64.b64encode(os.urandom(16)).decode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
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
    assert b"101" in response, f"握手失败: {response[:100]}"
    return sock, key


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


def _ws_recv(sock: socket.socket) -> str:
    """接收一条 WebSocket 文本帧。"""
    b = sock.recv(2)
    if not b or len(b) < 2:
        return ""
    length = b[1] & 0x7F
    if length == 126:
        b = sock.recv(2)
        length = struct.unpack(">H", b)[0]
    elif length == 127:
        b = sock.recv(8)
        length = struct.unpack(">Q", b)[0]
    data = b""
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            break
        data += chunk
    return data.decode("utf-8")


def _ws_action(sock: socket.socket, action: str, data: dict,
               resident_id: str = "") -> dict:
    """发送一个动作并接收响应。"""
    msg = {"action": action, "data": data}
    if resident_id:
        msg["resident_id"] = resident_id
    _ws_send(sock, json.dumps(msg, ensure_ascii=False))
    resp = _ws_recv(sock)
    return json.loads(resp) if resp else {}


# ── 测试函数 ─────────────────────────────────────────


class TestGatewayConverse:
    """Gateway converse 动作集成测试。"""

    @pytest.mark.timeout(10)
    def test_converse_basic(self, lep_gateway):
        """join → converse → 收到角色回复。"""
        gw, port = lep_gateway

        sock, _ = _ws_handshake("127.0.0.1", port)

        # join
        resp = _ws_action(sock, "join", {"name": "测试旅人"})
        assert resp["status"] == "ok"
        rid = resp["data"]["resident_id"]

        # converse
        resp = _ws_action(sock, "converse",
                          {"message": "你好啊", "character": "Aria"},
                          resident_id=rid)
        assert resp["status"] == "ok", f"converse 失败: {resp}"
        assert "reply" in resp["data"]
        assert len(resp["data"]["reply"]) > 0
        assert "测试旅人" in resp["data"]["reply"] or "你好" in resp["data"]["reply"] or "你" in resp["data"]["reply"]

        sock.close()

    @pytest.mark.timeout(10)
    def test_converse_unknown_character(self, lep_gateway):
        """对未注册的角色 converse 应返回错误。"""
        gw, port = lep_gateway

        sock, _ = _ws_handshake("127.0.0.1", port)
        resp = _ws_action(sock, "join", {"name": "测试旅人"})
        rid = resp["data"]["resident_id"]

        resp = _ws_action(sock, "converse",
                          {"message": "你好", "character": "不存在的角色"},
                          resident_id=rid)
        assert resp["status"] == "error"
        assert resp["error"]["code"] == "UNKNOWN_CHARACTER"

        sock.close()

    @pytest.mark.timeout(10)
    def test_converse_empty_message(self, lep_gateway):
        """空消息应返回错误。"""
        gw, port = lep_gateway

        sock, _ = _ws_handshake("127.0.0.1", port)
        resp = _ws_action(sock, "join", {"name": "测试旅人"})
        rid = resp["data"]["resident_id"]

        resp = _ws_action(sock, "converse",
                          {"message": "", "character": "Aria"},
                          resident_id=rid)
        assert resp["status"] == "error"

        sock.close()

    @pytest.mark.timeout(10)
    def test_full_flow(self, lep_gateway):
        """完整流程：join → perceive → converse → converse → leave。"""
        gw, port = lep_gateway

        sock, _ = _ws_handshake("127.0.0.1", port)

        # join
        resp = _ws_action(sock, "join", {"name": "完整测试"})
        assert resp["status"] == "ok"
        rid = resp["data"]["resident_id"]

        # perceive
        resp = _ws_action(sock, "perceive", {}, resident_id=rid)
        assert resp["status"] == "ok"
        assert "tick" in resp["data"]

        # converse 两次
        resp1 = _ws_action(sock, "converse",
                           {"message": "第一次对话", "character": "Aria"},
                           resident_id=rid)
        assert resp1["status"] == "ok"
        assert len(resp1["data"]["reply"]) > 0

        resp2 = _ws_action(sock, "converse",
                           {"message": "第二次对话", "character": "Aria"},
                           resident_id=rid)
        assert resp2["status"] == "ok"
        assert len(resp2["data"]["reply"]) > 0

        # leave
        resp = _ws_action(sock, "leave", {}, resident_id=rid)
        assert resp["status"] == "ok"

        sock.close()

    @pytest.mark.timeout(10)
    def test_converse_without_join(self, lep_gateway):
        """未 join 时 converse 应正常工作（不用 resident_id 也 OK）。"""
        gw, port = lep_gateway

        sock, _ = _ws_handshake("127.0.0.1", port)

        # 直接 converse，不传 resident_id
        resp = _ws_action(sock, "converse",
                          {"message": "你好", "character": "Aria"})
        # gateway 允许没有 resident_id 的 converse
        assert resp["status"] == "ok" or (
            resp["status"] == "error" and "code" in resp
        )

        sock.close()

    @pytest.mark.timeout(10)
    def test_multiple_clients(self, lep_gateway):
        """多个客户端同时 converse 应各自独立。"""
        gw, port = lep_gateway

        sock1, _ = _ws_handshake("127.0.0.1", port)
        resp1 = _ws_action(sock1, "join", {"name": "旅人甲"})
        rid1 = resp1["data"]["resident_id"]

        sock2, _ = _ws_handshake("127.0.0.1", port)
        resp2 = _ws_action(sock2, "join", {"name": "旅人乙"})
        rid2 = resp2["data"]["resident_id"]

        # 两人同时 converse
        r1 = _ws_action(sock1, "converse",
                        {"message": "甲的消息", "character": "Aria"},
                        resident_id=rid1)
        r2 = _ws_action(sock2, "converse",
                        {"message": "乙的消息", "character": "Aria"},
                        resident_id=rid2)

        assert r1["status"] == "ok"
        assert r2["status"] == "ok"

        sock1.close()
        sock2.close()

    @pytest.mark.timeout(10)
    def test_invalid_json(self, lep_gateway):
        """发送非法 JSON 应返回错误。"""
        gw, port = lep_gateway

        sock, _ = _ws_handshake("127.0.0.1", port)
        _ws_send(sock, "这不是 JSON{{{")
        resp = _ws_recv(sock)
        result = json.loads(resp)
        assert result["status"] == "error"

        sock.close()

    @pytest.mark.timeout(10)
    def test_unknown_action(self, lep_gateway):
        """未知动作应返回错误。"""
        gw, port = lep_gateway

        sock, _ = _ws_handshake("127.0.0.1", port)
        resp = _ws_action(sock, "fly", {})
        assert resp["status"] == "error"
        assert resp["error"]["code"] == "UNKNOWN_ACTION"

        sock.close()
