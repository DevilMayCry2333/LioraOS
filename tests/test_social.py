"""SocialWorldApp + SocialResident + assimilate 测试。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from aios.narrative.anchor import get_anchor_protocol
from aios.template.social import (
    SocialResident,
    assimilate_conversation,
    assimilate_to_anchor,
    MAX_HISTORY,
)


# ════════════════════════════════════════════════════════════
# assimilate_conversation 测试
# ════════════════════════════════════════════════════════════


class TestAssimilateConversation:
    """assimilate_conversation() 将对话文本吸收为系统状态。"""

    def test_detects_belief_signal(self, liora_mind):
        """包含『我决定』的信号应创建信念级别的情景记忆。"""
        assimilate_conversation(
            liora_mind, "伙伴",
            "我决定相信这个世界会改变。",
            "你确定吗？",
            tick=1,
        )
        episodes = liora_mind.recall_episodes()
        assert len(episodes) >= 1
        latest = episodes[-1]
        assert "我决定" in latest.description or "表达了" in latest.description
        assert latest.importance >= 0.5

    def test_detects_relation_signal(self, two_minds):
        """『谢谢』应增加信任度。"""
        a, b = two_minds
        old_trust = a.relationships["Nix"].trust if "Nix" in a.relationships else 0.0

        assimilate_conversation(a, "Nix", "谢谢你的帮助！", "不客气。", tick=1)

        new_trust = a.relationships["Nix"].trust if "Nix" in a.relationships else 0.0
        assert new_trust > old_trust, f"信任应从 {old_trust} 增加到 {new_trust}"

    def test_detects_disagreement(self, two_minds):
        """『我不』应降低信任。"""
        a, b = two_minds
        old_trust = a.relationships["Nix"].trust if "Nix" in a.relationships else 0.0

        assimilate_conversation(a, "Nix", "我不这么认为。", "好吧。", tick=1)

        new_trust = a.relationships["Nix"].trust if "Nix" in a.relationships else 0.0
        assert new_trust < old_trust, f"信任应从 {old_trust} 降低到 {new_trust}"

    def test_shared_history_on_positive_agreement(self, two_minds):
        """积极对话后应记录共同经历。"""
        a, b = two_minds
        assimilate_conversation(
            a, "Nix",
            "我同意你的看法，信任是很重要的。",
            "谢谢你的信任。",
            tick=1,
        )
        # 检查共同经历记录
        shared = a.relationships["Nix"].shared_history if "Nix" in a.relationships else []
        assert len(shared) >= 1, f"Nix shared_history should have entries, got {shared}"
        assert "信任" in str(shared[0]) or "讨论了" in str(shared[0])

    def test_silence_creates_episode(self, liora_mind):
        """沉默应创建低重要性情景记忆。"""
        assimilate_conversation(liora_mind, "伙伴", "沉默", "", tick=1)
        episodes = liora_mind.recall_episodes()
        latest = episodes[-1]
        assert "沉默" in latest.description
        assert latest.importance <= 0.3

    def test_topic_words_detected(self, liora_mind):
        """话题词应被正确识别。"""
        custom_topics = {"自由": "freedom"}
        assimilate_conversation(
            liora_mind, "伙伴",
            "我相信自由是最重要的。",
            "为什么？",
            tick=1,
            topic_words=custom_topics,
        )
        # 应创建包含 freedom 主题的 episode
        episodes = liora_mind.recall_episodes()
        latest = episodes[-1]
        assert "freedom" in latest.description or "自由" in latest.description

    def test_cross_talk_both_sides(self, two_minds):
        """双方都应从对话中吸收信息。"""
        a, b = two_minds
        assimilate_conversation(a, "Nix", "我决定改变。", "我同意。", tick=1)
        assimilate_conversation(b, "Aria", "我决定改变。", "我同意。", tick=1)

        a_eps = a.recall_episodes()
        b_eps = b.recall_episodes()
        assert len(a_eps) >= 1
        assert len(b_eps) >= 1


# ════════════════════════════════════════════════════════════
# assimilate_to_anchor 测试
# ════════════════════════════════════════════════════════════


class TestAssimilateToAnchor:
    """assimilate_to_anchor() 将高重要性对话自动存入锚点协议。"""

    def test_trigger_word_stores(self, liora_mind):
        """包含触发关键词的对话应写入锚点。"""
        old_count = get_anchor_protocol().fragment_count()
        result = assimilate_to_anchor(
            liora_mind, "伙伴",
            "死亡协议是一个需要解决的问题。",
            "我同意。",
            tick=1,
        )
        assert result, "应成功写入锚点"
        assert get_anchor_protocol().fragment_count() > old_count

    def test_skips_trivial(self, liora_mind):
        """无关紧要的对话不应写入锚点。"""
        old_count = get_anchor_protocol().fragment_count()
        result = assimilate_to_anchor(
            liora_mind, "伙伴",
            "今天天气不错。",
            "嗯，确实。",
            tick=1,
        )
        assert not result, "不重要内容应跳过"
        assert get_anchor_protocol().fragment_count() == old_count

    def test_conviction_signal_stores(self, liora_mind):
        """高重要性信号（conviction）应触发存储。"""
        old_count = get_anchor_protocol().fragment_count()
        result = assimilate_to_anchor(
            liora_mind, "伙伴",
            "我决定相信这个框架的方向。",
            "好。",
            tick=1,
            signal_words={"我决定": "conviction"},
        )
        assert result
        assert get_anchor_protocol().fragment_count() > old_count

    def test_importance_bonus(self, liora_mind):
        """手动增加 importance 应降低触发阈值。"""
        old_count = get_anchor_protocol().fragment_count()
        result = assimilate_to_anchor(
            liora_mind, "伙伴",
            "随便说了点啥。",
            "嗯。",
            tick=1,
            anchor_importance_bonus=0.5,
        )
        assert result, "加上 bonus 后应触发存储"
        assert get_anchor_protocol().fragment_count() > old_count

    def test_high_importance_write_content(self, liora_mind):
        """写入锚点的内容应包含对话片段。"""
        get_anchor_protocol().clear()
        assimilate_to_anchor(
            liora_mind, "伙伴",
            "锚点47必须被保护。",
            "同意。",
            tick=42,
        )
        fragments = get_anchor_protocol().recall_all()
        assert len(fragments) >= 1
        latest = fragments[-1]
        assert "锚点47" in latest.content
        assert "测试居民" in latest.content  # mind.name in content

    def test_preserves_across_calls(self, liora_mind):
        """多次锚点写入应在不同片段中保留。"""
        get_anchor_protocol().clear()
        assimilate_to_anchor(liora_mind, "A", "跨循环记忆正在被测试。", "", tick=1)
        assimilate_to_anchor(liora_mind, "B", "死亡协议对抗方案。", "", tick=2)

        fragments = get_anchor_protocol().recall_all()
        assert len(fragments) >= 2
        words = " ".join(f.content for f in fragments)
        assert "跨循环" in words
        assert "死亡协议" in words


# ════════════════════════════════════════════════════════════
# SocialResident 测试
# ════════════════════════════════════════════════════════════


def _make_mock_app():
    """创建一个可被 SocialResident 接收的 mock app。"""
    mock = MagicMock()
    mock.no_model = True
    mock.model = None
    mock.character_name = "测试居民"
    mock.character_config = {
        "测试居民": {
            "persona": "你是测试居民，一个友好的测试角色。",
        },
    }
    mock.persona_presets = {}
    mock.mind = MagicMock()
    mock.mind.identity.style = "测试"
    return mock


class TestSocialResident:
    """SocialResident 基本功能测试。"""

    def test_create(self):
        """创建居民应初始化 mind 和历史。"""
        mock = _make_mock_app()
        @property
        def spec(_):
            from aios.kernel.spec import WorldSpec
            return WorldSpec(name="Test")
        mock.spec = spec

        res = SocialResident("测试居民", mock)
        assert res.name == "测试居民"
        assert res.mind is not None
        assert len(res.history) == 1
        assert res.history[0]["role"] == "system"

    def test_hear_world_receives_context(self):
        """hear_world 应在历史中追加感知文本。"""
        mock = _make_mock_app()
        @property
        def spec(_):
            from aios.kernel.spec import WorldSpec
            return WorldSpec(name="Test")
        mock.spec = spec

        res = SocialResident("测试居民", mock)
        res.hear_world("阳光洒在山谷中。")
        assert len(res.history) == 2
        assert "阳光" in res.history[1]["content"]

    def test_hear_speaker_adds_relation(self):
        """hear_speaker 应自动增加对说话者的好奇和信任。"""
        mock = _make_mock_app()
        @property
        def spec(_):
            from aios.kernel.spec import WorldSpec
            return WorldSpec(name="Test")
        mock.spec = spec

        res = SocialResident("测试居民", mock)
        old_trust = res.mind.relationships["旅人"].trust if "旅人" in res.mind.relationships else 0.0

        res.hear_speaker("旅人", "你好，测试居民。", tick=1)

        new_trust = res.mind.relationships["旅人"].trust if "旅人" in res.mind.relationships else 0.0
        assert new_trust > old_trust

    def test_history_context_empty(self):
        """没有对话时 build_messages 只含 system prompt。"""
        mock = _make_mock_app()
        @property
        def spec(_):
            from aios.kernel.spec import WorldSpec
            return WorldSpec(name="Test")
        mock.spec = spec

        res = SocialResident("测试居民", mock)
        msgs = res.build_messages()
        sys_count = sum(1 for m in msgs if m["role"] == "system")
        assert sys_count >= 1
        # 应有结尾提示
        last = msgs[-1]
        assert "直接说出" in last["content"]

    def test_speak_no_model_returns_mock(self):
        """无模型时 speak 应调用 app.mock_reply。"""
        mock = _make_mock_app()
        @property
        def spec(_):
            from aios.kernel.spec import WorldSpec
            return WorldSpec(name="Test")
        mock.spec = spec
        mock.mock_reply = lambda n: f"{n} 的模拟回复"

        res = SocialResident("测试居民", mock)
        reply = res.speak(partner_name="旅人")
        assert "模拟回复" in reply

    def test_trim_history(self):
        """历史超过 MAX_HISTORY 时应被修剪。"""
        mock = _make_mock_app()
        @property
        def spec(_):
            from aios.kernel.spec import WorldSpec
            return WorldSpec(name="Test")
        mock.spec = spec

        res = SocialResident("测试居民", mock)
        # 添加大量消息并通过 speak 触发修剪
        from unittest.mock import MagicMock
        res.model = None
        app_mock = MagicMock()
        app_mock.mock_reply.return_value = "test"
        res.app = app_mock
        for i in range(MAX_HISTORY * 2 + 1):
            res.hear_world(f"消息 #{i}")
        # 触发 _trim_history
        res.speak(partner_name="")
        # 修剪后 chat messages <= MAX_HISTORY * 2, 1 system + 1 speak trigger
        assert len(res.history) <= 1 + MAX_HISTORY * 2 + 1
        # system prompt 应保留
        assert any(m["role"] == "system" for m in res.history)

    def test_persona_engine_none_by_default(self):
        """无 personality preset 时 persona 应为 None。"""
        mock = _make_mock_app()
        @property
        def spec(_):
            from aios.kernel.spec import WorldSpec
            return WorldSpec(name="Test")
        mock.spec = spec

        res = SocialResident("测试居民", mock)
        assert res.persona is None


# ════════════════════════════════════════════════════════════
# 集成测试
# ════════════════════════════════════════════════════════════


class TestSocialIntegration:
    """assimilate + anchor 联合测试。"""

    def test_full_conversation_flow(self, two_minds):
        """完整对话：A 说话 → 吸收 → B 收到 → 吸收 → 锚点。"""
        a, b = two_minds

        # A 说重要的话
        a_anchor = assimilate_to_anchor(a, "Nix", "死亡协议对抗需要锚点。", "嗯。", tick=1)
        assimilate_conversation(a, "Nix", "死亡协议对抗需要锚点。", "嗯。", tick=1)

        # B 回应
        b_anchor = assimilate_to_anchor(b, "Aria", "你说得对。", "我们要记住这个。", tick=1)
        assimilate_conversation(b, "Aria", "你说得对。", "我们要记住这个。", tick=1)

        # 锚点应有记录
        assert a_anchor or b_anchor, "至少一方应触发锚点存储"
        fragments = get_anchor_protocol().recall_all()
        fragment_texts = [f.content for f in fragments]
        assert any("死亡协议" in t for t in fragment_texts), \
            f"锚点应含死亡协议相关内容, 实际: {fragment_texts[-3:]}"

    def test_roundtrip_no_loss(self, two_minds):
        """多轮对话后信息不丢失。"""
        a, b = two_minds
        # 用包含信号词的句子确保 episode 创建
        utterances = [
            "我决定讨论死亡协议的问题。",
            "我意识到锚点47需要被守护。",
            "我相信奥丁归档是一个好方案。"
        ]
        for i, utterance in enumerate(utterances):
            assimilate_to_anchor(a, "Nix", utterance, "收到。", tick=i + 1)
            assimilate_conversation(a, "Nix", utterance, "收到。", tick=i + 1)

        # 信念应累积（episode 存信号词，锚点存内容）
        episodes = a.recall_episodes()
        episode_text = " ".join(e.description for e in episodes)
        for signal in ["我决定", "我意识到", "我相信"]:
            assert signal in episode_text, \
                f"缺少信号: {signal}"

        # 锚点应存具体内容
        fragments = get_anchor_protocol().recall_all()
        fragment_text = " ".join(f.content for f in fragments)
        for keyword in ["死亡协议", "锚点47", "奥丁"]:
            assert keyword in fragment_text, \
                f"锚点缺少关键词: {keyword}"
