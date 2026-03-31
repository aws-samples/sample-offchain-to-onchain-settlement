# Web UI Dashboard

React + TypeScript + Vite dashboard for creating and tracking settlement instructions.

## Features

- Dashboard with instruction counts by status
- Create settlement instructions (`MINT_ONLY`, `BURN_AND_MINT`, `BURN_ONLY`)
- Instruction detail view with latest transaction status
- API integration with the AWS ingestion service

## Prerequisites

- Node.js 20+
- npm
- AWS credentials configured (only needed when auto-fetching config)
- Root `.env` populated with deployed contract addresses (for `fetch-config.sh`)

## Configuration

The app reads these Vite variables from `web-ui/.env.local`:

```bash
VITE_API_BASE_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com/prod
VITE_API_KEY=<api-key-value>
VITE_TOKEN_ADDRESS=0x...
VITE_SETTLEMENT_CONSUMER=0x...
```

### Option 1: Auto-generate config (recommended)

```bash
cd web-ui
./scripts/fetch-config.sh
```

This script reads AWS CloudFormation outputs and `../.env`, then writes `.env.local`.

### Option 2: Manual config

Create `web-ui/.env.local` yourself with the variables above.

## Run locally

```bash
cd web-ui
npm install
npm run dev
```

Open `http://localhost:5173`.

## Build

```bash
cd web-ui
npm run build
npm run preview
```

## Lint

```bash
cd web-ui
npm run lint
```
