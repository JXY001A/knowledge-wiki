import { cn } from '@/lib/utils';

export function StatCard({ value, label, sub, onClick }: {
  value: string; label: string; sub?: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-card border border-border rounded-xl p-5',
        onClick && 'cursor-pointer hover:border-primary/30 hover:shadow-sm transition-all duration-150'
      )}
    >
      <div className="text-3xl font-bold text-foreground tracking-tight">{value}</div>
      <div className="text-sm text-muted-foreground mt-1">{label}</div>
      {sub && <div className="text-xs text-muted-foreground/70 mt-1">{sub}</div>}
    </div>
  );
}
