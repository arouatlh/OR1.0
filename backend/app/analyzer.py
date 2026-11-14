
from datetime import datetime
from math import isfinite


# --------------------------------------------------
# 1. DEMONSTRATION THRESHOLDS
# --------------------------------------------------
# Synthetic prototype thresholds only.
# NOT validated medical or astronaut safety limits.

THRESHOLDS = {
    "heart_rate_bpm": {
        "low_review": 45,
        "high_review": 120,
        "low_critical": 35,
        "high_critical": 150,
    },
    "spo2_percent": {
        "low_review": 94,
        "low_critical": 90,
    },
    "body_temperature_c": {
        "low_review": 35.0,
        "high_review": 38.0,
        "low_critical": 34.0,
        "high_critical": 39.0,
    },
}

VALID_ACTIVITIES = {
    "resting",
    "walking",
    "exercising",
    "sleeping",
    "unknown",
}


# --------------------------------------------------
# 2. INPUT VALIDATION
# --------------------------------------------------

def validate_reading(reading: dict) -> list:
    """Return a list of input validation errors."""

    errors = []

    if not isinstance(reading, dict):
        return ["Reading must be a dictionary."]

    # Required fields available in the current backend.
    required = [
        "astronaut_id",
        "timestamp",
        "heart_rate_bpm",
        "spo2_percent",
    ]

    for field in required:
        if field not in reading or reading[field] is None:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    # Required numeric measurements.
    numeric_fields = [
        "heart_rate_bpm",
        "spo2_percent",
    ]

    # Temperature is optional.
    if reading.get("body_temperature_c") is not None:
        numeric_fields.append("body_temperature_c")

    for field in numeric_fields:
        try:
            value = float(reading[field])

            if not isfinite(value) or not (-1000 < value < 1000):
                errors.append(f"Invalid value for {field}.")

        except (TypeError, ValueError):
            errors.append(f"{field} must be numeric.")

    # Activity is optional.
    activity = reading.get("activity")

    if activity is not None:
        activity = str(activity).lower()

        if activity not in VALID_ACTIVITIES:
            errors.append(f"Unsupported activity: {activity}")

    # Validate timestamp.
    try:
        datetime.fromisoformat(
            str(reading["timestamp"]).replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        errors.append("Invalid timestamp format.")

    return errors


# --------------------------------------------------
# 3. ABNORMAL VITAL SIGN DETECTION
# --------------------------------------------------

def detect_abnormalities(reading: dict) -> list:
    """Detect vital signs outside demonstration thresholds."""

    findings = []

    hr = float(reading["heart_rate_bpm"])
    spo2 = float(reading["spo2_percent"])

    # Heart rate.
    t = THRESHOLDS["heart_rate_bpm"]

    if hr < t["low_critical"] or hr > t["high_critical"]:
        findings.append({
            "metric": "heart_rate_bpm",
            "severity": "critical",
            "message": (
                f"Heart rate is {hr} bpm, outside "
                "the critical demonstration range."
            ),
        })

    elif hr < t["low_review"] or hr > t["high_review"]:
        findings.append({
            "metric": "heart_rate_bpm",
            "severity": "review",
            "message": (
                f"Heart rate is {hr} bpm, outside "
                "the demonstration review range."
            ),
        })

    # Oxygen saturation.
    t = THRESHOLDS["spo2_percent"]

    if spo2 < t["low_critical"]:
        findings.append({
            "metric": "spo2_percent",
            "severity": "critical",
            "message": (
                f"SpO2 is {spo2}%, below "
                "the critical demonstration threshold."
            ),
        })

    elif spo2 < t["low_review"]:
        findings.append({
            "metric": "spo2_percent",
            "severity": "review",
            "message": (
                f"SpO2 is {spo2}%, below "
                "the demonstration review threshold."
            ),
        })

    # Body temperature: only analyze when available.
    if reading.get("body_temperature_c") is not None:
        temp = float(reading["body_temperature_c"])
        t = THRESHOLDS["body_temperature_c"]

        if temp < t["low_critical"] or temp > t["high_critical"]:
            findings.append({
                "metric": "body_temperature_c",
                "severity": "critical",
                "message": (
                    f"Body temperature is {temp}°C, outside "
                    "the critical demonstration range."
                ),
            })

        elif temp < t["low_review"] or temp > t["high_review"]:
            findings.append({
                "metric": "body_temperature_c",
                "severity": "review",
                "message": (
                    f"Body temperature is {temp}°C, outside "
                    "the demonstration review range."
                ),
            })

    return findings


# --------------------------------------------------
# 4. TREND DETECTION
# --------------------------------------------------

def detect_trends(reading: dict, recent_history: list) -> list:
    """
    Compare current measurements with recent history.

    Uses the average of up to five previous valid readings.
    At least three historical values are required per metric.
    """

    alerts = []

    if not isinstance(recent_history, list):
        return alerts

    metrics = [
        "heart_rate_bpm",
        "spo2_percent",
        "body_temperature_c",
    ]

    for metric in metrics:

        # Skip measurements unavailable in the current reading.
        if reading.get(metric) is None:
            continue

        historical_values = []

        for item in recent_history[-5:]:
            try:
                value = float(item[metric])

                if isfinite(value):
                    historical_values.append(value)

            except (KeyError, TypeError, ValueError):
                continue

        if len(historical_values) < 3:
            continue

        current = float(reading[metric])
        baseline = sum(historical_values) / len(historical_values)
        difference = current - baseline

        # Heart rate trend.
        if metric == "heart_rate_bpm":
            if abs(difference) >= 20:
                alerts.append(
                    f"Heart rate changed by {difference:.1f} bpm "
                    "compared with recent readings."
                )

        # Oxygen saturation trend.
        elif metric == "spo2_percent":
            if difference <= -3:
                alerts.append(
                    f"SpO2 decreased by {abs(difference):.1f} "
                    "percentage points compared with recent readings."
                )

        # Body temperature trend.
        elif metric == "body_temperature_c":
            if abs(difference) >= 0.8:
                alerts.append(
                    f"Body temperature changed by {difference:.1f}°C "
                    "compared with recent readings."
                )

    return alerts


# --------------------------------------------------
# 5. RISK SCORING
# --------------------------------------------------

def calculate_risk(findings: list, trend_alerts: list) -> tuple:
    """
    Calculate an illustrative 0-100 risk score.

    These weights are demonstration settings,
    not clinical risk probabilities.
    """

    score = 0
    has_critical_finding = False

    # Score abnormal vital signs.
    for finding in findings:

        if finding["severity"] == "critical":
            score += 40
            has_critical_finding = True

        elif finding["severity"] == "review":
            score += 15

    # Add trend contributions, capped at 24.
    trend_score = min(len(trend_alerts) * 8, 24)

    score += trend_score

    # Keep score within 0-100.
    score = min(score, 100)

    # Determine risk category.
    if has_critical_finding or score >= 70:
        risk_level = "critical"

    elif score >= 25:
        risk_level = "review"

    else:
        risk_level = "low"

    return score, risk_level


# --------------------------------------------------
# 6. EVA GUARDIAN ASSESSMENT
# --------------------------------------------------

def assess_eva_readiness(risk_level: str) -> dict:
    """
    Illustrative readiness workflow.
    This is not an operational EVA safety decision.
    """

    if risk_level == "critical":
        return {
            "status": "not_ready_for_demo",
            "message": "Critical demonstration flags require review.",
        }

    if risk_level == "review":
        return {
            "status": "review_required",
            "message": (
                "Crew review is suggested before the simulated EVA."
            ),
        }

    return {
        "status": "ready_for_review",
        "message": (
            "No configured demonstration risk flags. "
            "Human review is still required."
        ),
    }


# --------------------------------------------------
# 7. MAIN ANALYTICS FUNCTION
# --------------------------------------------------

def analyze(
    reading: dict,
    recent_history: list | None = None,
) -> dict:
    """Main entry point for AstroVitals analytics."""

    recent_history = recent_history or []

    errors = validate_reading(reading)

    if errors:
        return {
            "astronaut_id": (
                reading.get("astronaut_id")
                if isinstance(reading, dict)
                else None
            ),
            "status": "invalid_input",
            "errors": errors,
            "risk_level": "unknown",
            "risk_score": None,
            "reasons": [],
            "trend_alerts": [],
            "action": "Correct the input data before analysis.",
            "eva_status": "assessment_unavailable",
            "model_type": "rules_v1",
        }

    findings = detect_abnormalities(reading)

    trend_alerts = detect_trends(
        reading,
        recent_history,
    )

    risk_score, risk_level = calculate_risk(
        findings,
        trend_alerts,
    )

    reasons = [
        finding["message"]
        for finding in findings
    ]

    reasons.extend(trend_alerts)

    if risk_level == "critical":
        action = "Urgent crew review suggested."

    elif risk_level == "review":
        action = "Crew review suggested."

    else:
        action = "Continue routine monitoring."

    eva = assess_eva_readiness(risk_level)

    return {
        "astronaut_id": reading["astronaut_id"],
        "timestamp": reading["timestamp"],
        "status": "success",
        "risk_level": risk_level,
        "risk_score": risk_score,
        "reasons": reasons,
        "trend_alerts": trend_alerts,
        "action": action,
        "eva_status": eva["status"],
        "eva_message": eva["message"],
        "model_type": "rules_v1",
    }
