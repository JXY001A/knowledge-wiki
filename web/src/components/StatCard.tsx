export function StatCard({ value, label, sub, onClick }: {
  value: string; label: string; sub?: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-gray-100 rounded-lg p-5 text-center ${
        onClick ? 'cursor-pointer hover:border-accent/30 hover:shadow-card transition-all duration-150' : ''
      }`}
    >
      <div className="text-2xl font-bold text-accent">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
      {sub && <div className="text-[10px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}
