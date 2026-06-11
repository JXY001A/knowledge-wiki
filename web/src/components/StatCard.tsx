import { cn } from '@/lib/utils';

export function StatCard({ value, label, sub, onClick }: {
  value: string; label: string; sub?: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-card border border-border rounded-lg p-5 text-center',
        onClick && 'cursor-pointer hover:border-primary/30 hover:shadow-sm transition-all duration-150'
      )}
    >
      <div className="text-2xl font-bold text-primary">{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
      {sub && <div className="text-[10px] text-muted-foreground/70 mt-0.5">{sub}</div>}
    </div>
  );
}
