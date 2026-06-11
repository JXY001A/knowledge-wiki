import { Link, useLocation } from 'react-router-dom';

const nav = [
  { to: '/', label: '首页' },
  { to: '/chat', label: '对话' },
  { to: '/admin', label: '管理' },
  { to: '/status', label: '状态' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 导航栏 */}
      <header className="sticky top-0 z-10 h-12 flex items-center justify-between px-6 bg-white border-b border-gray-200">
        <Link to="/" className="flex items-center gap-2 text-sm font-semibold text-gray-900 no-underline">
          <span className="w-2 h-2 rounded-full bg-accent" />
          mindbase
        </Link>

        <nav className="flex items-center gap-1">
          {nav.map((n) => {
            const active = pathname === n.to;
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`px-3 py-1.5 text-[13px] rounded-md transition-colors duration-150 ${
                  active
                    ? 'text-accent font-medium bg-accent-light'
                    : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <main>{children}</main>
    </div>
  );
}
