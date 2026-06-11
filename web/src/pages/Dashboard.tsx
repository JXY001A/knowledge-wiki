import { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { StatCard } from '../components/StatCard';
import { TrendChart, DoughnutCard } from '../components/ChartCard';
import WikiPageViewer from '../components/WikiPageViewer';
import TodoPanel from '../components/TodoPanel';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { DashboardData } from '../types';

const tabs = ['概览', 'Skills', '知识库', '操作日志', '质量', '待办管理'] as const;

export default function Dashboard() {
  const { data, loading } = usePolling<DashboardData>(api.getDashboard, 60);
  const [tab, setTab] = useState<typeof tabs[number]>('概览');
  const [viewingPage, setViewingPage] = useState<string | null>(null);

  if (loading || !data) return (
    <div className="text-center py-20 text-muted-foreground">
      <div className="w-6 h-6 border-2 border-border border-t-primary rounded-full animate-spin mx-auto mb-3" />
      加载中...
    </div>
  );

  const { overview: ov, eval_trend, wiki_growth, todos: td, memory_dist, gaps, skills, wiki_pages, query_log, server_status: ss, quality: q } = data;
  const svc = ss.services; const gpu = ss.gpu; const sys = ss.system;
  const done = ov.todos_total - ov.todos_pending;

  return (
    <div className="max-w-6xl mx-auto p-4">
      {/* Tab 栏 */}
      <div className="flex gap-6 mb-6 border-b border-border">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={cn('relative pb-2.5 text-sm transition-colors', tab === t ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground')}>
            {t}
            {tab === t && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />}
          </button>
        ))}
      </div>

      {/* 概览 */}
      {tab === '概览' && <>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <StatCard value={ov.wiki_pages.toString()} label="Wiki 页面" sub={`${ov.concepts} 概念`} onClick={() => setTab('知识库')} />
          <StatCard value={`⭐ ${ov.eval_avg}`} label="回答均分" sub={`${ov.eval_count} 次评估`} onClick={() => setTab('操作日志')} />
          <StatCard value={ov.memories.toString()} label="操作记忆" onClick={() => setTab('操作日志')} />
          <StatCard value={`${done}/${ov.todos_total}`} label="待办完成" sub={`剩余 ${ov.todos_pending} 项`} onClick={() => setTab('待办管理')} />
        </div>
        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">评估趋势</CardTitle></CardHeader><CardContent><TrendChart data={eval_trend} lines={[{ key: 'avg', color: '#4d6bfe' }, { key: 'count', color: '#16a34a', yAxisId: 'y1' }]} /></CardContent></Card>
          <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">知识增长</CardTitle></CardHeader><CardContent><TrendChart data={wiki_growth.map(r => ({ date: r.date.slice(5), pages: r.pages }))} lines={[{ key: 'pages', color: '#16a34a' }]} /></CardContent></Card>
          <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">记忆分布</CardTitle></CardHeader><CardContent><DoughnutCard labels={memory_dist.labels} data={memory_dist.counts} /></CardContent></Card>
          <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">待办</CardTitle></CardHeader><CardContent><DoughnutCard labels={['未完成', '已完成', '已取消']} data={[td.pending, td.done, td.cancelled]} /></CardContent></Card>
          <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">知识缺口</CardTitle></CardHeader><CardContent>{gaps.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : gaps.map(g => (<div key={g.topic} className="flex justify-between text-sm py-1.5 border-b border-border"><span className="text-foreground">{g.topic}</span><span className="text-xs text-muted-foreground bg-muted px-2 rounded-full">{g.count}次</span></div>))}</CardContent></Card>
          <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">DevMechin</CardTitle></CardHeader><CardContent><div className="grid grid-cols-2 gap-1 text-xs mb-2">{Object.entries(svc).map(([k, v]) => (<div key={k} className="flex items-center gap-1.5"><span className={`w-1.5 h-1.5 rounded-full ${v ? 'bg-emerald-500' : 'bg-red-500'}`} /><span className="text-foreground">{k}</span></div>))}</div>{gpu.name && <p className="text-[10px] text-muted-foreground">🎮 {gpu.name.split(' ').slice(-2).join(' ')} {gpu.util} | {gpu.mem_used} | {gpu.temp}°C</p>}<p className="text-[10px] text-muted-foreground mt-1">⏱ {sys.uptime} | 📀 {sys.disk_pct}</p></CardContent></Card>
        </div>
      </>}

      {/* Skills */}
      {tab === 'Skills' && <div className="grid md:grid-cols-2 gap-4">
        <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">全部 Skills ({skills.length})</CardTitle></CardHeader><CardContent>{skills.map(s => (<div key={s.name} className="flex justify-between items-center text-sm py-1.5 border-b border-border"><div className="flex items-center gap-2"><span className="text-foreground">{s.name}</span><span className="text-[10px] bg-primary/10 text-primary px-1.5 rounded">T{s.tier}</span></div><span className="text-xs text-muted-foreground">{s.count || 0}次</span></div>))}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">最近待办</CardTitle></CardHeader><CardContent>{td.recent.map((t, i) => (<div key={i} className="flex justify-between text-sm py-1.5 border-b border-border"><span className={t.status === 'done' ? 'text-emerald-600' : t.status === 'cancelled' ? 'text-muted-foreground' : 'text-amber-600'}>{t.status === 'done' ? '✓' : '○'} {t.title}</span><span className="text-[10px] text-muted-foreground">{t.created}{t.deadline ? ` · ⏰${t.deadline}` : ''}</span></div>))}{td.recent.length === 0 && <p className="text-sm text-muted-foreground">暂无</p>}</CardContent></Card>
      </div>}

      {/* 知识库 */}
      {tab === '知识库' && <Card><CardContent><div className="grid grid-cols-2 gap-3 mb-4 text-center"><StatCard value={wiki_pages.reduce((a, d) => a + d.count, 0).toString()} label="总页面" /><StatCard value={wiki_pages.length.toString()} label="目录数" /></div>{wiki_pages.map(d => (<div key={d.directory} className="mb-4"><h4 className="text-sm font-medium text-foreground mb-2">{d.directory} <span className="text-xs text-muted-foreground">({d.count})</span></h4><div className="flex flex-wrap gap-1.5">{d.pages.map(p => (<button key={p.title} onClick={() => setViewingPage(p.path)} className="bg-muted border border-border rounded-md px-2.5 py-1 text-[11px] text-foreground hover:bg-primary/10 hover:text-primary cursor-pointer transition-colors">{p.title}</button>))}</div></div>))}</CardContent></Card>}

      {/* 操作日志 */}
      {tab === '操作日志' && <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">操作日志（最近 50 条）</CardTitle></CardHeader><CardContent>{query_log.map((l, i) => (<div key={i} className="flex justify-between text-sm py-1.5 border-b border-border"><span className="text-foreground">{l.summary}</span><span className="text-xs text-muted-foreground">{l.score ? `⭐${l.score} ` : ''}{l.created}</span></div>))}{query_log.length === 0 && <p className="text-sm text-muted-foreground">暂无</p>}</CardContent></Card>}

      {/* 质量 */}
      {tab === '质量' && q && <div className="grid md:grid-cols-2 gap-4">
        <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">评估概览</CardTitle></CardHeader><CardContent><div className="grid grid-cols-3 gap-2 mb-3"><div className="text-center bg-muted rounded-lg p-3"><div className="text-xl font-bold text-primary">{q.eval_avg}</div><div className="text-[10px] text-muted-foreground mt-0.5">均分 / 5</div></div><div className="text-center bg-muted rounded-lg p-3"><div className="text-xl font-bold text-emerald-600">{q.eval_total}</div><div className="text-[10px] text-muted-foreground mt-0.5">评估次数</div></div><div className="text-center bg-muted rounded-lg p-3"><div className="text-xl font-bold text-foreground">{q.eval_stars}</div><div className="text-[10px] text-muted-foreground mt-0.5">评级</div></div></div>{q.low_score_domains.length > 0 && <><h4 className="text-xs font-medium text-destructive mb-2">低分领域排行</h4>{q.low_score_domains.map((d, i) => (<div key={i} className="flex justify-between text-sm py-1 border-b border-border"><span className="text-foreground">{d.domain}</span><span className="text-xs bg-red-50 text-destructive px-2 rounded-full">{d.count}次</span></div>))}</>}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">自动摄取</CardTitle></CardHeader><CardContent><div className="flex items-center gap-2 mb-3"><div className="flex-1 bg-muted rounded-full h-2"><div className="bg-primary rounded-full h-2 transition-all" style={{ width: `${Math.min(100, (q.auto_ingest.week_count / q.auto_ingest.week_limit) * 100)}%` }} /></div><span className="text-xs text-muted-foreground">{q.auto_ingest.week_count}/{q.auto_ingest.week_limit}</span></div>{q.auto_ingest.ingested.length > 0 ? q.auto_ingest.ingested.map((item, i) => (<div key={i} className="text-xs py-1 border-b border-border"><span className="text-emerald-600">✓</span> {item.topic}</div>)) : <p className="text-sm text-muted-foreground">本周暂无自动摄取</p>}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">反复缺口 ({q.recurring_gaps.length})</CardTitle></CardHeader><CardContent>{q.recurring_gaps.length === 0 ? <p className="text-sm text-muted-foreground">暂无反复出现的缺口</p> : q.recurring_gaps.slice(0, 8).map((g, i) => (<div key={i} className="flex justify-between text-sm py-1.5 border-b border-border"><span className="text-foreground">{g.topic}</span><span className={`text-xs px-2 rounded-full ${g.count >= 3 ? 'bg-red-50 text-destructive' : 'bg-amber-50 text-amber-600'}`}>{g.count}次{g.count >= 3 ? ' ⚠' : ''}</span></div>))}</CardContent></Card>
        <Card><CardHeader><CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">关联建议</CardTitle></CardHeader><CardContent>{q.relation_suggestions.length === 0 ? <p className="text-sm text-muted-foreground">暂无关联建议</p> : q.relation_suggestions.map((r, i) => (<div key={i} className="text-xs py-1.5 border-b border-border"><span className={r.action === 'merge' ? 'text-amber-500' : 'text-primary'}>{r.action === 'merge' ? '↔' : '→'}</span> {r.page1} ↔ {r.page2} <span className="text-muted-foreground">({(r.similarity * 100).toFixed(0)}%)</span></div>))}{q.unprocessed_raw.length > 0 && <div className="mt-3 pt-3 border-t border-border"><h4 className="text-xs font-medium text-amber-500 mb-1">待摄取 ({q.unprocessed_raw.length})</h4>{q.unprocessed_raw.slice(0, 3).map((u, i) => <div key={i} className="text-[10px] text-muted-foreground truncate">· {u}</div>)}</div>}{q.missing_concepts.length > 0 && <div className="mt-2"><h4 className="text-xs font-medium text-primary mb-1">缺失概念</h4><div className="flex flex-wrap gap-1">{q.missing_concepts.slice(0, 5).map((c, i) => (<span key={i} className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">{c}</span>))}</div></div>}</CardContent></Card>
      </div>}

      {tab === '待办管理' && <Card><CardContent><TodoPanel /></CardContent></Card>}
      {viewingPage && <WikiPageViewer path={viewingPage} onClose={() => setViewingPage(null)} />}
    </div>
  );
}
