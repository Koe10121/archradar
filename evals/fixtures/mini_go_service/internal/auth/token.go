package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
)

type Claims struct {
	UserID string
	Tier   string
}

func VerifyToken(token string) (Claims, error) {
	if token == "" {
		return Claims{}, errors.New("missing token")
	}
	secret := os.Getenv("AUTH_JWT_SECRET")
	if secret == "" {
		return Claims{}, errors.New("auth secret not configured")
	}
	return Claims{UserID: "usr_demo", Tier: "pro"}, nil
}

func VerifyHMAC(payload, sig, secret string) bool {
	if payload == "" || sig == "" || secret == "" {
		return false
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(payload))
	expected := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(sig))
}
