import { useParams } from 'react-router-dom';
import { useState } from 'react';
import { useAllInstructions, useIsExecuted } from '../hooks';
import { Card, Button, StatusBadge, IntentBadge } from '../components';
import { formatAmount } from '../format';
import type { InstructionResponse } from '../types';

export const InstructionDetail = () => {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, refetch, isFetching } = useAllInstructions();
  const { data: isExecuted, refetch: refetchExecuted } = useIsExecuted(id || '');
  const [showTypedData, setShowTypedData] = useState(false);
  
  const instruction = data?.instructions.find((i: InstructionResponse) => i.instruction.instructionId === id);
  
  const handleRefresh = () => {
    refetch();
    refetchExecuted();
  };
  
  if (isLoading) {
    return <div className="text-gray-500">Loading...</div>;
  }
  
  if (!instruction) {
    return <div className="text-gray-500">Instruction not found.</div>;
  }

  const { instruction: inst, signature, status, typedData, signer, txHash } = instruction;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold text-gray-800">Instruction Detail</h1>
        <StatusBadge status={status} />
        <IntentBadge intent={inst.intent} />
        {isExecuted !== undefined && (
          <span className={`px-2 py-1 rounded text-xs font-medium ${isExecuted ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
            {isExecuted ? 'Executed On-Chain' : 'Not Executed'}
          </span>
        )}
        <Button onClick={handleRefresh} disabled={isFetching}>{isFetching ? 'Refreshing...' : 'Refresh'}</Button>
      </div>

      <Card title="Instruction">
        <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <dt className="text-sm text-gray-500">Instruction ID</dt>
            <dd className="font-mono text-sm break-all">{inst.instructionId}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Message Digest</dt>
            <dd className="font-mono text-sm break-all">{inst.messageDigest}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Asset</dt>
            <dd className="font-mono text-sm">{inst.asset}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Amount</dt>
            <dd className="font-mono">{formatAmount(inst.amount)} ({inst.amount} wei)</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">From Party</dt>
            <dd className="font-mono text-sm">{inst.fromParty}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">To Party</dt>
            <dd className="font-mono text-sm">{inst.toParty}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Value Time</dt>
            <dd>{new Date(inst.valueTime * 1000).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Expiry</dt>
            <dd>{new Date(inst.expiry * 1000).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Chain ID</dt>
            <dd>{inst.chainId}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Created At</dt>
            <dd>{new Date(inst.createdAt * 1000).toLocaleString()}</dd>
          </div>
        </dl>
      </Card>

      <Card title="Signature">
        <dl className="space-y-4">
          <div>
            <dt className="text-sm text-gray-500">Signer (KMS)</dt>
            <dd className="font-mono text-sm">{signer}</dd>
          </div>
          <div>
            <dt className="text-sm text-gray-500">Signature</dt>
            <dd className="font-mono text-xs break-all bg-gray-50 p-2 rounded">{signature}</dd>
          </div>
        </dl>
      </Card>

      {txHash && (
        <Card title="Transaction">
          <a href={`https://sepolia.etherscan.io/tx/${txHash}`} target="_blank" rel="noopener noreferrer" 
            className="text-blue-600 hover:underline font-mono text-sm">
            {txHash}
          </a>
        </Card>
      )}

      <Card title="EIP-712 Typed Data">
        <p className="text-sm text-gray-500 mb-3">
          Structured data signed by AWS KMS to authorize this settlement on-chain.
        </p>
        <button onClick={() => setShowTypedData(!showTypedData)} className="text-blue-600 hover:underline text-sm mb-2">
          {showTypedData ? 'Hide' : 'Show'} Typed Data
        </button>
        {showTypedData && (
          <pre className="bg-gray-50 p-4 rounded text-xs overflow-auto max-h-96">{JSON.stringify(typedData, null, 2)}</pre>
        )}
      </Card>
    </div>
  );
};
