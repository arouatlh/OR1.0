package apperr

import (
	"errors"
	"fmt"
	"strings"
)

type Kind uint8

const (
	KindInternal Kind = iota
	KindBadRequest
	KindNotFound
	KindConflict
	KindValidation
	KindUnavailable
	KindPayloadTooLarge
)

// Error is opaque: fields are unexported; behavior is exposed via methods.
type Error struct {
	kind    Kind
	op      string       // e.g. "store.telemetry.insert"
	public  string       // safe, client-facing message
	details []FieldIssue // validation only
	cause   error        // internal only, never serialized
}

type FieldIssue struct {
	Field string
	Issue string
}

func (e *Error) Error() string {
	if e.cause != nil {
		return fmt.Sprintf("%s: %v", e.op, e.cause)
	}
	if e.public != "" {
		return fmt.Sprintf("%s: %s", e.op, e.public)
	}
	return e.op
}

func (e *Error) Unwrap() error {
	return e.cause
}

func (e *Error) Kind() Kind {
	return e.kind
}

func (e *Error) Public() string {
	return e.public
}

func (e *Error) Details() []FieldIssue {
	return e.details
}

func (e *Error) Op() string {
	return e.op
}

// Wrap creates an Error with op, kind, public safe message, and internal cause.
func Wrap(op string, kind Kind, public string, cause error) error {
	if cause == nil && public == "" {
		return nil
	}
	if public == "" && kind == KindInternal {
		public = "Something went wrong."
	}
	return &Error{
		kind:   kind,
		op:     op,
		public: public,
		cause:  cause,
	}
}

// NotFound returns a KindNotFound error with a public message.
func NotFound(op, public string) error {
	if public == "" {
		public = "Resource not found."
	}
	return &Error{
		kind:   KindNotFound,
		op:     op,
		public: public,
	}
}

// BadRequest returns a KindBadRequest error.
func BadRequest(op, public string, cause error) error {
	if public == "" {
		public = "Bad request."
	}
	return &Error{
		kind:   KindBadRequest,
		op:     op,
		public: public,
		cause:  cause,
	}
}

// Conflict returns a KindConflict error.
func Conflict(op, public string, cause error) error {
	if public == "" {
		public = "Conflict."
	}
	return &Error{
		kind:   KindConflict,
		op:     op,
		public: public,
		cause:  cause,
	}
}

// Validation returns a KindValidation error formatted with field issues.
func Validation(op string, issues ...FieldIssue) error {
	var parts []string
	for _, issue := range issues {
		if issue.Field != "" {
			parts = append(parts, fmt.Sprintf("%s %s", issue.Field, issue.Issue))
		} else {
			parts = append(parts, issue.Issue)
		}
	}
	msg := "validation failed"
	if len(parts) > 0 {
		msg = "validation failed: " + strings.Join(parts, ", ")
	}
	return &Error{
		kind:    KindValidation,
		op:      op,
		public:  msg,
		details: issues,
	}
}

// ValidationMessage creates a validation error from a direct message.
func ValidationMessage(op, message string) error {
	return &Error{
		kind:   KindValidation,
		op:     op,
		public: message,
	}
}

// Unavailable returns a KindUnavailable error.
func Unavailable(op string, cause error) error {
	return &Error{
		kind:   KindUnavailable,
		op:     op,
		public: "Service temporarily unavailable.",
		cause:  cause,
	}
}

// Internal returns a KindInternal error. Safe message is always generic.
func Internal(op string, cause error) error {
	return &Error{
		kind:   KindInternal,
		op:     op,
		public: "Something went wrong.",
		cause:  cause,
	}
}

// KindOf returns the Kind of an error, default KindInternal.
func KindOf(err error) Kind {
	if err == nil {
		return KindInternal
	}
	var e *Error
	if errors.As(err, &e) {
		return e.kind
	}
	return KindInternal
}

// PublicMessage returns the safe, client-facing message.
func PublicMessage(err error) string {
	if err == nil {
		return ""
	}
	var e *Error
	if errors.As(err, &e) {
		if e.public != "" {
			return e.public
		}
		if e.kind == KindInternal {
			return "Something went wrong."
		}
		return "An error occurred."
	}
	return "Something went wrong."
}

// OpOf returns the op string if present.
func OpOf(err error) string {
	if err == nil {
		return ""
	}
	var e *Error
	if errors.As(err, &e) {
		return e.op
	}
	return ""
}
