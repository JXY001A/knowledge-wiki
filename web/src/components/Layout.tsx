import { Link, useLocation } from 'react-router-dom';

const nav = [
  { to: '/', label: '首页' },
  { to: '/chat', label: '对话' },
  { to: '/admin', label: '管理后台' },
  { to: '/status', label: '服务器' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-10 bg-white border-b border-slate-200 h-14 flex items-center justify-between px-6">
        <Link to="/" className="text-base font-semibold text-slate-800 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500" />AI 自进化知识系统
        </Link>
        <nav className="flex gap-4 text-sm">
          {nav.map(n => (
            <Link key={n.to} to={n.to}
              className={`${pathname === n.to ? 'text-blue-600 font-medium' : 'text-slate-500 hover:text-slate-700'}`}>
              {n.label}
            </Link>
          ))}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
