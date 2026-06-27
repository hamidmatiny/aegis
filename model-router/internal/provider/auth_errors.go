package provider

import (
	"errors"
	"fmt"
	"strings"
)

// AuthError indicates upstream rejected credentials (401/403). Must not silently
// fall back to mock or other providers when the caller requested this provider.
type AuthError struct {
	Provider  string
	Status    int
	Body      string
	APIKeyEnv string
}

func (e *AuthError) Error() string {
	envHint := e.APIKeyEnv
	if envHint == "" {
		envHint = "API key env"
	}
	return fmt.Sprintf(
		"provider %q authentication failed (HTTP %d): check %s at container runtime — %s",
		e.Provider,
		e.Status,
		envHint,
		authGuidance(e.Body),
	)
}

func (e *AuthError) ErrorType() string {
	return "auth_failed"
}

// AsAuthError unwraps an AuthError from an error chain.
func AsAuthError(err error) (*AuthError, bool) {
	var target *AuthError
	if errors.As(err, &target) {
		return target, true
	}
	return nil, false
}

// IsAuthError reports whether err is an authentication failure.
func IsAuthError(err error) bool {
	_, ok := AsAuthError(err)
	return ok
}

func authGuidance(body string) string {
	trimmed := strings.TrimSpace(body)
	if trimmed == "" {
		return "invalid or missing API key"
	}
	if len(trimmed) > 160 {
		return trimmed[:160] + "…"
	}
	return trimmed
}

func isAuthFailure(status int, body string) bool {
	if status == 401 || status == 403 {
		return true
	}
	lower := strings.ToLower(body)
	return strings.Contains(lower, "invalid api key") ||
		strings.Contains(lower, "incorrect api key") ||
		strings.Contains(lower, "invalid authentication") ||
		strings.Contains(lower, "authentication failed") ||
		strings.Contains(lower, "permission denied") && strings.Contains(lower, "api")
}
