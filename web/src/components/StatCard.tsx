export function StatCard({ value, label, sub, onClick }: {
  value: string; label: string; sub?: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-border rounded-md p-5 text-center ${
        onClick ? 'cursor-pointer hover:border-accent/30 hover:shadow-card transition-all duration-150' : ''
      }`}
    >
      <div className="text-2xl font-serif font-medium text-ink tracking-tight">{value}</div>
      <div className="text-xs text-muted mt-1">{label}</div>
      {sub && <div className="text-[10px] text-faint mt-0.5">{sub}</div>}
    </div>
  );
}
