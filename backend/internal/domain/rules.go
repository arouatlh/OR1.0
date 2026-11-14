package domain

import (
	"fmt"
	"time"
)

type ActionType string

const (
	ActionOpen     ActionType = "open"
	ActionEscalate ActionType = "escalate"
	ActionResolve  ActionType = "resolve"
)

type AlertAction struct {
	Type       ActionType
	Alert      Alert
	ExistingID string
}

type RuleDefinition struct {
	RuleID          string
	Metric          string
	Title           string
	WarningCompare  func(val float64, mode Mode) bool
	CriticalCompare func(val float64, mode Mode) bool
	WarningThresh   func(mode Mode) float64
	CriticalThresh  func(mode Mode) float64
	ExtractVal      func(t Telemetry) (float64, bool)
	FormatMsg       func(val, thresh float64, sev Severity) string
}

// Built-in rule definitions
var RuleDefinitions = []RuleDefinition{
	{
		RuleID: "hr_high",
		Metric: "heart_rate",
		Title:  "Elevated heart rate",
		WarningCompare: func(val float64, mode Mode) bool {
			thresh := 120.0
			if mode == ModeEVA {
				thresh = 140.0
			}
			return val > thresh
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			thresh := 150.0
			if mode == ModeEVA {
				thresh = 170.0
			}
			return val > thresh
		},
		WarningThresh: func(mode Mode) float64 {
			if mode == ModeEVA {
				return 140.0
			}
			return 120.0
		},
		CriticalThresh: func(mode Mode) float64 {
			if mode == ModeEVA {
				return 170.0
			}
			return 150.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.HeartRate != nil {
				return float64(*t.HeartRate), true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Heart rate %d bpm exceeds %s threshold of %d bpm.", int(val), sev, int(thresh))
		},
	},
	{
		RuleID: "hr_low",
		Metric: "heart_rate",
		Title:  "Low heart rate",
		WarningCompare: func(val float64, mode Mode) bool {
			return val < 50.0
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return val < 40.0
		},
		WarningThresh: func(mode Mode) float64 {
			return 50.0
		},
		CriticalThresh: func(mode Mode) float64 {
			return 40.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.HeartRate != nil {
				return float64(*t.HeartRate), true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Heart rate %d bpm below %s threshold of %d bpm.", int(val), sev, int(thresh))
		},
	},
	{
		RuleID: "spo2_low",
		Metric: "spo2",
		Title:  "Low oxygen saturation",
		WarningCompare: func(val float64, mode Mode) bool {
			return val < 94.0
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return val < 90.0
		},
		WarningThresh: func(mode Mode) float64 {
			return 94.0
		},
		CriticalThresh: func(mode Mode) float64 {
			return 90.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.SpO2 != nil {
				return float64(*t.SpO2), true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Oxygen saturation %d%% below %s threshold of %d%%.", int(val), sev, int(thresh))
		},
	},
	{
		RuleID: "bp_high",
		Metric: "systolic",
		Title:  "High blood pressure",
		WarningCompare: func(val float64, mode Mode) bool {
			return val > 140.0
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return val > 170.0
		},
		WarningThresh: func(mode Mode) float64 {
			return 140.0
		},
		CriticalThresh: func(mode Mode) float64 {
			return 170.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.Systolic != nil {
				return float64(*t.Systolic), true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Systolic blood pressure %d mmHg exceeds %s threshold of %d mmHg.", int(val), sev, int(thresh))
		},
	},
	{
		RuleID: "bp_low",
		Metric: "systolic",
		Title:  "Low blood pressure",
		WarningCompare: func(val float64, mode Mode) bool {
			return val < 90.0
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return val < 80.0
		},
		WarningThresh: func(mode Mode) float64 {
			return 90.0
		},
		CriticalThresh: func(mode Mode) float64 {
			return 80.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.Systolic != nil {
				return float64(*t.Systolic), true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Systolic blood pressure %d mmHg below %s threshold of %d mmHg.", int(val), sev, int(thresh))
		},
	},
	{
		RuleID: "rr_high",
		Metric: "resp_rate",
		Title:  "High respiratory rate",
		WarningCompare: func(val float64, mode Mode) bool {
			return val > 22.0
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return val > 28.0
		},
		WarningThresh: func(mode Mode) float64 {
			return 22.0
		},
		CriticalThresh: func(mode Mode) float64 {
			return 28.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.RespRate != nil {
				return float64(*t.RespRate), true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Respiratory rate %d breaths/min exceeds %s threshold of %d breaths/min.", int(val), sev, int(thresh))
		},
	},
	{
		RuleID: "rr_low",
		Metric: "resp_rate",
		Title:  "Low respiratory rate",
		WarningCompare: func(val float64, mode Mode) bool {
			return val < 10.0
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return val < 8.0
		},
		WarningThresh: func(mode Mode) float64 {
			return 10.0
		},
		CriticalThresh: func(mode Mode) float64 {
			return 8.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.RespRate != nil {
				return float64(*t.RespRate), true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Respiratory rate %d breaths/min below %s threshold of %d breaths/min.", int(val), sev, int(thresh))
		},
	},
	{
		RuleID: "ecg_irregular",
		Metric: "ecg_summary",
		Title:  "Irregular cardiac rhythm",
		WarningCompare: func(val float64, mode Mode) bool {
			return val > 0.5 // 1.0 means irregular
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return false // No critical level for ecg_irregular
		},
		WarningThresh: func(mode Mode) float64 {
			return 1.0
		},
		CriticalThresh: func(mode Mode) float64 {
			return 1.0
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.ECGSummary != nil {
				if *t.ECGSummary == "irregular" {
					return 1.0, true
				}
				return 0.0, true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return "ECG rhythm marked irregular for 3 consecutive samples."
		},
	},
	{
		RuleID: "stress_high",
		Metric: "stress_index",
		Title:  "High stress index",
		WarningCompare: func(val float64, mode Mode) bool {
			return val > 0.7
		},
		CriticalCompare: func(val float64, mode Mode) bool {
			return val > 0.9
		},
		WarningThresh: func(mode Mode) float64 {
			return 0.7
		},
		CriticalThresh: func(mode Mode) float64 {
			return 0.9
		},
		ExtractVal: func(t Telemetry) (float64, bool) {
			if t.StressIndex != nil {
				return *t.StressIndex, true
			}
			return 0, false
		},
		FormatMsg: func(val, thresh float64, sev Severity) string {
			return fmt.Sprintf("Stress index %.2f exceeds %s threshold of %.2f.", val, sev, thresh)
		},
	},
}

// Evaluate is a pure function that analyzes a chronological window of telemetry samples
// (index 0 is oldest, index len-1 is newest) against configured rules, returning actions.
func Evaluate(
	astronautID string,
	window []Telemetry,
	mode Mode,
	openAlerts map[string]Alert,
	sustainCount int,
	resolveCount int,
	evalTime time.Time,
) []AlertAction {
	if len(window) == 0 {
		return nil
	}

	if sustainCount <= 0 {
		sustainCount = 3
	}
	if resolveCount <= 0 {
		resolveCount = 5
	}

	var actions []AlertAction

	for _, rule := range RuleDefinitions {
		existingAlert, hasExisting := openAlerts[rule.RuleID]

		// Extract values for this metric across the window
		type sampleVal struct {
			val float64
			ok  bool
		}
		vals := make([]sampleVal, len(window))
		for i, t := range window {
			v, ok := rule.ExtractVal(t)
			vals[i] = sampleVal{val: v, ok: ok}
		}

		// Check resolve condition if an alert is currently active
		if hasExisting && (existingAlert.Status == AlertStatusOpen || existingAlert.Status == AlertStatusAcknowledged) {
			// Auto-resolve: metric is back in range for resolveCount consecutive samples
			if len(vals) >= resolveCount {
				allNormal := true
				for i := len(vals) - resolveCount; i < len(vals); i++ {
					if !vals[i].ok || rule.WarningCompare(vals[i].val, mode) || rule.CriticalCompare(vals[i].val, mode) {
						allNormal = false
						break
					}
				}
				if allNormal {
					resolvedAlert := existingAlert
					resolvedAlert.Status = AlertStatusResolved
					resolvedAlert.UpdatedAt = evalTime
					actions = append(actions, AlertAction{
						Type:       ActionResolve,
						Alert:      resolvedAlert,
						ExistingID: existingAlert.ID,
					})
					continue
				}
			}
		}

		// Check sustain condition for opening or escalating
		if len(vals) >= sustainCount {
			sub := vals[len(vals)-sustainCount:]
			allCritical := true
			allWarningOrCritical := true
			for _, s := range sub {
				if !s.ok {
					allCritical = false
					allWarningOrCritical = false
					break
				}
				isCrit := rule.CriticalCompare(s.val, mode)
				isWarn := rule.WarningCompare(s.val, mode)
				if !isCrit {
					allCritical = false
				}
				if !isCrit && !isWarn {
					allWarningOrCritical = false
				}
			}

			latestVal := sub[len(sub)-1].val
			var currentSev Severity
			var threshold float64

			if allCritical {
				currentSev = SeverityCritical
				threshold = rule.CriticalThresh(mode)
			} else if allWarningOrCritical {
				currentSev = SeverityWarning
				threshold = rule.WarningThresh(mode)
			}

			if currentSev != "" {
				if !hasExisting || (existingAlert.Status != AlertStatusOpen && existingAlert.Status != AlertStatusAcknowledged) {
					// Open new alert
					newAlert := Alert{
						AstronautID: astronautID,
						RuleID:      rule.RuleID,
						Severity:    currentSev,
						Title:       rule.Title,
						Message:     rule.FormatMsg(latestVal, threshold, currentSev),
						Metric:      rule.Metric,
						Value:       latestVal,
						Threshold:   threshold,
						Status:      AlertStatusOpen,
						Origin:      AlertOriginRules,
						CreatedAt:   evalTime,
						UpdatedAt:   evalTime,
					}
					actions = append(actions, AlertAction{
						Type:  ActionOpen,
						Alert: newAlert,
					})
				} else if existingAlert.Severity.Rank() < currentSev.Rank() {
					// Escalation
					escalated := existingAlert
					escalated.Severity = currentSev
					escalated.Value = latestVal
					escalated.Threshold = threshold
					escalated.Message = rule.FormatMsg(latestVal, threshold, currentSev)
					escalated.UpdatedAt = evalTime
					actions = append(actions, AlertAction{
						Type:       ActionEscalate,
						Alert:      escalated,
						ExistingID: existingAlert.ID,
					})
				}
			}
		}
	}

	return actions
}
