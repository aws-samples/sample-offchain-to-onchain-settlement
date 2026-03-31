export type Intent = 'MINT_ONLY' | 'BURN_AND_MINT' | 'BURN_ONLY';
export type Status = 'PENDING' | 'SUBMITTED' | 'CONFIRMED' | 'FAILED';

export interface Instruction {
  instructionId: string;
  messageDigest: string;
  asset: string;
  amount: string;
  fromParty: string;
  toParty: string;
  valueTime: number;
  createdAt: number;
  expiry: number;
  intent: Intent;
  chainId: number;
  nonce: string;
}

export interface InstructionResponse {
  instruction: Instruction;
  signature: string;
  status: Status;
  typedData: object;
  messageDigest: string;
  signer: string;
  txHash?: string;
}

export interface CreateInstructionRequest {
  rawMessage: string;
  asset: string;
  amount: string;
  fromParty: string;
  toParty: string;
  valueTime: number;
  intent: Intent;
  chainId: number;
  reference?: string;
  expirySeconds?: number;
}

export interface UpdateStatusRequest {
  status: Status;
  txHash?: string;
  workflowRunId?: string;
  chainId?: number;
  reason?: string;
}

export interface Settings {
  apiKey: string;
  apiBaseUrl: string;
  rpcUrl: string;
  tokenAddress: string;
  settlementConsumerAddress: string;
}

export const ZERO_ADDRESS = '0x0000000000000000000000000000000000000000';
