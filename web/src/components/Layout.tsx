import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';

const nav = [
  { to: '/', label: '首页' },
  { to: '/chat', label: '对话' },
  { to: '/admin', label: '管理' },
  { to: '/status', label: '状态' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 h-12 flex items-center justify-between px-6 bg-background border-b border-border">
        <Link to="/" className="flex items-center gap-2 text-sm font-semibold text-foreground no-underline">
          <span className="w-2 h-2 rounded-full bg-primary" />
          mindbase
        </Link>

        <nav className="flex items-center gap-1">
          {nav.map((n) => {
            const active = pathname === n.to;
            return (
              <Link
                key={n.to}
                to={n.to}
                className={cn(
                  'px-3 py-1.5 text-[13px] rounded-md transition-colors duration-150',
                  active
                    ? 'text-primary font-medium bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
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
