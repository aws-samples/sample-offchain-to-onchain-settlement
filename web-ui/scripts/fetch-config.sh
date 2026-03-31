#!/bin/bash
# Fetch settings from AWS and .env, output as Vite env vars

# Load contract addresses from .env
source ../.env 2>/dev/null

# Get API Base URL from CloudFormation
API_BASE=$(aws cloudformation describe-stacks --stack-name SettlementStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue' --output text 2>/dev/null)

# Get API Key
API_KEY_ID=$(aws cloudformation describe-stacks --stack-name SettlementStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' --output text 2>/dev/null)
API_KEY=$(aws apigateway get-api-key --api-key "$API_KEY_ID" --include-value \
  --query 'value' --output text 2>/dev/null)

cat > .env.local << EOF
VITE_API_BASE_URL=$API_BASE
VITE_API_KEY=$API_KEY
VITE_TOKEN_ADDRESS=$TOKEN
VITE_SETTLEMENT_CONSUMER=$SETTLEMENT_CONSUMER
EOF

echo "Created .env.local with settings from AWS"
