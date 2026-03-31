#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Install forge-std if missing
if [ ! -f "lib/forge-std/src/Script.sol" ]; then
  echo "Installing forge-std..."
  forge install foundry-rs/forge-std
fi

if [ ! -f .env ]; then
  cp .env-sample .env
  echo "Created .env from .env-sample - please set PRIVATE_KEY and re-run"
  exit 1
fi

set -a
source .env
set +a

if [ -z "$PRIVATE_KEY" ]; then
  echo "PRIVATE_KEY not set in .env"
  exit 1
fi

CHAIN_ID=${CHAIN_ID:-11155111}
RPC_URL=${RPC_URL:-https://ethereum-sepolia-rpc.publicnode.com}

echo "Deploying contracts using CHAIN_ID=$CHAIN_ID"

forge script script/Deploy.s.sol:Deploy \
  --chain-id "$CHAIN_ID" \
  --rpc-url "$RPC_URL" \
  --broadcast \
  --private-key "$PRIVATE_KEY" \
  -vvv
