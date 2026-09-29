#!/bin/bash

# Polar.sh payment webhook handler
PAYMENT_SUCCESS_URL="https://api.polar.sh/payments/verify"

# Verify payment and trigger install
if curl -s -X POST $PAYMENT_SUCCESS_URL -H "Content-Type: application/json" \
-d '{"transaction_id":"$1"}' | grep -q "success"; then
    echo "Payment verified. Running installation...";
    bash scripts/install.sh
else
    echo "Payment verification failed."
    exit 1
fi