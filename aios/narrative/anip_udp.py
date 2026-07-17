"""ANIP over UDP — 网络传输层。

把 ANIP 从进程内内存模拟改成真正的 UDP 网络传输。
保留上层协议（TIF、RelayMessage、PresenceSignal、加密）不变，
替换底层传输：

    send("A", "B", "消息")
      → 内存模式: receiver.pending_messages.append(msg)
      → UDP 模式: socket.sendto(wire_bytes, (中继IP, 端口))

Wire 格式:

    [magic:4][ver:1][type:1][ttl:1][msg_id:8][len:2][payload:N]
    [type==RELAY: hop_idx:2 + sender_ip:4 + port:2 + recv_ip:4 + port:2]

消息类型:
    0x01 RELAY          — 中继消息（需路由头）
    0x02 PRESENCE       — 存在信号
    0x03 PRESENCE_REPLY — 存在回复（含地址信息）
    0x04 PING / 0x05 PONG — 存活探测
"""

from __future__ import annotations

import json
import logging
import queue
import secrets
import socket
import struct
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("aios.narrative.anip_udp")

# ── 帧格式常量 ──

ANIP_MAGIC = b"ANIP"
ANIP_VERSION = 0x02

MSG_RELAY = 0x01
MSG_PRESENCE = 0x02
MSG_PRESENCE_REPLY = 0x03
MSG_PING = 0x04
MSG_PONG = 0x05

FRAME_HEADER_SIZE = 17       # magic(4) + ver(1) + type(1) + ttl(1) + id(8) + len(2)
RELAY_ROUTE_SIZE = 14        # hop_idx(2) + sender_ip(4) + port(2) + recv_ip(4) + port(2)
MAX_PAYLOAD_SIZE = 1400      # 避免 IP 分片
MAX_FRAME_SIZE = FRAME_HEADER_SIZE + MAX_PAYLOAD_SIZE + RELAY_ROUTE_SIZE

DEFAULT_ANIP_PORT = 9200


# ════════════════════════════════════════════════════════════════
# 帧编解码
# ════════════════════════════════════════════════════════════════


def encode_frame(
    msg_type: int,
    payload: bytes,
    current_hop: int = 0,
    sender_addr: tuple[str, int] = ("0.0.0.0", 0),
    receiver_addr: tuple[str, int] = ("0.0.0.0", 0),
) -> bytes:
    """编码 ANIP 帧为二进制。

    Args:
        msg_type: 消息类型（MSG_RELAY 等）
        payload: 载荷字节
        current_hop: 中继链当前跳索引（仅 RELAY）
        sender_addr: 发送方 (ip, port)
        receiver_addr: 接收方 (ip, port)

    Returns:
        二进制帧
    """
    msg_id = secrets.token_bytes(8)
    ttl = 16

    frame = bytearray()
    frame.extend(ANIP_MAGIC)
    frame.append(ANIP_VERSION)
    frame.append(msg_type)
    frame.append(ttl)
    frame.extend(msg_id)
    frame.extend(struct.pack(">H", len(payload)))
    frame.extend(payload)

    if msg_type == MSG_RELAY:
        frame.extend(struct.pack(">H", current_hop))
        try:
            frame.extend(socket.inet_aton(sender_addr[0]))
        except OSError:
            frame.extend(socket.inet_aton("0.0.0.0"))
        frame.extend(struct.pack(">H", sender_addr[1]))
        try:
            frame.extend(socket.inet_aton(receiver_addr[0]))
        except OSError:
            frame.extend(socket.inet_aton("0.0.0.0"))
        frame.extend(struct.pack(">H", receiver_addr[1]))

    return bytes(frame)


def decode_frame(data: bytes) -> Optional[dict]:
    """解码二进制 ANIP 帧。

    Args:
        data: 收到的原始字节

    Returns:
        dict 包含 msg_type / ttl / msg_id / payload 等字段，或 None
    """
    if len(data) < FRAME_HEADER_SIZE:
        return None
    if data[:4] != ANIP_MAGIC:
        return None

    version = data[4]
    msg_type = data[5]
    ttl = data[6]
    msg_id = data[7:15]
    payload_len = struct.unpack(">H", data[15:17])[0]

    if len(data) < FRAME_HEADER_SIZE + payload_len:
        return None

    payload = data[17:17 + payload_len]
    result: dict[str, Any] = {
        "version": version,
        "msg_type": msg_type,
        "ttl": ttl,
        "msg_id": msg_id.hex(),
        "payload": payload,
    }

    if msg_type == MSG_RELAY:
        offset = FRAME_HEADER_SIZE + payload_len
        if len(data) < offset + RELAY_ROUTE_SIZE:
            return None
        hop_idx = struct.unpack(">H", data[offset:offset + 2])[0]
        sender_ip = socket.inet_ntoa(data[offset + 2:offset + 6])
        sender_port = struct.unpack(">H", data[offset + 6:offset + 8])[0]
        receiver_ip = socket.inet_ntoa(data[offset + 8:offset + 12])
        receiver_port = struct.unpack(">H", data[offset + 12:offset + 14])[0]
        result.update({
            "current_hop": hop_idx,
            "sender_addr": (sender_ip, sender_port),
            "receiver_addr": (receiver_ip, receiver_port),
        })

    return result


# ════════════════════════════════════════════════════════════════
# UDPTransport
# ════════════════════════════════════════════════════════════════


class UDPTransport:
    """ANIP 的 UDP 传输层。

    一个进程绑定一个 UDP 端口，接收线程持续处理入站帧。
    中继消息（RELAY）自动判断是否需要转发；最终跳投递到 inbox。

    使用方式:
        transport = UDPTransport()
        port = transport.bind()
        transport.send_frame(frame, ("192.168.1.5", 9200))
        msgs = transport.get_incoming()
        transport.close()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 0):
        self._host = host
        self._port = port
        self._sock: Optional[socket.socket] = None
        self._running = False
        self._recv_thread: Optional[threading.Thread] = None

        # 入站消息队列：(type, payload_dict, sender_addr)
        self._inbox: queue.Queue[tuple[str, dict, tuple]] = queue.Queue()

        # 地址映射：fingerprint_prefix → (ip, port[, node_id])
        # 用于中继转发时查找下一跳地址
        self.relay_addr_map: dict[str, tuple] = {}

        # 回调（可选，非阻塞通知）
        self.on_message: Optional[Callable[[dict, tuple], None]] = None
        # PRESENCE 信号处理回调（由 NodeDiscovery 注册）
        self.on_presence_received: Optional[Callable[[dict, tuple], None]] = None

    # ── 生命周期 ──

    @property
    def port(self) -> int:
        return self._port

    @property
    def address(self) -> tuple[str, int]:
        return (self._host, self._port)

    def bind(self) -> int:
        """创建 UDP socket 并启动接收线程。返回实际端口。"""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind((self._host, self._port))
        except OSError as e:
            logger.error("UDP 绑定 %s:%d 失败: %s", self._host, self._port, e)
            raise
        self._sock.settimeout(1.0)
        self._port = self._sock.getsockname()[1]
        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        logger.info("ANIP UDP bound %s:%d", self._host, self._port)
        return self._port

    def close(self):
        """停止接收线程并关闭 socket。"""
        self._running = False
        if self._recv_thread:
            self._recv_thread.join(timeout=3)
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # ── 发送 ──

    def send_frame(self, frame: bytes, addr: tuple[str, int]) -> bool:
        """发送原始帧到指定地址。"""
        if not self._sock:
            return False
        try:
            self._sock.sendto(frame, addr)
            return True
        except OSError as e:
            logger.debug("sendto %s:%d failed: %s", addr[0], addr[1], e)
            return False

    def send_relay(
        self,
        relay_dict: dict,
        next_hop_addr: tuple[str, int],
        current_hop: int,
        my_addr: tuple[str, int],
    ) -> bool:
        """编码并发送一条中继消息到下一跳。

        Args:
            relay_dict: RelayMessage.to_dict() 格式的 dict
            next_hop_addr: 下一跳的 (ip, port)
            current_hop: 当前跳索引（0 = 发送方）
            my_addr: 本机地址（写入帧头供下一跳知道来源）

        Returns:
            发送成功?
        """
        payload = json.dumps(relay_dict, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_PAYLOAD_SIZE:
            logger.warning("中继消息载荷超限: %d > %d", len(payload), MAX_PAYLOAD_SIZE)
            return False
        frame = encode_frame(
            msg_type=MSG_RELAY,
            payload=payload,
            current_hop=current_hop,
            sender_addr=my_addr,
            receiver_addr=next_hop_addr,
        )
        return self.send_frame(frame, next_hop_addr)

    def send_presence(self, payload_bytes: bytes, mcast_group: str, mcast_port: int):
        """发送存在信号（通常发往组播地址）。"""
        frame = encode_frame(msg_type=MSG_PRESENCE, payload=payload_bytes)
        self.send_frame(frame, (mcast_group, mcast_port))

    # ── 接收循环 ──

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(MAX_FRAME_SIZE)  # type: ignore
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.debug("recvfrom failed")
                break

            try:
                frame = decode_frame(data)
                if frame is None:
                    continue
            except Exception:
                logger.debug("frame decode failed from %s", addr)
                continue

            try:
                self._dispatch_frame(frame, addr)
            except Exception:
                logger.debug("frame dispatch failed from %s", addr)

    def _dispatch_frame(self, frame: dict, recv_addr: tuple[str, int]):
        """分发收到的帧到对应处理逻辑。"""
        msg_type = frame["msg_type"]

        if msg_type == MSG_RELAY:
            self._handle_relay_frame(frame, recv_addr)
        elif msg_type == MSG_PRESENCE:
            self._inbox.put(("presence", frame, recv_addr))
            if self.on_presence_received:
                self.on_presence_received(frame, recv_addr)
        elif msg_type == MSG_PRESENCE_REPLY:
            self._inbox.put(("presence_reply", frame, recv_addr))
            # presence_reply handled by NodeDiscovery via inbox polling
        elif msg_type == MSG_PING:
            # 回复 PONG
            pong = encode_frame(MSG_PONG, b"")
            self.send_frame(pong, recv_addr)
        elif msg_type == MSG_PONG:
            self._inbox.put(("pong", frame, recv_addr))
        else:
            self._inbox.put(("unknown", frame, recv_addr))

    def _handle_relay_frame(self, frame: dict, recv_addr: tuple[str, int]):
        """处理中继消息。

        如果 current_hop 到达 hops 末尾 → 投递到本地 inbox。
        否则 → 查找下一跳地址 → 转发。
        """
        payload = frame["payload"]
        current_hop = frame.get("current_hop", 0)

        try:
            relay_msg = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        hops = relay_msg.get("hops", [])

        if not hops or current_hop >= len(hops):
            # 无中继链或已过最后一跳 → 直接投递
            relay_msg["_recv_addr"] = recv_addr
            self._inbox.put(("relay", relay_msg, recv_addr))
            if self.on_message:
                self.on_message(relay_msg, recv_addr)
            return

        # 检查是否是最终跳
        if current_hop >= len(hops) - 1:
            # 最终跳
            relay_msg["_recv_addr"] = recv_addr
            self._inbox.put(("relay", relay_msg, recv_addr))
            if self.on_message:
                self.on_message(relay_msg, recv_addr)
            return

        # 需要转发：找下一跳
        next_hop_name = hops[current_hop + 1]
        next_hop_addr = self.relay_addr_map.get(next_hop_name)
        if next_hop_addr is None:
            logger.debug("relay: unknown next hop %s", next_hop_name)
            return

        ttl = frame.get("ttl", 16) - 1
        if ttl <= 0:
            logger.debug("relay: TTL expired for %s", relay_msg.get("msg_id", ""))
            return

        relay_frame = encode_frame(
            msg_type=MSG_RELAY,
            payload=payload,
            current_hop=current_hop + 1,
            sender_addr=(frame["sender_addr"][0], frame["sender_addr"][1]),
            receiver_addr=(next_hop_addr[0], next_hop_addr[1]),
        )
        self.send_frame(relay_frame, (next_hop_addr[0], next_hop_addr[1]))

    # ── 消息读取 ──

    def get_incoming(self, timeout: float = 0) -> list[tuple[str, dict, tuple]]:
        """读取所有排队消息（非阻塞）。

        Returns:
            [(msg_type, payload_dict, sender_addr), ...]
        """
        msgs: list[tuple[str, dict, tuple]] = []
        while True:
            try:
                msgs.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return msgs

    def get_incoming_blocking(self, timeout: float = 1.0) -> Optional[tuple[str, dict, tuple]]:
        """阻塞读取一条消息。"""
        try:
            return self._inbox.get(timeout=timeout)
        except queue.Empty:
            return None


# ════════════════════════════════════════════════════════════════
# NodeDiscovery — 节点发现（P0 基本版）
# ════════════════════════════════════════════════════════════════

MCAST_GROUP = "239.255.76.76"
MCAST_PORT = 9210
DISCOVERY_INTERVAL = 60  # 广播间隔（秒）
PEER_EXPIRY = 180  # 未收到消息的超时时间（秒）


class NodeDiscovery:
    """ANIP 节点发现。

    P0: 支持手动注册 + 自动回复 PRESENCE 探测。
    P1+: 完整的局域网组播自动发现。
    """

    def __init__(self, transport: UDPTransport, node_fingerprint: str):
        self._transport = transport
        self._node_fingerprint = node_fingerprint
        self._running = False

        # fingerprint → (ip, port, node_id, last_seen)
        self._peers: dict[str, tuple] = {}

        # 收到 PRESENCE 时注册的回调
        transport.on_presence_received = self._handle_presence

    # ── 手动添加对等节点 ──

    def add_peer(
        self,
        node_id: str,
        fingerprint: str,
        addr: tuple[str, int],
    ):
        """手动注册一个对等节点（用于测试或静态配置）。

        Args:
            node_id: 节点名称
            fingerprint: 对面 TIF 公钥前缀
            addr: (ip, port)
        """
        self._peers[fingerprint] = (addr[0], addr[1], node_id, time.time())
        self._transport.relay_addr_map[fingerprint] = (addr[0], addr[1], node_id)
        logger.info("Discovery: added peer %s @ %s:%d", node_id, addr[0], addr[1])

    def get_peer_by_name(self, node_id: str) -> Optional[tuple[str, int, str]]:
        """按节点名称查找地址。"""
        for fp, (ip, port, nid, _ts) in self._peers.items():
            if nid == node_id:
                return (ip, port, fp)
        return None

    def get_peer_by_fingerprint(self, fingerprint: str) -> Optional[tuple[str, int, str]]:
        """按指纹查找地址。"""
        entry = self._peers.get(fingerprint)
        if entry:
            return (entry[0], entry[1], entry[2])
        return None

    def list_peers(self) -> list[dict]:
        """列出已知对等节点（不含地址，保护隐私）。"""
        return [
            {"node_id": nid, "fingerprint": fp[:12]}
            for fp, (_ip, _port, nid, _ts) in self._peers.items()
        ]

    # ── PRESENCE 处理 ──

    def _handle_presence(self, frame: dict, recv_addr: tuple[str, int]):
        """收到 PRESENCE 信号 → 回复 PRESENCE_REPLY。"""
        try:
            payload_data = json.loads(frame["payload"].decode("utf-8"))
        except Exception:
            return

        remote_fp = payload_data.get("node_fingerprint", "")
        if not remote_fp:
            return

        # 回复：携带本机信息
        reply = json.dumps({
            "fingerprint": self._node_fingerprint,
            "addr": list(self._transport.address),
        }, ensure_ascii=False).encode("utf-8")
        reply_frame = encode_frame(MSG_PRESENCE_REPLY, reply)
        self._transport.send_frame(reply_frame, recv_addr)

    def handle_presence_reply(self, payload_data: dict, recv_addr: tuple[str, int]):
        """处理 PRESENCE_REPLY：学习对方地址。"""
        fp = payload_data.get("fingerprint", "")
        addr_info = payload_data.get("addr")
        if not fp or not addr_info or len(addr_info) < 2:
            return
        ip, port = addr_info[0], int(addr_info[1])
        # 请求方不知道对面 node_id，暂时用 fingerprint 存
        if fp not in self._peers:
            self._peers[fp] = (ip, port, "", time.time())
            self._transport.relay_addr_map[fp] = (ip, port, "")
            logger.debug("Discovery: learned %s @ %s:%d", fp[:12], ip, port)

    def learn_node_id(self, fingerprint: str, node_id: str):
        """关联 fingerprint 和 node_id（在 ANIP 消息交换中学习）。"""
        entry = self._peers.get(fingerprint)
        if entry:
            self._peers[fingerprint] = (entry[0], entry[1], node_id, entry[3])
            self._transport.relay_addr_map[fingerprint] = (entry[0], entry[1], node_id)

    # ── 存活管理 ──

    def update_liveness(self, fingerprint: str):
        """更新节点活跃时间。"""
        entry = self._peers.get(fingerprint)
        if entry:
            self._peers[fingerprint] = (entry[0], entry[1], entry[2], time.time())

    def clean_expired(self):
        """清理过期节点。"""
        now = time.time()
        expired = [fp for fp, (_ip, _port, _nid, ts) in self._peers.items()
                   if now - ts > PEER_EXPIRY]
        for fp in expired:
            self._peers.pop(fp, None)
            self._transport.relay_addr_map.pop(fp, None)
        if expired:
            logger.debug("Discovery: cleaned %d expired peers", len(expired))
