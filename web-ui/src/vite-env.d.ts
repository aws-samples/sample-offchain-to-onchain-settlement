/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_API_KEY: string
  readonly VITE_TOKEN_ADDRESS: string
  readonly VITE_SETTLEMENT_CONSUMER: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
