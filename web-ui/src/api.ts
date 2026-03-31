import type { Settings, CreateInstructionRequest, InstructionResponse, UpdateStatusRequest } from './types';

const getSettings = (): Settings => {
  const stored = localStorage.getItem('settlement-settings');
  return stored ? JSON.parse(stored) : { apiKey: '', apiBaseUrl: '', rpcUrl: '', tokenAddress: '', settlementConsumerAddress: '' };
};

const apiFetch = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
  const { apiKey, apiBaseUrl } = getSettings();
  if (!apiBaseUrl || !apiKey) throw new Error('API settings not configured');
  
  const res = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey, ...options.headers },
  });
  
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Request failed: ${res.status}`);
  return data;
};

export const api = {
  createInstruction: (req: CreateInstructionRequest) => 
    apiFetch<InstructionResponse>('/messages', { method: 'POST', body: JSON.stringify(req) }),
  
  getPending: () => 
    apiFetch<{ pending: InstructionResponse[] }>('/instructions/pending'),
  
  getAll: () =>
    apiFetch<{ instructions: InstructionResponse[] }>('/instructions'),
  
  updateStatus: (instructionId: string, req: UpdateStatusRequest) =>
    apiFetch<InstructionResponse>(`/instructions/${instructionId}/status`, { method: 'POST', body: JSON.stringify(req) }),
};
