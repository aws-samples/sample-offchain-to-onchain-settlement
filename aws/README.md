# AWS Ingestion Layer

Lambda-based API that receives financial messages, normalizes them into Canonical Settlement Instructions (CSI), signs with KMS, and stores for CRE pickup.

## Components

| File | Purpose |
|------|---------|
| `app.py` | Lambda handler with API routes |
| `csi.py` | CSI builder, EIP-712 typed data, instructionId derivation |
| `kms_signer.py` | Signs EIP-712 digest using AWS KMS secp256k1 key |
| `crypto.py` | Pure-Python keccak256, signature parsing, address recovery |

## API Endpoints

### POST /messages

Submit a financial message for settlement.

**Request:**
```json
{
  "rawMessage": "SWIFT MT103|REF=ABC123|AMT=100000",
  "asset": "0x1111111111111111111111111111111111111111",
  "amount": "1000000000000000000",
  "fromParty": "0x0000000000000000000000000000000000000000",
  "toParty": "0x3333333333333333333333333333333333333333",
  "valueTime": 1737500000,
  "intent": "MINT_ONLY",
  "chainId": 11155111,
  "reference": "ABC123",
  "expirySeconds": 3600
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `rawMessage` | string | Yes | Original financial message (stored in S3) |
| `asset` | address | Yes | Token contract address |
| `amount` | uint256 string | Yes | Amount in token's smallest unit |
| `fromParty` | address | Yes | Source address (use zero address for MINT_ONLY) |
| `toParty` | address | Yes | Destination address |
| `valueTime` | uint64 | Yes | Settlement value date (unix timestamp) |
| `intent` | string | Yes | `MINT_ONLY`, `BURN_AND_MINT`, or `BURN_ONLY` |
| `chainId` | uint256 | Yes | Target chain ID (e.g., 11155111 for Sepolia) |
| `reference` | string | No | External reference (used in nonce derivation) |
| `expirySeconds` | uint64 | No | Seconds until expiry (default: 3600) |
| `createdAt` | uint64 | No | Override creation timestamp |
| `expiry` | uint64 | No | Override expiry timestamp |

**Response (201):**
```json
{
  "instruction": {
    "instructionId": "0x...",
    "messageDigest": "0x...",
    "asset": "0x...",
    "amount": "1000000000000000000",
    "fromParty": "0x...",
    "toParty": "0x...",
    "valueTime": 1737500000,
    "createdAt": 1737400000,
    "expiry": 1737403600,
    "intent": "MINT_ONLY",
    "chainId": 11155111,
    "nonce": "0x..."
  },
  "signature": "0x...",
  "status": "PENDING",
  "typedData": { ... },
  "messageDigest": "0x...",
  "signer": "0x..."
}
```

### GET /instructions/pending

Fetch all instructions with status `PENDING`.

**Response (200):**
```json
{
  "pending": [
    {
      "instruction": { ... },
      "signature": "0x...",
      "status": "PENDING",
      "typedData": { ... },
      "messageDigest": "0x...",
      "signer": "0x..."
    }
  ]
}
```

### GET /instructions

Fetch all instructions (any status).

**Response (200):**
```json
{
  "instructions": [
    {
      "instruction": { ... },
      "signature": "0x...",
      "status": "PENDING|SUBMITTED|CONFIRMED|FAILED",
      "typedData": { ... },
      "messageDigest": "0x...",
      "signer": "0x..."
    }
  ]
}
```

### POST /instructions/{instructionId}/status

Update instruction status (called by CRE after on-chain submission).

**Request:**
```json
{
  "status": "CONFIRMED",
  "txHash": "0x...",
  "workflowRunId": "staging",
  "chainId": 11155111,
  "reason": ""
}
```

| Status | Description |
|--------|-------------|
| `SUBMITTED` | Transaction sent to chain |
| `CONFIRMED` | Transaction confirmed on-chain |
| `FAILED` | Transaction failed or reverted |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `INSTRUCTIONS_TABLE` | DynamoDB table for CSI records |
| `IDEMPOTENCY_TABLE` | DynamoDB table for idempotency keys |
| `AUDIT_TABLE` | DynamoDB table for audit trail |
| `RAW_BUCKET` | S3 bucket for raw messages |
| `KMS_KEY_ID` | KMS key ID for signing (secp256k1) |
| `VERIFYING_CONTRACT` | SettlementConsumer address (EIP-712 domain) |
| `STATUS_INDEX` | GSI name for status queries (default: `status-index`) |
| `ALLOWED_CHAIN_ID` | Optional: restrict to single chain |

## Idempotency

Idempotency key is derived from:
```
keccak256("CSI_IDEMPOTENCY_V1" || messageDigest || asset || amount || fromParty || toParty || valueTime || intent || chainId || referenceHash)
```

Submitting the same message twice returns the same `instructionId` and signature.

## Signing Flow

1. Build CSI from normalized fields
2. Compute EIP-712 typed data hash: `keccak256("\x19\x01" || domainSeparator || structHash)`
3. Call KMS Sign with `ECDSA_SHA_256`, `MessageType=DIGEST`
4. Parse DER signature, enforce low-s, derive recovery byte `v`
5. Return 65-byte signature `r || s || v`

## Storage

| Store | Key | Content |
|-------|-----|---------|
| S3 | `raw/{messageDigest}.txt` | Original raw message bytes |
| DynamoDB Instructions | `instructionId` | CSI, signature, status, typedData |
| DynamoDB Idempotency | `idempotencyKey` | Maps to instructionId |
| DynamoDB Audit | `instructionId + ts` | Status changes, tx outcomes |
