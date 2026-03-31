import { usePendingInstructions, useTokenInfo, useAllInstructions } from '../hooks';
import { Card, StatusBadge, IntentBadge, Button } from '../components';
import { truncateAddress, formatAmount } from '../format';
import { Link } from 'react-router-dom';
import { useState } from 'react';

export const Dashboard = () => {
  const { data: pendingData, isLoading } = usePendingInstructions();
  const { data: allData } = useAllInstructions();
  const { data: token } = useTokenInfo();
  const [showCRECommand, setShowCRECommand] = useState(false);
  
  const pending = pendingData?.pending || [];
  const all = allData?.instructions || [];
  const today = new Date().setHours(0, 0, 0, 0) / 1000;
  const confirmedToday = all.filter(i => i.status === 'CONFIRMED' && i.instruction.createdAt >= today).length;
  const failedToday = all.filter(i => i.status === 'FAILED' && i.instruction.createdAt >= today).length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-3xl font-bold text-yellow-600">{pending.length}</div>
          <div className="text-gray-500">Pending</div>
        </Card>
        <Card>
          <div className="text-3xl font-bold text-green-600">{confirmedToday}</div>
          <div className="text-gray-500">Confirmed Today</div>
        </Card>
        <Card>
          <div className="text-3xl font-bold text-red-600">{failedToday}</div>
          <div className="text-gray-500">Failed Today</div>
        </Card>
        {token && (
          <Card>
            <div className="text-3xl font-bold text-blue-600">{parseFloat(token.totalSupply).toLocaleString()}</div>
            <div className="text-gray-500">{token.symbol} Supply</div>
          </Card>
        )}
      </div>

      {pending.length > 0 && (
        <Card title="CRE Simulation">
          <p className="text-gray-600 mb-3">Execute pending instructions via Chainlink CRE workflow.</p>
          <Button onClick={() => setShowCRECommand(!showCRECommand)}>
            {showCRECommand ? 'Hide Command' : 'Show CRE Command'}
          </Button>
          {showCRECommand && (
            <pre className="mt-3 p-3 bg-gray-900 text-green-400 rounded text-sm overflow-x-auto">
cd cre && cre workflow simulate settlement-workflow --target staging-settings --broadcast
            </pre>
          )}
        </Card>
      )}

      <Card title="Recent Activity">
        {isLoading ? (
          <div className="text-gray-500">Loading...</div>
        ) : pending.length === 0 ? (
          <div className="text-gray-500">No instructions yet. <Link to="/create" className="text-blue-600 hover:underline">Create one</Link></div>
        ) : (
          <div className="space-y-2">
            {pending.slice(0, 10).map(item => (
              <Link key={item.instruction.instructionId} to={`/instructions/${item.instruction.instructionId}`} 
                className="flex items-center justify-between p-3 bg-gray-50 rounded hover:bg-gray-100">
                <div className="flex items-center gap-3">
                  <IntentBadge intent={item.instruction.intent} />
                  <span className="font-mono text-sm">{truncateAddress(item.instruction.instructionId)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-gray-600">{formatAmount(item.instruction.amount)} tokens</span>
                  <StatusBadge status={item.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
