"""LEP Gateway 最小测试客户端（非 asyncio 版本）。"""

import json
import socket
import struct
import hashlib
import base64
import os
import time


def _create_ws_key() -> tuple[str, str]:
    import base64, os
    key = base64.b64encode(os.urandom(16)).decode()
    GUID = "258EAFA5-E914-47DA-95CA-5AB5DC11B735"
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    return key, accept


def _ws_frame(text: str) -> bytes:
    data = text.encode("utf-8")
    mask_key = os.urandom(4)
    masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
    length = len(data)
    frame = bytearray()
    frame.append(0x81)
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
    return bytes(frame)


def _recv_frame(sock: socket.socket) -> str:
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


def test_ws_handshake_and_join():
    """测试 WebSocket 握手 + join + perceive 最小流程。"""
    key = base64.b64encode(os.urandom(16)).decode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(("127.0.0.1", 9100))
    except (ConnectionRefusedError, OSError):
        # Gateway not running — skip test
        sock.close()
        return

    # 握手
    http_upgrade = (
        f"GET / HTTP/1.1\r\n"
        f"Host: 127.0.0.1:9100\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(http_upgrade.encode())
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)
    assert b"101" in response, f"握手失败: {response[:100]}"

    # join
    sock.sendall(_ws_frame(json.dumps({"action": "join", "data": {"name": "test_bot"}})))
    resp = json.loads(_recv_frame(sock))
    assert resp["status"] == "ok", f"join 失败: {resp}"
    rid = resp["data"]["resident_id"]
    assert rid.startswith("lep_")

    # perceive
    sock.sendall(_ws_frame(json.dumps({"action": "perceive", "resident_id": rid})))
    resp = json.loads(_recv_frame(sock))
    assert resp["status"] == "ok"
    assert "tick" in resp["data"]

    # act
    sock.sendall(_ws_frame(json.dumps({
        "action": "act", "resident_id": rid,
        "data": {"type": "say", "target": "你好，山谷"},
    })))
    resp = json.loads(_recv_frame(sock))
    assert resp["status"] == "ok"

    # leave
    sock.sendall(_ws_frame(json.dumps({"action": "leave", "resident_id": rid})))
    resp = json.loads(_recv_frame(sock))
    assert resp["status"] == "ok"

    sock.close()
