package main

import (
	"fmt"

	"github.com/acme/billing-go/internal/billing"
	"github.com/acme/billing-go/internal/webhooks"
)

func HandleCheckout(token string, planID string) error {
	inv, err := billing.ChargeSubscription(token, planID)
	if err != nil {
		return err
	}
	fmt.Println("charged:", billing.FormatCents(inv.AmountCents))
	return nil
}

func StartServer() {
	_ = webhooks.HandleBillingWebhook("{}", "sig")
	_ = HandleCheckout("tok_demo", "plan_pro")
}
