package service

import (
	"context"
	"time"

	"astrovitals/internal/domain"
	"astrovitals/internal/store"
)

type AstronautSummary struct {
	Astronaut       domain.Astronaut  `json:"astronaut"`
	LatestTelemetry *domain.Telemetry `json:"latest_telemetry,omitempty"`
	Stats5Min       *store.Stats5Min  `json:"stats_5min"`
	OpenAlerts      []domain.Alert    `json:"open_alerts"`
}

type SummaryService struct {
	astronautRepo *store.AstronautRepo
	telemetryRepo *store.TelemetryRepo
	alertRepo     *store.AlertRepo
}

func NewSummaryService(
	astronautRepo *store.AstronautRepo,
	telemetryRepo *store.TelemetryRepo,
	alertRepo *store.AlertRepo,
) *SummaryService {
	return &SummaryService{
		astronautRepo: astronautRepo,
		telemetryRepo: telemetryRepo,
		alertRepo:     alertRepo,
	}
}

func (s *SummaryService) GetSummary(ctx context.Context, astronautID string) (*AstronautSummary, error) {
	astro, err := s.astronautRepo.GetByID(ctx, astronautID)
	if err != nil {
		return nil, err
	}

	latest, err := s.telemetryRepo.GetLatestByAstronautID(ctx, astronautID)
	if err != nil {
		return nil, err
	}

	now := time.Now().UTC()
	stats, err := s.telemetryRepo.GetStats5Min(ctx, astronautID, now)
	if err != nil {
		return nil, err
	}

	openAlertsMap, err := s.alertRepo.GetOpenByAstronautID(ctx, astronautID)
	if err != nil {
		return nil, err
	}

	var openAlerts []domain.Alert
	for _, a := range openAlertsMap {
		openAlerts = append(openAlerts, a)
	}

	return &AstronautSummary{
		Astronaut:       *astro,
		LatestTelemetry: latest,
		Stats5Min:       stats,
		OpenAlerts:      openAlerts,
	}, nil
}
