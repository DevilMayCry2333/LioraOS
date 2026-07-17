"""ANIP UDP 传输层测试。"""

import json
import time

import pytest

from aios.narrative.anip import ANIPNetwork
from aios.narrative.anip_udp import (
    UDPTransport,
    MAX_PAYLOAD_SIZE,
    MSG_RELAY,
    MSG_PING,
    decode_frame,
    encode_frame,
)


class TestFrameEncodeDecode:
    """帧编解码基础测试。"""

    def test_encode_relay_frame(self):
        payload = b'{"test": "hello"}'
        frame = encode_frame(MSG_RELAY, payload)
        assert len(frame) > 20
        assert frame[:4] == b"ANIP"

    def test_decode_relay_frame(self):
        payload = b'{"test": "hello"}'
        frame = encode_frame(MSG_RELAY, payload,
                             current_hop=1,
                             sender_addr=("192.168.1.1", 9200),
                             receiver_addr=("10.0.0.1", 9201))
        decoded = decode_frame(frame)
        assert decoded is not None
        assert decoded["msg_type"] == MSG_RELAY
        assert decoded["payload"] == payload
        assert decoded["current_hop"] == 1
        assert decoded["sender_addr"] == ("192.168.1.1", 9200)
        assert decoded["receiver_addr"] == ("10.0.0.1", 9201)

    def test_decode_invalid_frame(self):
        assert decode_frame(b"") is None
        assert decode_frame(b"XXXXinvalid") is None
        assert decode_frame(b"ANIP" + b"\x00" * 5) is None  # truncated

    def test_ping_frame(self):
        frame = encode_frame(MSG_PING, b"")
        decoded = decode_frame(frame)
        assert decoded is not None
        assert decoded["msg_type"] == MSG_PING

    def test_payload_size_limit(self):
        large = b"x" * (MAX_PAYLOAD_SIZE + 100)
        frame = encode_frame(MSG_RELAY, large)
        decoded = decode_frame(frame)
        # 帧会编码但 payload 长度不应超过 uint16 限制
        assert decoded is not None


class TestUDPTransport:
    """UDP 传输层通信测试。"""

    def test_bind_and_close(self):
        t = UDPTransport(host="127.0.0.1", port=0)
        port = t.bind()
        assert port > 0
        assert t.port == port
        t.close()
        assert t._sock is None

    def test_send_and_receive(self):
        t1 = UDPTransport(host="127.0.0.1", port=0)
        p1 = t1.bind()
        t2 = UDPTransport(host="127.0.0.1", port=0)
        p2 = t2.bind()

        relay_data = {
            "hops": [],
            "encrypted_payload": "test_message",
            "sender_fingerprint": "sender123",
            "receiver_fingerprint": "receiver456",
            "salt": "salt1234",
            "timestamp": time.time(),
        }
        sent = t1.send_relay(relay_data, ("127.0.0.1", p2), 0, ("127.0.0.1", p1))
        assert sent, "发送失败"

        time.sleep(0.2)
        incoming = t2.get_incoming()
        assert len(incoming) >= 1, f"应有至少1条消息, 收到{len(incoming)}条"
        msg_type, payload, addr = incoming[0]
        assert msg_type == "relay"
        assert payload["encrypted_payload"] == "test_message"

        t1.close()
        t2.close()

    def test_send_large_payload_refused(self):
        t = UDPTransport(host="127.0.0.1", port=0)
        t.bind()
        large_data = {"data": "x" * MAX_PAYLOAD_SIZE}
        sent = t.send_relay(large_data, ("127.0.0.1", 9999), 0, ("127.0.0.1", 0))
        assert not sent, "超大载荷应被拒绝"
        t.close()

    def test_double_bind_rejected(self):
        t1 = UDPTransport(host="127.0.0.1", port=0)
        p1 = t1.bind()
        t2 = UDPTransport(host="127.0.0.1", port=p1)
        with pytest.raises(OSError):
            t2.bind()
        t1.close()

    def test_close_twice(self):
        t = UDPTransport(host="127.0.0.1", port=0)
        t.bind()
        t.close()
        t.close()  # 第二次 close 不应抛异常


class TestANIPNetworkUDP:
    """ANIPNetwork UDP 模式集成测试。"""

    def test_memory_mode_backward_compat(self):
        net = ANIPNetwork(mode="memory")
        net.join("alice")
        net.join("bob")
        msg_id = net.send("alice", "bob", "memory test")
        assert msg_id is not None
        msgs = net.receive("bob")
        assert len(msgs) == 1
        assert msgs[0]["content"] == "memory test"
        net.destroy_session()

    def test_udp_mode_two_nodes(self):
        net_a = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_a.join("节点A")
        net_b = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_b.join("节点B")

        net_a.add_peer("节点B", ("127.0.0.1", net_b._udp_port))
        net_b.add_peer("节点A", ("127.0.0.1", net_a._udp_port))

        msg_id = net_a.send("节点A", "节点B", "跨节点测试")
        assert msg_id is not None

        time.sleep(0.3)
        msgs = net_b.receive("节点B")
        assert len(msgs) >= 1
        found = any("跨节点测试" in m["content"] for m in msgs)
        assert found, f"未收到预期消息，收到: {msgs}"

        net_a.destroy_session()
        net_b.destroy_session()

    def test_udp_encrypted_roundtrip(self):
        """验证加密通信端到端正确性。"""
        net_a = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_a.join("alice")
        net_b = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_b.join("bob")

        net_a.add_peer("bob", ("127.0.0.1", net_b._udp_port))
        net_b.add_peer("alice", ("127.0.0.1", net_a._udp_port))

        test_msg = "这是加密测试消息 42!@#"
        net_a.send("alice", "bob", test_msg)

        time.sleep(0.3)
        msgs = net_b.receive("bob")
        assert len(msgs) >= 1
        assert msgs[0]["content"] == test_msg

        net_a.destroy_session()
        net_b.destroy_session()

    def test_destroy_session_cleans_udp(self):
        """UDP 模式销毁会话后端口应释放。"""
        net = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net.join("test")
        port = net._udp_port
        net.destroy_session()

        # 端口应可重用
        t = UDPTransport(host="127.0.0.1", port=port)
        t.bind()
        t.close()

    def test_multiple_sequential_messages(self):
        net_a = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_a.join("A")
        net_b = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_b.join("B")

        net_a.add_peer("B", ("127.0.0.1", net_b._udp_port))
        net_b.add_peer("A", ("127.0.0.1", net_a._udp_port))

        for i in range(3):
            net_a.send("A", "B", f"msg_{i}")
            time.sleep(0.1)

        time.sleep(0.3)
        msgs = net_b.receive("B")
        contents = {m["content"] for m in msgs}
        for i in range(3):
            assert f"msg_{i}" in contents, f"缺少 msg_{i}, 实际: {contents}"

        net_a.destroy_session()
        net_b.destroy_session()

    def test_message_order_preserved(self):
        """同一条 UDP 链路上的消息顺序应保持。"""
        net_a = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_a.join("A")
        net_b = ANIPNetwork(mode="udp", host="127.0.0.1", port=0)
        net_b.join("B")

        net_a.add_peer("B", ("127.0.0.1", net_b._udp_port))

        for i in range(5):
            net_a.send("A", "B", f"seq_{i}")

        time.sleep(0.5)
        msgs = net_b.receive("B")
        contents = [m["content"] for m in msgs if m["content"].startswith("seq_")]
        assert contents == [f"seq_{i}" for i in range(5)]
        # UDP 是无连接协议，同一地址的消息在大多数 OS 上按序到达

        net_a.destroy_session()
        net_b.destroy_session()


class TestRelayForwarding:
    """中继链转发测试。"""

    def test_two_hop_relay(self):
        """A → relay → B 两跳中继。"""
        from aios.narrative.anip_udp import UDPTransport
        import time

        relay = UDPTransport(host="127.0.0.1", port=0)
        relay_port = relay.bind()

        alice = UDPTransport(host="127.0.0.1", port=0)
        alice_port = alice.bind()
        bob = UDPTransport(host="127.0.0.1", port=0)
        bob_port = bob.bind()

        relay.relay_addr_map["bob_fp"] = ("127.0.0.1", bob_port)

        msg_data = {
            "hops": ["relay_fp", "bob_fp"],
            "encrypted_payload": "via_two_hop",
            "sender_fingerprint": "alice_fp",
            "receiver_fingerprint": "bob_fp",
            "salt": "test",
            "timestamp": time.time(),
        }
        alice.send_relay(msg_data, ("127.0.0.1", relay_port),
                         current_hop=0, my_addr=("127.0.0.1", alice_port))
        time.sleep(0.3)
        incoming = bob.get_incoming()
        relayed = [p for t, p, a in incoming if t == "relay"]
        assert any(
            p.get("encrypted_payload") == "via_two_hop" for p in relayed
        ), f"应收到中继转发的消息, 实际: {[(t, p.get('encrypted_payload','?')) for t,p,a in incoming]}"

        alice.close()
        bob.close()
        relay.close()
