package billing

import (
	"errors"

	"github.com/acme/billing-go/internal/auth"
)

type Invoice struct {
	ID          string
	AmountCents int64
}

func ChargeSubscription(token string, planID string) (Invoice, error) {
	claims, err := auth.VerifyToken(token)
	if err != nil {
		return Invoice{}, err
	}
	if planID == "" {
		return Invoice{}, errors.New("plan id required")
	}
	return Invoice{
		ID:          "inv_" + claims.UserID,
		AmountCents: 4900,
	}, nil
}

func SyncInvoice(customerID string) error {
	if customerID == "" {
		return errors.New("customer id required")
	}
	return nil
}
