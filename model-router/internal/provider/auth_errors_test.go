package provider

import "testing"

func TestClassifyAuthFailure(t *testing.T) {
	body := `{"error":{"message":"Invalid API key"}}`
	err := classifyUpstreamError("grok", "grok-4.3", "XAI_API_KEY", 401, body)
	authErr, ok := AsAuthError(err)
	if !ok {
		t.Fatalf("expected AuthError, got %T: %v", err, err)
	}
	if authErr.APIKeyEnv != "XAI_API_KEY" {
		t.Fatalf("unexpected env: %s", authErr.APIKeyEnv)
	}
}

func TestResolveAPIKeyFromEnv(t *testing.T) {
	t.Setenv("XAI_API_KEY", "runtime-key-value")
	got := ResolveAPIKey(ProviderConfig{APIKeyEnv: "XAI_API_KEY", APIKey: "baked-should-not-use"})
	if got != "runtime-key-value" {
		t.Fatalf("expected runtime key, got %q", got)
	}
}

func TestAPIKeyFingerprint(t *testing.T) {
	if APIKeyFingerprint("") != "" {
		t.Fatal("empty key should have empty fingerprint")
	}
	if got := APIKeyFingerprint("abcdefghijklmnop"); got != "…mnop" {
		t.Fatalf("unexpected fingerprint: %s", got)
	}
}
