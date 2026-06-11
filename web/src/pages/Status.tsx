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
    timer.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { reload(); return intervalSec; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer.current);
  }, [intervalSec, reload]);

  const ss = data?.server_status; const svc = ss?.services ?? {}; const gpu = ss?.gpu; const sys = ss?.system;
  const memPct = sys ? Math.round((parseFloat(sys.mem_used) || 0) / Math.max(1, parseFloat(sys.mem_total) || 1) * 100) : 0;
  const diskPct = parseInt(sys?.disk_pct ?? '0') || 0;
  const gpuUtil = parseInt(gpu?.util ?? '0') || 0;

  return (
    <div className="bg-[#1a1b23] min-h-[calc(100vh-48px)]">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* 标题 */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-white">DevMechin</h1>
          <p className="text-gray-400 text-sm mt-1">8.133.175.201 · Ubuntu 24.04 · i7-14700KF · RTX 4080 SUPER</p>
        </div>

        {/* 刷新控制 */}
        <div className="flex items-center justify-center gap-3 text-sm text-gray-400 mb-6">
          <span className="text-xs uppercase tracking-wider">刷新间隔</span>
          <select
            value={intervalSec}
            onChange={e => changeInterval(Number(e.target.value))}
            className="bg-[#25262f] border border-gray-700 rounded-md px-2.5 py-1 text-sm text-white"
          >
            <option value={5}>5s</option>
            <option value={15}>15s</option>
            <option value={30}>30s</option>
            <option value={60}>60s</option>
          </select>
          <span className="text-xs">
            下次 <span className="text-accent font-mono font-medium">{countdown}</span>s
          </span>
          <button onClick={reload} className="text-xs text-accent border border-accent/30 px-3 py-1 rounded-md hover:bg-accent/10 transition-colors">
            刷新
          </button>
        </div>

        {/* 加载/错误状态 */}
        {loading && (
          <div className="text-center py-12 text-gray-400">
            <div className="w-6 h-6 border-2 border-gray-600 border-t-accent rounded-full animate-spin mx-auto mb-3" />
            加载中...
          </div>
        )}
        {error && (
          <div className="text-center py-12 text-red-400">
            <p>⚠ 加载失败: {error}</p>
            <button onClick={reload} className="mt-3 text-sm text-accent border border-accent/30 px-3 py-1 rounded-md hover:bg-accent/10">重试</button>
          </div>
        )}

        {/* 服务状态 */}
        {ss && <>
          <div className="grid sm:grid-cols-2 gap-3 mb-6">
            {serviceDefs.map(({ key, ...s }) => (
              <ServiceBadge key={key} {...s} up={svc[key] !== false} />
            ))}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white/5 border border-white/10 rounded-lg p-4 text-center">
              <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">运行时间</div>
              <div className="text-lg font-medium text-white font-mono">{sys?.uptime ?? '—'}</div>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-lg p-4 text-center">
              <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">内存</div>
              <div className="text-lg font-medium text-white font-mono">
                {sys?.mem_used ?? '—'}<span className="text-sm text-gray-400">/{sys?.mem_total ?? '—'}</span>
              </div>
              <ProgressBar pct={memPct} />
            </div>
            <div className="bg-white/5 border border-white/10 rounded-lg p-4 text-center">
              <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">磁盘</div>
              <div className="text-lg font-medium text-white font-mono">{sys?.disk_pct ?? '—'}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">{sys?.disk_used ?? '—'}/{sys?.disk_total ?? '—'}</div>
              <ProgressBar pct={diskPct} color="bg-emerald-500" />
            </div>
            {gpu?.name && (
              <div className="bg-white/5 border border-white/10 rounded-lg p-4 text-center">
                <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">GPU</div>
                <div className="text-lg font-medium text-white font-mono">{gpuUtil}%</div>
                <div className="text-[10px] text-gray-500 mt-0.5">{gpu.mem_used}/{gpu.mem_total} | {gpu.temp}°C</div>
                <ProgressBar pct={gpuUtil} color="bg-purple-500" />
              </div>
            )}
          </div>
        </>}
      </div>
    </div>
  );
}
