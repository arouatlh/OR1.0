from collections.abc import Sequence

from app.analyzer import analyze
from app.domain.models import Sample
from app.ml.features import extract_features
from app.ml.predictor import AssessmentResult


class DefaultPredictor:
    """Adapts the rules-based analyzer to the backend Predictor interface."""

    version = "rules_v1"

    def predict(self, window: Sequence[Sample]) -> AssessmentResult:
        # Keep samples that contain the two required analyzer measurements.
        valid_samples = [
            sample
            for sample in window
            if sample.heart_rate is not None and sample.spo2 is not None
        ]

        if not valid_samples:
            return AssessmentResult(
                risk_score=0.0,
                label="normal",
                explanation="Insufficient heart rate and SpO2 data for analysis.",
                model_version=self.version,
            )

        latest = valid_samples[-1]

        # Convert the backend Sample object into the analyzer's input format.
        reading = {
            "astronaut_id": latest.astronaut_id,
            "timestamp": latest.recorded_at.isoformat(),
            "heart_rate_bpm": latest.heart_rate,
            "spo2_percent": latest.spo2,
            "activity": "unknown",
        }

        # Previous samples are used for trend detection.
        recent_history = [
            {
                "heart_rate_bpm": sample.heart_rate,
                "spo2_percent": sample.spo2,
            }
            for sample in valid_samples[:-1]
        ]

        result = analyze(
            reading=reading,
            recent_history=recent_history,
        )

        # The analyzer returns 0–100; the backend expects 0–1.
        risk_score = float(result["risk_score"]) / 100.0

        label_map = {
            "low": "normal",
            "review": "warning",
            "critical": "anomaly",
        }

        label = label_map.get(result["risk_level"], "warning")

        explanation = "; ".join(result["reasons"])
        if not explanation:
            explanation = result.get(
                "action",
                "No configured demonstration risk flags.",
            )

        return AssessmentResult(
            risk_score=round(risk_score, 2),
            label=label,
            explanation=explanation,
            model_version=self.version,
        )

