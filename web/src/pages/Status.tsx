import { useState, useEffect, useRef } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { ServiceBadge } from '../components/ServiceBadge';
import { ProgressBar } from '../components/ProgressBar';
import type { DashboardData } from '../types';

const serviceDefs: { key: string; name: string; desc: string; port: string }[] = [
  { key: 'wiki-mcp', name: 'wiki-mcp', desc: 'MCP Server — AI 工具调用入口', port: ':9300' },
  { key: 'wecom-webhook', name: 'wecom-webhook', desc: '企业微信 Bot + Web 服务', port: ':9400' },
  { key: 'wiki-scheduler', name: 'wiki-scheduler', desc: '定时调度 — 提醒/早报/备份', port: '内部' },
  { key: 'ollama', name: 'Ollama', desc: '本地 LLM — qwen2.5:3b + qwen3-vl:8b', port: ':11434' },
  { key: 'frpc', name: 'FRP 隧道', desc: '内网穿透 — 外网访问入口', port: ':60022' },
];

export default function Status() {
  const { data, loading, error, reload } = usePolling<DashboardData>(api.getDashboard, 15);
  const [intervalSec, setIntervalSec] = useState(15);
  const [countdown, setCountdown] = useState(15);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  function changeInterval(sec: number) { setIntervalSec(sec); setCountdown(sec); }

  useEffect(() => {
    clearInterval(timer.current);
    setCountdown(intervalSec);
    timer.current = setInterval(() => setCountdown(prev => { if (prev <= 1) { reload(); return intervalSec; } return prev - 1; }), 1000);
    return () => clearInterval(timer.current);
  }, [intervalSec, reload]);

  const ss = data?.server_status; const svc = ss?.services ?? {}; const gpu = ss?.gpu; const sys = ss?.system;
  const memPct = sys ? Math.round((parseFloat(sys.mem_used) || 0) / Math.max(1, parseFloat(sys.mem_total) || 1) * 100) : 0;
  const diskPct = parseInt(sys?.disk_pct ?? '0') || 0;
  const gpuUtil = parseInt(gpu?.util ?? '0') || 0;

  return (
    <div className="bg-[#0b1121] min-h-[calc(100vh-56px)] text-white">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold">DevMechin 服务器</h1>
          <p className="text-slate-400 text-sm mt-1">8.133.175.201 · Ubuntu 24.04 · i7-14700KF · RTX 4080 SUPER</p>
        </div>

        <div className="flex items-center justify-center gap-3 text-sm text-slate-400 mb-6">
          刷新间隔
          <select value={intervalSec} onChange={e => changeInterval(Number(e.target.value))} className="bg-slate-800 border border-slate-600 rounded px-2 py-1 text-sm text-white">
            <option value={5}>5 秒</option><option value={15}>15 秒</option><option value={30}>30 秒</option><option value={60}>60 秒</option>
          </select>
          · 下次刷新 <span className="text-blue-400 font-mono font-bold w-8 text-center">{countdown}</span>s
          <button onClick={reload} className="bg-blue-600/20 text-blue-400 border border-blue-500/30 px-3 py-1 rounded text-xs hover:bg-blue-600/30">🔄 刷新</button>
        </div>

        {loading && <div className="text-center py-8 text-slate-400"><div className="w-6 h-6 border-2 border-slate-600 border-t-blue-400 rounded-full animate-spin mx-auto mb-2" />加载中...</div>}
        {error && <div className="text-center py-8 text-red-400">⚠️ 加载失败: {error}<br /><button onClick={reload} className="mt-2 bg-blue-600/20 text-blue-400 border border-blue-500/30 px-3 py-1 rounded text-xs">重试</button></div>}

        {ss && <>
          <div className="grid sm:grid-cols-2 gap-3 mb-6">
            {serviceDefs.map(({ key, ...s }) => <ServiceBadge key={key} {...s} up={svc[key] !== false} />)}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <div className="text-xs text-slate-400 uppercase mb-1">⏱ 运行时间</div>
              <div className="text-lg font-bold">{sys?.uptime ?? '—'}</div>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <div className="text-xs text-slate-400 uppercase mb-1">💾 内存</div>
              <div className="text-lg font-bold">{sys?.mem_used ?? '—'}<span className="text-sm text-slate-400">/{sys?.mem_total ?? '—'}</span></div>
              <ProgressBar pct={memPct} />
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <div className="text-xs text-slate-400 uppercase mb-1">📀 磁盘</div>
              <div className="text-lg font-bold">{sys?.disk_pct ?? '—'}</div>
              <div className="text-[10px] text-slate-500">{sys?.disk_used ?? '—'}/{sys?.disk_total ?? '—'}</div>
              <ProgressBar pct={diskPct} color="bg-emerald-500" />
            </div>
            {gpu?.name && <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-center">
              <div className="text-xs text-slate-400 uppercase mb-1">🎮 GPU</div>
              <div className="text-lg font-bold">{gpuUtil}%</div>
              <div className="text-[10px] text-slate-500">{gpu.mem_used}/{gpu.mem_total} | {gpu.temp}°C</div>
              <ProgressBar pct={gpuUtil} color="bg-purple-500" />
            </div>}
          </div>
        </>}
      </div>
    </div>
  );
}
