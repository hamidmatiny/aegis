package signer

import (
	"crypto/ed25519"
	"crypto/x509"
	"fmt"
)

func parsePKCS8Ed25519(der []byte) (ed25519.PrivateKey, error) {
	key, err := x509.ParsePKCS8PrivateKey(der)
	if err != nil {
		return nil, fmt.Errorf("parse PKCS8 key: %w", err)
	}
	priv, ok := key.(ed25519.PrivateKey)
	if !ok {
		return nil, fmt.Errorf("expected Ed25519 private key, got %T", key)
	}
	return priv, nil
}
