package domain

import "time"

type Mode string

const (
	ModeNormal Mode = "normal"
	ModeEVA    Mode = "eva"
)

type Astronaut struct {
	ID          string    `json:"id"`
	DisplayName string    `json:"display_name"`
	Mission     string    `json:"mission"`
	Mode        Mode      `json:"mode"`
	BaselineHR  int       `json:"baseline_hr"`
	CreatedAt   time.Time `json:"created_at"`
}

type AstronautWithLatest struct {
	Astronaut
	LatestTelemetry *Telemetry `json:"latest_telemetry,omitempty"`
	OpenAlertsCount int        `json:"open_alerts_count"`
	Status          string     `json:"status"` // "nominal", "warning", "critical"
}
