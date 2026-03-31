import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import { chain } from './chain';
import type { CreateInstructionRequest, Settings } from './types';

export const useSettings = () => {
  const defaults: Settings = {
    apiKey: import.meta.env.VITE_API_KEY || '',
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '',
    rpcUrl: '',
    tokenAddress: import.meta.env.VITE_TOKEN_ADDRESS || '',
    settlementConsumerAddress: import.meta.env.VITE_SETTLEMENT_CONSUMER || '',
  };
  
  const get = (): Settings => {
    const stored = localStorage.getItem('settlement-settings');
    if (!stored) {
      // Auto-save defaults on first load
      localStorage.setItem('settlement-settings', JSON.stringify(defaults));
      return defaults;
    }
    const parsed = JSON.parse(stored);
    // Merge: localStorage overrides defaults, but use defaults for empty values
    const merged = {
      apiKey: parsed.apiKey || defaults.apiKey,
      apiBaseUrl: parsed.apiBaseUrl || defaults.apiBaseUrl,
      rpcUrl: parsed.rpcUrl || defaults.rpcUrl,
      tokenAddress: parsed.tokenAddress || defaults.tokenAddress,
      settlementConsumerAddress: parsed.settlementConsumerAddress || defaults.settlementConsumerAddress,
    };
    // Auto-save merged settings if defaults filled in gaps
    localStorage.setItem('settlement-settings', JSON.stringify(merged));
    return merged;
  };
  const save = (settings: Settings) => localStorage.setItem('settlement-settings', JSON.stringify(settings));
  return { get, save, defaults };
};

export const usePendingInstructions = () => 
  useQuery({ 
    queryKey: ['pending'], 
    queryFn: () => api.getPending(), 
    refetchInterval: 30000 
  });

export const useAllInstructions = () =>
  useQuery({
    queryKey: ['instructions'],
    queryFn: () => api.getAll(),
    refetchInterval: 30000,
  });

export const useCreateInstruction = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: CreateInstructionRequest) => api.createInstruction(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pending'] }),
  });
};

export const useTokenInfo = () => {
  const { get } = useSettings();
  const { tokenAddress } = get();
  return useQuery({
    queryKey: ['token', tokenAddress],
    queryFn: () => chain.getTokenInfo(tokenAddress as `0x${string}`),
    enabled: !!tokenAddress && tokenAddress.length === 42,
  });
};

export const useIsExecuted = (instructionId: string) => {
  const { get } = useSettings();
  const { settlementConsumerAddress } = get();
  return useQuery({
    queryKey: ['executed', instructionId],
    queryFn: () => chain.isExecuted(settlementConsumerAddress as `0x${string}`, instructionId as `0x${string}`),
    enabled: !!settlementConsumerAddress && !!instructionId,
  });
};
