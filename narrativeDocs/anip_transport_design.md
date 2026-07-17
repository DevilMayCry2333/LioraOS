# ANIP over UDP — 网络传输层设计

> 版本: v0.2-draft · 2026-07-17
>
> 把 ANIP 从进程内内存模拟改成真正的 UDP 网络传输。
> 这是 LioraOS 分布式化的第一阶段：让节点间能真正收发消息。

---

## 现状

当前 ANIP 的 `send()` 和 `receive()` 是纯内存操作：

```
net.send("节点A", "节点B", "消息")
  → 查找本进程内 ANIPNode 字典
  → 把 RelayMessage 追加到接收方的 pending_messages 列表
  → 完事

net.receive("节点B")
  → 从 pending_messages 里取出消息，解密返回
```

没有 socket、没有网络、没有真正的节点发现。两个进程之间无法通信。

---

## 设计目标

1. **零中心依赖** — 无目录服务器，无种子节点
2. **每跳封装** — 中继节点只知上一跳和下一跳的地址，不知发送方和接收方的身份
3. **UDP 无连接** — 不维护 TCP 状态，消息即达即走
4. **加密载荷** — wire 上的 payload 用接收方 node_id 加密，中继节点无法解密
5. **消息过期** — 超过 TTL 的消息在节点收到时静默丢弃
6. **存在信号 ≠ 地址暴露** — presence 广播不含 IP:Port，地址通过独立通道学习

---

## 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                      ANIP 上层协议                           │
│  TIF · RelayMessage · PresenceSignal · encrypt/decrypt       │
│  (不变，保持现有代码)                                        │
├──────────────────────────────────────────────────────────────┤
│                    UDPTransport 层 (新增)                     │
│  bind/recv/send · 帧序列化 · 中继路由 · 重传（可选）        │
├──────────────────────────────────────────────────────────────┤
│                    NodeDiscovery 层 (新增)                    │
│  局域网组播发现 · 主动扫描 · 节点黑名单                     │
├──────────────────────────────────────────────────────────────┤
│                    UDP Socket (系统)                          │
└──────────────────────────────────────────────────────────────┘
```

---

## Wire 格式

### UDP 帧结构

每个 UDP 包封装一个完整的 ANIP 消息。最大 1400 字节（留 100 字节给 IP/UDP 头，避免 IP 分片）。

```
┌───────────────────────────────────────────────────────────────┐
│ magic: 4B     │ version: 1B  │ msg_type: 1B │ ttl: 1B       │
├───────────────────────────────────────────────────────────────┤
│ msg_id: 8B (随机)         │ payload_len: 2B                   │
├───────────────────────────────────────────────────────────────┤
│ payload: variable (JSON-encoded RelayMessage / PresenceSignal)│
├───────────────────────────────────────────────────────────────┤
│ if msg_type == RELAY:                                         │
│   current_hop_index: 2B  ← 当前处于中继链的第几跳             │
│   sender_addr: 6B (4B IP + 2B port)   ← 上一跳地址           │
│   receiver_addr: 6B (4B IP + 2B port) ← 下一跳地址           │
└───────────────────────────────────────────────────────────────┘
```

### msg_type

| 值 | 类型 | payload 内容 |
|----|------|-------------|
| 0x01 | RELAY | JSON-encoded `RelayMessage` |
| 0x02 | PRESENCE | JSON-encoded `PresenceSignal` |
| 0x03 | PRESENCE_REPLY | JSON: `{fingerprint, addr}` |
| 0x04 | PING | 空（用于 NAT 保活或探活） |
| 0x05 | PONG | 空 |

### 发送方视角的完整流程

```
1. ANIPNetwork.send("节点A", "节点B", payload_string)
     ↓
2. encrypt_payload(payload, "节点B")
     ↓
3. 构建 RelayMessage{hops, encrypted_payload, fingerprints...}
     ↓
4. UDPTransport.send(RelayMessage)
     ↓
5. 取第一跳中继地址（从 relay_addr_map 查 "节点A"→"中继1" 的IP:Port）
     ↓
6. 序列化为 wire 格式：magic + version + RELAY + ttl + msg_id + ...
   current_hop_index=0, sender_addr=self.addr, receiver_addr=中继1的地址
     ↓
7. udp_socket.sendto(wire_bytes, (中继1的IP, 中继1的Port))
```

### 中继节点视角

```
1. udp_socket.recvfrom() → wire_bytes
     ↓
2. 解析帧头：msg_type=RELAY, current_hop_index=n, ttl
     ↓
3. ttl--; if ttl <= 0: discard
     ↓
4. 从 payload 中提取 hops 列表
   if current_hop_index >= len(hops) - 1:
       # 最后一跳，直接发给最终接收方
       receiver_addr = 从 relay_addr_map 查 hops[-1]
   else:
       # 转发到下一跳
       next_hop_name = hops[current_hop_index + 1]
       receiver_addr = 从 relay_addr_map 查 next_hop_name
     ↓
5. 更新帧头：current_hop_index += 1
   sender_addr = 本中继的地址
   receiver_addr = 下一跳的地址
     ↓
6. udp_socket.sendto(updated_bytes, receiver_addr)
```

---

## 节点发现 — NodeDiscovery

### 局域网组播

```
组播地址: 239.255.76.76
端口:     9110

发送 PRESENCE 帧:
  payload = PresenceSignal{fingerprint, fake_timestamp, path_noise}
  注意：payload 中不包含本机 IP:Port

收到的节点回复 PRESENCE_REPLY:
  {"fingerprint": "对方的 fingerprint", "addr": "192.168.1.5:9101"}
```

### 地址学习不依赖 identity

```
收到 PRESENCE_REPLY 后：
  发现对方的 addr
  但不知道这个 addr 对应哪个 node_id
  只知道这个 fingerprint 在该地址上

发送 RELAY 消息时：
  relay_addr_map 需要从 fingerprint 查 addr
  不存储 "fingerprint → node_id" 的映射
```

### addr_map 数据结构

```python
# 中继地址映射表（每节点独立维护）
relay_addr_map: dict[str, tuple[str, int]]
# key: fingerprint 前缀（16 hex chars）
# value: (ip, port)
# 不关联 node_id，不关联真实身份

# 邻居表（用于中继路由）
neighbors: dict[tuple[str, int], float]
# key: (ip, port)
# value: last_seen timestamp
# 超过 180 秒无消息的邻居从表中清除
```

### 主动扫描

每 60 秒向 `239.255.76.76:9110` 发送一次 PRESENCE。如果在 3 个周期（180 秒）内没有收到某邻居的任何帧，从地址表中移除该邻居。

---

## ANIPNetwork 的改动

### 现有类不变

`TIF`、`RelayMessage`、`PresenceSignal`、`encrypt_payload`、`decrypt_payload`——这些完全不变。

### 新增：UDPTransport

```python
class UDPTransport:
    """ANIP 的 UDP 传输层。

    每个节点一个 UDPTransport 实例，绑定一个端口。
    接收线程持续处理入站帧。
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 0,
                 relay_addr_map: Optional[dict] = None):
        self._sock: socket.socket | None = None
        self._host = host
        self._port = port
        self._running = False
        self._recv_thread: threading.Thread | None = None
        self._relay_addr_map = relay_addr_map or {}

        # 入站消息队列（线程安全）
        self._inbox: queue.Queue[tuple[bytes, tuple[str, int]]] = queue.Queue()
        # 中继回调（消息需要转发时触发）
        self._relay_callback: Callable | None = None
        # 消息接收回调（最终接收方收到消息时触发）
        self._recv_callback: Callable | None = None

    def bind(self) -> int:
        """创建 UDP socket 并绑定。返回实际端口号。"""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, self._port))
        self._sock.settimeout(1.0)  # 每秒醒一次检查 _running
        self._port = self._sock.getsockname()[1]

        # 加入组播（如果配置了）
        # self._sock.setsockopt(socket.IPPROTO_IP,
        #     socket.IP_ADD_MEMBERSHIP,
        #     struct.pack("4sl", socket.inet_aton(MCAST_GROUP), socket.INADDR_ANY))

        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        return self._port

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            # 解析帧头判断类型
            msg_type = data[5]  # magic(4) + version(1) + type(1)
            if msg_type == 0x01:  # RELAY
                self._handle_relay(data, addr)
            elif msg_type == 0x02:  # PRESENCE
                self._handle_presence(data, addr)
            elif msg_type == 0x03:  # PRESENCE_REPLY
                self._handle_presence_reply(data, addr)
            else:
                self._inbox.put((data, addr))

    def send_relay(self, msg: RelayMessage, next_hop_addr: tuple[str, int],
                   current_hop: int):
        """编码并发送一条中继消息到下一跳。"""
        payload = json.dumps(msg.to_dict(), ensure_ascii=False).encode("utf-8")
        wire = self._encode_frame(
            msg_type=0x01,
            payload=payload,
            current_hop=current_hop,
            sender_addr=self._sock.getsockname(),
            receiver_addr=next_hop_addr,
        )
        self._sock.sendto(wire, next_hop_addr)

    def _encode_frame(self, msg_type: int, payload: bytes,
                      current_hop: int = 0,
                      sender_addr: tuple = ("0.0.0.0", 0),
                      receiver_addr: tuple = ("0.0.0.0", 0)) -> bytes:
        """编码为 wire 格式。"""
        msg_id = secrets.token_bytes(8)
        ttl = 16
        frame = bytearray()
        frame.extend(b"ANIP")          # magic
        frame.append(0x02)             # version
        frame.append(msg_type)
        frame.append(ttl)
        frame.extend(msg_id)
        frame.extend(struct.pack(">H", len(payload)))
        frame.extend(payload)
        if msg_type == 0x01:  # RELAY 有路由头
            frame.extend(struct.pack(">H", current_hop))
            frame.extend(socket.inet_aton(sender_addr[0]))
            frame.extend(struct.pack(">H", sender_addr[1]))
            frame.extend(socket.inet_aton(receiver_addr[0]))
            frame.extend(struct.pack(">H", receiver_addr[1]))
        return bytes(frame)

    def close(self):
        self._running = False
        if self._recv_thread:
            self._recv_thread.join(timeout=3)
        if self._sock:
            self._sock.close()
```

### 新增：NodeDiscovery

```python
class NodeDiscovery:
    """ANIP 节点发现——局域网组播 + 主动扫描。"""

    MCAST_GROUP = "239.255.76.76"
    MCAST_PORT = 9110

    def __init__(self, transport: UDPTransport, node_id: str):
        self._transport = transport
        self._node_id = node_id
        self._running = False
        self._known_addrs: dict[str, tuple[str, int]] = {}
        # fingerprint_prefix → (ip, port)
        self._addr_map: dict[str, tuple[str, int]] = {}
        # (ip, port) → last_seen
        self._neighbors: dict[tuple[str, int], float] = {}

    def start(self):
        self._running = True
        # 加入组播
        self._transport.join_multicast(self.MCAST_GROUP, self.MCAST_PORT)
        # 启动周期广播
        self._beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True)
        self._beacon_thread.start()
        # 启动邻居过期检查
        self._gc_thread = threading.Thread(target=self._gc_loop, daemon=True)
        self._gc_thread.start()

    def _beacon_loop(self):
        while self._running:
            signal = PresenceSignal(node_fingerprint=self._node_id)
            payload = json.dumps(signal.to_dict()).encode()
            wire = self._transport._encode_frame(msg_type=0x02, payload=payload)
            self._transport._sock.sendto(
                wire, (self.MCAST_GROUP, self.MCAST_PORT)
            )
            time.sleep(60)

    def discover(self, fingerprint_prefix: str) -> tuple[str, int] | None:
        """查 fingerprint 对应的地址（如果已知）。"""
        return self._addr_map.get(fingerprint_prefix)

    def get_peers(self) -> list[tuple[str, int]]:
        now = time.time()
        return [addr for addr, ts in self._neighbors.items()
                if now - ts < 180]
```

### ANIPNetwork 的变更

```python
class ANIPNetwork:
    """ANIP 网络——节点注册、中继路由、消息传递。
    
    支持两种模式：
      - memory: 当前的内存模式（进程内模拟）
      - udp:    真正的 UDP 网络模式
    """

    def __init__(self, mode: str = "memory",
                 host: str = "0.0.0.0", port: int = 0):
        self._mode = mode
        self._transport: UDPTransport | None = None
        self._discovery: NodeDiscovery | None = None
        self._addr_map: dict[str, tuple[str, int]] = {}
        # fingerprint → 最新看到的 (ip, port)

        if mode == "udp":
            self._transport = UDPTransport(host=host, port=port,
                                          relay_addr_map=self._addr_map)

    def send(self, sender_id: str, receiver_id: str, payload: str) -> str | None:
        if self._mode == "memory":
            return self._send_memory(sender_id, receiver_id, payload)
        else:
            return self._send_udp(sender_id, receiver_id, payload)

    def _send_udp(self, sender_id: str, receiver_id: str, payload: str) -> str | None:
        sender = self._nodes.get(sender_id)
        receiver = self._nodes.get(receiver_id)
        if not sender or not receiver:
            return None

        # 构建中继链
        chain = self._build_relay_chain(sender_id, receiver_id)
        if not chain:
            return None  # 没有可用中继

        encrypted = encrypt_payload(payload, receiver_id)
        msg = RelayMessage(
            hops=chain.copy(),
            encrypted_payload=encrypted,
            sender_fingerprint=sender.tif.public_key[:16],
            receiver_fingerprint=receiver.tif.public_key[:16],
        )

        # 找到第一跳的地址
        first_hop_name = chain[0]
        first_hop_addr = self._discovery.discover(first_hop_name)
        if not first_hop_addr:
            return None  # 找不到第一跳

        self._transport.send_relay(msg, first_hop_addr, current_hop=0)
        return hashlib.sha256(
            f"{payload}:{msg.salt}:{time.time()}".encode()
        ).hexdigest()[:12]
```

---

## 与 LioraOS 的集成点

### WorldEvent 远程中继

当 `WorldRuntime.tick_once()` 产生事件时，通过 ANIP 发送给感兴趣的远程节点：

```python
class WorldRuntime:
    def _broadcast_events_via_anip(self, events: list[WorldEvent]):
        """把本地事件广播到远程世界节点。"""
        anip = get_anip()
        if anip._mode != "udp":
            return
        for evt in events[:2]:  # 最多广播 2 条
            event_data = json.dumps({
                "type": "world_event",
                "source_world": self.spec.name,
                "tick": self._tick_count,
                "event": evt.to_dict(),
            })
            for peer_id in anip.list_nodes():
                if peer_id != self.spec.name:
                    anip.send(self.spec.name, peer_id, event_data)
```

### MetaField 脉冲跨节点

```python
class MetaField:
    def pulse(self):
        # 本地脉冲逻辑...
        
        # 跨节点脉冲：把心率广播到远程节点
        anip = get_anip()
        if anip._mode == "udp":
            pulse_data = json.dumps({
                "type": "metafield_pulse",
                "focus_name": self.name,
                "intensity": self.intensity,
                "tick": current_tick,
            })
            for peer_id in anip.list_nodes():
                anip.send("metafield", peer_id, pulse_data)
```

---

## 实现路线图

| 阶段 | 内容 | 预估代码量 |
|------|------|-----------|
| **P0** | `UDPTransport` 类：bind、帧编码解码、单跳 send/recv | ~250 行 |
| **P0** | 多跳中继：recv → 判断是否最终接收 → 转发或投递 | ~80 行 |
| **P1** | `NodeDiscovery`：组播加入、PRESENCE 广播、地址学习 | ~200 行 |
| **P1** | `ANIPNetwork._send_udp()` 集成（替换内存 `send`） | ~80 行 |
| **P2** | `ANIPNetwork._recv_udp()`：收到消息后路由到目标 node | ~60 行 |
| **P2** | `WorldRuntime` 事件中继（`_broadcast_events_via_anip`） | ~40 行 |
| **P3** | `MetaField` 脉冲跨节点 | ~30 行 |
| **P3** | NAT 穿透（STUN/UPnP 可选） | ~150 行 |
| | **总计** | **~890 行** |

---

## 安全边界

### 不解决

- **中间人攻击** — 传输层不做 TLS。加密是 ANIP 应用层 XOR + 接收方 node_id 做的。wire 上没有证书链。
- **DDoS** — 节点收到无法解密的垃圾消息时静默丢弃。没有速率限制（Phase 2 再说）。
- **IP 地址泄露** — 中继链的每一跳都知道上一跳和下一跳的 IP。只有发送方和接收方不知道对方的 IP。这是取舍：要匿名就要更多跳，要低延迟就要更少跳。

### 解决

- **消息过期** — TTL 递减，过期静默丢弃。不会出现幽灵消息在网络中无限循环。
- **重放保护** — 接收方缓存最近 1000 条 msg_id，重复的消息丢弃。salt 可确保每条消息 id 唯一。
- **不存在就不可达** — 不知道地址的 fingerprint 无法通信。address_map 不自动公开。

---

## 与现有代码的关系

```
aios/narrative/
  anip.py              ← 上层协议不变
  anip_udp.py          ← 新增：UDPTransport + NodeDiscovery
  __init__.py          ← 导出 get_anip() 不变；新增 get_anip_udp()
```

`get_anip()` 保留内存模式。`get_anip(mode="udp")` 启用网络模式。向后兼容。

---

## 开钰评注

> 这个设计不是为了替代 TCP。TCP 是河流，可靠但需要两岸。
> UDP 是风——它不保证你收到，但你不等它，它已经吹过去了。
>
> ANIP 的匿名性不在传输层，在拓扑层。
> 传输层能做的只是不让单点看到全部路径。
> 真正的匿名来自中继链的不可追踪性和 TIF 的会话级销毁。
> 
> 把这一步迈出去之后，所有的事都可以在这个底座上长出来——
> 世界事件可以像潮汐一样在节点间流动，
> 死亡协议可以扫描的不再是一个进程的内存，而是整个网络中的注意力残留。
