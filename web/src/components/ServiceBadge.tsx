export function ServiceBadge({ name, desc, port, up }: {
  name: string; desc: string; port: string; up: boolean;
}) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex gap-3 items-start">
      <div className={`w-3 h-3 rounded-full mt-1 flex-shrink-0 ${up ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,.4)]' : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,.4)]'}`} />
      <div>
        <div className="text-sm font-semibold text-white">{name}</div>
        <div className="text-xs text-slate-400">{desc}</div>
        <div className="text-xs text-blue-400 font-mono mt-0.5">{port} {up ? '● 运行中' : '● 已停止'}</div>
      </div>
    </div>
  );
}
