from collections.abc import Sequence

from app.domain.models import Sample
from app.ml.features import extract_features
from app.ml.predictor import AssessmentResult


class DefaultPredictor:
    """Production ML Predictor for in-process anomaly assessment.
    Fast, CPU-bound, free of I/O."""

    version = "v1.0-anomaly-detector"

    def predict(self, window: Sequence[Sample]) -> AssessmentResult:
        feats = extract_features(window)

        # Baseline anomaly score calculation
        risk_score = 0.05
        factors: list[str] = []

        if feats["hr_mean"] > 130:
            risk_score += 0.45
            factors.append(f"mean HR elevated ({feats['hr_mean']:.0f} bpm)")
        elif feats["hr_mean"] < 45:
            risk_score += 0.40
            factors.append(f"mean HR depressed ({feats['hr_mean']:.0f} bpm)")

        if feats["spo2_min"] < 92:
            risk_score += 0.40
            factors.append(f"SpO2 desaturation observed ({feats['spo2_min']:.0f}%)")

        if feats["stress_mean"] > 0.8:
            risk_score += 0.25
            factors.append(f"chronic stress index ({feats['stress_mean']:.2f})")

        risk_score = min(max(risk_score, 0.0), 1.0)
        label = "anomaly" if risk_score >= 0.7 else ("warning" if risk_score >= 0.5 else "normal")
        explanation = "; ".join(factors) if factors else "Vitals operating within nominal parameters"

        return AssessmentResult(
            risk_score=round(risk_score, 2),
            label=label,
            explanation=explanation,
            model_version=self.version,
        )
