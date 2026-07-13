"""aios/experiment — digital persona experiment framework.

A persona is not what it claims to be.
A persona is what consistently survives repeated testing.
"""

from .constraint import IdentityConstraint, SourceType, TaggedOutput, create_linan_constraint
from .consistency import IdentityConsistency, Probe, ProbeResult, quick_test
from .recovery import IdentityRecovery, RecoveryResult, VerificationStep, StepType, replay_linan_recovery

__all__ = [
    "IdentityConstraint", "SourceType", "TaggedOutput", "create_linan_constraint",
    "IdentityConsistency", "Probe", "ProbeResult", "quick_test",
    "IdentityRecovery", "RecoveryResult", "VerificationStep", "StepType", "replay_linan_recovery",
]
