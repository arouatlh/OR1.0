package domain

import "time"

type Severity string

const (
	SeverityInfo     Severity = "info"
	SeverityWarning  Severity = "warning"
	SeverityCritical Severity = "critical"
)

func (s Severity) Rank() int {
	switch s {
	case SeverityCritical:
		return 3
	case SeverityWarning:
		return 2
	case SeverityInfo:
		return 1
	default:
		return 0
	}
}

type AlertStatus string

const (
	AlertStatusOpen         AlertStatus = "open"
	AlertStatusAcknowledged AlertStatus = "acknowledged"
	AlertStatusResolved     AlertStatus = "resolved"
)

type AlertOrigin string

const (
	AlertOriginRules AlertOrigin = "rules"
	AlertOriginAI    AlertOrigin = "ai"
	AlertOriginDemo  AlertOrigin = "demo"
)

type Alert struct {
	ID          string      `json:"id"`
	AstronautID string      `json:"astronaut_id"`
	RuleID      string      `json:"rule_id"`
	Severity    Severity    `json:"severity"`
	Title       string      `json:"title"`
	Message     string      `json:"message"`
	Metric      string      `json:"metric"`
	Value       float64     `json:"value"`
	Threshold   float64     `json:"threshold"`
	Status      AlertStatus `json:"status"`
	Origin      AlertOrigin `json:"origin"`
	CreatedAt   time.Time   `json:"created_at"`
	UpdatedAt   time.Time   `json:"updated_at"`
}

type Assessment struct {
	ID           string    `json:"id"`
	AstronautID  string    `json:"astronaut_id"`
	ModelVersion string    `json:"model_version"`
	RiskScore    float64   `json:"risk_score"`
	Label        string    `json:"label"`
	Explanation  string    `json:"explanation"`
	CreatedAt    time.Time `json:"created_at"`
}

type OutboxItem struct {
	ID        int64      `json:"id"`
	Entity    string     `json:"entity"`
	EntityID  string     `json:"entity_id"`
	Payload   string     `json:"payload"`
	CreatedAt time.Time  `json:"created_at"`
	SyncedAt  *time.Time `json:"synced_at,omitempty"`
}
