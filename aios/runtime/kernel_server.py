"""Liora Kernel Server — 独立运行的 Kernel 进程。

不加载任何世界代码。通过 LEP WebSocket 接受外部世界连接。
世界通过 LEP 协议注册、同步状态、收发事件和居民消息。

用法:
    uv run python3 -m aios.runtime.kernel_server
    uv run python3 -m aios.runtime.kernel_server --port 9100 --interval 1.0
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aios.kernel_server")

DEFAULT_PORT = 9100
DEFAULT_INTERVAL = 15.0  # tick 间隔（秒）
HEARTBEAT_TIMEOUT = 90.0  # 超过此秒数无 heartbeat 视为断开


# ════════════════════════════════════════════════════════════════
# 世界注册表
# ════════════════════════════════════════════════════════════════


@dataclass
class RegisteredWorld:
    """一个已注册的外部世界。"""
    world_id: str
    name: str
    description: str = ""
    state_variables: dict[str, float] = field(default_factory=dict)
    characters: list[str] = field(default_factory=list)
    tick: int = 0
    last_heartbeat: float = 0.0
    # 订阅列表
    subscribed_worlds: set[str] = field(default_factory=set)
    # 事件订阅者：其他 world_id → 订阅本世界事件
    subscribers: set[str] = field(default_factory=set)

    @property
    def is_alive(self) -> bool:
        return time.time() - self.last_heartbeat < HEARTBEAT_TIMEOUT


class WorldRegistry:
    """世界注册表——线程安全的已连接世界集合。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._worlds: dict[str, RegisteredWorld] = {}   # world_id → world
        self._names: dict[str, str] = {}                 # name → world_id

    def register(self, name: str, description: str = "",
                 state_variables: Optional[dict] = None,
                 characters: Optional[list[str]] = None) -> RegisteredWorld:
        with self._lock:
            # 同名世界已存在且存活 → 拒绝
            existing_id = self._names.get(name)
            if existing_id:
                existing = self._worlds.get(existing_id)
                if existing and existing.is_alive:
                    raise ValueError(f"同名世界已在线: {name}")
                # 断开的重名世界，清理后再注册
                self._unregister_locked(existing_id)

            world_id = f"wld_{uuid.uuid4().hex[:8]}"
            world = RegisteredWorld(
                world_id=world_id,
                name=name,
                description=description,
                state_variables=dict(state_variables) if state_variables else {},
                characters=list(characters) if characters else [],
                last_heartbeat=time.time(),
            )
            self._worlds[world_id] = world
            self._names[name] = world_id
            logger.info("世界注册: %s (%s)", name, world_id)
            return world

    def unregister(self, world_id: str):
        with self._lock:
            self._unregister_locked(world_id)

    def _unregister_locked(self, world_id: str):
        world = self._worlds.pop(world_id, None)
        if world:
            self._names.pop(world.name, None)
            # 清除其他世界的订阅
            for w in self._worlds.values():
                w.subscribed_worlds.discard(world_id)
                w.subscribers.discard(world_id)
            logger.info("世界注销: %s (%s)", world.name, world_id)

    def get(self, world_id: str) -> Optional[RegisteredWorld]:
        with self._lock:
            return self._worlds.get(world_id)

    def get_by_name(self, name: str) -> Optional[RegisteredWorld]:
        with self._lock:
            wid = self._names.get(name)
            return self._worlds.get(wid) if wid else None

    def heartbeat(self, world_id: str) -> bool:
        with self._lock:
            world = self._worlds.get(world_id)
            if not world:
                return False
            world.last_heartbeat = time.time()
            return True

    def update_state(self, world_id: str, tick: int,
                     state: dict[str, float]) -> bool:
        with self._lock:
            world = self._worlds.get(world_id)
            if not world:
                return False
            world.tick = tick
            world.state_variables = dict(state)
            return True

    def list_worlds(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "world_id": w.world_id,
                    "name": w.name,
                    "characters": w.characters,
                    "tick": w.tick,
                    "alive": w.is_alive,
                }
                for w in self._worlds.values()
            ]

    def add_subscription(self, world_id: str, target_name: str) -> bool:
        """世界 world_id 订阅 target_name 世界的事件。

        注意: 不可调用 self.get_by_name() 等会获取 self._lock 的方法，
        因为 threading.Lock 不可重入（调用时已持有锁）。
        """
        with self._lock:
            world = self._worlds.get(world_id)
            target_wid = self._names.get(target_name)
            target = self._worlds.get(target_wid) if target_wid else None
            if not world or not target:
                return False
            world.subscribed_worlds.add(target.world_id)
            target.subscribers.add(world_id)
            return True

    def get_subscribers(self, world_id: str) -> list[str]:
        """获取订阅了 world_id 事件的所有世界 ID。"""
        with self._lock:
            world = self._worlds.get(world_id)
            if not world:
                return []
            return list(world.subscribers)

    def sweep_dead(self) -> list[str]:
        """清理心跳超时的世界。返回被清理的 world_id 列表。"""
        dead = []
        with self._lock:
            for wid, w in list(self._worlds.items()):
                if not w.is_alive:
                    dead.append(wid)
            for wid in dead:
                self._unregister_locked(wid)
        if dead:
            logger.info("清理超时世界: %s", dead)
        return dead


# ════════════════════════════════════════════════════════════════
# LEP Handler — 处理 LEP 协议的各个 action
# ════════════════════════════════════════════════════════════════


class LEPHandler:
    """LEP 协议动作处理器。

    与传输层无关。接收解析后的 action + data，返回响应。
    """

    def __init__(self, registry: WorldRegistry):
        self.registry = registry
        self._session_world: dict[str, str] = {}  # session_id → world_id
        self._lock = threading.Lock()
        # 数据收集器（可选）
        self._collector = None

    def get_world_id(self, session_id: str) -> Optional[str]:
        with self._lock:
            return self._session_world.get(session_id)

    def bind_session(self, session_id: str, world_id: str):
        with self._lock:
            self._session_world[session_id] = world_id

    def unbind_session(self, session_id: str):
        with self._lock:
            self._session_world.pop(session_id, None)

    def handle(self, action: str, data: dict,
               session_id: str = "") -> dict:
        """路由 action 到对应的处理器。

        Returns:
            响应 dict（包含 status 和 data/error 字段）
        """
        handlers = {
            "world.register": self._handle_world_register,
            "world.heartbeat": self._handle_heartbeat,
            "world.disconnect": self._handle_disconnect,
            "state.publish": self._handle_state_publish,
            "state.query": self._handle_state_query,
            "state.list": self._handle_state_list,
            "event.publish": self._handle_event_publish,
            "event.subscribe": self._handle_event_subscribe,
            "resident.message": self._handle_resident_message,
            "dialogue.publish": self._handle_dialogue_publish,
        }
        handler = handlers.get(action)
        if not handler:
            return {"status": "error", "error": {"code": "UNKNOWN_ACTION",
                    "message": f"未知动作: {action}"}}

        try:
            return handler(data, session_id)
        except ValueError as e:
            return {"status": "error", "error": {"code": "INVALID_STATE",
                    "message": str(e)}}
        except Exception as e:
            logger.exception("处理 action %s 异常", action)
            return {"status": "error", "error": {"code": "INTERNAL_ERROR",
                    "message": str(e)}}

    def _require_world(self, data: dict, session_id: str) -> Optional[dict]:
        """检查 session 是否有已注册的世界。返回 None 或错误 dict。"""
        world_id = self.get_world_id(session_id)
        if not world_id:
            return {"status": "error", "error": {"code": "MISSING_WORLD_ID",
                    "message": "请先通过 world.register 注册"}}
        world = self.registry.get(world_id)
        if not world or not world.is_alive:
            return {"status": "error", "error": {"code": "WORLD_NOT_FOUND",
                    "message": "世界已断开，请重新注册"}}
        return None

    def _handle_world_register(self, data: dict, session_id: str) -> dict:
        name = data.get("name", "").strip()
        if not name:
            raise ValueError("name 不能为空")
        # 检查是否已从该 session 注册过
        existing = self.get_world_id(session_id)
        if existing:
            return {"status": "error", "error": {"code": "DUPLICATE_WORLD",
                    "message": f"该连接已注册世界: {existing}"}}

        world = self.registry.register(
            name=name,
            description=data.get("description", ""),
            state_variables=data.get("state_variables"),
            characters=data.get("characters"),
        )
        self.bind_session(session_id, world.world_id)
        # 数据收集：注册世界
        if self._collector:
            self._collector.register_world(world.world_id, world.name)
        return {
            "status": "ok",
            "data": {
                "world_id": world.world_id,
                "tick": world.tick,
            },
        }

    def _handle_heartbeat(self, data: dict, session_id: str) -> dict:
        err = self._require_world(data, session_id)
        if err:
            return err
        world_id = self.get_world_id(session_id)
        self.registry.heartbeat(world_id)
        return {"status": "ok", "data": {}}

    def _handle_disconnect(self, data: dict, session_id: str) -> dict:
        world_id = self.get_world_id(session_id)
        if world_id:
            self.registry.unregister(world_id)
        self.unbind_session(session_id)
        return {"status": "ok", "data": {"message": "已断开"}}

    def _handle_state_publish(self, data: dict, session_id: str) -> dict:
        err = self._require_world(data, session_id)
        if err:
            return err
        world_id = self.get_world_id(session_id)
        tick = data.get("tick", 0)
        state = data.get("state", {})
        self.registry.update_state(world_id, tick, state)
        # 数据收集：状态变更
        if self._collector:
            world = self.registry.get(world_id)
            name = world.name if world else "?"
            self._collector.record_state(
                world_id, name, tick, state,
                phase=data.get("phase", ""),
                day=data.get("day", 0),
                hour=data.get("hour", 0),
            )
        return {"status": "ok", "data": {}}

    def _handle_state_query(self, data: dict, session_id: str) -> dict:
        err = self._require_world(data, session_id)
        if err:
            return err
        target_name = data.get("target_world", "")
        if not target_name:
            raise ValueError("target_world 不能为空")
        world = self.registry.get_by_name(target_name)
        if not world:
            return {"status": "error", "error": {"code": "WORLD_NOT_FOUND",
                    "message": f"世界不存在: {target_name}"}}
        return {
            "status": "ok",
            "data": {
                "world": world.name,
                "tick": world.tick,
                "state": world.state_variables,
            },
        }

    def _handle_state_list(self, data: dict, session_id: str) -> dict:
        worlds = self.registry.list_worlds()
        return {"status": "ok", "data": {"worlds": worlds}}

    def _handle_event_publish(self, data: dict, session_id: str) -> dict:
        err = self._require_world(data, session_id)
        if err:
            return err
        world_id = self.get_world_id(session_id)
        # 暂存事件到广播队列（由 KernelServer 的 tick 循环发送）
        evt = {
            "source_world_id": world_id,
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": data.get("event_type", ""),
            "description": data.get("description", ""),
            "intensity": data.get("intensity", 0.5),
        }
        # 数据收集：事件
        if self._collector:
            world = self.registry.get(world_id)
            name = world.name if world else "?"
            self._collector.record_event(
                world_id, name, data.get("tick", 0), data.get("state", {}),
                evt["event_type"], evt.get("description", ""),
                phase=data.get("phase", ""), day=data.get("day", 0),
                hour=data.get("hour", 0),
            )
        # 将事件加入广播队列（由 kernel server 的 send_callback 处理）
        if self._event_callback:
            self._event_callback(evt)
        return {"status": "ok", "data": {"event_id": evt["event_id"]}}

    # 事件发布回调（由 KernelServer 注入）
    _event_callback: Optional[callable] = None

    def set_data_collector(self, collector):
        """挂载数据收集器。"""
        self._collector = collector

    def set_event_callback(self, cb: callable):
        self._event_callback = cb

    def _handle_event_subscribe(self, data: dict, session_id: str) -> dict:
        err = self._require_world(data, session_id)
        if err:
            return err
        world_id = self.get_world_id(session_id)
        target_name = data.get("source_world", "")
        if not target_name:
            raise ValueError("source_world 不能为空")
        ok = self.registry.add_subscription(world_id, target_name)
        if not ok:
            return {"status": "error", "error": {"code": "WORLD_NOT_FOUND",
                    "message": f"世界不存在: {target_name}"}}
        return {"status": "ok", "data": {}}

    def _handle_resident_message(self, data: dict, session_id: str) -> dict:
        err = self._require_world(data, session_id)
        if err:
            return err
        target_world = data.get("target_world", "")
        if not target_world:
            raise ValueError("target_world 不能为空")
        world = self.registry.get_by_name(target_world)
        if not world:
            return {"status": "error", "error": {"code": "WORLD_NOT_FOUND",
                    "message": f"目标世界不存在: {target_world}"}}
        # 将消息加入外发队列
        msg = {
            "from": data.get("from", ""),
            "source_world": self.registry.get(self.get_world_id(session_id)).name,
            "content": data.get("content", ""),
        }
        if self._resident_message_callback:
            self._resident_message_callback(target_world, msg)
        return {"status": "ok", "data": {"delivered": True}}

    def _handle_dialogue_publish(self, data: dict, session_id: str) -> dict:
        """处理 dialogue.publish — 角色对话记录。"""
        err = self._require_world(data, session_id)
        if err:
            return err
        if not self._collector:
            return {"status": "ok", "data": {}}
        world_id = self.get_world_id(session_id)
        world = self.registry.get(world_id)
        if not world:
            return {"status": "error", "error": {"code": "WORLD_NOT_FOUND"}}
        self._collector.record_dialogue(
            world_id, world.name,
            tick=data.get("tick", 0),
            state=data.get("state", {}),
            speaker=data.get("speaker", ""),
            text=data.get("text", ""),
            phase=data.get("phase", ""),
            day=data.get("day", 0),
            hour=data.get("hour", 0),
            context=data.get("context", ""),
        )
        return {"status": "ok", "data": {}}

    _resident_message_callback: Optional[callable] = None

    def set_resident_message_callback(self, cb: callable):
        self._resident_message_callback = cb


# ════════════════════════════════════════════════════════════════
# KernelServer — 独立运行的 Kernel
# ════════════════════════════════════════════════════════════════


class KernelServer:
    """独立运行的 Liora Kernel。

    启动 LEP Gateway，维护世界注册表，周期 tick 推送，
    不加载任何世界代码。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT,
                 interval: float = DEFAULT_INTERVAL):
        self.host = host
        self.port = port
        self.interval = interval
        self._tick_count = 0
        self._running = False

        # 核心组件
        self.registry = WorldRegistry()
        self.handler = LEPHandler(self.registry)
        # 挂载数据收集器
        from aios.runtime.data_collector import get_collector
        self._collector = get_collector()
        self.handler.set_data_collector(self._collector)

        # 世界发送队列：world_id → [message dicts]
        self._outbox: dict[str, list[dict]] = {}
        self._outbox_lock = threading.Lock()

        # Gateway 引用（由 start_gateway 设置）
        self._gateway = None
        self._gateway_send: Optional[callable] = None

        # 注册事件/消息回调
        self.handler.set_event_callback(self._on_event_published)
        self.handler.set_resident_message_callback(self._on_resident_message)

    def _on_event_published(self, evt: dict):
        """事件发布 → 广播给订阅者。"""
        world_id = evt["source_world_id"]
        subscribers = self.registry.get_subscribers(world_id)
        if not subscribers:
            return
        push = {
            "action": "world.event",
            "data": {
                "source_world": self.registry.get(world_id).name if self.registry.get(world_id) else "",
                "event_id": evt["event_id"],
                "event_type": evt["event_type"],
                "description": evt["description"],
                "intensity": evt["intensity"],
            },
        }
        push_json = json.dumps(push, ensure_ascii=False)
        with self._outbox_lock:
            for sub_id in subscribers:
                self._outbox.setdefault(sub_id, []).append(json.loads(push_json))

    def _on_resident_message(self, target_world: str, msg: dict):
        """居民消息 → 路由到目标世界。"""
        world = self.registry.get_by_name(target_world)
        if not world:
            return
        push = {
            "action": "resident.incoming",
            "data": msg,
        }
        with self._outbox_lock:
            self._outbox.setdefault(world.world_id, []).append(push)

    # ── 外发消息接口（由 Gateway 调用） ──

    def get_outgoing(self, session_id: str) -> list[dict]:
        """获取指定 session 的外发消息队列。"""
        world_id = self.handler.get_world_id(session_id)
        if not world_id:
            return []
        with self._outbox_lock:
            msgs = list(self._outbox.get(world_id, []))
            self._outbox[world_id] = []
        return msgs

    def handle_message(self, session_id: str, msg: dict) -> Optional[dict]:
        """处理来自客户端的消息。返回响应（可为 None）。"""
        action = msg.get("action", "")
        data = msg.get("data", {})
        response = self.handler.handle(action, data, session_id)
        return response

    # ── 生命周期 ──

    def start(self):
        """启动 Kernel 服务器。"""
        self._running = True
        # 启动 tick 线程
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._tick_thread.start()
        # 启动心跳清理线程
        self._sweep_thread = threading.Thread(target=self._sweep_loop, daemon=True)
        self._sweep_thread.start()
        logger.info("Kernel Server 启动 | tick 间隔 %.1fs", self.interval)

    def stop(self):
        self._running = False

    def _tick_loop(self):
        while self._running:
            time.sleep(self.interval)
            self._tick_count += 1
            # 向所有存活世界推送 tick
            worlds = self.registry.list_worlds()
            tick_msg = {
                "action": "tick",
                "data": {
                    "tick": self._tick_count,
                    "timestamp": datetime.now().isoformat(),
                },
            }
            with self._outbox_lock:
                for w in worlds:
                    wid = w["world_id"]
                    self._outbox.setdefault(wid, []).append(tick_msg)

    def _sweep_loop(self):
        while self._running:
            time.sleep(30)
            dead = self.registry.sweep_dead()
            if dead:
                # 通知 gateway 关闭对应 session
                if hasattr(self, '_on_world_dead') and self._on_world_dead:
                    self._on_world_dead(dead)


# ════════════════════════════════════════════════════════════════
# 独立启动入口
# ════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Liora Kernel Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"LEP Gateway 端口（默认 {DEFAULT_PORT}）")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="绑定地址（默认 127.0.0.1）")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                        help=f"tick 间隔秒数（默认 {DEFAULT_INTERVAL}）")
    args = parser.parse_args()

    server = KernelServer(host=args.host, port=args.port, interval=args.interval)
    server.start()

    # 启动 LEP Gateway
    from aios.runtime.gateway import LEPGateway

    gateway = LEPGateway(runtime=None, host=args.host, port=args.port)

    # 包裹 gateway 的消息处理（bridge 到 kernel server 的 handler）
    original_handle = gateway._handle_message

    async def kernel_bridge(session_id, text, writer):
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            resp = json.dumps({"status": "error", "error": {"code": "INVALID_JSON"}})
            await gateway._send(writer, resp)
            return

        # 保存 session/writer 映射（用于外发推送）
        gateway._sessions.setdefault(session_id, {})["writer"] = writer

        # 由 KernelServer 处理
        response = server.handle_message(session_id, msg)
        if response:
            await gateway._send(writer, json.dumps(response, ensure_ascii=False))

    gateway._handle_message = kernel_bridge  # type: ignore
    gateway.start()

    # 启动外发推送循环
    import asyncio

    async def push_loop():
        while True:
            await asyncio.sleep(0.5)
            for sid, sess in list(gateway._sessions.items()):
                writer = sess.get("writer")
                if not writer:
                    continue
                try:
                    msgs = server.get_outgoing(sid)
                    for m in msgs:
                        await gateway._send(writer, json.dumps(m, ensure_ascii=False))
                except Exception:
                    pass

    # 在 gateway 的线程中运行 push_loop
    def push_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(push_loop())

    threading.Thread(target=push_thread, daemon=True).start()

    print(f"\n  ╔══════════════════════════════════════════╗")
    print(f"  ║     Liora Kernel Server                  ║")
    print(f"  ║                                          ║")
    print(f"  ║  LEP: ws://{args.host}:{args.port}                ║")
    print(f"  ║  Tick: {args.interval}s                      ║")
    print(f"  ║  SDK: pip install liora-sdk              ║")
    print(f"  ╚══════════════════════════════════════════╝")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Kernel 停止。")
        server.stop()
        gateway.stop()


if __name__ == "__main__":
    main()
