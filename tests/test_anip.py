"""Tests for aios/kernel/anip.py — Anonymous Interconnect Protocol."""

import time

from aios.narrative.anip import (
    TIF,
    RelayMessage,
    PresenceSignal,
    encrypt_payload,
    decrypt_payload,
    ANIPNode,
    ANIPNetwork,
    get_anip,
)


def _reset_anip():
    import aios.narrative.anip as m
    m._global_anip = None


class TestTIF:
    def test_generate(self):
        tif = TIF.generate("kaiyu")
        assert tif.node_id == "kaiyu"
        assert len(tif.session_id) == 12
        assert len(tif.public_key) == 64
        assert len(tif.private_key) == 64
        assert tif.created_at > 0

    def test_generate_unique_session(self):
        t1 = TIF.generate("kaiyu")
        t2 = TIF.generate("kaiyu")
        assert t1.session_id != t2.session_id

    def test_destroy(self):
        tif = TIF.generate("kaiyu")
        tif.destroy()
        assert tif.private_key == ""
        assert tif.public_key == ""

    def test_to_dict_obfuscates_key(self):
        tif = TIF.generate("kaiyu")
        d = tif.to_dict()
        assert d["public_key"].endswith("...")
        assert "private_key" not in d


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "这是一条秘密消息"
        cipher = encrypt_payload(plaintext, "receiver_alice")
        decrypted = decrypt_payload(cipher, "receiver_alice")
        assert decrypted == plaintext

    def test_decrypt_wrong_receiver(self):
        plaintext = "secret message"
        cipher = encrypt_payload(plaintext, "alice")
        decrypted = decrypt_payload(cipher, "bob")
        assert decrypted != plaintext

    def test_encrypt_different_salt(self):
        msg = "test"
        c1 = encrypt_payload(msg, "alice")
        c2 = encrypt_payload(msg, "alice")
        assert c1 != c2

    def test_decrypt_invalid_data(self):
        assert decrypt_payload("invalid", "receiver") == "[解密失败]"

    def test_decrypt_bad_format(self):
        assert decrypt_payload("no_colon_here", "receiver") == "[解密失败]"


class TestRelayMessage:
    def test_default(self):
        msg = RelayMessage()
        assert msg.version == "anip-v0.1"
        assert len(msg.salt) == 16
        assert msg.hops == []
        assert msg.timestamp > 0

    def test_expired(self):
        msg = RelayMessage(timestamp=time.time() - 60)
        assert msg.expired(max_age=30) is True

    def test_not_expired(self):
        msg = RelayMessage(timestamp=time.time())
        assert msg.expired(max_age=30) is False

    def test_to_dict(self):
        msg = RelayMessage(
            hops=["node1", "node2", "node3"],
            sender_fingerprint="abc123def456",
            receiver_fingerprint="xyz789",
        )
        d = msg.to_dict()
        assert d["hops"] == 3
        assert len(d["sender"]) == 12


class TestPresenceSignal:
    def test_default(self):
        sig = PresenceSignal(node_fingerprint="test_node")
        assert sig.node_fingerprint == "test_node"
        assert len(sig.path_noise) >= 2
        assert sig.fake_timestamp != 0

    def test_fake_timestamp_differs(self):
        sig = PresenceSignal(node_fingerprint="test")
        now = time.time()
        assert abs(sig.fake_timestamp - now) <= 310

    def test_to_dict(self):
        sig = PresenceSignal(node_fingerprint="abcdef123456")
        d = sig.to_dict()
        assert "fingerprint" in d


class TestANIPNode:
    def test_create(self):
        tif = TIF.generate("test")
        node = ANIPNode(node_id="test", tif=tif)
        assert node.node_id == "test"
        assert node.tif is tif
        assert node.pending_messages == []

    def test_get_known_fingerprints(self):
        tif = TIF.generate("test")
        node = ANIPNode(node_id="test", tif=tif)
        node.active_fingerprints.add("abc123")
        assert "abc123" in node.get_known_fingerprints()


class TestANIPNetwork:
    def setup_method(self):
        self.net = ANIPNetwork()

    def test_join(self):
        tif = self.net.join("kaiyu")
        assert tif.node_id == "kaiyu"
        assert self.net.get_node("kaiyu") is not None

    def test_join_multiple(self):
        self.net.join("kaiyu")
        self.net.join("linan")
        assert len(self.net.list_nodes()) == 2

    def test_leave(self):
        self.net.join("temp")
        self.net.leave("temp")
        assert self.net.get_node("temp") is None

    def test_leave_nonexistent(self):
        self.net.leave("nobody")  # should not raise

    def test_get_node_nonexistent(self):
        assert self.net.get_node("nobody") is None

    def test_list_nodes(self):
        self.net.join("a")
        self.net.join("b")
        nodes = self.net.list_nodes()
        assert "a" in nodes
        assert "b" in nodes

    def test_send_between_nodes(self):
        self.net.join("alice")
        self.net.join("bob")
        msg_id = self.net.send("alice", "bob", "hello bob")
        assert msg_id is not None

    def test_send_nonexistent_sender(self):
        self.net.join("bob")
        assert self.net.send("nobody", "bob", "hello") is None

    def test_send_nonexistent_receiver(self):
        self.net.join("alice")
        assert self.net.send("alice", "nobody", "hello") is None

    def test_receive_dict_structure(self):
        self.net.join("alice")
        self.net.join("bob")
        self.net.send("alice", "bob", "secret message")
        msgs = self.net.receive("bob")
        assert len(msgs) >= 1
        assert msgs[0]["content"] == "secret message"
        assert "sender" in msgs[0]
        assert "timestamp" in msgs[0]

    def test_receive_nonexistent(self):
        assert self.net.receive("nobody") == []

    def test_rotate_relays(self):
        self.net.join("alice")
        self.net.join("bob")
        self.net.join("carol")
        chain = self.net.rotate_relays("alice", "bob")
        assert isinstance(chain, list)

    def test_destroy_session(self):
        self.net.join("alice")
        self.net.join("bob")
        self.net.destroy_session()
        assert self.net.list_nodes() == []

    def test_get_known_nodes_returns_fingerprints(self):
        self.net.join("alice")
        self.net.join("bob")
        nodes = self.net.get_known_nodes("alice")
        # returns fingerprint prefixes, not node IDs
        assert all(isinstance(n, str) and len(n) > 0 for n in nodes)

    def test_get_known_nodes_nonexistent(self):
        assert self.net.get_known_nodes("nobody") == []

    def test_broadcast_presence(self):
        self.net.join("alice")
        self.net.join("bob")
        signal = self.net.broadcast_presence("alice")
        assert signal is not None
        assert isinstance(signal, PresenceSignal)

    def test_broadcast_presence_nonexistent(self):
        assert self.net.broadcast_presence("nobody") is None


class TestGlobalSingleton:
    def setup_method(self):
        _reset_anip()

    def teardown_method(self):
        _reset_anip()

    def test_get_anip(self):
        net1 = get_anip()
        net2 = get_anip()
        assert net1 is net2

    def test_get_anip_creates_network(self):
        net = get_anip()
        assert isinstance(net, ANIPNetwork)
