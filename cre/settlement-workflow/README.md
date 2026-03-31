# Settlement Workflow

CRE workflow that polls AWS for pending settlement instructions and submits them on-chain.

## Flow

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ Cron Trigger│────▶│ Fetch       │────▶│ Encode Report    │────▶│ Submit via         │
│ (every 10s) │     │ Pending CSIs│     │ (CSI + signature)│     │ KeystoneForwarder  │
└─────────────┘     └─────────────┘     └──────────────────┘     └────────────────────┘
                                                                          │
                    ┌─────────────┐                                       │
                    │ Report      │◀──────────────────────────────────────┘
                    │ Status      │
                    └─────────────┘
```

## Configuration

Edit `config.staging.json` before running:

```json
{
  "schedule": "*/10 * * * * *",
  "awsApiBase": "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod",
  "receiverAddress": "0x<SettlementConsumerAddress>",
  "chainSelector": 16015286601757825753,
  "chainId": 11155111,
  "gasLimit": 1200000,
  "workflowRunId": "staging"
}
```

## Running

### Network configuration source of truth

For simulation/deploy chain switching steps (including `KEYSTONE_FORWARDER`), use the single checklist in `../README.md`:
- [Changing chains (RPC + chain selector + forwarder)](../README.md#changing-chains-rpc--chain-selector--forwarder)

For this workflow specifically:
- `../project.yaml` selects RPC by `--target`.
- `config.staging.json` / `config.production.json` set `chainSelector` + `chainId`.

### Simulation

```bash
cd cre
cre workflow simulate settlement-workflow --target staging-settings
```

### What Happens

1. Workflow triggers on cron schedule
2. Fetches pending instructions from AWS API
3. For each instruction:
   - Validates chain ID matches config
   - Converts to `CanonicalSettlementInstruction` struct
   - ABI-encodes as `SettlementReport` (instruction + signature)
   - Generates CRE report with DON signatures
   - Submits to SettlementConsumer via KeystoneForwarder
   - Reports outcome (CONFIRMED/FAILED) back to AWS

## Report Encoding

The report is ABI-encoded as:

```solidity
struct SettlementReport {
    CanonicalSettlementInstruction instruction;
    bytes signature;
}
```

This matches `SettlementConsumer.onReport()` which decodes and processes the settlement.

## Status Callbacks

After each submission, the workflow calls `POST /instructions/{id}/status`:

| Status | When |
|--------|------|
| `CONFIRMED` | Transaction succeeded on-chain |
| `FAILED` | Transaction reverted or submission failed |

The callback includes `txHash` and `reason` for debugging.

## Chain Selectors

| Network | Chain ID | Chain Selector |
|---------|----------|----------------|
| Sepolia | 11155111 | 16015286601757825753 |
| Mainnet | 1 | 5009297550715157269 |

Always verify against the official CRE EVM client reference when changing chains:
https://docs.chain.link/cre/reference/sdk/evm-client-go#chain-selectors

## Forwarder

- **Simulation**: Uses MockForwarder (provided by CRE simulator)
- **Production**: Uses KeystoneForwarder (`0xF8344CFd5c43616a4366C34E3EEE75af79a74482` on Sepolia)

Ensure `SettlementConsumer.forwarder` is set correctly for your environment.

