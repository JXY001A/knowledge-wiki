export function ProgressBar({ pct, color = 'bg-accent' }: { pct: number; color?: string }) {
  return (
    <div className="h-1 bg-dark-border rounded-full overflow-hidden">
      <div
        className={`h-full ${color} rounded-full transition-all duration-500`}
        style={{ width: `${Math.min(100, pct)}%` }}
      />
    </div>
  );
}
