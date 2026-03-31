import { createPublicClient, http, formatUnits } from 'viem';
import { sepolia } from 'viem/chains';
import type { Settings } from './types';

const getSettings = (): Settings => {
  const stored = localStorage.getItem('settlement-settings');
  return stored ? JSON.parse(stored) : { apiKey: '', apiBaseUrl: '', rpcUrl: '', tokenAddress: '', settlementConsumerAddress: '' };
};

const getClient = () => {
  const { rpcUrl } = getSettings();
  return createPublicClient({ chain: sepolia, transport: http(rpcUrl || undefined) });
};

const erc20Abi = [
  { name: 'balanceOf', type: 'function', stateMutability: 'view', inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }] },
  { name: 'totalSupply', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  { name: 'name', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'string' }] },
  { name: 'symbol', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'string' }] },
  { name: 'decimals', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint8' }] },
] as const;

const settlementAbi = [
  { name: 'executed', type: 'function', stateMutability: 'view', inputs: [{ name: 'instructionId', type: 'bytes32' }], outputs: [{ type: 'bool' }] },
] as const;

export const chain = {
  async getTokenInfo(address: `0x${string}`) {
    const client = getClient();
    const [name, symbol, totalSupply, decimals] = await Promise.all([
      client.readContract({ address, abi: erc20Abi, functionName: 'name' }),
      client.readContract({ address, abi: erc20Abi, functionName: 'symbol' }),
      client.readContract({ address, abi: erc20Abi, functionName: 'totalSupply' }),
      client.readContract({ address, abi: erc20Abi, functionName: 'decimals' }),
    ]);
    return { name, symbol, totalSupply: formatUnits(totalSupply, decimals), decimals };
  },

  async isExecuted(consumerAddress: `0x${string}`, instructionId: `0x${string}`) {
    return getClient().readContract({ address: consumerAddress, abi: settlementAbi, functionName: 'executed', args: [instructionId] });
  },
};
