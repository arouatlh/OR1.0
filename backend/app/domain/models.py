from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Mode(StrEnum):
    NORMAL = "normal"
    EVA = "eva"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        match self:
            case Severity.CRITICAL:
                return 3
            case Severity.WARNING:
                return 2
            case Severity.INFO:
                return 1
            case _:
                return 0


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertOrigin(StrEnum):
    RULES = "rules"
    AI = "ai"
    DEMO = "demo"


class ActionType(StrEnum):
    OPEN = "open"
    ESCALATE = "escalate"
    RESOLVE = "resolve"


@dataclass(frozen=True)
class Sample:
    astronaut_id: str
    client_id: str
    recorded_at: datetime
    source: str = "watch"
    received_at: datetime | None = None
    heart_rate: int | None = None
    spo2: int | None = None
    systolic: int | None = None
    diastolic: int | None = None
    resp_rate: int | None = None
    ecg_summary: str | None = None
    stress_index: float | None = None
    id: int | None = None


@dataclass
class Astronaut:
    id: str
    display_name: str
    mission: str = ""
    mode: Mode = Mode.NORMAL
    baseline_hr: int = 70
    created_at: datetime | None = None


@dataclass
class Alert:
    id: str
    astronaut_id: str
    rule_id: str
    severity: Severity
    title: str
    message: str
    metric: str
    value: float
    threshold: float
    status: AlertStatus
    origin: AlertOrigin
    created_at: datetime
    updated_at: datetime


@dataclass
class AlertAction:
    type: ActionType
    alert: Alert
    existing_id: str | None = None


@dataclass
class Assessment:
    astronaut_id: str
    model_version: str
    risk_score: float
    label: str
    explanation: str = ""
    id: str | None = None
    created_at: datetime | None = None


@dataclass
class OutboxItem:
    entity: str
    entity_id: str
    payload: str
    created_at: datetime
    id: int | None = None
    synced_at: datetime | None = None
