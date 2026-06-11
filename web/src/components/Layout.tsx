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
    <div className="min-h-screen bg-paper">
      {/* 导航栏 — 半透明 glass */}
      <header className="sticky top-0 z-10 h-12 flex items-center justify-between px-6 bg-paper/80 backdrop-blur-md border-b border-border">
        {/* 品牌 */}
        <Link to="/" className="flex items-center gap-2.5 text-sm font-medium text-ink no-underline">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.4)]" />
          <span className="font-serif text-base tracking-tight">mindbase</span>
        </Link>

        {/* 导航链接 */}
        <nav className="flex items-center gap-1">
          {nav.map((n) => {
            const active = pathname === n.to;
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`relative px-3 py-1.5 text-[13px] rounded-md transition-colors duration-150 ${
                  active
                    ? 'text-ink font-medium'
                    : 'text-muted hover:text-ink'
                }`}
              >
                {n.label}
                {/* 活跃态下划线 */}
                {active && (
                  <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-accent rounded-full" />
                )}
              </Link>
            );
          })}
        </nav>
      </header>

      <main>{children}</main>
    </div>
  );
}
