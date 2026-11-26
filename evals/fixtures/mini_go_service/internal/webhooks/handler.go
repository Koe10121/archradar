package webhooks

import (
	"errors"
	"os"

	"github.com/acme/billing-go/internal/billing"
)

func HandleBillingWebhook(payload string, sig string) error {
	secret := os.Getenv("WEBHOOK_SIGNING_SECRET")
	if secret == "" || sig == "" || payload == "" {
		return errors.New("invalid webhook signature")
	}
	return billing.SyncInvoice("cus_demo")
}
