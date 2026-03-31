import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAllInstructions } from '../hooks';
import { Card, Button, StatusBadge, IntentBadge } from '../components';
import { truncateAddress, formatAmount } from '../format';
import type { Status, InstructionResponse } from '../types';

export const InstructionsList = () => {
  const { data, isLoading, refetch, isFetching } = useAllInstructions();
  const [filter, setFilter] = useState<Status | 'ALL'>('ALL');
  
  const allInstructions = (data?.instructions || []).sort((a, b) => b.instruction.createdAt - a.instruction.createdAt);
  const filtered = filter === 'ALL' ? allInstructions : allInstructions.filter((i: InstructionResponse) => i.status === filter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Instructions</h1>
        <Button onClick={() => refetch()} disabled={isFetching}>{isFetching ? 'Refreshing...' : 'Refresh'}</Button>
      </div>

      <div className="flex gap-2">
        {(['ALL', 'PENDING', 'SUBMITTED', 'CONFIRMED', 'FAILED'] as const).map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded text-sm ${filter === s ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}>
            {s}
          </button>
        ))}
      </div>

      <Card>
        {isLoading ? (
          <div className="text-gray-500">Loading...</div>
        ) : filtered.length === 0 ? (
          <div className="text-gray-500">No instructions found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-gray-500 border-b">
                  <th className="pb-2">ID</th>
                  <th className="pb-2">Intent</th>
                  <th className="pb-2">Amount</th>
                  <th className="pb-2">From → To</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item: InstructionResponse) => (
                  <tr key={item.instruction.instructionId} className="border-b hover:bg-gray-50">
                    <td className="py-3">
                      <Link to={`/instructions/${item.instruction.instructionId}`} className="font-mono text-sm text-blue-600 hover:underline">
                        {truncateAddress(item.instruction.instructionId)}
                      </Link>
                    </td>
                    <td><IntentBadge intent={item.instruction.intent} /></td>
                    <td className="font-mono text-sm">{formatAmount(item.instruction.amount)}</td>
                    <td className="font-mono text-xs text-gray-600">
                      {truncateAddress(item.instruction.fromParty)} → {truncateAddress(item.instruction.toParty)}
                    </td>
                    <td><StatusBadge status={item.status} /></td>
                    <td className="text-sm text-gray-500">{new Date(item.instruction.createdAt * 1000).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
