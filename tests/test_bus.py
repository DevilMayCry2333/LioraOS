"""MessageBus 测试。"""

from aios.kernel.bus import MessageBus, Message, MessageType, get_bus


def test_send_and_subscribe():
    """订阅者应收到定向消息。"""
    bus = MessageBus()
    received = []

    def handler(msg):
        received.append(msg)

    bus.subscribe(MessageType.SYSTEM, recipient="resident_1", callback=handler)
    bus.send(Message(msg_type=MessageType.SYSTEM, sender="system",
                     recipient="resident_1", payload={"hello": "world"}))

    assert len(received) == 1
    assert received[0].payload["hello"] == "world"


def test_broadcast():
    """广播消息（recipient=""）应发送给所有订阅者。"""
    bus = MessageBus()
    received = []

    def handler(msg):
        received.append(msg)

    bus.subscribe(MessageType.PERCEIVE, callback=handler)
    bus.subscribe(MessageType.PERCEIVE, callback=handler)

    bus.send(Message(msg_type=MessageType.PERCEIVE, sender="system",
                     payload={"broadcast": True}))

    assert len(received) == 2


def test_unrelated_subscriber_not_called():
    """不相关消息类型的订阅者不应被调用。"""
    bus = MessageBus()
    called = []

    def handler(msg):
        called.append(msg)

    bus.subscribe(MessageType.ACT, recipient="r1", callback=handler)
    bus.send(Message(msg_type=MessageType.PERCEIVE, sender="system",
                     recipient="r1"))

    assert len(called) == 0


def test_subscriber_exception_isolation():
    """一个订阅者抛异常不应影响其他订阅者。"""
    bus = MessageBus()
    received = []

    def bad_handler(msg):
        raise ValueError("oops")

    def good_handler(msg):
        received.append(msg)

    bus.subscribe(MessageType.SYSTEM, callback=bad_handler)
    bus.subscribe(MessageType.SYSTEM, callback=good_handler)

    bus.send(Message(msg_type=MessageType.SYSTEM, sender="test"))

    assert len(received) == 1


def test_history_limited():
    """历史消息应限制在最近 1000 条。"""
    bus = MessageBus()
    for i in range(1010):
        bus.send(Message(msg_type=MessageType.SYSTEM, sender=str(i)))

    assert bus.count() == 1000  # history 被截断到最近 1000 条

    # get_history 只返回最近 10 条
    assert len(bus.get_history()) == 10
    assert bus.get_history(500) == bus._history[-500:]


def test_get_bus_singleton():
    """get_bus 应返回同一实例。"""
    b1 = get_bus()
    b2 = get_bus()
    assert b1 is b2


def test_message_auto_id():
    """未指定 msg_id 时应自动生成。"""
    msg = Message()
    assert msg.msg_id.startswith("msg_")


def test_message_to_dict():
    """to_dict 应返回可序列化结构。"""
    msg = Message(msg_type=MessageType.ACT, sender="r1", recipient="r2",
                  payload={"action": "touch"})
    d = msg.to_dict()
    assert d["type"] == "act"
    assert d["from"] == "r1"
    assert d["to"] == "r2"
    assert d["payload"] == {"action": "touch"}
