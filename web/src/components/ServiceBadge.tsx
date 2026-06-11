export function ServiceBadge({ name, desc, port, up }: {
  name: string; desc: string; port: string; up: boolean;
}) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-lg p-4 flex gap-3 items-start">
      <div className={`w-2.5 h-2.5 rounded-full mt-0.5 flex-shrink-0 ${
        up
          ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.3)]'
          : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.3)]'
      }`} />
      <div>
        <div className="text-sm font-medium text-white">{name}</div>
        <div className="text-xs text-gray-400 mt-0.5">{desc}</div>
        <div className="text-xs text-accent font-mono mt-1">{port} {up ? '● 运行中' : '● 已停止'}</div>
      </div>
    </div>
  );
}
