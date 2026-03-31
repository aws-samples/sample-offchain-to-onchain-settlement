import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Dashboard } from './pages/Dashboard';
import { CreateInstruction } from './pages/CreateInstruction';
import { InstructionsList } from './pages/InstructionsList';
import { InstructionDetail } from './pages/InstructionDetail';
import { Settings } from './pages/Settings';

const queryClient = new QueryClient();

const Nav = () => (
  <nav className="bg-gray-900 text-white">
    <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
      <span className="font-bold text-lg">Digital Asset Operations</span>
      {[
        { to: '/', label: 'Dashboard' },
        { to: '/create', label: 'Create' },
        { to: '/instructions', label: 'Instructions' },
        { to: '/settings', label: 'Settings' },
      ].map(({ to, label }) => (
        <NavLink key={to} to={to} className={({ isActive }) => `hover:text-blue-300 ${isActive ? 'text-blue-400' : ''}`}>{label}</NavLink>
      ))}
    </div>
  </nav>
);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-100">
          <Nav />
          <main className="max-w-6xl mx-auto px-4 py-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/create" element={<CreateInstruction />} />
              <Route path="/instructions" element={<InstructionsList />} />
              <Route path="/instructions/:id" element={<InstructionDetail />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
