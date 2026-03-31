# Infrastructure (CDK)

AWS CDK stack that deploys the settlement ingestion infrastructure.

## Resources Created

| Resource | Type | Purpose |
|----------|------|---------|
| SignerKey | KMS Key | secp256k1 key for EIP-712 signing |
| RawMessageBucket | S3 Bucket | Stores original financial messages |
| InstructionsTable | DynamoDB | CSI records with status GSI |
| IdempotencyTable | DynamoDB | Idempotency key → instructionId mapping |
| AuditTable | DynamoDB | Append-only audit trail |
| IngestionHandler | Lambda | API handler (Python 3.11) |
| SettlementApi | API Gateway | REST API endpoints |

## Prerequisites

```bash
pip install -r requirements.txt
npm install -g aws-cdk  # if not already installed
```

## Deployment

```bash
cd infra

# First time only
cdk bootstrap

# Deploy with contract address
cdk deploy \
  -c verifyingContract=0x<SettlementConsumerAddress> \
  -c chainId=11155111
```

## Context Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `verifyingContract` | SettlementConsumer address (EIP-712 domain) | `0x0000...0000` |
| `chainId` | Allowed chain ID | `11155111` (Sepolia) |

## Outputs

After deployment, CDK outputs:

| Output | Description |
|--------|-------------|
| `ApiBaseUrl` | API Gateway endpoint URL |
| `KmsKeyId` | KMS key ID for signer address derivation |
| `RawBucketName` | S3 bucket name |
| `InstructionsTableName` | DynamoDB table name |
| `IdempotencyTableName` | DynamoDB table name |
| `AuditTableName` | DynamoDB table name |

## Lambda Environment

The Lambda function receives these environment variables:

| Variable | Source |
|----------|--------|
| `INSTRUCTIONS_TABLE` | InstructionsTable.tableName |
| `IDEMPOTENCY_TABLE` | IdempotencyTable.tableName |
| `AUDIT_TABLE` | AuditTable.tableName |
| `RAW_BUCKET` | RawMessageBucket.bucketName |
| `KMS_KEY_ID` | SignerKey.keyId |
| `VERIFYING_CONTRACT` | Context parameter |
| `STATUS_INDEX` | `status-index` |
| `ALLOWED_CHAIN_ID` | Context parameter |

## API Routes

| Method | Path | Handler |
|--------|------|---------|
| POST | /messages | Submit settlement instruction |
| GET | /instructions/pending | List pending instructions |
| GET | /instructions | List all instructions |
| POST | /instructions/{id}/status | Update instruction status |

## DynamoDB Schema

### InstructionsTable
- Partition key: `instructionId` (String)
- GSI `status-index`: partition=`status`, sort=`createdAt`

### IdempotencyTable
- Partition key: `idempotencyKey` (String)

### AuditTable
- Partition key: `instructionId` (String)
- Sort key: `ts` (Number)

## Updating Contract Address

After deploying smart contracts, update the Lambda with the real SettlementConsumer address:

```bash
cdk deploy -c verifyingContract=0x<actual-address> -c chainId=11155111
```

This updates the `VERIFYING_CONTRACT` environment variable, which is used in EIP-712 domain separator calculation.

## Cleanup

```bash
cdk destroy
```

Note: Resources have `RemovalPolicy.DESTROY` and `autoDeleteObjects=True` for easy cleanup. Change these for production.
