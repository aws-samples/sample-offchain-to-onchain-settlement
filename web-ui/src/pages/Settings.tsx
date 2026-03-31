import { useState } from 'react';
import { useSettings } from '../hooks';
import { Card, Button, Input } from '../components';
import type { Settings as SettingsType } from '../types';

export const Settings = () => {
  const { get, save } = useSettings();
  const [form, setForm] = useState<SettingsType>(get());
  const [saved, setSaved] = useState(false);


  const handleSave = () => {
    save(form);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Settings</h1>

      <Card title="API Configuration">
        <div className="space-y-4">
          <Input label="API Base URL" value={form.apiBaseUrl} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, apiBaseUrl: e.target.value }))}
            placeholder="https://xxx.execute-api.us-east-1.amazonaws.com/prod" />
          <Input label="API Key" type="password" value={form.apiKey} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, apiKey: e.target.value }))}
            placeholder="Your X-API-Key value" />
        </div>
      </Card>

      <Card title="Blockchain Configuration">
        <div className="space-y-4">
          <Input label="RPC URL (optional)" value={form.rpcUrl} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, rpcUrl: e.target.value }))}
            placeholder="https://sepolia.infura.io/v3/..." />
          <Input label="Token Contract Address" value={form.tokenAddress} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, tokenAddress: e.target.value }))}
            placeholder="0x..." pattern="^0x[a-fA-F0-9]{40}$" />
          <Input label="SettlementConsumer Address" value={form.settlementConsumerAddress} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, settlementConsumerAddress: e.target.value }))}
            placeholder="0x..." pattern="^0x[a-fA-F0-9]{40}$" />
        </div>
      </Card>

      <div className="flex items-center gap-4">
        <Button onClick={handleSave}>Save Settings</Button>
        {saved && <span className="text-green-600">Settings saved!</span>}
      </div>
    </div>
  );
};
