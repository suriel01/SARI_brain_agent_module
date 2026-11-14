"""Phase B S1-S3: the pure alarm state machine and its trigger policy (Alarmo model)."""
import pytest

from app.domain.alarm import (
    DEFAULT_CONFIG,
    INITIAL_STATUS,
    AlarmConfig,
    AlarmState,
    AlarmStatus,
    ArmMode,
    Detection,
    InvalidTransition,
    ModeConfig,
    Outcome,
    ZoneConfig,
    advance,
    arm,
    disarm,
    evaluate,
)

INTRUSION = Detection(event_type="intrusion", confidence=0.9, zone=None, source="Jetson-PTZ_1")
WEAK = Detection(event_type="intrusion", confidence=0.5, zone=None, source="Jetson-PTZ_1")
TAMPER = Detection(event_type="tamper", confidence=1.0, zone=None, source="Jetson-PTZ_1")

ALL_MODES = frozenset(ArmMode)
CONFIG = AlarmConfig(
    modes={
        ArmMode.AWAY: ModeConfig(exit_delay=60, entry_delay=30),
        ArmMode.HOME: ModeConfig(exit_delay=0, entry_delay=20),
        ArmMode.NIGHT: ModeConfig(exit_delay=0, entry_delay=0),
    },
    zones={
        "perimeter": ZoneConfig(modes=ALL_MODES, immediate=True),
        "door": ZoneConfig(modes=ALL_MODES, immediate=False),
        "garden": ZoneConfig(modes=frozenset({ArmMode.AWAY}), immediate=True),
    },
    trigger_time=30,
)


def status(state, mode=None, since=0.0, deadline=None):
    return AlarmStatus(state=state, mode=mode, since=since, deadline=deadline)


DISARMED = status(AlarmState.DISARMED)
AWAY = status(AlarmState.ARMED_AWAY, ArmMode.AWAY)
HOME = status(AlarmState.ARMED_HOME, ArmMode.HOME)


# -- initial state (S7 fail toward safety) ---------------------------------------------------
def test_first_state_is_armed_away_so_today_behavior_is_kept():
    assert INITIAL_STATUS.state is AlarmState.ARMED_AWAY
    assert INITIAL_STATUS.mode is ArmMode.AWAY
    outcome, after = evaluate(INITIAL_STATUS, INTRUSION, 10.0, DEFAULT_CONFIG)
    assert outcome is Outcome.RAISE
    assert after.state is AlarmState.TRIGGERED


# -- arming --------------------------------------------------------------------------------
def test_arm_with_exit_delay_goes_through_arming():
    after = arm(DISARMED, ArmMode.AWAY, 100.0, CONFIG)
    assert after == status(AlarmState.ARMING, ArmMode.AWAY, since=100.0, deadline=160.0)


def test_arm_without_exit_delay_is_armed_at_once():
    assert arm(DISARMED, ArmMode.HOME, 5.0, CONFIG) == status(AlarmState.ARMED_HOME, ArmMode.HOME, since=5.0)
    assert arm(DISARMED, ArmMode.NIGHT, 5.0, CONFIG) == status(AlarmState.ARMED_NIGHT, ArmMode.NIGHT, since=5.0)


def test_arming_completes_when_exit_delay_elapses():
    arming = arm(DISARMED, ArmMode.AWAY, 100.0, CONFIG)
    assert advance(arming, 159.9, CONFIG) == arming
    assert advance(arming, 160.0, CONFIG) == status(AlarmState.ARMED_AWAY, ArmMode.AWAY, since=160.0)


def test_switching_between_armed_modes_is_allowed():
    assert arm(AWAY, ArmMode.NIGHT, 7.0, CONFIG) == status(AlarmState.ARMED_NIGHT, ArmMode.NIGHT, since=7.0)


def test_arming_again_while_arming_restarts_the_exit_delay():
    arming = arm(DISARMED, ArmMode.AWAY, 100.0, CONFIG)
    assert arm(arming, ArmMode.AWAY, 110.0, CONFIG).deadline == 170.0


@pytest.mark.parametrize("state", [AlarmState.PENDING, AlarmState.TRIGGERED])
def test_cannot_arm_while_pending_or_triggered(state):
    with pytest.raises(InvalidTransition):
        arm(status(state, ArmMode.AWAY, deadline=50.0), ArmMode.HOME, 10.0, CONFIG)


# -- disarming -----------------------------------------------------------------------------
@pytest.mark.parametrize("state,mode", [
    (AlarmState.DISARMED, None),
    (AlarmState.ARMING, ArmMode.AWAY),
    (AlarmState.ARMED_AWAY, ArmMode.AWAY),
    (AlarmState.ARMED_HOME, ArmMode.HOME),
    (AlarmState.ARMED_NIGHT, ArmMode.NIGHT),
    (AlarmState.PENDING, ArmMode.AWAY),
    (AlarmState.TRIGGERED, ArmMode.AWAY),
])
def test_disarm_from_every_state(state, mode):
    assert disarm(status(state, mode, deadline=99.0), 42.0) == status(AlarmState.DISARMED, None, since=42.0)


# -- detections and the trigger policy (S2, S3) ---------------------------------------------
def test_alert_while_disarmed_is_recorded_only():
    outcome, after = evaluate(DISARMED, INTRUSION, 10.0, CONFIG)
    assert outcome is Outcome.RECORD_ONLY
    assert after == DISARMED


def test_alert_while_arming_is_recorded_only():
    arming = arm(DISARMED, ArmMode.AWAY, 0.0, CONFIG)
    assert evaluate(arming, INTRUSION, 10.0, CONFIG) == (Outcome.RECORD_ONLY, arming)


def test_weak_or_non_intrusion_detection_never_raises():
    assert evaluate(AWAY, WEAK, 1.0, CONFIG) == (Outcome.RECORD_ONLY, AWAY)
    person = Detection(event_type="person", confidence=0.99, zone=None, source="n")
    assert evaluate(AWAY, person, 1.0, CONFIG) == (Outcome.RECORD_ONLY, AWAY)


def test_threshold_is_inclusive():
    edge = Detection(event_type="intrusion", confidence=0.70, zone=None, source="n")
    assert evaluate(AWAY, edge, 1.0, CONFIG)[0] is Outcome.RAISE


def test_immediate_zone_triggers_at_once():
    outcome, after = evaluate(AWAY, INTRUSION, 10.0, CONFIG)
    assert outcome is Outcome.RAISE
    assert after == AlarmStatus(AlarmState.TRIGGERED, ArmMode.AWAY, since=10.0, deadline=40.0, cause="Jetson-PTZ_1")


def test_unknown_zone_uses_the_default_zone():
    other = Detection(event_type="intrusion", confidence=0.9, zone="nowhere", source="n")
    assert evaluate(AWAY, other, 10.0, CONFIG)[0] is Outcome.RAISE


def test_entry_zone_starts_the_entry_delay():
    door = Detection(event_type="intrusion", confidence=0.9, zone="door", source="cam-door")
    outcome, after = evaluate(HOME, door, 10.0, CONFIG)
    assert outcome is Outcome.ENTRY_DELAY
    assert after == AlarmStatus(AlarmState.PENDING, ArmMode.HOME, since=10.0, deadline=30.0, cause="cam-door")


def test_entry_zone_with_zero_entry_delay_triggers_at_once():
    night = status(AlarmState.ARMED_NIGHT, ArmMode.NIGHT)
    door = Detection(event_type="intrusion", confidence=0.9, zone="door", source="n")
    assert evaluate(night, door, 10.0, CONFIG)[1].state is AlarmState.TRIGGERED


def test_zone_not_armed_in_the_current_mode_is_recorded_only():
    garden = Detection(event_type="intrusion", confidence=0.9, zone="garden", source="n")
    assert evaluate(HOME, garden, 10.0, CONFIG) == (Outcome.RECORD_ONLY, HOME)
    assert evaluate(AWAY, garden, 10.0, CONFIG)[0] is Outcome.RAISE


def test_entry_delay_expiry_triggers():
    pending = AlarmStatus(AlarmState.PENDING, ArmMode.HOME, since=10.0, deadline=30.0, cause="cam-door")
    assert advance(pending, 29.0, CONFIG) == pending
    assert advance(pending, 30.0, CONFIG) == AlarmStatus(
        AlarmState.TRIGGERED, ArmMode.HOME, since=30.0, deadline=60.0, cause="cam-door")


def test_immediate_zone_during_pending_triggers_at_once():
    pending = AlarmStatus(AlarmState.PENDING, ArmMode.HOME, since=10.0, deadline=30.0, cause="cam-door")
    outcome, after = evaluate(pending, INTRUSION, 12.0, CONFIG)
    assert outcome is Outcome.RAISE
    assert after.state is AlarmState.TRIGGERED


def test_entry_zone_during_pending_keeps_counting():
    pending = AlarmStatus(AlarmState.PENDING, ArmMode.HOME, since=10.0, deadline=30.0, cause="cam-door")
    door = Detection(event_type="intrusion", confidence=0.9, zone="door", source="cam-door")
    assert evaluate(pending, door, 12.0, CONFIG) == (Outcome.RECORD_ONLY, pending)


def test_alert_while_triggered_sounds_again_and_extends():
    triggered = AlarmStatus(AlarmState.TRIGGERED, ArmMode.AWAY, since=10.0, deadline=40.0, cause="a")
    outcome, after = evaluate(triggered, INTRUSION, 35.0, CONFIG)
    assert outcome is Outcome.RAISE
    assert after.deadline == 65.0
    assert after.since == 10.0


def test_triggered_returns_to_its_armed_mode():
    triggered = AlarmStatus(AlarmState.TRIGGERED, ArmMode.HOME, since=10.0, deadline=40.0, cause="a")
    assert advance(triggered, 40.0, CONFIG) == status(AlarmState.ARMED_HOME, ArmMode.HOME, since=40.0)


# -- tamper (S2) ---------------------------------------------------------------------------
@pytest.mark.parametrize("before", [DISARMED, AWAY, HOME, status(AlarmState.ARMING, ArmMode.AWAY, deadline=60.0)])
def test_tamper_always_raises(before):
    outcome, after = evaluate(before, TAMPER, 10.0, CONFIG)
    assert outcome is Outcome.RAISE
    assert after.state is AlarmState.TRIGGERED


def test_tamper_while_disarmed_returns_to_disarmed():
    _, triggered = evaluate(DISARMED, TAMPER, 10.0, CONFIG)
    assert triggered.mode is None
    assert advance(triggered, 40.0, CONFIG) == status(AlarmState.DISARMED, None, since=40.0)


# -- states and parsing --------------------------------------------------------------------
def test_state_values_are_the_alarmo_names():
    assert [s.value for s in AlarmState] == [
        "disarmed", "arming", "armed_away", "armed_home", "armed_night", "pending", "triggered"]


def test_mode_parse_rejects_unknown_modes():
    assert ArmMode.parse("away") is ArmMode.AWAY
    assert ArmMode.parse("NIGHT") is ArmMode.NIGHT
    with pytest.raises(InvalidTransition):
        ArmMode.parse("vacation")


def test_advance_without_deadline_is_a_no_op():
    assert advance(AWAY, 1e9, CONFIG) == AWAY
    assert advance(DISARMED, 1e9, CONFIG) == DISARMED


def test_status_round_trips_through_a_dict():
    pending = AlarmStatus(AlarmState.PENDING, ArmMode.HOME, since=10.0, deadline=30.0, cause="cam-door")
    assert AlarmStatus.from_dict(pending.to_dict()) == pending
    assert pending.to_dict() == {"state": "pending", "mode": "home", "since": 10.0, "deadline": 30.0, "cause": "cam-door"}
