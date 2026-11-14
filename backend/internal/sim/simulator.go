package sim

import (
	"context"
	"fmt"
	"math/rand/v2"
	"sync"
	"time"

	"astrovitals/internal/apperr"
	"astrovitals/internal/domain"
	"astrovitals/internal/service"

	"go.uber.org/zap"
)

type Scenario string

const (
	ScenarioNormal      Scenario = "normal"
	ScenarioTachycardia Scenario = "tachycardia"
	ScenarioHypoxia     Scenario = "hypoxia"
	ScenarioArrhythmia  Scenario = "arrhythmia"
)

type Simulator struct {
	mu            sync.Mutex
	ingestService *service.IngestService
	interval      time.Duration
	logger        *zap.SugaredLogger

	running     bool
	cancelFunc  context.CancelFunc
	scenario    Scenario
	astronautID string
}

func NewSimulator(ingestService *service.IngestService, interval time.Duration, logger *zap.SugaredLogger) *Simulator {
	if interval <= 0 {
		interval = 1 * time.Second
	}
	return &Simulator{
		ingestService: ingestService,
		interval:      interval,
		logger:        logger,
	}
}

func (s *Simulator) Start(scenario Scenario, astronautID string) error {
	const op = "sim.start"

	s.mu.Lock()
	defer s.mu.Unlock()

	if s.running {
		return apperr.Conflict(op, "Simulator is already running.", nil)
	}

	switch scenario {
	case ScenarioNormal, ScenarioTachycardia, ScenarioHypoxia, ScenarioArrhythmia:
	default:
		return apperr.BadRequest(op, fmt.Sprintf("Unknown scenario %q: valid options are normal, tachycardia, hypoxia, arrhythmia", scenario), nil)
	}

	if astronautID == "" {
		astronautID = "astro-a"
	}

	ctx, cancel := context.WithCancel(context.Background())
	s.running = true
	s.cancelFunc = cancel
	s.scenario = scenario
	s.astronautID = astronautID

	if s.logger != nil {
		s.logger.Infow("simulator start", "scenario", string(scenario), "astronaut_id", astronautID)
	}

	go s.runLoop(ctx, scenario, astronautID)

	return nil
}

func (s *Simulator) Stop() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.running {
		return nil
	}

	if s.cancelFunc != nil {
		s.cancelFunc()
	}
	s.running = false

	if s.logger != nil {
		s.logger.Infow("simulator stop", "scenario", string(s.scenario), "astronaut_id", s.astronautID)
	}

	return nil
}

func (s *Simulator) Status() (bool, Scenario, string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.running, s.scenario, s.astronautID
}

func (s *Simulator) runLoop(ctx context.Context, scenario Scenario, astronautID string) {
	ticker := time.NewTicker(s.interval)
	defer ticker.Stop()

	// Seeded PRNG for reproducible runs
	rng := rand.New(rand.NewPCG(42, 1024))
	step := 0

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			sample := generateSample(rng, scenario, step, astronautID)
			step++

			_, err := s.ingestService.Ingest(ctx, astronautID, []domain.Telemetry{sample})
			if err != nil && s.logger != nil {
				// Internal sim error, do not panic
				s.logger.Warnw("sim sample ingest error", "err", err.Error())
			}
		}
	}
}

func generateSample(rng *rand.Rand, scenario Scenario, step int, astronautID string) domain.Telemetry {
	now := time.Now().UTC()
	clientID := fmt.Sprintf("sim-%s-%d-%d", scenario, now.UnixMilli(), step)

	// Defaults for normal
	hr := 68 + rng.IntN(12) // 68 to 80
	spo2 := 97 + rng.IntN(3) // 97 to 99
	sys := 115 + rng.IntN(8) // 115 to 123
	dia := 74 + rng.IntN(5)  // 74 to 79
	rr := 13 + rng.IntN(4)   // 13 to 16
	ecg := "sinus"
	stress := 0.15 + (float64(rng.IntN(10)) / 100.0) // 0.15 - 0.25

	switch scenario {
	case ScenarioNormal:
		// Normal variations

	case ScenarioTachycardia:
		// Ramps to 155 over 20 ticks, holds for 15, then recovers
		cycle := step % 50
		if cycle < 20 {
			hr = 75 + int(float64(cycle)/20.0*80.0) // ramps up to 155
		} else if cycle < 35 {
			hr = 154 + rng.IntN(5) // holds at 154-158 (critical!)
			stress = 0.85
		} else {
			hr = 155 - int(float64(cycle-35)/15.0*80.0) // recovers down
		}

	case ScenarioHypoxia:
		// SpO2 ramps down to 88, RR rises
		cycle := step % 40
		if cycle < 15 {
			spo2 = 98 - int(float64(cycle)/15.0*10.0) // down to 88 (critical)
			rr = 14 + int(float64(cycle)/15.0*15.0)   // up to 29
		} else if cycle < 25 {
			spo2 = 87 + rng.IntN(2) // 87-88
			rr = 28 + rng.IntN(3)   // 28-30
			stress = 0.75
		} else {
			spo2 = 88 + int(float64(cycle-25)/15.0*10.0)
			rr = 28 - int(float64(cycle-25)/15.0*14.0)
		}

	case ScenarioArrhythmia:
		// ECG flips to irregular for 10 ticks, HR jitter
		cycle := step % 30
		if cycle >= 5 && cycle < 18 {
			ecg = "irregular"
			hr = 85 + rng.IntN(40) // erratic HR
			stress = 0.72
		}
	}

	return domain.Telemetry{
		AstronautID: astronautID,
		ClientID:    clientID,
		RecordedAt:  now,
		Source:      domain.SourceSimulator,
		HeartRate:   &hr,
		SpO2:        &spo2,
		Systolic:    &sys,
		Diastolic:   &dia,
		RespRate:    &rr,
		ECGSummary:  &ecg,
		StressIndex: &stress,
	}
}
