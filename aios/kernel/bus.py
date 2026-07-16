"""AIOS Kernel — Bus (消息总线)

最小消息总线。居民和外设通过总线通信，不直接 import。
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("aios.kernel.bus")


class MessageType(str, Enum):
    PERCEIVE = "perceive"
    ACT = "act"
    EVENT = "event"
    SEARCH = "search"
    RESPONSE = "response"
    SYSTEM = "system"


@dataclass
class Message:
    """总线消息。"""
    msg_id: str = ""
    msg_type: MessageType = MessageType.SYSTEM
    sender: str = "system"
    recipient: str = ""           # "" = broadcast
    payload: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.msg_id:
            self.msg_id = f"msg_{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.msg_id, "type": self.msg_type.value,
            "from": self.sender, "to": self.recipient,
            "payload": self.payload, "ts": self.timestamp,
        }


class MessageBus:
    """轻量消息总线。

    居民/外设通过 send/subscribe 通信，不需要互相 import。

    注意：subscriber 回调在当前线程同步执行。
    如果某个 callback 耗时较长，会阻塞 send() 的调用方。
    未来可考虑引入异步队列或线程池分发。
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._history: list[Message] = []

    def send(self, msg: Message) -> str:
        """发送消息。返回 msg_id。"""
        self._history.append(msg)
        self._history = self._history[-1000:]  # 只保留最近 1000 条

        # 广播或定向投递
        recipients = [""] if not msg.recipient else [msg.recipient, ""]
        for r in recipients:
            key = f"{msg.msg_type.value}:{r}"
            for cb in self._subscribers.get(key, []):
                try:
                    cb(msg)
                except Exception:
                    logger.debug("subscriber callback failed")

        return msg.msg_id

    def subscribe(self, msg_type: MessageType, recipient: str = "",
                   callback: Optional[Callable] = None):
        """订阅某类消息。"""
        if callback is None:
            return
        key = f"{msg_type.value}:{recipient}"
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(callback)

    def get_history(self, n: int = 10) -> list[Message]:
        return self._history[-n:]

    def count(self) -> int:
        return len(self._history)


_global_bus: Optional[MessageBus] = None


def get_bus() -> MessageBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = MessageBus()
    return _global_bus
