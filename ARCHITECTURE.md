# Architecture Reference

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| API Gateway | AWS | Exposes REST endpoints |
| Lambda | `aws/app.py` | Normalizes messages, signs with KMS, stores CSI |
| DynamoDB | AWS | Instructions, idempotency, audit tables |
| S3 | AWS | Raw message storage |
| KMS | AWS | secp256k1 signing key |
| CRE Workflow | `cre/settlement-workflow/` | Polls pending, submits on-chain |
| KeystoneForwarder | Chainlink | Validates DON signatures, forwards to receiver |
| SettlementConsumer | `contracts/` | Verifies AWS signature, executes settlement |
| KeyRegistry | `contracts/` | Allowlist of authorized signers |
| Token | `contracts/` | ERC20-like with mint/burn |

## Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OFF-CHAIN BOUNDARY                                │
│  - Raw messages and signing keys remain in AWS (KMS/HSM in prod)           │
│  - Only hashes and canonical semantics leave this boundary                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION BOUNDARY                               │
│  - CRE can only submit signed CSIs; cannot forge settlements               │
│  - DON consensus ensures report integrity                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ON-CHAIN BOUNDARY                                  │
│  - SettlementConsumer is final authority                                   │
│  - Verifies signature against KeyRegistry allowlist                        │
│  - Enforces expiry, idempotency, chain ID                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Ingestion**: Raw message received via `POST /messages`
2. **Hashing**: `messageDigest = keccak256(rawMessage)`
3. **Normalization**: Build CSI with deterministic `instructionId`
4. **Signing**: Lambda requests KMS signature over EIP-712 digest
5. **Storage**: Raw message → S3, CSI → DynamoDB (status=PENDING)
6. **Pickup**: CRE polls `GET /instructions/pending`
7. **Report**: CRE encodes CSI + signature, generates DON report
8. **Submission**: KeystoneForwarder validates DON sigs, calls `onReport()`
9. **Verification**: SettlementConsumer verifies AWS signature, checks rules
10. **Execution**: Mint/burn tokens based on intent
11. **Callback**: CRE reports outcome to AWS via `POST /instructions/{id}/status`

## Canonical Settlement Instruction (CSI)

```
struct CanonicalSettlementInstruction {
    bytes32 instructionId;    // Deterministic ID from content hash
    bytes32 messageDigest;    // keccak256(rawMessage)
    address asset;            // Token contract
    uint256 amount;           // Amount in smallest unit
    address fromParty;        // Source (zero for MINT_ONLY)
    address toParty;          // Destination
    uint64  valueTime;        // Settlement value date
    uint64  createdAt;        // Creation timestamp
    uint64  expiry;           // Expiration timestamp
    uint8   intent;           // 0=MINT_ONLY, 1=BURN_AND_MINT, 2=BURN_ONLY
    uint256 chainId;          // Target chain
    bytes32 nonce;            // Derived from reference
}
```

## instructionId Derivation

```
instructionId = keccak256(
    "CSI_V1" ||
    messageDigest ||
    asset ||
    amount ||
    fromParty ||
    toParty ||
    valueTime ||
    intent ||
    chainId ||
    createdAt ||
    expiry ||
    nonce
)
```

This ensures the same logical instruction always produces the same ID, enabling:
- Idempotent retries
- Cross-system correlation (AWS logs ↔ CRE ↔ on-chain events)

## EIP-712 Signing

Domain:
```
EIP712Domain(string name, string version, uint256 chainId, address verifyingContract)
name = "SettlementInstruction"
version = "1"
chainId = <target chain>
verifyingContract = <SettlementConsumer address>
```

The digest signed by KMS is:
```
keccak256("\x19\x01" || domainSeparator || structHash)
```

## Security Invariants

1. **Only KMS can sign**: Settlement requires signature from KeyRegistry-authorized address
2. **No replay**: `executed[instructionId]` prevents double-execution
3. **Time-bound**: `block.timestamp <= expiry` enforced on-chain
4. **Chain-bound**: `chainId == block.chainid` enforced on-chain
5. **Forwarder-only**: `onReport()` only accepts calls from KeystoneForwarder
6. **Deterministic ID**: `instructionId` must match on-chain derivation
