package apperr_test

import (
	"errors"
	"strings"
	"testing"

	"astrovitals/internal/apperr"
)

func TestAppErr_OpaqueErrorWrapping(t *testing.T) {
	internalErr := errors.New("sqlite: disk I/O error or syntax error in table schema at line 42")
	wrapped := apperr.Internal("store.telemetry.insert", internalErr)

	// Kind must be internal
	if kind := apperr.KindOf(wrapped); kind != apperr.KindInternal {
		t.Errorf("expected KindInternal, got %v", kind)
	}

	// Internal error string includes cause for server logs
	logStr := wrapped.Error()
	if !strings.Contains(logStr, "store.telemetry.insert") || !strings.Contains(logStr, "disk I/O error") {
		t.Errorf("expected internal cause in log string, got %q", logStr)
	}

	// Public message MUST NEVER leak internal error, SQL, or file paths
	pubMsg := apperr.PublicMessage(wrapped)
	if pubMsg != "Something went wrong." {
		t.Errorf("expected public message 'Something went wrong.', got %q", pubMsg)
	}

	// Raw unhandled standard error also gets generic safe message
	rawErr := errors.New("raw unexpected crash")
	if pubMsg := apperr.PublicMessage(rawErr); pubMsg != "Something went wrong." {
		t.Errorf("expected public message 'Something went wrong.', got %q", pubMsg)
	}
}

func TestAppErr_ValidationMessage(t *testing.T) {
	valErr := apperr.Validation("httpapi.telemetry.validate",
		apperr.FieldIssue{Field: "samples[0].spo2", Issue: "must be between 50 and 100"},
	)

	if kind := apperr.KindOf(valErr); kind != apperr.KindValidation {
		t.Errorf("expected KindValidation, got %v", kind)
	}

	pubMsg := apperr.PublicMessage(valErr)
	expected := "validation failed: samples[0].spo2 must be between 50 and 100"
	if pubMsg != expected {
		t.Errorf("expected %q, got %q", expected, pubMsg)
	}
}
