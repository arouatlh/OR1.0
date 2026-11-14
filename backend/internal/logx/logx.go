package logx

import (
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// New creates and returns a SugaredLogger configured for dev or prod.
func New(appEnv string) (*zap.SugaredLogger, error) {
	var cfg zap.Config
	if appEnv == "prod" || appEnv == "production" {
		cfg = zap.NewProductionConfig()
		cfg.EncoderConfig.TimeKey = "ts"
		cfg.EncoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
	} else {
		cfg = zap.NewDevelopmentConfig()
		cfg.EncoderConfig.EncodeLevel = zapcore.CapitalColorLevelEncoder
	}

	logger, err := cfg.Build()
	if err != nil {
		return nil, err
	}

	return logger.Sugar(), nil
}

// NewNop returns a no-op SugaredLogger for testing.
func NewNop() *zap.SugaredLogger {
	return zap.NewNop().Sugar()
}
