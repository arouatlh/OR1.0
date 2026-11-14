from datetime import UTC, datetime

from app.domain.models import ActionType, Alert, AlertOrigin, AlertStatus, Mode, Sample, Severity
from app.domain.rules import evaluate


def test_rules_sustain_window_and_thresholds():
    eval_time = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)

    # 1. Below sustain count (only 2 samples > 120 bpm) -> no alert
    window = [
        Sample(astronaut_id="astro-a", client_id="c1", recorded_at=eval_time, heart_rate=70),
        Sample(astronaut_id="astro-a", client_id="c2", recorded_at=eval_time, heart_rate=125),
        Sample(astronaut_id="astro-a", client_id="c3", recorded_at=eval_time, heart_rate=128),
    ]
    actions = evaluate("astro-a", window, Mode.NORMAL, {}, sustain_count=3, resolve_count=5, eval_time=eval_time)
    assert len(actions) == 0

    # 2. Satisfies sustain count (3 consecutive samples > 120 bpm) -> Warning alert
    window_warn = [
        Sample(astronaut_id="astro-a", client_id="c1", recorded_at=eval_time, heart_rate=125),
        Sample(astronaut_id="astro-a", client_id="c2", recorded_at=eval_time, heart_rate=128),
        Sample(astronaut_id="astro-a", client_id="c3", recorded_at=eval_time, heart_rate=130),
    ]
    actions = evaluate("astro-a", window_warn, Mode.NORMAL, {}, sustain_count=3, resolve_count=5, eval_time=eval_time)
    assert len(actions) == 1
    assert actions[0].type == ActionType.OPEN
    assert actions[0].alert.severity == Severity.WARNING
    assert actions[0].alert.rule_id == "hr_high"

    # 3. Critical threshold (> 150 bpm) -> Critical alert
    window_crit = [
        Sample(astronaut_id="astro-a", client_id="c1", recorded_at=eval_time, heart_rate=152),
        Sample(astronaut_id="astro-a", client_id="c2", recorded_at=eval_time, heart_rate=155),
        Sample(astronaut_id="astro-a", client_id="c3", recorded_at=eval_time, heart_rate=156),
    ]
    actions = evaluate("astro-a", window_crit, Mode.NORMAL, {}, sustain_count=3, resolve_count=5, eval_time=eval_time)
    assert len(actions) == 1
    assert actions[0].type == ActionType.OPEN
    assert actions[0].alert.severity == Severity.CRITICAL


def test_rules_eva_relaxation():
    eval_time = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)

    # 135 bpm is warning in normal mode (>120), but nominal in EVA mode (>140)
    window = [
        Sample(astronaut_id="astro-a", client_id="c1", recorded_at=eval_time, heart_rate=132),
        Sample(astronaut_id="astro-a", client_id="c2", recorded_at=eval_time, heart_rate=135),
        Sample(astronaut_id="astro-a", client_id="c3", recorded_at=eval_time, heart_rate=138),
    ]
    normal_actions = evaluate("astro-a", window, Mode.NORMAL, {}, sustain_count=3, resolve_count=5, eval_time=eval_time)
    assert len(normal_actions) == 1
    assert normal_actions[0].alert.severity == Severity.WARNING

    eva_actions = evaluate("astro-a", window, Mode.EVA, {}, sustain_count=3, resolve_count=5, eval_time=eval_time)
    assert len(eva_actions) == 0


def test_rules_dedup_escalate_resolve():
    eval_time = datetime(2026, 11, 14, 10, 30, tzinfo=UTC)

    existing_warning = Alert(
        id="alert-1",
        astronaut_id="astro-a",
        rule_id="hr_high",
        severity=Severity.WARNING,
        title="Elevated heart rate",
        message="HR elevated",
        metric="heart_rate",
        value=128.0,
        threshold=120.0,
        status=AlertStatus.OPEN,
        origin=AlertOrigin.RULES,
        created_at=eval_time,
        updated_at=eval_time,
    )
    open_alerts = {"hr_high": existing_warning}

    # 1. Dedup: ongoing warning -> no new actions
    window_warn = [
        Sample(astronaut_id="astro-a", client_id="c1", recorded_at=eval_time, heart_rate=125),
        Sample(astronaut_id="astro-a", client_id="c2", recorded_at=eval_time, heart_rate=128),
        Sample(astronaut_id="astro-a", client_id="c3", recorded_at=eval_time, heart_rate=130),
    ]
    actions = evaluate("astro-a", window_warn, Mode.NORMAL, open_alerts, 3, 5, eval_time)
    assert len(actions) == 0

    # 2. Escalate: HR enters critical (> 150) -> ActionType.ESCALATE
    window_crit = [
        Sample(astronaut_id="astro-a", client_id="c1", recorded_at=eval_time, heart_rate=152),
        Sample(astronaut_id="astro-a", client_id="c2", recorded_at=eval_time, heart_rate=155),
        Sample(astronaut_id="astro-a", client_id="c3", recorded_at=eval_time, heart_rate=156),
    ]
    actions = evaluate("astro-a", window_crit, Mode.NORMAL, open_alerts, 3, 5, eval_time)
    assert len(actions) == 1
    assert actions[0].type == ActionType.ESCALATE
    assert actions[0].alert.severity == Severity.CRITICAL
    assert actions[0].existing_id == "alert-1"

    # 3. Auto-resolve: 5 consecutive in-range samples (< 120 bpm) -> ActionType.RESOLVE
    window_normal = [
        Sample(astronaut_id="astro-a", client_id="c0", recorded_at=eval_time, heart_rate=140),
        Sample(astronaut_id="astro-a", client_id="c1", recorded_at=eval_time, heart_rate=72),
        Sample(astronaut_id="astro-a", client_id="c2", recorded_at=eval_time, heart_rate=74),
        Sample(astronaut_id="astro-a", client_id="c3", recorded_at=eval_time, heart_rate=70),
        Sample(astronaut_id="astro-a", client_id="c4", recorded_at=eval_time, heart_rate=75),
        Sample(astronaut_id="astro-a", client_id="c5", recorded_at=eval_time, heart_rate=71),
    ]
    actions = evaluate("astro-a", window_normal, Mode.NORMAL, open_alerts, 3, 5, eval_time)
    assert len(actions) == 1
    assert actions[0].type == ActionType.RESOLVE
    assert actions[0].alert.status == AlertStatus.RESOLVED
