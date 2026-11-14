package service

import (
	"context"

	"astrovitals/internal/domain"
	"astrovitals/internal/store"
	"astrovitals/internal/stream"
)

type IngestResult struct {
	Accepted     int `json:"accepted"`
	Duplicates   int `json:"duplicates"`
	AlertsOpened int `json:"alerts_opened"`
}

type IngestService struct {
	telemetryRepo *store.TelemetryRepo
	astronautRepo *store.AstronautRepo
	alertService  *AlertService
	hub           *stream.Hub
}

func NewIngestService(
	telemetryRepo *store.TelemetryRepo,
	astronautRepo *store.AstronautRepo,
	alertService *AlertService,
	hub *stream.Hub,
) *IngestService {
	return &IngestService{
		telemetryRepo: telemetryRepo,
		astronautRepo: astronautRepo,
		alertService:  alertService,
		hub:           hub,
	}
}

func (s *IngestService) Ingest(ctx context.Context, astronautID string, samples []domain.Telemetry) (*IngestResult, error) {
	// First fetch the astronaut to confirm existence and current mode
	astronaut, err := s.astronautRepo.GetByID(ctx, astronautID)
	if err != nil {
		return nil, err
	}

	accepted, duplicates, acceptedSamples, err := s.telemetryRepo.IngestBatch(ctx, astronautID, samples)
	if err != nil {
		return nil, err
	}

	// Broadcast accepted telemetry to real-time subscribers
	if s.hub != nil {
		for _, smp := range acceptedSamples {
			s.hub.BroadcastTelemetry(smp)
		}
	}

	// If any samples were accepted, evaluate rules on the recent window
	alertsOpened := 0
	if accepted > 0 {
		window, err := s.telemetryRepo.GetRecentWindow(ctx, astronautID, 25)
		if err == nil && len(window) > 0 {
			opened, err := s.alertService.EvaluateAndAct(ctx, astronaut, window)
			if err == nil {
				alertsOpened = opened
			}
		}
	}

	return &IngestResult{
		Accepted:     accepted,
		Duplicates:   duplicates,
		AlertsOpened: alertsOpened,
	}, nil
}
