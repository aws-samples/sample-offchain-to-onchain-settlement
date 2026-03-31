#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "=== Settlement System Deployment ==="

# Check prerequisites
command -v aws >/dev/null 2>&1 || { echo "AWS CLI required"; exit 1; }
command -v cdk >/dev/null 2>&1 || { echo "CDK CLI required (npm install -g aws-cdk)"; exit 1; }
command -v forge >/dev/null 2>&1 || { echo "Foundry required"; exit 1; }

# Ensure .env exists with PRIVATE_KEY
if [ ! -f .env ]; then
  cp .env-sample .env
  echo "Created .env from .env-sample - please set PRIVATE_KEY and re-run"
  exit 1
fi

source .env
if [ -z "$PRIVATE_KEY" ]; then
  echo "PRIVATE_KEY not set in .env"
  exit 1
fi

CHAIN_ID=${CHAIN_ID:-11155111}
REGION=${AWS_REGION:-us-east-1}
CRE_CHAIN_NAME=${CRE_CHAIN_NAME:-ethereum-testnet-sepolia}
CHAIN_SELECTOR=${CHAIN_SELECTOR:-16015286601757825753}

# Step 1: Deploy AWS infrastructure (initial)
echo ""
echo "=== Step 1/4: Deploying AWS infrastructure ==="
cd infra
pip install -q -r requirements.txt
cdk bootstrap --quiet 2>/dev/null || true
cdk deploy -c verifyingContract=0x0000000000000000000000000000000000000000 -c chainId=$CHAIN_ID --require-approval never
cd ..

# Step 2: Get KMS signer address
echo ""
echo "=== Step 2/4: Getting KMS signer address ==="
pip install -q -r aws/requirements.txt
KMS_KEY_ID=$(aws cloudformation describe-stacks --stack-name SettlementStack \
  --query 'Stacks[0].Outputs[?OutputKey==`KmsKeyId`].OutputValue' --output text --region $REGION)
KMS_SIGNER=$(PYTHONPATH=. python3 scripts/kms_signer_address.py --key-id $KMS_KEY_ID --region $REGION)
echo "KMS_SIGNER=$KMS_SIGNER"

# Update .env with KMS_SIGNER (remove old entry if exists)
grep -v "^KMS_SIGNER=" .env > .env.tmp && mv .env.tmp .env
echo "KMS_SIGNER=$KMS_SIGNER" >> .env
source .env

# Step 3: Deploy smart contracts
echo ""
echo "=== Step 3/4: Deploying smart contracts to Sepolia ==="
./scripts/deploy-contracts.sh
source .env

# Step 4: Update AWS with contract address and configure CRE
echo ""
echo "=== Step 4/4: Updating AWS and configuring CRE ==="
cd infra
cdk deploy -c verifyingContract=$SETTLEMENT_CONSUMER -c chainId=$CHAIN_ID --require-approval never
cd ..

# Configure CRE
API_KEY_ID=$(aws cloudformation describe-stacks --stack-name SettlementStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' --output text --region $REGION)
AWS_API_KEY=$(aws apigateway get-api-key --api-key $API_KEY_ID --include-value \
  --query 'value' --output text --region $REGION)
API_BASE=$(aws cloudformation describe-stacks --stack-name SettlementStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue' --output text --region $REGION)

cd cre && go mod tidy 2>/dev/null; cd ..

cat > cre/.env << EOF
AWS_API_KEY_VALUE=$AWS_API_KEY
CRE_ETH_PRIVATE_KEY=$PRIVATE_KEY
EOF

cat > cre/project.yaml << EOF
staging-settings:
  rpcs:
    - chain-name: $CRE_CHAIN_NAME
      url: $RPC_URL

production-settings:
  rpcs:
    - chain-name: $CRE_CHAIN_NAME
      url: $RPC_URL
EOF

cat > cre/settlement-workflow/config.staging.json << EOF
{
  "schedule": "*/10 * * * * *",
  "awsApiBase": "$API_BASE",
  "receiverAddress": "$SETTLEMENT_CONSUMER",
  "chainSelector": $CHAIN_SELECTOR,
  "chainId": $CHAIN_ID,
  "gasLimit": 1200000,
  "workflowRunId": "staging"
}
EOF

cat > cre/settlement-workflow/config.production.json << EOF
{
  "schedule": "*/10 * * * * *",
  "awsApiBase": "$API_BASE",
  "receiverAddress": "$SETTLEMENT_CONSUMER",
  "chainSelector": $CHAIN_SELECTOR,
  "chainId": $CHAIN_ID,
  "gasLimit": 1200000,
  "workflowRunId": "production"
}
EOF

echo ""
echo "=== Deployment Complete ==="
echo "TOKEN=$TOKEN"
echo "SETTLEMENT_CONSUMER=$SETTLEMENT_CONSUMER"
echo "KEY_REGISTRY=$KEY_REGISTRY"
echo "API_BASE=$API_BASE"
echo "CRE_CHAIN_NAME=$CRE_CHAIN_NAME"
echo "CHAIN_SELECTOR=$CHAIN_SELECTOR"
