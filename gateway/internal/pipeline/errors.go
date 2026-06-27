package pipeline

import "fmt"

// PolicyBlockedError is returned when a defense or policy layer blocks the request.
type PolicyBlockedError struct {
	Message       string
	Layer         string
	Action        string
	PolicyAction  string
	FusedScore    float64
	Details       map[string]any
}

func (e *PolicyBlockedError) Error() string {
	return e.Message
}

// ApprovalRequiredError indicates agent-gate requires human approval.
type ApprovalRequiredError struct {
	Message    string
	ApprovalID string
	ToolName   string
	Details    map[string]any
}

func (e *ApprovalRequiredError) Error() string {
	return e.Message
}

// ProviderError wraps upstream model-router failures.
type ProviderError struct {
	Message    string
	StatusCode int
	Provider   string
	Model      string
	ErrorType  string
	Details    map[string]any
}

func (e *ProviderError) Error() string {
	return e.Message
}

// StreamingUnsupportedError is returned for stream=true requests.
type StreamingUnsupportedError struct{}

func (e *StreamingUnsupportedError) Error() string {
	return "defended streaming is not supported: output defense requires the complete assistant response before content is released to the client"
}

func (e *StreamingUnsupportedError) ErrorType() string {
	return "streaming_unsupported"
}

// HTTPError indicates a downstream service returned an unexpected status.
type HTTPError struct {
	URL        string
	StatusCode int
	Body       string
}

func (e *HTTPError) Error() string {
	return fmt.Sprintf("%s returned %d: %s", e.URL, e.StatusCode, e.Body)
}
