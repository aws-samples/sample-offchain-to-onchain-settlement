# Post-Deploy Manual Test Plan

## Prerequisites

- Deployed contracts: KeyRegistry, SettlementConsumer, Token
- AWS stack deployed (API base URL, KMS key ID, table names, bucket)
- CRE workflow config updated with `awsApiBase` and `receiverAddress`
- Access to a funded Sepolia account for on-chain txs

## Environment Variables

```bash
export API_BASE="https://<api-id>.execute-api.us-east-1.amazonaws.com/prod"
export AWS_API_KEY="<api-key-value>"
export AWS_REGION="us-east-1"
export KMS_KEY_ID="<kms-key-id>"
export KEY_REGISTRY="0x..."
export SETTLEMENT_CONSUMER="0x..."
export TOKEN="0x..."
export RPC_URL="https://sepolia.infura.io/v3/<key>"
export ADMIN_PK="0x..."
```

## Data Setup

1. Pick a sample raw message in `examples/` or create a new one
2. Note the expected asset, amount, fromParty, toParty, valueTime, expiry

---

## AWS + API Tests

### 1. Create Instruction
```bash
curl -X POST "$API_BASE/messages" \
  -H "X-API-Key: $AWS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "rawMessage": "<ISO 20022 pacs.008 or SWIFT MT103 message content>",
    "asset": "'"$TOKEN"'",
    "amount": "1000000000000000000",
    "fromParty": "0x0000000000000000000000000000000000000000",
    "toParty": "0x1234567890123456789012345678901234567890",
    "valueTime": 1737500000,
    "intent": "MINT_ONLY",
    "chainId": 11155111
  }'
```
- Expect 200 and a new `instructionId`
- Verify raw message in S3 and CSI in DynamoDB

### 2. Idempotency Check
- POST same payload again
- Expect same `instructionId` (idempotent replay)

### 3. Get Pending Instructions
```bash
curl -H "X-API-Key: $AWS_API_KEY" "$API_BASE/instructions/pending"
```
- Expect the new `instructionId` in the pending list

### 4. Update Status (Valid)
```bash
curl -X POST "$API_BASE/instructions/$INSTRUCTION_ID/status" \
  -H "X-API-Key: $AWS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "CONFIRMED", "txHash": "0x..."}'
```
- Expect 200 and audit record appended

### 5. Update Status (Invalid)
```bash
curl -X POST "$API_BASE/instructions/$INSTRUCTION_ID/status" \
  -H "X-API-Key: $AWS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "INVALID_STATUS"}'
```
- Expect 4xx error

### 6. Verify KMS Signer
```bash
KMS_SIGNER=$(python3 scripts/kms_signer_address.py --key-id "$KMS_KEY_ID" --region "$AWS_REGION")
cast call "$KEY_REGISTRY" "isSigner(address)(bool)" "$KMS_SIGNER" --rpc-url "$RPC_URL"
```
- Expect `true`

---

## CRE Simulation

### Dry Run
```bash
cd cre
cre workflow simulate settlement-workflow --target staging-settings
```

### With Broadcast
```bash
cre workflow simulate settlement-workflow --target staging-settings --broadcast
```
- Confirm report is generated and sent to SettlementConsumer
- Check logs for `txHash`

---

## On-Chain Happy Paths

### MINT_ONLY Settlement
```bash
# Before
cast call "$TOKEN" "totalSupply()(uint256)" --rpc-url "$RPC_URL"
cast call "$TOKEN" "balanceOf(address)(uint256)" "$TO_ADDRESS" --rpc-url "$RPC_URL"

# Run CRE workflow with MINT_ONLY instruction

# After - expect totalSupply increased, recipient balance increased
cast call "$TOKEN" "totalSupply()(uint256)" --rpc-url "$RPC_URL"
cast call "$TOKEN" "balanceOf(address)(uint256)" "$TO_ADDRESS" --rpc-url "$RPC_URL"
```

### BURN_AND_MINT Settlement
```bash
# Before
cast call "$TOKEN" "balanceOf(address)(uint256)" "$FROM_ADDRESS" --rpc-url "$RPC_URL"
cast call "$TOKEN" "balanceOf(address)(uint256)" "$TO_ADDRESS" --rpc-url "$RPC_URL"
cast call "$TOKEN" "totalSupply()(uint256)" --rpc-url "$RPC_URL"

# Run CRE workflow with BURN_AND_MINT instruction

# After - expect source decreased, destination increased, totalSupply unchanged
cast call "$TOKEN" "balanceOf(address)(uint256)" "$FROM_ADDRESS" --rpc-url "$RPC_URL"
cast call "$TOKEN" "balanceOf(address)(uint256)" "$TO_ADDRESS" --rpc-url "$RPC_URL"
cast call "$TOKEN" "totalSupply()(uint256)" --rpc-url "$RPC_URL"
```

---

## On-Chain Negative Paths

### 1. Replay Protection
- Submit the same CSI twice
- Expect second call reverts with `ALREADY_EXECUTED`

```bash
cast call "$SETTLEMENT_CONSUMER" "executed(bytes32)(bool)" "$INSTRUCTION_ID" --rpc-url "$RPC_URL"
# Should return true after first execution
```

### 2. Invalid Signature
- Corrupt the signature or use a non-allowlisted signer
- Expect `SIGNER_UNAUTHORIZED` revert

### 3. Expired CSI
- Use a CSI with expiry in the past
- Expect `EXPIRED` revert

### 4. Unauthorized Forwarder
- Call `onReport` directly (not via forwarder)
- Expect revert

```bash
cast send "$SETTLEMENT_CONSUMER" "onReport(bytes,bytes)" "0x" "0x" \
  --private-key "$ADMIN_PK" --rpc-url "$RPC_URL"
# Should revert
```

---

## Key Rotation

### Add New Signer
```bash
NEW_SIGNER=$(python3 scripts/kms_signer_address.py --key-id "$NEW_KMS_KEY_ID" --region "$AWS_REGION")
cast send "$KEY_REGISTRY" "addSigner(address)" "$NEW_SIGNER" \
  --private-key "$ADMIN_PK" --rpc-url "$RPC_URL"
```

### Remove Old Signer
```bash
cast send "$KEY_REGISTRY" "removeSigner(address)" "$OLD_SIGNER" \
  --private-key "$ADMIN_PK" --rpc-url "$RPC_URL"
```

- After removal, CSIs signed by old key should revert with `SIGNER_UNAUTHORIZED`

---

## Post-Run Verification

```bash
# Check instruction was executed on-chain
cast call "$SETTLEMENT_CONSUMER" "executed(bytes32)(bool)" "$INSTRUCTION_ID" --rpc-url "$RPC_URL"

# Check events
cast logs --rpc-url "$RPC_URL" --address "$SETTLEMENT_CONSUMER"
```

- DynamoDB audit trail reflects status changes
- On-chain events correspond to `instructionId`
