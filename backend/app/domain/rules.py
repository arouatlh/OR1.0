import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.models import (
    ActionType,
    Alert,
    AlertAction,
    AlertOrigin,
    AlertStatus,
    Mode,
    Sample,
    Severity,
)


@dataclass(frozen=True)
class RuleDef:
    rule_id: str
    metric: str
    title: str
    extract_val: Callable[[Sample], float | None]
    warning_compare: Callable[[float, Mode], bool]
    critical_compare: Callable[[float, Mode], bool]
    warning_thresh: Callable[[Mode], float]
    critical_thresh: Callable[[Mode], float]
    format_msg: Callable[[float, float, Severity], str]


RULES: list[RuleDef] = [
    RuleDef(
        rule_id="hr_high",
        metric="heart_rate",
        title="Elevated heart rate",
        extract_val=lambda s: float(s.heart_rate) if s.heart_rate is not None else None,
        warning_compare=lambda v, m: v > (140.0 if m == Mode.EVA else 120.0),
        critical_compare=lambda v, m: v > (170.0 if m == Mode.EVA else 150.0),
        warning_thresh=lambda m: 140.0 if m == Mode.EVA else 120.0,
        critical_thresh=lambda m: 170.0 if m == Mode.EVA else 150.0,
        format_msg=lambda v, t, s: f"Heart rate {int(v)} bpm exceeds {s} threshold of {int(t)} bpm.",
    ),
    RuleDef(
        rule_id="hr_low",
        metric="heart_rate",
        title="Low heart rate",
        extract_val=lambda s: float(s.heart_rate) if s.heart_rate is not None else None,
        warning_compare=lambda v, m: v < 50.0,
        critical_compare=lambda v, m: v < 40.0,
        warning_thresh=lambda m: 50.0,
        critical_thresh=lambda m: 40.0,
        format_msg=lambda v, t, s: f"Heart rate {int(v)} bpm below {s} threshold of {int(t)} bpm.",
    ),
    RuleDef(
        rule_id="spo2_low",
        metric="spo2",
        title="Low oxygen saturation",
        extract_val=lambda s: float(s.spo2) if s.spo2 is not None else None,
        warning_compare=lambda v, m: v < 94.0,
        critical_compare=lambda v, m: v < 90.0,
        warning_thresh=lambda m: 94.0,
        critical_thresh=lambda m: 90.0,
        format_msg=lambda v, t, s: f"Oxygen saturation {int(v)}% below {s} threshold of {int(t)}%.",
    ),
    RuleDef(
        rule_id="bp_high",
        metric="systolic",
        title="High blood pressure",
        extract_val=lambda s: float(s.systolic) if s.systolic is not None else None,
        warning_compare=lambda v, m: v > 140.0,
        critical_compare=lambda v, m: v > 170.0,
        warning_thresh=lambda m: 140.0,
        critical_thresh=lambda m: 170.0,
        format_msg=lambda v, t, s: f"Systolic blood pressure {int(v)} mmHg exceeds {s} threshold of {int(t)} mmHg.",
    ),
    RuleDef(
        rule_id="bp_low",
        metric="systolic",
        title="Low blood pressure",
        extract_val=lambda s: float(s.systolic) if s.systolic is not None else None,
        warning_compare=lambda v, m: v < 90.0,
        critical_compare=lambda v, m: v < 80.0,
        warning_thresh=lambda m: 90.0,
        critical_thresh=lambda m: 80.0,
        format_msg=lambda v, t, s: f"Systolic blood pressure {int(v)} mmHg below {s} threshold of {int(t)} mmHg.",
    ),
    RuleDef(
        rule_id="rr_high",
        metric="resp_rate",
        title="High respiratory rate",
        extract_val=lambda s: float(s.resp_rate) if s.resp_rate is not None else None,
        warning_compare=lambda v, m: v > 22.0,
        critical_compare=lambda v, m: v > 28.0,
        warning_thresh=lambda m: 22.0,
        critical_thresh=lambda m: 28.0,
        format_msg=lambda v, t, s: f"Respiratory rate {int(v)} breaths/min exceeds {s} threshold of {int(t)} breaths/min.",
    ),
    RuleDef(
        rule_id="rr_low",
        metric="resp_rate",
        title="Low respiratory rate",
        extract_val=lambda s: float(s.resp_rate) if s.resp_rate is not None else None,
        warning_compare=lambda v, m: v < 10.0,
        critical_compare=lambda v, m: v < 8.0,
        warning_thresh=lambda m: 10.0,
        critical_thresh=lambda m: 8.0,
        format_msg=lambda v, t, s: f"Respiratory rate {int(v)} breaths/min below {s} threshold of {int(t)} breaths/min.",
    ),
    RuleDef(
        rule_id="ecg_irregular",
        metric="ecg_summary",
        title="Irregular cardiac rhythm",
        extract_val=lambda s: 1.0 if s.ecg_summary == "irregular" else (0.0 if s.ecg_summary is not None else None),
        warning_compare=lambda v, m: v > 0.5,
        critical_compare=lambda v, m: False,
        warning_thresh=lambda m: 1.0,
        critical_thresh=lambda m: 1.0,
        format_msg=lambda v, t, s: "ECG rhythm marked irregular for 3 consecutive samples.",
    ),
    RuleDef(
        rule_id="stress_high",
        metric="stress_index",
        title="High stress index",
        extract_val=lambda s: float(s.stress_index) if s.stress_index is not None else None,
        warning_compare=lambda v, m: v > 0.7,
        critical_compare=lambda v, m: v > 0.9,
        warning_thresh=lambda m: 0.7,
        critical_thresh=lambda m: 0.9,
        format_msg=lambda v, t, s: f"Stress index {v:.2f} exceeds {s} threshold of {t:.2f}.",
    ),
]


def evaluate(
    astronaut_id: str,
    window: Sequence[Sample],
    mode: Mode,
    open_alerts: dict[str, Alert],
    sustain_count: int = 3,
    resolve_count: int = 5,
    eval_time: datetime | None = None,
) -> list[AlertAction]:
    """Pure evaluation function that inspects a chronological window of samples
    (oldest first) and determines which alert actions to take."""
    if not window:
        return []

    if eval_time is None:
        eval_time = datetime.now(UTC)

    actions: list[AlertAction] = []

    for rule in RULES:
        existing = open_alerts.get(rule.rule_id)
        vals = [rule.extract_val(s) for s in window]

        # 1. Check auto-resolve condition if an alert is currently active
        if existing and existing.status in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED):
            if len(vals) >= resolve_count:
                last_resolve = vals[-resolve_count:]
                if all(
                    v is not None
                    and not rule.warning_compare(v, mode)
                    and not rule.critical_compare(v, mode)
                    for v in last_resolve
                ):
                    resolved_alert = Alert(
                        id=existing.id,
                        astronaut_id=existing.astronaut_id,
                        rule_id=existing.rule_id,
                        severity=existing.severity,
                        title=existing.title,
                        message=existing.message,
                        metric=existing.metric,
                        value=existing.value,
                        threshold=existing.threshold,
                        status=AlertStatus.RESOLVED,
                        origin=existing.origin,
                        created_at=existing.created_at,
                        updated_at=eval_time,
                    )
                    actions.append(AlertAction(type=ActionType.RESOLVE, alert=resolved_alert, existing_id=existing.id))
                    continue

        # 2. Check sustain condition for opening or escalating
        if len(vals) >= sustain_count:
            last_sustain = vals[-sustain_count:]
            if any(v is None for v in last_sustain):
                continue

            all_crit = all(rule.critical_compare(v, mode) for v in last_sustain)  # type: ignore
            all_warn = all(rule.warning_compare(v, mode) or rule.critical_compare(v, mode) for v in last_sustain)  # type: ignore

            latest_val = last_sustain[-1]  # type: ignore
            sev: Severity | None = None
            threshold: float = 0.0

            if all_crit:
                sev = Severity.CRITICAL
                threshold = rule.critical_thresh(mode)
            elif all_warn:
                sev = Severity.WARNING
                threshold = rule.warning_thresh(mode)

            if sev is not None:
                if not existing or existing.status not in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED):
                    new_alert = Alert(
                        id=str(uuid.uuid4()),
                        astronaut_id=astronaut_id,
                        rule_id=rule.rule_id,
                        severity=sev,
                        title=rule.title,
                        message=rule.format_msg(latest_val, threshold, sev),
                        metric=rule.metric,
                        value=latest_val,
                        threshold=threshold,
                        status=AlertStatus.OPEN,
                        origin=AlertOrigin.RULES,
                        created_at=eval_time,
                        updated_at=eval_time,
                    )
                    actions.append(AlertAction(type=ActionType.OPEN, alert=new_alert))
                elif existing.severity.rank < sev.rank:
                    escalated = Alert(
                        id=existing.id,
                        astronaut_id=existing.astronaut_id,
                        rule_id=existing.rule_id,
                        severity=sev,
                        title=rule.title,
                        message=rule.format_msg(latest_val, threshold, sev),
                        metric=rule.metric,
                        value=latest_val,
                        threshold=threshold,
                        status=existing.status,
                        origin=existing.origin,
                        created_at=existing.created_at,
                        updated_at=eval_time,
                    )
                    actions.append(AlertAction(type=ActionType.ESCALATE, alert=escalated, existing_id=existing.id))

    return actions
