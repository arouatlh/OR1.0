package domain_test

import (
	"testing"
	"time"

	"astrovitals/internal/domain"
)

func intPtr(v int) *int {
	return &v
}

func strPtr(s string) *string {
	return &s
}

func floatPtr(f float64) *float64 {
	return &f
}

func TestRules_SustainWindowAndThresholds(t *testing.T) {
	evalTime := time.Date(2026, 11, 14, 10, 30, 0, 0, time.UTC)

	tests := []struct {
		name          string
		window        []domain.Telemetry
		mode          domain.Mode
		openAlerts    map[string]domain.Alert
		sustainCount  int
		resolveCount  int
		expectedActs  int
		expectedType  domain.ActionType
		expectedSev   domain.Severity
		expectedRule  string
	}{
		{
			name: "HR high below sustain count (only 2 samples > 120)",
			window: []domain.Telemetry{
				{HeartRate: intPtr(70)},
				{HeartRate: intPtr(125)},
				{HeartRate: intPtr(128)},
			},
			mode:         domain.ModeNormal,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 0,
		},
		{
			name: "HR high satisfies sustain count (3 samples > 120) => Warning alert",
			window: []domain.Telemetry{
				{HeartRate: intPtr(125)},
				{HeartRate: intPtr(128)},
				{HeartRate: intPtr(130)},
			},
			mode:         domain.ModeNormal,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 1,
			expectedType: domain.ActionOpen,
			expectedSev:  domain.SeverityWarning,
			expectedRule: "hr_high",
		},
		{
			name: "HR high satisfies critical (3 samples > 150) => Critical alert",
			window: []domain.Telemetry{
				{HeartRate: intPtr(152)},
				{HeartRate: intPtr(155)},
				{HeartRate: intPtr(156)},
			},
			mode:         domain.ModeNormal,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 1,
			expectedType: domain.ActionOpen,
			expectedSev:  domain.SeverityCritical,
			expectedRule: "hr_high",
		},
		{
			name: "EVA mode relaxes HR high: 130 bpm is normal in EVA (warning is > 140)",
			window: []domain.Telemetry{
				{HeartRate: intPtr(130)},
				{HeartRate: intPtr(132)},
				{HeartRate: intPtr(135)},
			},
			mode:         domain.ModeEVA,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 0,
		},
		{
			name: "EVA mode HR 145 bpm triggers Warning (warning > 140 in EVA)",
			window: []domain.Telemetry{
				{HeartRate: intPtr(142)},
				{HeartRate: intPtr(145)},
				{HeartRate: intPtr(148)},
			},
			mode:         domain.ModeEVA,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 1,
			expectedType: domain.ActionOpen,
			expectedSev:  domain.SeverityWarning,
			expectedRule: "hr_high",
		},
		{
			name: "SpO2 low critical (<90)",
			window: []domain.Telemetry{
				{SpO2: intPtr(89)},
				{SpO2: intPtr(88)},
				{SpO2: intPtr(87)},
			},
			mode:         domain.ModeNormal,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 1,
			expectedType: domain.ActionOpen,
			expectedSev:  domain.SeverityCritical,
			expectedRule: "spo2_low",
		},
		{
			name: "ECG irregular for 3 consecutive samples",
			window: []domain.Telemetry{
				{ECGSummary: strPtr("irregular")},
				{ECGSummary: strPtr("irregular")},
				{ECGSummary: strPtr("irregular")},
			},
			mode:         domain.ModeNormal,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 1,
			expectedType: domain.ActionOpen,
			expectedSev:  domain.SeverityWarning,
			expectedRule: "ecg_irregular",
		},
		{
			name: "Stress index high critical (>0.9)",
			window: []domain.Telemetry{
				{StressIndex: floatPtr(0.92)},
				{StressIndex: floatPtr(0.95)},
				{StressIndex: floatPtr(0.91)},
			},
			mode:         domain.ModeNormal,
			openAlerts:   nil,
			sustainCount: 3,
			expectedActs: 1,
			expectedType: domain.ActionOpen,
			expectedSev:  domain.SeverityCritical,
			expectedRule: "stress_high",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			acts := domain.Evaluate("astro-a", tc.window, tc.mode, tc.openAlerts, tc.sustainCount, tc.resolveCount, evalTime)
			if len(acts) != tc.expectedActs {
				t.Fatalf("expected %d actions, got %d: %+v", tc.expectedActs, len(acts), acts)
			}
			if tc.expectedActs > 0 {
				act := acts[0]
				if act.Type != tc.expectedType {
					t.Errorf("expected type %s, got %s", tc.expectedType, act.Type)
				}
				if act.Alert.Severity != tc.expectedSev {
					t.Errorf("expected severity %s, got %s", tc.expectedSev, act.Alert.Severity)
				}
				if act.Alert.RuleID != tc.expectedRule {
					t.Errorf("expected rule %s, got %s", tc.expectedRule, act.Alert.RuleID)
				}
			}
		})
	}
}

func TestRules_DedupEscalateResolve(t *testing.T) {
	evalTime := time.Date(2026, 11, 14, 10, 30, 0, 0, time.UTC)

	existingWarningAlert := domain.Alert{
		ID:          "alert-123",
		AstronautID: "astro-a",
		RuleID:      "hr_high",
		Severity:    domain.SeverityWarning,
		Status:      domain.AlertStatusOpen,
	}

	// 1. Dedup: warning persists, already open -> 0 actions
	t.Run("dedup warning alert", func(t *testing.T) {
		window := []domain.Telemetry{
			{HeartRate: intPtr(125)},
			{HeartRate: intPtr(128)},
			{HeartRate: intPtr(130)},
		}
		openAlerts := map[string]domain.Alert{
			"hr_high": existingWarningAlert,
		}
		acts := domain.Evaluate("astro-a", window, domain.ModeNormal, openAlerts, 3, 5, evalTime)
		if len(acts) != 0 {
			t.Fatalf("expected 0 actions for already open warning alert, got %d", len(acts))
		}
	})

	// 2. Escalation: HR rises to >150 (critical) -> ActionEscalate
	t.Run("escalate warning to critical", func(t *testing.T) {
		window := []domain.Telemetry{
			{HeartRate: intPtr(152)},
			{HeartRate: intPtr(155)},
			{HeartRate: intPtr(156)},
		}
		openAlerts := map[string]domain.Alert{
			"hr_high": existingWarningAlert,
		}
		acts := domain.Evaluate("astro-a", window, domain.ModeNormal, openAlerts, 3, 5, evalTime)
		if len(acts) != 1 {
			t.Fatalf("expected 1 action, got %d", len(acts))
		}
		if acts[0].Type != domain.ActionEscalate {
			t.Errorf("expected ActionEscalate, got %s", acts[0].Type)
		}
		if acts[0].Alert.Severity != domain.SeverityCritical {
			t.Errorf("expected SeverityCritical, got %s", acts[0].Alert.Severity)
		}
		if acts[0].ExistingID != "alert-123" {
			t.Errorf("expected ExistingID alert-123, got %s", acts[0].ExistingID)
		}
	})

	// 3. Auto-resolve: HR returns to normal for 5 consecutive samples (< 120)
	t.Run("auto resolve after 5 in-range samples", func(t *testing.T) {
		window := []domain.Telemetry{
			{HeartRate: intPtr(140)}, // earlier elevated sample
			{HeartRate: intPtr(72)},
			{HeartRate: intPtr(74)},
			{HeartRate: intPtr(70)},
			{HeartRate: intPtr(75)},
			{HeartRate: intPtr(71)},
		}
		openAlerts := map[string]domain.Alert{
			"hr_high": existingWarningAlert,
		}
		acts := domain.Evaluate("astro-a", window, domain.ModeNormal, openAlerts, 3, 5, evalTime)
		if len(acts) != 1 {
			t.Fatalf("expected 1 action, got %d", len(acts))
		}
		if acts[0].Type != domain.ActionResolve {
			t.Errorf("expected ActionResolve, got %s", acts[0].Type)
		}
		if acts[0].Alert.Status != domain.AlertStatusResolved {
			t.Errorf("expected StatusResolved, got %s", acts[0].Alert.Status)
		}
	})

	// 4. Auto-resolve NOT triggered if only 4 in-range samples
	t.Run("auto resolve not triggered with 4 in-range samples", func(t *testing.T) {
		window := []domain.Telemetry{
			{HeartRate: intPtr(130)},
			{HeartRate: intPtr(72)},
			{HeartRate: intPtr(74)},
			{HeartRate: intPtr(70)},
			{HeartRate: intPtr(75)},
		}
		openAlerts := map[string]domain.Alert{
			"hr_high": existingWarningAlert,
		}
		acts := domain.Evaluate("astro-a", window, domain.ModeNormal, openAlerts, 3, 5, evalTime)
		if len(acts) != 0 {
			t.Fatalf("expected 0 actions (only 4 in-range samples), got %d", len(acts))
		}
	})
}
