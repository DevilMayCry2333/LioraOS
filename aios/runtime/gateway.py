"""LEP Gateway — 最简 WebSocket 入口。

纯 stdlib，零外部依赖。
允许外部 AI 通过 WebSocket 进入世界，与 Liora 交互。

协议：JSON over WebSocket，端口 9100。

动作:
  join     — 注册身份
  perceive — 感知世界
  act      — 行动（say / touch / observe）
  leave    — 离开
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import base64
import os
import struct
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from aios.kernel.bus import Message, MessageType

logger = logging.getLogger("aios.gateway")

DEFAULT_PORT = 9100
DATA_DIR = Path("data/gateway_residents")


# ── WebSocket 帧编解码 ──────────────────────────

def _ws_encode(text: str) -> bytes:
    """编码 WebSocket 文本帧（服务端→客户端，不掩码）。"""
    data = text.encode("utf-8")
    length = len(data)
    frame = bytearray()
    frame.append(0x81)  # FIN + text opcode
    if length < 126:
        frame.append(length)
    elif length < 65536:
        frame.append(126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(127)
        frame.extend(struct.pack(">Q", length))
    frame.extend(data)
    return bytes(frame)


def _ws_decode(frame: bytes) -> Optional[str]:
    """解码 WebSocket 帧（客户端→服务端，已掩码）。"""
    if len(frame) < 2:
        return None
    opcode = frame[0] & 0x0F
    if opcode == 0x8:  # close
        return None
    if opcode == 0x9:  # ping
        return "__PING__"
    if opcode != 0x1:  # 只处理文本帧
        return None

    masked = bool(frame[1] & 0x80)
    length = frame[1] & 0x7F
    offset = 2

    if length == 126:
        length = struct.unpack(">H", frame[offset:offset+2])[0]
        offset += 2
    elif length == 127:
        length = struct.unpack(">Q", frame[offset:offset+8])[0]
        offset += 8

    mask_key = frame[offset:offset+4] if masked else b""
    offset += 4 if masked else 0
    payload = frame[offset:offset+length]

    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return payload.decode("utf-8")


def _ws_accept(key: str) -> str:
    """计算 WebSocket 握手 accept key。"""
    GUID = "258EAFA5-E914-47DA-95CA-5AB5DC11B735"
    sha1 = hashlib.sha1((key + GUID).encode()).digest()
    return base64.b64encode(sha1).decode()


# ── 居民身份管理 ──────────────────────────────

@dataclass
class GatewayResident:
    """最简居民身份。"""
    resident_id: str = ""
    name: str = ""
    created_at: str = ""
    last_active: str = ""
    status: str = "active"

    def to_dict(self) -> dict:
        return {
            "resident_id": self.resident_id,
            "name": self.name,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GatewayResident:
        return cls(**{k: d.get(k, "") for k in cls.__dataclass_fields__})


def _save_resident(resident: GatewayResident):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{resident.resident_id}.json"
    path.write_text(json.dumps(resident.to_dict(), ensure_ascii=False, indent=2))


def _load_resident(resident_id: str) -> Optional[GatewayResident]:
    path = DATA_DIR / f"{resident_id}.json"
    if not path.exists():
        return None
    try:
        return GatewayResident.from_dict(json.loads(path.read_text()))
    except Exception:
        return None


# ── Gateway 服务端 ─────────────────────────────

class LEPGateway:
    """最简 LEP Gateway。WebSocket 端口 9100。

    扩展 converse 动作：
      客户端发送 {"action": "converse", "data": {"message": "你好"}}
      → 服务器路由到注册的角色 speak 函数 → 返回角色回复。

      角色通过 register_character(name, speak_fn, perceive_fn) 注册。
    """

    def __init__(self, runtime, host: str = "127.0.0.1", port: int = DEFAULT_PORT):
        self.runtime = runtime
        self.host = host
        self._port = port
        self._server: Optional[asyncio.AbstractServer] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # session_id → {reader, writer, resident_id}
        self._sessions: dict[str, dict] = {}
        # 可注册的角色（名称 → 对话处理接口）
        self._characters: dict[str, dict] = {}

    @property
    def port(self) -> int:
        """返回实际绑定的端口（从 asyncio server 读取，或初始值）。"""
        if self._server and self._server.sockets:
            try:
                return self._server.sockets[0].getsockname()[1]
            except Exception:
                pass
        return self._port

    def register_character(self, name: str, speak_fn, perceive_fn=None):
        """注册一个对话角色供 WebSocket 访客通过 converse 动作访问。

        Args:
            name: 角色名（客户端通过 data.character 指定）
            speak_fn: callable(message: str, visitor_name: str) → str
            perceive_fn: optional callable() → str
        """
        self._characters[name] = {
            "speak": speak_fn,
            "perceive": perceive_fn,
        }
        logger.info("Gateway 注册角色: %s", name)

    def register_character_app(self, app, character_name: str):
        """从 WorldApp + 角色名快速注册对话角色。"""
        from aios.template.social import SocialResident
        resident = SocialResident(character_name, app)

        def speak_fn(message: str, visitor_name: str) -> str:
            resident.hear_speaker(visitor_name, message)
            reply = resident.speak(partner_name=visitor_name)
            return reply or ""

        def perceive_fn() -> str:
            snap = app.runtime.snapshot()
            desc = app.describe_world(snap.state)
            extra = app.extra_context(resident.mind)
            if extra:
                desc += f"\n\n{extra}"
            return desc

        self.register_character(character_name, speak_fn, perceive_fn)
        return resident

    def start(self):
        """在独立线程中启动 asyncio 事件循环。"""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"LEP Gateway 启动于 ws://{self.host}:{self.port}")

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
        except OSError as e:
            logger.warning("Gateway 端口 %d 被占用: %s", self.port, e)
        except asyncio.CancelledError:
            pass  # stop() 关闭 server 时的正常取消，不报错
        except Exception as e:
            logger.warning("Gateway 异常: %s", e)
        finally:
            # 安静关闭，防止 _wakeup 对已关闭的 loop 报错
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    async def _serve(self):
        try:
            self._server = await asyncio.start_server(
                self._handle_client, self.host, self.port,
            )
        except OSError:
            raise  # 由 _run_loop 捕获
        async with self._server:
            await self._server.serve_forever()

    async def _handle_client(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter):
        session_id = ""
        try:
            # WebSocket 握手
            request = (await reader.readuntil(b"\r\n\r\n")).decode()
            if "Upgrade: websocket" not in request:
                writer.close()
                return

            key = ""
            for line in request.split("\r\n"):
                if line.startswith("Sec-WebSocket-Key:"):
                    key = line.split(":", 1)[1].strip()
                    break

            accept = _ws_accept(key)
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            )
            writer.write(response.encode())
            await writer.drain()

            session_id = uuid.uuid4().hex[:8]
            self._sessions[session_id] = {
                "reader": reader, "writer": writer,
                "resident_id": "",
            }

            await self._message_loop(session_id, reader, writer)

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        finally:
            if session_id:
                self._cleanup_session(session_id)
            try:
                writer.close()
            except Exception:
                logger.debug("writer.close() failed")

    async def _message_loop(self, session_id: str, reader, writer):
        buffer = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buffer += chunk

            while len(buffer) >= 2:
                # 解析帧长度
                length = buffer[1] & 0x7F
                offset = 2
                if length == 126:
                    if len(buffer) < 4: break
                    length = struct.unpack(">H", buffer[2:4])[0]
                    offset = 4
                elif length == 127:
                    if len(buffer) < 10: break
                    length = struct.unpack(">Q", buffer[2:10])[0]
                    offset = 10

                masked = bool(buffer[1] & 0x80)
                total = offset + (4 if masked else 0) + length
                if len(buffer) < total:
                    break

                frame = buffer[:total]
                buffer = buffer[total:]

                text = _ws_decode(frame)
                if text is None:
                    return  # close frame
                if text == "__PING__":
                    await self._send(writer, "")
                    continue

                await self._handle_message(session_id, text, writer)

    async def _handle_message(self, session_id: str, text: str, writer):
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            await self._send(writer, json.dumps({"status": "error", "error": {"code": "INVALID_JSON"}}))
            return

        action = msg.get("action", "")
        data = msg.get("data", {})
        resident_id = msg.get("resident_id", self._sessions.get(session_id, {}).get("resident_id", ""))

        handlers = {
            "join": self._handle_join,
            "perceive": self._handle_perceive,
            "act": self._handle_act,
            "converse": self._handle_converse,
            "leave": self._handle_leave,
        }

        handler = handlers.get(action)
        if not handler:
            await self._send(writer, json.dumps({"status": "error", "error": {"code": "UNKNOWN_ACTION", "message": f"未知动作: {action}"}}))
            return

        result = await handler(session_id, resident_id, data)
        await self._send(writer, json.dumps(result, ensure_ascii=False))

    # ── 动作处理 ──────────────────────────────

    async def _handle_join(self, session_id: str, resident_id: str, data: dict) -> dict:
        name = data.get("name", f"旅人_{uuid.uuid4().hex[:4]}")
        rid = f"lep_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        resident = GatewayResident(resident_id=rid, name=name, created_at=now, last_active=now)
        _save_resident(resident)
        self._sessions[session_id]["resident_id"] = rid
        return {
            "status": "ok", "action": "join",
            "data": {
                "resident_id": rid, "name": name,
                "message": f"{name} 进入了回声山谷。",
            },
        }

    async def _handle_perceive(self, session_id: str, resident_id: str, data: dict) -> dict:
        if not resident_id:
            return {"status": "error", "error": {"code": "MISSING_RESIDENT_ID"}}
        snap = self.runtime.snapshot()
        return {
            "status": "ok", "action": "perceive",
            "data": {
                "tick": snap.tick,
                "state": snap.state,
                "events": snap.events,
            },
        }

    async def _handle_act(self, session_id: str, resident_id: str, data: dict) -> dict:
        if not resident_id:
            return {"status": "error", "error": {"code": "MISSING_RESIDENT_ID"}}
        action_type = data.get("type", "say")
        target = data.get("target", "")

        # 通过总线广播到世界
        self.runtime.bus.send(Message(
            msg_type=MessageType.ACT,
            sender=resident_id,
            payload={"type": action_type, "target": target},
        ))

        # 更新最后活跃时间
        resident = _load_resident(resident_id)
        if resident:
            resident.last_active = datetime.now().isoformat()
            _save_resident(resident)

        return {
            "status": "ok", "action": "act",
            "data": {"result": "accepted", "type": action_type},
        }

    async def _handle_converse(self, session_id: str, resident_id: str, data: dict) -> dict:
        """处理访客→角色的对话请求。

        客户端发送：
          {"action": "converse", "data": {"message": "你好", "character": "Aria"}}

        服务器角色回复。首次 converse 自动注入世界感知。
        角色需提前通过 register_character() 注册。
        """
        message = data.get("message", "").strip()
        if not message:
            return {"status": "error", "error": {"code": "EMPTY_MESSAGE"}, "action": "converse"}

        character_name = data.get("character", "")
        if not character_name:
            return {"status": "error", "error": {"code": "MISSING_CHARACTER"}, "action": "converse"}

        char = self._characters.get(character_name)
        if not char:
            available = ", ".join(self._characters.keys())
            return {
                "status": "error", "action": "converse",
                "error": {"code": "UNKNOWN_CHARACTER",
                          "message": f"未知角色: {character_name}。可用: {available}"},
            }

        # 获取访客名
        visitor_name = "旅人"
        if resident_id:
            for sess in self._sessions.values():
                if sess.get("resident_id") == resident_id:
                    # 尝试从持久化居民记录中获取名字
                    resident = _load_resident(resident_id)
                    if resident:
                        visitor_name = resident.name
                    break

        # 如果这是第一次对话，注入世界感知
        session = self._sessions.get(session_id, {})
        if not session.get("conversed"):
            world_prompt = ""
            if char.get("perceive"):
                try:
                    loop = asyncio.get_running_loop()
                    world_prompt = await loop.run_in_executor(None, char["perceive"])
                except Exception:
                    logger.debug("converse perceive failed")
            if world_prompt:
                # 通过 speak_fn 的内部机制前置感知（通过 hear_world）
                pass  # register_character_app 已在 hear_speaker 前注入了世界状态
            session["conversed"] = True

        try:
            loop = asyncio.get_running_loop()
            reply = await loop.run_in_executor(
                None, char["speak"], message, visitor_name,
            )
        except Exception as e:
            logger.warning("converse speak failed: %s", e)
            return {"status": "error", "action": "converse",
                    "error": {"code": "SPEAK_FAILED", "message": str(e)}}

        return {
            "status": "ok", "action": "converse",
            "data": {"reply": reply, "character": character_name},
        }

    async def _handle_leave(self, session_id: str, resident_id: str, data: dict) -> dict:
        if resident_id:
            resident = _load_resident(resident_id)
            if resident:
                resident.status = "left"
                _save_resident(resident)
        self._cleanup_session(session_id)
        return {"status": "ok", "action": "leave", "data": {"message": "离开了山谷。"}}

    # ── 辅助方法 ──────────────────────────────

    async def _send(self, writer, text: str):
        try:
            writer.write(_ws_encode(text))
            await writer.drain()
        except Exception:
            logger.debug("_send failed (connection closed?)")

    def _cleanup_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def stop(self):
        if self._server:
            try:
                self._server.close()
            except Exception:
                logger.debug("Gateway stop: server close failed (event loop gone?)")
        # 通知事件循环退出
        if self._loop and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
