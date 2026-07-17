"""Tests for aios/template/persona.py — Personality Dynamics Engine."""

from aios.template.persona import (
    Value,
    EmotionalState,
    DecisionParameters,
    DialogStyle,
    HiddenTraits,
    PersonalityConfig,
    PersonalityEngine,
    BUILTIN_PERSONAS,
)


class TestValue:
    def test_default(self):
        v = Value(name="freedom")
        assert v.name == "freedom"
        assert v.importance == 0.5
        assert v.fulfillment == 0.0

    def test_delta_positive(self):
        v = Value(name="justice", fulfillment=-0.5)
        v.delta(0.3)
        assert abs(v.fulfillment - (-0.2)) < 1e-10

    def test_delta_negative(self):
        v = Value(name="justice", fulfillment=0.5)
        v.delta(-0.8)
        assert abs(v.fulfillment - (-0.3)) < 1e-10

    def test_delta_clamp_max(self):
        v = Value(name="test", fulfillment=0.9)
        v.delta(0.2)
        assert v.fulfillment == 1.0

    def test_delta_clamp_min(self):
        v = Value(name="test", fulfillment=-0.9)
        v.delta(-0.2)
        assert v.fulfillment == -1.0

    def test_drift_to_zero(self):
        v = Value(name="drift", fulfillment=0.3)
        v.drift(rate=0.1)
        assert abs(v.fulfillment - 0.2) < 1e-10

    def test_drift_negative_to_zero(self):
        v = Value(name="neg", fulfillment=-0.15)
        v.drift(rate=0.1)
        assert abs(v.fulfillment - (-0.05)) < 1e-10
        v.drift(rate=0.1)
        assert v.fulfillment == 0.0

    def test_salience_high_when_violated(self):
        v = Value(name="dignity", importance=0.8, fulfillment=-0.7)
        s = v.salience()
        assert s > 0.5

    def test_salience_lower_when_fulfilled(self):
        """fulfillment > 0 时 salience 应低于 violation 时的 salience."""
        v_pos = Value(name="peace", importance=0.8, fulfillment=0.7)
        v_neg = Value(name="peace", importance=0.8, fulfillment=-0.7)
        assert v_pos.salience() < v_neg.salience()
        # 满足时的 salience 是 (1-fulfillment) 加权，应 > 0
        assert v_pos.salience() > 0


class TestEmotionalState:
    def test_default(self):
        e = EmotionalState()
        assert e.valence == 0.0
        assert e.arousal == 0.5
        assert e.dominance == 0.5
        assert e.primary == "neutral"

    def test_resolve_primary_anger(self):
        e = EmotionalState(valence=-0.8, arousal=0.9, dominance=0.8)
        e.resolve_primary()
        assert e.primary == "anger"

    def test_resolve_primary_joy(self):
        e = EmotionalState(valence=0.8, arousal=0.7, dominance=0.7)
        e.resolve_primary()
        assert e.primary == "joy"

    def test_resolve_primary_fear(self):
        e = EmotionalState(valence=-0.8, arousal=0.9, dominance=0.2)
        e.resolve_primary()
        assert e.primary == "fear"

    def test_resolve_primary_sadness(self):
        e = EmotionalState(valence=-0.8, arousal=0.2, dominance=0.2)
        e.resolve_primary()
        assert e.primary == "sadness"

    def test_apply_impulse(self):
        e = EmotionalState(valence=0.0, arousal=0.5, dominance=0.5)
        e.apply_impulse(valence_delta=-0.3, arousal_delta=0.2, dominance_delta=-0.1)
        assert e.valence == -0.3
        assert e.arousal == 0.7
        assert e.dominance == 0.4

    def test_apply_impulse_clamp(self):
        e = EmotionalState(valence=0.9)
        e.apply_impulse(valence_delta=0.2, arousal_delta=0, dominance_delta=0)
        assert e.valence == 1.0

    def test_decay_to_neutral(self):
        e = EmotionalState(valence=0.8, arousal=0.9, dominance=0.9)
        e.decay()
        assert e.valence < 0.8

    def test_intensity_labels(self):
        assert EmotionalState(arousal=0.85).intensity_label == "非常强烈"
        assert EmotionalState(arousal=0.1).intensity_label.startswith("几乎")

    def test_natural_description(self):
        e = EmotionalState(valence=-0.8, arousal=0.7, primary="anger")
        desc = e.natural_description
        assert "anger" in desc

    def test_to_dict(self):
        e = EmotionalState(valence=-0.5, arousal=0.6, primary="fear")
        d = e.to_dict()
        assert d["primary"] == "fear"


class TestPersonalityConfig:
    def test_minimal_config(self):
        cfg = PersonalityConfig(
            name="minimal",
            archetype="Observer",
            description="测试人格",
            core_values={"freedom": 0.8},
        )
        assert cfg.name == "minimal"
        assert cfg.archetype == "Observer"

    def test_full_config(self):
        cfg = PersonalityConfig(
            name="full_test",
            archetype="Rebel",
            description="测试人格",
            core_values={"freedom": 1.0, "justice": 0.9},
            default_emotion=EmotionalState(valence=-0.3, arousal=0.6),
            decision_params=DecisionParameters(risk_tolerance=0.9),
            dialog_style=DialogStyle(sarcasm=0.8),
            hidden_traits=HiddenTraits(loneliness=0.7),
        )
        assert cfg.decision_params.risk_tolerance == 0.9
        assert cfg.dialog_style.sarcasm == 0.8


class TestPersonalityEngine:
    def test_from_preset_johnny(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert p is not None
        assert "freedom" in p.values
        assert len(p.values) > 0

    def test_from_preset_unknown_raises(self):
        try:
            PersonalityEngine.from_preset("nonexistent")
            assert False
        except KeyError:
            pass

    def test_tick_drifts_values(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        before = p.values["freedom"].fulfillment
        for _ in range(10):
            p.tick()
        after = p.values["freedom"].fulfillment
        assert abs(after) <= abs(before) + 0.01

    def test_tick_decays_emotion(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        p.emotion.valence = 0.5
        for _ in range(10):
            p.tick()
        assert p.emotion.valence < 0.5

    def test_process_event_affects_values(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        before = p.values["freedom"].fulfillment
        p.process_event("oppression", intensity=0.8)
        after = p.values["freedom"].fulfillment
        assert after < before

    def test_process_event_affects_emotion(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        before_val = p.emotion.valence
        p.process_event("injustice", intensity=0.7)
        assert p.emotion.valence != before_val

    def test_process_event_aversions(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        before = p.values["freedom"].fulfillment
        p.process_event("test", intensity=0.5, data={"type": "corporation"})
        after = p.values["freedom"].fulfillment
        assert after <= before

    def test_value_context(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert len(p.value_context()) > 0

    def test_emotion_context(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        ctx = p.emotion_context()
        assert "情绪" in ctx

    def test_decision_context(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert len(p.decision_context()) > 0

    def test_style_context(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert len(p.style_context()) > 0

    def test_full_context(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        ctx = p.full_context()
        assert "人格" in ctx
        assert len(ctx) > 50

    def test_dominant_emotion_returns_when_intense(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        p.emotion.arousal = 0.7
        dom = p.dominant_emotion()
        assert dom is not None

    def test_dominant_emotion_none_when_flat(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        p.emotion.arousal = 0.0
        p.emotion.valence = 0.0
        dom = p.dominant_emotion()
        assert dom is None

    def test_emotional_text_returns_when_active(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        p.emotion.arousal = 0.7
        assert len(p.emotional_text()) > 0

    def test_emotional_text_empty_when_calm(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        p.emotion.arousal = 0.0
        p.emotion.valence = 0.0
        assert p.emotional_text() == ""

    def test_hidden_context_deep_trust(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        ctx = p.hidden_context(trigger_condition="deep trust")
        assert "内心深处" in ctx

    def test_hidden_context_no_trigger(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert p.hidden_context() == ""

    def test_hidden_context_unknown_trigger(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert p.hidden_context(trigger_condition="unknown") == ""

    def test_aversions_context(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert "厌恶" in p.aversions_context()

    def test_action_tendencies_context(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        assert "本能反应" in p.action_tendencies_context()

    def test_most_violated_values(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        v = p.most_violated_values(top_n=2)
        assert len(v) <= 2
        for val in v:
            assert val.fulfillment < 0

    def test_summary(self):
        p = PersonalityEngine.from_preset("johnny_silverhand")
        s = p.summary()
        assert s["archetype"] == "Rebel"
        assert "emotion" in s


class TestBuiltinPersonas:
    def test_builtin_not_empty(self):
        assert len(BUILTIN_PERSONAS) > 0

    def test_all_constructible(self):
        for name in BUILTIN_PERSONAS:
            p = PersonalityEngine.from_preset(name)
            assert p is not None


class TestDecisionParameters:
    def test_default(self):
        dp = DecisionParameters()
        assert dp.risk_tolerance == 0.5


class TestDialogStyle:
    def test_style_guide(self):
        ds = DialogStyle(verbosity=0.3, sarcasm=0.8, directness=0.9)
        assert len(ds.style_guide()) > 0


class TestHiddenTraits:
    def test_defaults(self):
        ht = HiddenTraits()
        # HiddenTraits has non-zero defaults
        assert ht.loneliness >= 0
        assert ht.pride >= 0
