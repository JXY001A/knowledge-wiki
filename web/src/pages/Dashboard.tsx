import { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { StatCard } from '../components/StatCard';
import { TrendChart, DoughnutCard } from '../components/ChartCard';
import type { DashboardData } from '../types';

const tabs = ['概览', 'Skills', '知识库', '操作日志'] as const;

export default function Dashboard() {
  const { data, loading } = usePolling<DashboardData>(api.getDashboard, 60);
  const [tab, setTab] = useState<typeof tabs[number]>('概览');
  if (loading || !data) return <div className="text-center py-16 text-slate-400">加载中...</div>;

  const { overview: ov, eval_trend, wiki_growth, todos: td, memory_dist, gaps, reminders, skills, wiki_pages, query_log, server_status: ss } = data;
  const svc = ss.services; const gpu = ss.gpu; const sys = ss.system;
  const done = ov.todos_total - ov.todos_pending;

  return (
    <div className="max-w-6xl mx-auto p-4">
      <div className="flex gap-1 mb-4 bg-white rounded-lg p-1 border border-slate-200 w-fit">
        {tabs.map(t => <button key={t} onClick={() => setTab(t)} className={`px-4 py-1.5 rounded-md text-sm font-medium transition ${tab === t ? 'bg-blue-600 text-white' : 'text-slate-500 hover:text-slate-700'}`}>{t}</button>)}
      </div>

      {tab === '概览' && <>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <StatCard value={ov.wiki_pages.toString()} label="Wiki 页面" sub={`${ov.concepts} 概念`} onClick={() => setTab('知识库')} />
          <StatCard value={`⭐ ${ov.eval_avg}`} label="回答均分" sub={`${ov.eval_count} 次评估`} onClick={() => setTab('操作日志')} />
          <StatCard value={ov.memories.toString()} label="操作记忆" onClick={() => setTab('操作日志')} />
          <StatCard value={`${done}/${ov.todos_total}`} label="待办完成" sub={`剩余 ${ov.todos_pending} 项`} onClick={() => setTab('Skills')} />
        </div>
        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <div className="bg-white border border-slate-200 rounded-xl p-4"><h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">📊 评估趋势</h3><TrendChart data={eval_trend} lines={[{ key: 'avg', color: '#3b82f6' }, { key: 'count', color: '#16a34a', yAxisId: 'y1' }]} /></div>
          <div className="bg-white border border-slate-200 rounded-xl p-4"><h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">📈 知识增长</h3><TrendChart data={wiki_growth.map(r => ({ date: r.date.slice(5), pages: r.pages }))} lines={[{ key: 'pages', color: '#16a34a' }]} /></div>
          <div className="bg-white border border-slate-200 rounded-xl p-4"><h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">🧠 记忆分布</h3><DoughnutCard labels={memory_dist.labels} data={memory_dist.counts} /></div>
          <div className="bg-white border border-slate-200 rounded-xl p-4"><h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">✅ 待办</h3><DoughnutCard labels={['未完成', '已完成', '已取消']} data={[td.pending, td.done, td.cancelled]} /></div>
          <div className="bg-white border border-slate-200 rounded-xl p-4"><h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">🔍 知识缺口</h3>{gaps.length === 0 ? <p className="text-sm text-slate-400">暂无</p> : gaps.map(g => <div key={g.topic} className="flex justify-between text-sm py-1 border-b border-slate-50"><span>{g.topic}</span><span className="text-xs bg-slate-100 px-2 rounded-full">{g.count}次</span></div>)}</div>
          <div className="bg-white border border-slate-200 rounded-xl p-4"><h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">🖥️ DevMechin</h3><div className="grid grid-cols-2 gap-1 text-xs mb-2">{Object.entries(svc).map(([k, v]) => <div key={k} className="flex items-center gap-1"><span className={`w-2 h-2 rounded-full ${v ? 'bg-green-500' : 'bg-red-500'}`} />{k}</div>)}</div>{gpu.name && <p className="text-[10px] text-slate-400">🎮 {gpu.name.split(' ').slice(-2).join(' ')} {gpu.util} | {gpu.mem_used} | {gpu.temp}°C</p>}<p className="text-[10px] text-slate-400 mt-1">⏱ {sys.uptime} | 📀 {sys.disk_pct}</p></div>
        </div>
      </>}

      {tab === 'Skills' && <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">全部 Skills ({skills.length})</h3>
          {skills.map(s => <div key={s.name} className="flex justify-between items-center text-sm py-1.5 border-b border-slate-50"><div className="flex items-center gap-2"><span>{s.name}</span><span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 rounded">T{s.tier}</span></div><span className="text-xs text-slate-400">{s.count || 0}次</span></div>)}
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">📋 最近待办</h3>
          {td.recent.map((t, i) => <div key={i} className="flex justify-between text-sm py-1.5 border-b border-slate-50"><span style={{ color: t.status === 'done' ? '#16a34a' : t.status === 'cancelled' ? '#94a3b8' : '#eab308' }}>{t.status === 'done' ? '✅' : '⏳'} {t.title}</span><span className="text-[10px] text-slate-400">{t.created}{t.deadline ? ` · ⏰${t.deadline}` : ''}</span></div>)}
          {td.recent.length === 0 && <p className="text-sm text-slate-400">暂无</p>}
        </div>
      </div>}

      {tab === '知识库' && <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="grid grid-cols-3 gap-2 mb-4 text-center"><StatCard value={wiki_pages.reduce((a, d) => a + d.count, 0).toString()} label="总页面" /><StatCard value={wiki_pages.length.toString()} label="目录数" /></div>
        {wiki_pages.map(d => <div key={d.directory} className="mb-4"><h4 className="text-sm font-semibold text-blue-600 mb-2">📁 {d.directory} ({d.count})</h4><div className="flex flex-wrap gap-1.5">{d.pages.map(p => <span key={p.title} className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-[11px] text-slate-600">{p.title}</span>)}</div></div>)}
      </div>}

      {tab === '操作日志' && <div className="bg-white border border-slate-200 rounded-xl p-4">
        <h3 className="text-xs text-slate-500 font-semibold mb-3 uppercase">操作日志（最近 50 条）</h3>
        {query_log.map((l, i) => <div key={i} className="flex justify-between text-sm py-1.5 border-b border-slate-50"><span>{l.icon} {l.summary}</span><span className="text-xs text-slate-400">{l.score ? `⭐${l.score} ` : ''}{l.created}</span></div>)}
        {query_log.length === 0 && <p className="text-sm text-slate-400">暂无</p>}
      </div>}
    </div>
  );
}
