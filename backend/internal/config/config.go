package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	AppEnv              string
	HTTPAddr            string
	DBPath              string
	CORSOrigins         []string
	AlertSustainSamples int
	AlertResolveSamples int
	SimInterval         time.Duration
	SyncRemoteURL       string
	APIKey              string
}

// Load loads configuration from environment variables with fallbacks to defaults.
func Load() (*Config, error) {
	appEnv := getEnv("APP_ENV", "dev")
	httpAddr := getEnv("HTTP_ADDR", ":8080")
	dbPath := getEnv("DB_PATH", "./data/astrovitals.db")

	corsRaw := getEnv("CORS_ORIGINS", "*")
	corsOrigins := parseCSV(corsRaw)

	alertSustain := 3
	if v := os.Getenv("ALERT_SUSTAIN_SAMPLES"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return nil, fmt.Errorf("invalid ALERT_SUSTAIN_SAMPLES %q: must be positive integer", v)
		}
		alertSustain = n
	}

	alertResolve := 5
	if v := os.Getenv("ALERT_RESOLVE_SAMPLES"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return nil, fmt.Errorf("invalid ALERT_RESOLVE_SAMPLES %q: must be positive integer", v)
		}
		alertResolve = n
	}

	simIntervalMs := 1000
	if v := os.Getenv("SIM_INTERVAL_MS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return nil, fmt.Errorf("invalid SIM_INTERVAL_MS %q: must be positive integer", v)
		}
		simIntervalMs = n
	}

	syncRemoteURL := os.Getenv("SYNC_REMOTE_URL")
	apiKey := os.Getenv("API_KEY")

	return &Config{
		AppEnv:              appEnv,
		HTTPAddr:            httpAddr,
		DBPath:              dbPath,
		CORSOrigins:         corsOrigins,
		AlertSustainSamples: alertSustain,
		AlertResolveSamples: alertResolve,
		SimInterval:         time.Duration(simIntervalMs) * time.Millisecond,
		SyncRemoteURL:       syncRemoteURL,
		APIKey:              apiKey,
	}, nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func parseCSV(val string) []string {
	parts := strings.Split(val, ",")
	res := make([]string, 0, len(parts))
	for _, p := range parts {
		trimmed := strings.TrimSpace(p)
		if trimmed != "" {
			res = append(res, trimmed)
		}
	}
	if len(res) == 0 {
		return []string{"*"}
	}
	return res
}
