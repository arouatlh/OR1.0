package store_test

import (
	"context"
	"testing"
	"time"

	"astrovitals/internal/domain"
	"astrovitals/internal/store"
)

func intPtr(v int) *int {
	return &v
}

func TestStore_OpenAndSeed(t *testing.T) {
	ctx := context.Background()
	db, err := store.Open(ctx, ":memory:")
	if err != nil {
		t.Fatalf("failed to open in-memory db: %v", err)
	}
	defer db.Close()

	astroRepo := store.NewAstronautRepo(db)
	astronauts, err := astroRepo.List(ctx)
	if err != nil {
		t.Fatalf("failed to list astronauts: %v", err)
	}

	if len(astronauts) != 3 {
		t.Fatalf("expected 3 seeded astronauts, got %d", len(astronauts))
	}

	if astronauts[0].ID != "astro-a" || astronauts[1].ID != "astro-b" || astronauts[2].ID != "astro-c" {
		t.Errorf("unexpected astronaut IDs: %+v", astronauts)
	}
}

func TestStore_TelemetryIngestAndIdempotency(t *testing.T) {
	ctx := context.Background()
	db, err := store.Open(ctx, ":memory:")
	if err != nil {
		t.Fatalf("failed to open in-memory db: %v", err)
	}
	defer db.Close()

	telemetryRepo := store.NewTelemetryRepo(db)
	outboxRepo := store.NewOutboxRepo(db)

	now := time.Now().UTC()
	samples := []domain.Telemetry{
		{
			ClientID:   "test-client-1",
			RecordedAt: now,
			Source:     domain.SourceWatch,
			HeartRate:  intPtr(72),
			SpO2:       intPtr(98),
		},
		{
			ClientID:   "test-client-2",
			RecordedAt: now.Add(time.Second),
			Source:     domain.SourceWatch,
			HeartRate:  intPtr(75),
			SpO2:       intPtr(97),
		},
	}

	// 1. Initial Ingest
	accepted, duplicates, _, err := telemetryRepo.IngestBatch(ctx, "astro-a", samples)
	if err != nil {
		t.Fatalf("ingest failed: %v", err)
	}
	if accepted != 2 || duplicates != 0 {
		t.Fatalf("expected 2 accepted, 0 duplicates, got %d accepted, %d duplicates", accepted, duplicates)
	}

	// Verify outbox was populated in same transaction
	pendingCount, err := outboxRepo.GetPendingCount(ctx)
	if err != nil {
		t.Fatalf("failed to get outbox count: %v", err)
	}
	if pendingCount != 2 {
		t.Errorf("expected 2 pending outbox items, got %d", pendingCount)
	}

	// 2. Re-ingest exact same samples (idempotency test)
	accepted2, duplicates2, _, err := telemetryRepo.IngestBatch(ctx, "astro-a", samples)
	if err != nil {
		t.Fatalf("second ingest failed: %v", err)
	}
	if accepted2 != 0 || duplicates2 != 2 {
		t.Fatalf("expected 0 accepted, 2 duplicates on retry, got %d accepted, %d duplicates", accepted2, duplicates2)
	}

	// 3. Verify latest sample retrieval
	latest, err := telemetryRepo.GetLatestByAstronautID(ctx, "astro-a")
	if err != nil {
		t.Fatalf("failed to get latest: %v", err)
	}
	if latest == nil || latest.ClientID != "test-client-2" {
		t.Fatalf("expected latest client_id test-client-2, got %+v", latest)
	}
}

func TestStore_AlertLifecycle(t *testing.T) {
	ctx := context.Background()
	db, err := store.Open(ctx, ":memory:")
	if err != nil {
		t.Fatalf("failed to open in-memory db: %v", err)
	}
	defer db.Close()

	alertRepo := store.NewAlertRepo(db)
	now := time.Now().UTC()

	alert := domain.Alert{
		ID:          "test-alert-001",
		AstronautID: "astro-a",
		RuleID:      "hr_high",
		Severity:    domain.SeverityCritical,
		Title:       "Elevated heart rate",
		Message:     "Heart rate exceeds threshold",
		Metric:      "heart_rate",
		Value:       155,
		Threshold:   150,
		Status:      domain.AlertStatusOpen,
		Origin:      domain.AlertOriginRules,
		CreatedAt:   now,
		UpdatedAt:   now,
	}

	// Create
	if err := alertRepo.Create(ctx, alert); err != nil {
		t.Fatalf("failed to create alert: %v", err)
	}

	// Get
	fetched, err := alertRepo.GetByID(ctx, "test-alert-001")
	if err != nil {
		t.Fatalf("failed to get alert: %v", err)
	}
	if fetched.Severity != domain.SeverityCritical || fetched.Status != domain.AlertStatusOpen {
		t.Errorf("unexpected fetched alert: %+v", fetched)
	}

	// Acknowledge
	acked, err := alertRepo.Acknowledge(ctx, "test-alert-001", now.Add(time.Minute))
	if err != nil {
		t.Fatalf("failed to ack alert: %v", err)
	}
	if acked.Status != domain.AlertStatusAcknowledged {
		t.Errorf("expected status acknowledged, got %s", acked.Status)
	}

	// Resolve
	acked.Status = domain.AlertStatusResolved
	if err := alertRepo.Update(ctx, *acked); err != nil {
		t.Fatalf("failed to update alert to resolved: %v", err)
	}

	// Trying to ack a resolved alert must return conflict
	_, err = alertRepo.Acknowledge(ctx, "test-alert-001", now.Add(2*time.Minute))
	if err == nil {
		t.Errorf("expected conflict error when acknowledging resolved alert, got nil")
	}
}
