"""Order state machine (PLAN Phase 6). Illegal transitions raise."""
from __future__ import annotations

PLACED = "PLACED"
KYC_PENDING = "KYC_PENDING"
KYC_ACTION_REQUIRED = "KYC_ACTION_REQUIRED"
KYC_REVIEW = "KYC_REVIEW"
KYC_VERIFIED = "KYC_VERIFIED"
INSTALL_SCHEDULED = "INSTALL_SCHEDULED"
TECHNICIAN_ASSIGNED = "TECHNICIAN_ASSIGNED"
INSTALLED = "INSTALLED"
ACTIVATED = "ACTIVATED"
ON_HOLD = "ON_HOLD"
CANCELLED = "CANCELLED"

MAIN_FLOW = [PLACED, KYC_VERIFIED, INSTALL_SCHEDULED, TECHNICIAN_ASSIGNED, INSTALLED, ACTIVATED]  # what the tracker stepper shows
TERMINAL = {ACTIVATED, CANCELLED}

_KYC_OUT = {KYC_PENDING, KYC_ACTION_REQUIRED, KYC_REVIEW, KYC_VERIFIED, CANCELLED}
TRANSITIONS: dict[str, set[str]] = {
    PLACED: {KYC_PENDING, CANCELLED},
    KYC_PENDING: _KYC_OUT | {ON_HOLD},
    KYC_ACTION_REQUIRED: _KYC_OUT,  # after a re-upload the KYC result can go anywhere in the KYC family
    KYC_REVIEW: _KYC_OUT,
    KYC_VERIFIED: {INSTALL_SCHEDULED, ACTIVATED, ON_HOLD, CANCELLED},  # ACTIVATED directly when every line is digital
    INSTALL_SCHEDULED: {TECHNICIAN_ASSIGNED, ON_HOLD, CANCELLED},
    TECHNICIAN_ASSIGNED: {INSTALLED, INSTALL_SCHEDULED, ON_HOLD, CANCELLED},  # back to scheduled = reschedule
    INSTALLED: {ACTIVATED, ON_HOLD},
    ON_HOLD: {KYC_PENDING, KYC_VERIFIED, INSTALL_SCHEDULED, TECHNICIAN_ASSIGNED, INSTALLED, CANCELLED},  # resume returns to the held state
    ACTIVATED: set(),
    CANCELLED: set(),
}
TRANSITIONS = {src: dsts - {src} for src, dsts in TRANSITIONS.items()}  # no self-loops (the KYC service ignores same-state results)

# demo "advance" button: the single forward step from each state
ADVANCE: dict[str, str] = {
    PLACED: KYC_PENDING, KYC_PENDING: KYC_VERIFIED, KYC_ACTION_REQUIRED: KYC_VERIFIED, KYC_REVIEW: KYC_VERIFIED,
    KYC_VERIFIED: INSTALL_SCHEDULED, INSTALL_SCHEDULED: TECHNICIAN_ASSIGNED, TECHNICIAN_ASSIGNED: INSTALLED, INSTALLED: ACTIVATED,
}

# line states
L_PENDING, L_SCHEDULED, L_TECH, L_INSTALLED, L_ACTIVE = "PENDING", "SCHEDULED", "TECHNICIAN_ASSIGNED", "INSTALLED", "ACTIVATED"


class IllegalTransition(Exception):
    def __init__(self, src: str, dst: str):
        super().__init__(f"{src} -> {dst} is not allowed")
        self.src, self.dst = src, dst


def check(src: str, dst: str) -> None:
    if src == dst or dst not in TRANSITIONS.get(src, set()):
        raise IllegalTransition(src, dst)
