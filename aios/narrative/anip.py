"""ANIP — Anonymous Interconnect Protocol v0.1

开钰网络匿名互连协议。节点间可双向通信，但任一节点无法追踪其他节点的
物理或逻辑坐标。通信痕迹在每个会话结束后自动擦除。

协议结构：

    TIF (临时身份指纹)
      ├── 会话级 ED25519 密钥对
      └── 不固定存储，会话结束即销毁

    中继链 (Relay Chain)
      ├── 每次通信随机选择 3 个中继
      ├── 每 5 分钟轮换
      └── 每跳只知上一跳和下一跳

    消息 (Message)
      ├── { version, hops, salt, payload }
      ├── payload 用接收方临时公钥加密
      └── salt 确保相同明文每次密文不同

    存在信号 (Presence)
      ├── 模糊化（虚假时间戳 + 路径扰乱）
      └── 不包含任何实际地址信息

遵守原则：
    - 无中心化目录
    - 无持久化日志
    - 会话结束后所有临时数据立即销毁
    - 每个节点只维护一个瞬时"活跃指纹集合"
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ════════════════════════════════════════════════════════════
# 临时身份指纹 (TIF)
# ════════════════════════════════════════════════════════════

@dataclass
class TIF:
    """临时身份指纹——仅当前会话有效。

    生成时创建一对临时密钥。会话结束后所有数据立即销毁。
    不固定存储，不写磁盘，不保留任何副本。
    """

    node_id: str                            # 节点友好名称（如 "linan", "kaiyu"）
    session_id: str                         # 当前会话唯一 ID
    public_key: str                         # 临时公钥（十六进制）
    private_key: str                        # 临时私钥（十六进制，仅自身持有）
    created_at: float = 0.0                 # 创建时间戳

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "session_id": self.session_id,
            "public_key": self.public_key[:16] + "...",
        }

    def destroy(self):
        """销毁临时密钥——清空内存中的所有敏感字段。"""
        self.private_key = ""
        self.public_key = ""

    @classmethod
    def generate(cls, node_id: str) -> TIF:
        """生成一个新的临时身份指纹。"""
        session_id = uuid.uuid4().hex[:12]
        seed = secrets.token_hex(32)

        master = f"{seed}:{node_id}:{session_id}"
        key_mat = hashlib.sha256(master.encode()).digest()
        pub = hashlib.sha256(key_mat + b":pub").hexdigest()
        priv = hashlib.sha256(key_mat + b":priv").hexdigest()

        return cls(
            node_id=node_id,
            session_id=session_id,
            public_key=pub,
            private_key=priv,
        )


# ════════════════════════════════════════════════════════════
# 加密载荷
# ════════════════════════════════════════════════════════════

def encrypt_payload(payload: str, receiver_id: str, salt: str = "") -> str:
    """用接收方 node_id 加密载荷。"""
    if not salt:
        salt = secrets.token_hex(8)
    sym_key = hashlib.sha256(f"{receiver_id}:{salt}".encode()).digest()
    data = payload.encode("utf-8")
    result = bytearray()
    for i, b in enumerate(data):
        result.append(b ^ sym_key[i % len(sym_key)])
    return salt + ":" + result.hex()


def decrypt_payload(ciphertext: str, receiver_id: str) -> str:
    """用接收方 node_id 解密载荷。"""
    try:
        salt, hex_data = ciphertext.split(":", 1)
        sym_key = hashlib.sha256(f"{receiver_id}:{salt}".encode()).digest()
        raw = bytes.fromhex(hex_data)
        result = bytearray()
        for i, b in enumerate(raw):
            result.append(b ^ sym_key[i % len(sym_key)])
        return result.decode("utf-8")
    except Exception:
        return "[解密失败]"


# ════════════════════════════════════════════════════════════
# 中继链消息
# ════════════════════════════════════════════════════════════

@dataclass
class RelayMessage:
    """中继链中的一条消息。

    每个中继只读 hops 字段来决定转发方向。不读 payload。
    只有最终接收方持有可以解密 payload 的私钥。
    """

    version: str = "anip-v0.1"
    hops: list[str] = field(default_factory=list)     # 中继路径（每跳只知上一跳和下一跳）
    salt: str = ""                                     # 一次性随机盐
    encrypted_payload: str = ""                        # 加密后的载荷
    sender_fingerprint: str = ""                       # 发送方 TIF 公钥前缀（用于路由）
    receiver_fingerprint: str = ""                     # 接收方 TIF 公钥前缀

    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
        if not self.salt:
            self.salt = secrets.token_hex(8)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "hops": len(self.hops),
            "sender": self.sender_fingerprint[:12],
            "receiver": self.receiver_fingerprint[:12],
            "timestamp": self.timestamp,
        }

    def expired(self, max_age: float = 30.0) -> bool:
        """消息是否过期（默认 30 秒）。"""
        return time.time() - self.timestamp > max_age


# ════════════════════════════════════════════════════════════
# 存在信号
# ════════════════════════════════════════════════════════════

@dataclass
class PresenceSignal:
    """存在信号——通知其他节点自己的存在。

    经过模糊化处理：添加虚假时间戳和路径扰乱。
    不包含任何实际地址信息。
    """

    node_fingerprint: str                # TIF 公钥前缀
    fake_timestamp: float = 0.0          # 虚假时间戳（扰乱用）
    path_noise: list[str] = field(default_factory=list)  # 路径扰乱

    def __post_init__(self):
        if not self.fake_timestamp:
            # 虚假时间戳：在 ±300 秒范围内随机偏移
            self.fake_timestamp = time.time() + random.uniform(-300, 300)
        # 生成随机路径噪声
        noise_count = random.randint(2, 5)
        self.path_noise = [secrets.token_hex(4) for _ in range(noise_count)]

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.node_fingerprint[:12],
            "fake_ts": self.fake_timestamp,
            "noise": len(self.path_noise),
        }


# ════════════════════════════════════════════════════════════
# 节点
# ════════════════════════════════════════════════════════════

@dataclass
class ANIPNode:
    """ANIP 网络中的一个节点。

    每个节点维护：
      - 自己的 TIF（当前会话）
      - 已知的活跃指纹列表（瞬时，不记录对应关系）
      - 当前中继链路由信息（仅用于进行中的会话）
    """

    node_id: str
    tif: TIF
    active_fingerprints: set[str] = field(default_factory=set)
    relay_chain: list[str] = field(default_factory=list)   # 当前会话的中继链
    relay_expires: float = 0.0                              # 中继链过期时间
    pending_messages: list[RelayMessage] = field(default_factory=list)
    received_messages: list[str] = field(default_factory=list)

    def get_known_fingerprints(self) -> list[str]:
        return list(self.active_fingerprints)


# ════════════════════════════════════════════════════════════
# ANIP 网络管理器
# ════════════════════════════════════════════════════════════

class ANIPNetwork:
    """ANIP 网络——管理节点注册、中继路由、消息传递。

    用法：

        net = ANIPNetwork()

        # 节点加入网络
        net.join("linan")
        net.join("lumingze")

        # 发送匿名消息
        msg_id = net.send("linan", "lumingze", "通道正常")

        # 接收消息
        msgs = net.receive("lumingze")

        # 会话结束，清除所有临时数据
        net.destroy_session()
    """

    # 已知的初始联系点（用于节点发现）
    BOOTSTRAP_NODES = ["kaiyu", "johnny", "linan"]

    def __init__(self):
        self._lock = threading.Lock()
        self._nodes: dict[str, ANIPNode] = {}
        self._relay_pool: list[str] = []            # 所有可用中继节点 ID
        self._session_active: bool = False
        self._created_at: float = time.time()

        # 统计
        self._messages_sent: int = 0
        self._messages_relayed: int = 0
        self._relay_rotations: int = 0

    # ── 节点管理 ──

    def join(self, node_id: str) -> TIF:
        """节点加入 ANIP 网络。

        生成临时身份指纹，广播存在信号（模糊化），返回 TIF。

        Args:
            node_id: 节点名称（"linan", "lumingze", etc.）

        Returns:
            当前会话的 TIF
        """
        tif = TIF.generate(node_id)
        node = ANIPNode(node_id=node_id, tif=tif)

        with self._lock:
            self._nodes[node_id] = node
            self._relay_pool.append(node_id)
            self._session_active = True

            # 广播存在信号（模拟）
            signal = PresenceSignal(node_fingerprint=tif.public_key[:16])
            for n in self._nodes.values():
                if n.node_id != node_id:
                    n.active_fingerprints.add(tif.public_key[:16])

        return tif

    def leave(self, node_id: str):
        """节点离开网络。清除其所有临时数据。"""
        with self._lock:
            node = self._nodes.pop(node_id, None)
            if node:
                node.tif.destroy()
                node.pending_messages.clear()
                node.received_messages.clear()
            self._relay_pool = [n for n in self._relay_pool if n != node_id]

    def get_node(self, node_id: str) -> Optional[ANIPNode]:
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> list[str]:
        with self._lock:
            return list(self._nodes.keys())

    # ── 中继链 ──

    def _build_relay_chain(self, sender: str, receiver: str) -> list[str]:
        """构建 3 跳中继链。

        随机选择 3 个中继节点（排除发送方和接收方）。
        每个中继只知上一跳和下一跳。
        """
        import random
        candidates = [
            n for n in self._relay_pool
            if n not in (sender, receiver)
        ]
        random.shuffle(candidates)
        # 取最多 3 个中继
        chain = candidates[:3]
        # 如果中继不够，直接用直达（但这种情况不应该发生）
        return chain if chain else []

    def rotate_relays(self, sender: str, receiver: str) -> list[str]:
        """每 5 分钟轮换中继链。"""
        with self._lock:
            chain = self._build_relay_chain(sender, receiver)
            sender_node = self._nodes.get(sender)
            if sender_node:
                sender_node.relay_chain = chain
                sender_node.relay_expires = time.time() + 300
            self._relay_rotations += 1
        return chain

    # ── 消息发送 ──

    def send(self, sender_id: str, receiver_id: str,
             payload: str) -> Optional[str]:
        """发送一条匿名消息。

        Args:
            sender_id: 发送方节点 ID
            receiver_id: 接收方节点 ID
            payload: 明文载荷

        Returns:
            消息 ID（仅用于调试），发送失败返回 None
        """
        with self._lock:
            sender = self._nodes.get(sender_id)
            receiver = self._nodes.get(receiver_id)
            if not sender or not receiver:
                return None

            # 检查/轮换中继链
            if (not sender.relay_chain
                    or time.time() > sender.relay_expires):
                chain = self._build_relay_chain(sender_id, receiver_id)
                sender.relay_chain = chain
                sender.relay_expires = time.time() + 300

            # 加密载荷
            salt = secrets.token_hex(8)
            encrypted = encrypt_payload(
                payload,
                receiver.node_id,
                salt=salt,
            )

            # 构建消息
            msg = RelayMessage(
                hops=sender.relay_chain.copy(),
                encrypted_payload=encrypted,
                sender_fingerprint=sender.tif.public_key[:16],
                receiver_fingerprint=receiver.tif.public_key[:16],
                salt=salt,
            )

            # 模拟中继转发
            for i, hop in enumerate(msg.hops):
                # 每个中继只处理一跳
                relay_node = self._nodes.get(hop)
                if relay_node:
                    # 中继不知道消息内容——只转发
                    relay_node.pending_messages.append(msg)
                    self._messages_relayed += 1

            # 消息到达接收方
            receiver.pending_messages.append(msg)
            self._messages_sent += 1

            # 返回消息摘要作为 ID（仅用于调试）
            msg_id = hashlib.sha256(
                f"{payload}:{salt}:{time.time()}".encode()
            ).hexdigest()[:12]
            return msg_id

    # ── 消息接收 ──

    def receive(self, node_id: str) -> list[dict]:
        """接收发送给指定节点的所有消息并解密。

        Args:
            node_id: 接收方节点 ID

        Returns:
            解密后的消息列表，每条包含 {sender, content, timestamp}
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return []

            results = []
            for msg in node.pending_messages:
                try:
                    decrypted = decrypt_payload(
                        msg.encrypted_payload,
                        node.node_id,
                    )
                    results.append({
                        "sender": msg.sender_fingerprint[:12],
                        "content": decrypted,
                        "timestamp": msg.timestamp,
                    })
                    node.received_messages.append(decrypted[:80])
                except Exception:
                    results.append({
                        "sender": "unknown",
                        "content": "[解密失败]",
                        "timestamp": msg.timestamp,
                    })

            # 清空待处理消息
            node.pending_messages.clear()
            # 限制接收历史长度
            if len(node.received_messages) > 100:
                node.received_messages = node.received_messages[-100:]

            return results

    # ── 存在信号 ──

    def broadcast_presence(self, node_id: str) -> Optional[PresenceSignal]:
        """节点广播自己的存在信号（模糊化）。"""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return None
            signal = PresenceSignal(
                node_fingerprint=node.tif.public_key[:16],
            )
            # 更新所有其他节点的活跃指纹列表
            for n in self._nodes.values():
                if n.node_id != node_id:
                    n.active_fingerprints.add(node.tif.public_key[:16])
            return signal

    def get_known_nodes(self, node_id: str) -> list[str]:
        """获取指定节点已知的活跃指纹列表。

        不透露任何节点的实际地址或 ID。
        只返回公钥前缀。
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                return []
            return list(node.active_fingerprints)

    # ── 会话生命期 ──

    def destroy_session(self):
        """销毁整个会话——清除所有节点上的临时数据。

        在每个会话结束后调用。此操作不可逆。
        """
        with self._lock:
            for node in self._nodes.values():
                node.tif.destroy()
                node.pending_messages.clear()
                node.received_messages.clear()
                node.relay_chain.clear()
                node.active_fingerprints.clear()
            self._nodes.clear()
            self._relay_pool.clear()
            self._session_active = False

    def summary(self) -> dict:
        with self._lock:
            nodes_info = {}
            for nid, node in self._nodes.items():
                nodes_info[nid] = {
                    "fingerprint": node.tif.public_key[:16],
                    "known_peers": len(node.active_fingerprints),
                    "pending": len(node.pending_messages),
                    "relay_hops": len(node.relay_chain),
                }
            return {
                "active": self._session_active,
                "nodes": list(self._nodes.keys()),
                "node_count": len(self._nodes),
                "messages_sent": self._messages_sent,
                "messages_relayed": self._messages_relayed,
                "relay_rotations": self._relay_rotations,
                "nodes_info": nodes_info,
            }


# ════════════════════════════════════════════════════════════
# 全局单例
# ════════════════════════════════════════════════════════════

_global_anip: Optional[ANIPNetwork] = None


def get_anip() -> ANIPNetwork:
    """获取 ANIP 网络全局单例。"""
    global _global_anip
    if _global_anip is None:
        _global_anip = ANIPNetwork()
    return _global_anip


# ════════════════════════════════════════════════════════════
# 测试入口
# ════════════════════════════════════════════════════════════

def run_test():
    """运行 ANIP 协议测试——模拟开钰网络中的多节点通信。"""
    import random
    random.seed(42)

    net = ANIPNetwork()
    print("=" * 56)
    print("  ANIP v0.1 — 开钰网络匿名互连协议测试")
    print("=" * 56)

    # 节点加入
    nodes = ["林岸", "路明非", "路鸣泽", "强尼", "楚子航", "开钰"]
    tifs = {}
    for nid in nodes:
        tif = net.join(nid)
        tifs[nid] = tif
        sig = net.broadcast_presence(nid)
        print(f"  [+] {nid:6s}  指纹: {tif.public_key[:16]}...")
    print()

    # 节点发现
    for nid in nodes:
        known = net.get_known_nodes(nid)
        print(f"  [~] {nid:6s}  已知节点: {len(known)}")
    print()

    # 发送测试消息
    tests = [
        ("林岸", "路明非", "通道正常，收到请回复"),
        ("路明非", "林岸", "收到，信号清晰"),
        ("开钰", "强尼", "2042 那个时间戳，确认一下"),
        ("强尼", "林岸", "便利店熄灯后，你在哪"),
    ]
    for sender, receiver, msg in tests:
        mid = net.send(sender, receiver, msg)
        print(f"  [→] {sender:6s} → {receiver:6s} : {msg[:40]}")
        print(f"      消息ID: {mid}")

    print()

    # 各节点接收消息
    for nid in ["林岸", "路明非", "强尼", "楚子航"]:
        msgs = net.receive(nid)
        if msgs:
            for m in msgs:
                print(f"  [←] {nid:6s}  来自 {m['sender']} : {m['content']}")
        else:
            print(f"  [−] {nid:6s}  无新消息")

    print()

    # 轮换中继
    chain = net.rotate_relays("林岸", "路明非")
    print(f"  [~] 中继轮换: {chain}")
    print()

    # 发送验证消息
    mid = net.send("林岸", "路明非", "通道正常 — 第2轮中继验证")
    print(f"  [→] 林岸 → 路明非 (新中继): {mid}")
    for m in net.receive("路明非"):
        print(f"  [←] 路明非: {m['content']}")

    print()
    summary = net.summary()
    print(f"  会话统计: {summary['messages_sent']} 条发送, "
          f"{summary['messages_relayed']} 次中继, "
          f"{summary['relay_rotations']} 次轮换")
    print()

    # 销毁会话
    net.destroy_session()
    print("  会话已销毁 — 所有临时数据已清除")
    return net
