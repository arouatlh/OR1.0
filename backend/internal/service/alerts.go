package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"astrovitals/internal/domain"
	"astrovitals/internal/store"
	"astrovitals/internal/stream"

	"github.com/google/uuid"
	"go.uber.org/zap"
)

type AlertService struct {
	alertRepo     *store.AlertRepo
	astronautRepo *store.AstronautRepo
	outboxRepo    *store.OutboxRepo
	hub           *stream.Hub
	logger        *zap.SugaredLogger
	sustainCount  int
	resolveCount  int
}

func NewAlertService(
	alertRepo *store.AlertRepo,
	astronautRepo *store.AstronautRepo,
	outboxRepo *store.OutboxRepo,
	hub *stream.Hub,
	logger *zap.SugaredLogger,
	sustainCount, resolveCount int,
) *AlertService {
	return &AlertService{
		alertRepo:     alertRepo,
		astronautRepo: astronautRepo,
		outboxRepo:    outboxRepo,
		hub:           hub,
		logger:        logger,
		sustainCount:  sustainCount,
		resolveCount:  resolveCount,
	}
}

// EvaluateAndAct evaluates recent telemetry for the astronaut and executes resulting actions.
// Returns the number of alerts opened.
func (s *AlertService) EvaluateAndAct(ctx context.Context, astronaut *domain.Astronaut, window []domain.Telemetry) (int, error) {
	if len(window) == 0 {
		return 0, nil
	}

	openAlerts, err := s.alertRepo.GetOpenByAstronautID(ctx, astronaut.ID)
	if err != nil {
		return 0, err
	}

	now := time.Now().UTC()
	actions := domain.Evaluate(astronaut.ID, window, astronaut.Mode, openAlerts, s.sustainCount, s.resolveCount, now)

	alertsOpened := 0

	for _, act := range actions {
		switch act.Type {
		case domain.ActionOpen:
			act.Alert.ID = uuid.New().String()
			if err := s.alertRepo.Create(ctx, act.Alert); err != nil {
				return alertsOpened, err
			}

			// Add to outbox
			payloadBytes, _ := json.Marshal(act.Alert)
			_ = s.outboxRepo.Insert(ctx, domain.OutboxItem{
				Entity:    "alert",
				EntityID:  act.Alert.ID,
				Payload:   string(payloadBytes),
				CreatedAt: now,
			})

			// Broadcast SSE
			if s.hub != nil {
				s.hub.BroadcastAlert(act.Alert)
			}

			if s.logger != nil {
				s.logger.Infow("alert opened",
					"alert_id", act.Alert.ID,
					"astronaut_id", act.Alert.AstronautID,
					"rule_id", act.Alert.RuleID,
					"severity", string(act.Alert.Severity),
				)
			}
			alertsOpened++

		case domain.ActionEscalate:
			if err := s.alertRepo.Update(ctx, act.Alert); err != nil {
				return alertsOpened, err
			}

			if s.hub != nil {
				s.hub.BroadcastAlert(act.Alert)
			}

			if s.logger != nil {
				s.logger.Infow("alert escalated",
					"alert_id", act.Alert.ID,
					"astronaut_id", act.Alert.AstronautID,
					"rule_id", act.Alert.RuleID,
					"severity", string(act.Alert.Severity),
				)
			}

		case domain.ActionResolve:
			if err := s.alertRepo.Update(ctx, act.Alert); err != nil {
				return alertsOpened, err
			}

			if s.hub != nil {
				s.hub.BroadcastAlertUpdate(act.Alert.ID, string(act.Alert.Status), act.Alert.UpdatedAt, act.Alert.AstronautID)
			}

			if s.logger != nil {
				s.logger.Infow("alert resolved",
					"alert_id", act.Alert.ID,
					"astronaut_id", act.Alert.AstronautID,
					"rule_id", act.Alert.RuleID,
					"severity", string(act.Alert.Severity),
				)
			}
		}
	}

	return alertsOpened, nil
}

func (s *AlertService) AcknowledgeAlert(ctx context.Context, id string) (*domain.Alert, error) {
	now := time.Now().UTC()
	alert, err := s.alertRepo.Acknowledge(ctx, id, now)
	if err != nil {
		return nil, err
	}

	if s.hub != nil {
		s.hub.BroadcastAlertUpdate(alert.ID, string(alert.Status), alert.UpdatedAt, alert.AstronautID)
	}

	return alert, nil
}

func (s *AlertService) CreateAssessment(ctx context.Context, a domain.Assessment) error {
	now := time.Now().UTC()
	a.ID = uuid.New().String()
	a.CreatedAt = now

	if err := s.alertRepo.CreateAssessment(ctx, a); err != nil {
		return err
	}

	// Add assessment to outbox
	payloadBytes, _ := json.Marshal(a)
	_ = s.outboxRepo.Insert(ctx, domain.OutboxItem{
		Entity:    "assessment",
		EntityID:  a.ID,
		Payload:   string(payloadBytes),
		CreatedAt: now,
	})

	// If risk_score >= 0.8, open AI alert
	if a.RiskScore >= 0.8 {
		sev := domain.SeverityWarning
		if a.RiskScore >= 0.9 {
			sev = domain.SeverityCritical
		}

		aiAlert := domain.Alert{
			ID:          uuid.New().String(),
			AstronautID: a.AstronautID,
			RuleID:      "ai_risk_high",
			Severity:    sev,
			Title:       "High AI risk assessment",
			Message:     fmt.Sprintf("AI model %s detected risk score %.2f: %s", a.ModelVersion, a.RiskScore, a.Label),
			Metric:      "risk_score",
			Value:       a.RiskScore,
			Threshold:   0.8,
			Status:      domain.AlertStatusOpen,
			Origin:      domain.AlertOriginAI,
			CreatedAt:   now,
			UpdatedAt:   now,
		}

		if err := s.alertRepo.Create(ctx, aiAlert); err == nil {
			if s.hub != nil {
				s.hub.BroadcastAlert(aiAlert)
			}
			if s.logger != nil {
				s.logger.Infow("alert opened",
					"alert_id", aiAlert.ID,
					"astronaut_id", aiAlert.AstronautID,
					"rule_id", aiAlert.RuleID,
					"severity", string(aiAlert.Severity),
				)
			}
		}
	}

	return nil
}
