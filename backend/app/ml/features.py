from collections.abc import Sequence

from app.domain.models import Sample


def extract_features(window: Sequence[Sample]) -> dict[str, float]:
    """Extracts summary statistical features from a window of telemetry samples,
    gracefully handling missing or None vitals."""
    if not window:
        return {
            "hr_mean": 70.0,
            "hr_min": 70.0,
            "hr_max": 70.0,
            "spo2_mean": 98.0,
            "spo2_min": 98.0,
            "systolic_mean": 120.0,
            "stress_mean": 0.2,
        }

    hrs = [s.heart_rate for s in window if s.heart_rate is not None]
    spo2s = [s.spo2 for s in window if s.spo2 is not None]
    systolics = [s.systolic for s in window if s.systolic is not None]
    stresses = [s.stress_index for s in window if s.stress_index is not None]

    hr_mean = sum(hrs) / len(hrs) if hrs else 70.0
    hr_min = float(min(hrs)) if hrs else 70.0
    hr_max = float(max(hrs)) if hrs else 70.0

    spo2_mean = sum(spo2s) / len(spo2s) if spo2s else 98.0
    spo2_min = float(min(spo2s)) if spo2s else 98.0

    systolic_mean = sum(systolics) / len(systolics) if systolics else 120.0
    stress_mean = sum(stresses) / len(stresses) if stresses else 0.2

    return {
        "hr_mean": hr_mean,
        "hr_min": hr_min,
        "hr_max": hr_max,
        "spo2_mean": spo2_mean,
        "spo2_min": spo2_min,
        "systolic_mean": systolic_mean,
        "stress_mean": stress_mean,
    }
