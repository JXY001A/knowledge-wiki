export function StatCard({ value, label, sub, onClick }: {
  value: string; label: string; sub?: string; onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-slate-200 rounded-xl p-5 text-center ${onClick ? 'cursor-pointer hover:border-blue-400 hover:shadow-sm hover:-translate-y-0.5 transition-all' : ''}`}
    >
      <div className="text-2xl font-bold text-blue-600">{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}
