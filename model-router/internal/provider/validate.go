package provider

import (
	"context"
)

// ModelValidator can probe whether a specific model ID is accepted by the upstream.
type ModelValidator interface {
	CheckModel(ctx context.Context, model string) error
}

// CheckModel probes a model ID when the provider supports validation.
func CheckModel(ctx context.Context, p Provider, model string) error {
	if model == "" {
		return nil
	}
	if v, ok := p.(ModelValidator); ok {
		return v.CheckModel(ctx, model)
	}
	return nil
}
