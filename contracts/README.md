# Smart Contracts

Solidity contracts for on-chain settlement verification and execution.

## Contracts

### SettlementConsumer.sol

Main settlement contract that receives reports from Chainlink CRE and executes token operations.

**Key Functions:**
- `onReport(bytes metadata, bytes report)` - Called by KeystoneForwarder with DON-signed report
- `setForwarder(address)` - Update forwarder address (admin only)
- `setAdmin(address)` - Transfer admin role
- `_settle(CSI csi, bytes signature)` - Internal settlement logic (called by `onReport`)

**Verification Checks:**
1. `chainId == block.chainid` - Correct chain
2. `block.timestamp <= expiry` - Not expired
3. `expiry > createdAt` - Valid time range
4. `asset != address(0)` - Valid asset
5. `!executed[instructionId]` - Not already executed
6. `intent <= 2` - Valid intent (MINT_ONLY=0, BURN_AND_MINT=1, BURN_ONLY=2)
7. `instructionId == _deriveInstructionId(csi)` - ID matches content
8. `keyRegistry.isSigner(recoveredSigner)` - Authorized signer

### KeyRegistry.sol

Allowlist of authorized signers (KMS-derived Ethereum addresses).

**Key Functions:**
- `addSigner(address)` - Add authorized signer (admin only)
- `removeSigner(address)` - Remove signer (admin only)
- `isSigner(address)` - Check if address is authorized
- `isAuthorized(address)` - Alias for isSigner

### Token.sol

Simple ERC20-like token with controlled mint/burn.

**Key Functions:**
- `mint(address to, uint256 amount)` - Mint tokens (minter only)
- `burn(address from, uint256 amount)` - Burn tokens (minter only)
- `setMinter(address)` - Transfer minter role

## Deployment Order

1. **KeyRegistry** - Deploy with admin address and initial KMS signer
2. **SettlementConsumer** - Deploy with KeyRegistry and KeystoneForwarder addresses
3. **Token** - Deploy with SettlementConsumer as minter

## Build & Deploy

```bash
# Build
forge build

# Deploy (example for Sepolia)
export RPC_URL="https://sepolia.infura.io/v3/<key>"
export PRIVATE_KEY="0x..."
export KMS_SIGNER="0x..."  # from scripts/kms_signer_address.py
export ADMIN="0x..."       # your admin address
export FORWARDER="0xF8344CFd5c43616a4366C34E3EEE75af79a74482"

# 1. KeyRegistry
forge create contracts/KeyRegistry.sol:KeyRegistry \
  --constructor-args $ADMIN $KMS_SIGNER \
  --private-key $PRIVATE_KEY --rpc-url $RPC_URL

# 2. SettlementConsumer
forge create contracts/SettlementConsumer.sol:SettlementConsumer \
  --constructor-args $KEY_REGISTRY $FORWARDER \
  --private-key $PRIVATE_KEY --rpc-url $RPC_URL

# 3. Token
forge create contracts/Token.sol:Token \
  --constructor-args "TestToken" "TKN" $SETTLEMENT_CONSUMER \
  --private-key $PRIVATE_KEY --rpc-url $RPC_URL
```

## Verification Commands

```bash
# Check if signer is authorized
cast call $KEY_REGISTRY "isSigner(address)(bool)" $KMS_SIGNER --rpc-url $RPC_URL

# Check if instruction was executed
cast call $SETTLEMENT_CONSUMER "executed(bytes32)(bool)" $INSTRUCTION_ID --rpc-url $RPC_URL

# Check token balance
cast call $TOKEN "balanceOf(address)(uint256)" $ADDRESS --rpc-url $RPC_URL

# Check total supply
cast call $TOKEN "totalSupply()(uint256)" --rpc-url $RPC_URL
```

## Events

### SettlementConsumer
- `SettlementExecuted(instructionId, messageDigest, asset, fromParty, toParty, amount, intent)`
- `ForwarderUpdated(oldForwarder, newForwarder)`
- `AdminUpdated(oldAdmin, newAdmin)`

### KeyRegistry
- `SignerAdded(signer)`
- `SignerRemoved(signer)`
- `AdminUpdated(oldAdmin, newAdmin)`

### Token
- `Transfer(from, to, value)`
- `MinterUpdated(oldMinter, newMinter)`

## Forwarder Addresses

| Network | KeystoneForwarder |
|---------|-------------------|
| Sepolia | `0xF8344CFd5c43616a4366C34E3EEE75af79a74482` |

## Error Codes

| Error | Meaning |
|-------|---------|
| `CHAIN_ID` | Wrong chain |
| `EXPIRED` | CSI expired |
| `EXPIRY_ORDER` | expiry <= createdAt |
| `ASSET_ZERO` | Zero address asset |
| `ALREADY_EXECUTED` | instructionId already processed |
| `INTENT_INVALID` | Unknown intent value |
| `INSTRUCTION_ID` | Derived ID doesn't match |
| `SIGNER_UNAUTHORIZED` | Signer not in KeyRegistry |
| `FORWARDER_ONLY` | Called by non-forwarder |
| `SIG_LENGTH` | Signature not 65 bytes |
| `SIG_V` | Invalid v value |
| `SIG_S` | s value too high (malleable) |
| `SIG_RECOVER` | ecrecover returned zero |
