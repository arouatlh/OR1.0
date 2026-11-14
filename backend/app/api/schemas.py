from datetime import UTC, datetime, timedelta
from typing import Annotated

from pydantic import BaseModel, Field, model_validator


class SampleDTO(BaseModel):
    client_id: Annotated[str, Field(min_length=1, max_length=64)]
    recorded_at: datetime
    source: str = "watch"
    heart_rate: Annotated[int | None, Field(ge=20, le=250)] = None
    spo2: Annotated[int | None, Field(ge=50, le=100)] = None
    systolic: Annotated[int | None, Field(ge=50, le=260)] = None
    diastolic: Annotated[int | None, Field(ge=30, le=160)] = None
    resp_rate: Annotated[int | None, Field(ge=4, le=60)] = None
    ecg_summary: str | None = None
    stress_index: Annotated[float | None, Field(ge=0.0, le=1.0)] = None

    @model_validator(mode="after")
    def validate_sample(self) -> "SampleDTO":
        # 1. At least one vital per sample
        has_vital = any(
            v is not None
            for v in (
                self.heart_rate,
                self.spo2,
                self.systolic,
                self.diastolic,
                self.resp_rate,
                self.ecg_summary,
                self.stress_index,
            )
        )
        if not has_vital:
            raise ValueError("at least one vital metric must be present")

        # 2. Timezone-aware and not > 24h in the future
        rec = self.recorded_at
        if rec.tzinfo is None:
            rec = rec.replace(tzinfo=UTC)
        else:
            rec = rec.astimezone(UTC)
        self.recorded_at = rec

        max_future = datetime.now(UTC) + timedelta(hours=24)
        if self.recorded_at > max_future:
            raise ValueError("recorded_at cannot be more than 24h in the future")

        return self


class TelemetryBatchRequest(BaseModel):
    astronaut_id: Annotated[str, Field(min_length=1)]
    samples: Annotated[list[SampleDTO], Field(min_length=1, max_length=500)]


class ModeUpdateRequest(BaseModel):
    mode: str

    @model_validator(mode="after")
    def validate_mode(self) -> "ModeUpdateRequest":
        if self.mode not in ("normal", "eva"):
            raise ValueError("mode must be 'normal' or 'eva'")
        return self


class AssessmentRequest(BaseModel):
    astronaut_id: Annotated[str, Field(min_length=1)]
    model_version: Annotated[str, Field(min_length=1)]
    risk_score: Annotated[float, Field(ge=0.0, le=1.0)]
    label: Annotated[str, Field(min_length=1)]
    explanation: str = ""


class SimulateStartRequest(BaseModel):
    scenario: str = "normal"
    astronaut_id: str = "astro-a"
