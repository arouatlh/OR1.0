package domain

import "time"

type TelemetrySource string

const (
	SourceWatch     TelemetrySource = "watch"
	SourceSimulator TelemetrySource = "simulator"
	SourceDataset   TelemetrySource = "dataset"
)

type Telemetry struct {
	ID          int64           `json:"id,omitempty"`
	AstronautID string          `json:"astronaut_id"`
	ClientID    string          `json:"client_id"`
	RecordedAt  time.Time       `json:"recorded_at"`
	ReceivedAt  time.Time       `json:"received_at,omitempty"`
	Source      TelemetrySource `json:"source"`
	HeartRate   *int            `json:"heart_rate,omitempty"`
	SpO2        *int            `json:"spo2,omitempty"`
	Systolic    *int            `json:"systolic,omitempty"`
	Diastolic   *int            `json:"diastolic,omitempty"`
	RespRate    *int            `json:"resp_rate,omitempty"`
	ECGSummary  *string         `json:"ecg_summary,omitempty"`
	StressIndex *float64        `json:"stress_index,omitempty"`
}
