import type { Status, Intent } from './types';

export const StatusBadge = ({ status }: { status: Status }) => {
  const colors: Record<Status, string> = {
    PENDING: 'bg-yellow-100 text-yellow-800',
    SUBMITTED: 'bg-blue-100 text-blue-800',
    CONFIRMED: 'bg-green-100 text-green-800',
    FAILED: 'bg-red-100 text-red-800',
  };
  return <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status]}`}>{status}</span>;
};

export const IntentBadge = ({ intent }: { intent: Intent }) => {
  const colors: Record<Intent, string> = {
    MINT_ONLY: 'bg-emerald-100 text-emerald-800',
    BURN_AND_MINT: 'bg-purple-100 text-purple-800',
    BURN_ONLY: 'bg-orange-100 text-orange-800',
  };
  return <span className={`px-2 py-1 rounded text-xs font-medium ${colors[intent]}`}>{intent}</span>;
};


export const Card = ({ title, children, className = '' }: { title?: string; children: React.ReactNode; className?: string }) => (
  <div className={`bg-white rounded-lg shadow p-4 ${className}`}>
    {title && <h3 className="font-semibold text-gray-700 mb-3">{title}</h3>}
    {children}
  </div>
);

export const Button = ({ children, onClick, disabled, variant = 'primary', className = '' }: { 
  children: React.ReactNode; onClick?: () => void; disabled?: boolean; variant?: 'primary' | 'secondary'; className?: string 
}) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`px-4 py-2 rounded font-medium transition-colors disabled:opacity-50 ${className} ${
      variant === 'primary' ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
    }`}
  >
    {children}
  </button>
);

export const Input = ({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
    <input {...props} className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
  </div>
);

export const Select = ({ label, options, ...props }: { label: string; options: { value: string; label: string }[] } & React.SelectHTMLAttributes<HTMLSelectElement>) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
    <select {...props} className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500">
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  </div>
);

export const Textarea = ({ label, ...props }: { label: string } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
    <textarea {...props} className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500" />
  </div>
);
