import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateInstruction, useSettings } from '../hooks';
import { Card, Button, Input, Select, Textarea, StatusBadge, IntentBadge } from '../components';
import { ZERO_ADDRESS } from '../types';
import type { Intent, InstructionResponse } from '../types';
import { parseUnits } from 'viem';

const INTENTS: { value: Intent; label: string; desc: string; from: string; to: string }[] = [
  { value: 'MINT_ONLY', label: 'Mint Only', desc: 'Issuance/deposit - new tokens enter system', from: ZERO_ADDRESS, to: '0x1234567890123456789012345678901234567890' },
  { value: 'BURN_AND_MINT', label: 'Burn and Mint', desc: 'Transfer within system', from: '0x1234567890123456789012345678901234567890', to: '0xabcdefabcdefabcdefabcdefabcdefabcdefabcd' },
  { value: 'BURN_ONLY', label: 'Burn Only', desc: 'Redemption/withdrawal - tokens exit system', from: '0x1234567890123456789012345678901234567890', to: ZERO_ADDRESS },
];

const generateRawMessage = (intent: Intent, from: string, to: string, amount = '0') => {
  const msgId = `MSG-${Date.now()}`;
  const now = new Date().toISOString();
  const msgType = intent === 'MINT_ONLY' ? 'pacs.009' : intent === 'BURN_ONLY' ? 'pacs.009' : 'pacs.008';
  return `<?xml version="1.0"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:${msgType}">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>${msgId}</MsgId>
      <CreDtTm>${now}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId><InstrId>${msgId}</InstrId></PmtId>
      <Amt><InstdAmt Ccy="TOKEN">${amount}</InstdAmt></Amt>
      <Dbtr><Id>${from}</Id></Dbtr>
      <Cdtr><Id>${to}</Id></Cdtr>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>`;
};

const DEFAULT_INITIAL_RAW_MESSAGE = generateRawMessage(
  'MINT_ONLY',
  ZERO_ADDRESS,
  '0x1234567890123456789012345678901234567890',
);

export const CreateInstruction = () => {
  const navigate = useNavigate();
  const { get } = useSettings();
  const settings = get();
  const mutation = useCreateInstruction();

  const [form, setForm] = useState({
    rawMessage: DEFAULT_INITIAL_RAW_MESSAGE,
    asset: settings.tokenAddress || '',
    amount: '',
    amountUnit: 'eth',
    fromParty: ZERO_ADDRESS,
    toParty: '0x1234567890123456789012345678901234567890',
    intent: 'MINT_ONLY' as Intent,
    chainId: '11155111',
    reference: '',
  });
  const [result, setResult] = useState<InstructionResponse | null>(null);

  const handleIntentChange = (intent: Intent) => {
    const config = INTENTS.find(i => i.value === intent)!;
    setForm(f => ({ ...f, intent, fromParty: config.from, toParty: config.to, rawMessage: generateRawMessage(intent, config.from, config.to, f.amount || '0') }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amount = form.amountUnit === 'eth' ? parseUnits(form.amount, 18).toString() : form.amount;
    const res = await mutation.mutateAsync({
      rawMessage: form.rawMessage,
      asset: form.asset,
      amount,
      fromParty: form.fromParty,
      toParty: form.toParty,
      valueTime: Math.floor(Date.now() / 1000),
      intent: form.intent,
      chainId: parseInt(form.chainId),
      reference: form.reference || undefined,
    });
    setResult(res);
  };

  if (result) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-800">Instruction Created</h1>
        <Card>
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <StatusBadge status={result.status} />
              <IntentBadge intent={result.instruction.intent} />
            </div>
            <div>
              <div className="text-sm text-gray-500">Instruction ID</div>
              <div className="font-mono text-sm break-all">{result.instruction.instructionId}</div>
            </div>
            <div className="flex gap-4">
              <Button onClick={() => navigate(`/instructions/${result.instruction.instructionId}`)}>View Details</Button>
              <Button variant="secondary" onClick={() => { setResult(null); setForm(f => ({ ...f, rawMessage: '', reference: '' })); }}>Create Another</Button>
            </div>
          </div>
        </Card>
        <Card title="Execute via CRE">
          <p className="text-sm text-gray-500 mb-2">Run this command to settle the instruction on-chain:</p>
          <pre className="p-3 bg-gray-900 text-green-400 rounded text-sm overflow-x-auto">
cd cre{'\n'}cre workflow simulate settlement-workflow --target staging-settings --broadcast
          </pre>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Create Settlement Instruction</h1>
      
      {(!settings.apiKey || !settings.apiBaseUrl) && (
        <div className="bg-yellow-50 border border-yellow-200 p-4 rounded">
          Please configure API settings first. <a href="/settings" className="text-blue-600 hover:underline">Go to Settings</a>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card title="Intent">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {INTENTS.map(i => (
              <button key={i.value} type="button" onClick={() => handleIntentChange(i.value)}
                className={`p-4 rounded border-2 text-left transition-colors ${form.intent === i.value ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <div className="font-semibold">{i.label}</div>
                <div className="text-sm text-gray-500">{i.desc}</div>
              </button>
            ))}
          </div>
        </Card>

        <Card title="Details">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Asset (Token Address)" value={form.asset} onChange={e => setForm(f => ({ ...f, asset: e.target.value }))} 
              placeholder="0x..." pattern="^0x[a-fA-F0-9]{40}$" required />
            <div className="flex gap-2">
              <div className="flex-1">
                <Input label="Amount" type="number" step="any" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} required />
              </div>
              <div className="w-24">
                <Select label="Unit" value={form.amountUnit} onChange={e => setForm(f => ({ ...f, amountUnit: e.target.value }))}
                  options={[{ value: 'eth', label: 'Tokens' }, { value: 'wei', label: 'Base Units' }]} />
              </div>
            </div>
            <Input label="From Party" value={form.fromParty} onChange={e => setForm(f => ({ ...f, fromParty: e.target.value }))}
              placeholder="0x..." pattern="^0x[a-fA-F0-9]{40}$" required disabled={form.intent === 'MINT_ONLY'} />
            <Input label="To Party" value={form.toParty} onChange={e => setForm(f => ({ ...f, toParty: e.target.value }))}
              placeholder="0x..." pattern="^0x[a-fA-F0-9]{40}$" required disabled={form.intent === 'BURN_ONLY'} />
            <Input label="Chain ID" value={form.chainId} onChange={e => setForm(f => ({ ...f, chainId: e.target.value }))} required />
            <Input label="Reference (optional)" value={form.reference} onChange={e => setForm(f => ({ ...f, reference: e.target.value }))} />
          </div>
        </Card>

        <Card title="Raw Message">
          <p className="text-sm text-gray-500 mb-3">
            Sample ISO 20022 format shown below. Any financial messaging format can be used.
          </p>
          <Textarea label="Settlement Message" value={form.rawMessage} onChange={e => setForm(f => ({ ...f, rawMessage: e.target.value }))}
            rows={12} placeholder="Message identifier for this settlement..." required />
        </Card>

        <Button disabled={mutation.isPending || !settings.apiKey}>
          {mutation.isPending ? 'Creating...' : 'Create Instruction'}
        </Button>
        
        {mutation.isError && <div className="text-red-600">Error: {(mutation.error as Error).message}</div>}
      </form>
    </div>
  );
};
