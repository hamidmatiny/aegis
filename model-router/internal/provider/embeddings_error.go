package provider

import "fmt"

// EmbeddingNotSupportedError is returned when a provider has no embeddings API.
// Callers must surface this as HTTP 501 — never invent a vector.
type EmbeddingNotSupportedError struct {
	Provider string
}

func (e *EmbeddingNotSupportedError) Error() string {
	return fmt.Sprintf(
		"provider %q does not support embeddings (no upstream embeddings API)",
		e.Provider,
	)
}

// ErrorType is the stable machine-readable code for API responses.
func (e *EmbeddingNotSupportedError) ErrorType() string {
	return "embeddings_not_supported"
}

// AsEmbeddingNotSupportedError unwraps EmbeddingNotSupportedError.
func AsEmbeddingNotSupportedError(err error) (*EmbeddingNotSupportedError, bool) {
	if err == nil {
		return nil, false
	}
	if e, ok := err.(*EmbeddingNotSupportedError); ok {
		return e, true
	}
	return nil, false
}

// IsEmbeddingNotSupportedError reports whether err is EmbeddingNotSupportedError.
func IsEmbeddingNotSupportedError(err error) bool {
	_, ok := AsEmbeddingNotSupportedError(err)
	return ok
}
