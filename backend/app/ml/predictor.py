from dataclasses import dataclass
from typing import Protocol, Sequence

from app.domain.models import Sample


@dataclass(frozen=True)
class AssessmentResult:
    risk_score: float  # 0..1
    label: str  # "normal" | "anomaly" | ...
    explanation: str  # short human-readable reason
    model_version: str


class Predictor(Protocol):
    version: str

    def predict(self, window: Sequence[Sample]) -> AssessmentResult:
        ...


class NullPredictor:
    version = "none"

    def predict(self, window: Sequence[Sample]) -> AssessmentResult:
        return AssessmentResult(0.0, "normal", "ML disabled", self.version)
