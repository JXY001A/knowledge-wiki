import { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { StatCard } from '../components/StatCard';
import { TrendChart, DoughnutCard } from '../components/ChartCard';
import WikiPageViewer from '../components/WikiPageViewer';
import TodoPanel from '../components/TodoPanel';
import type { DashboardData } from '../types';

const tabs = ['概览', 'Skills', '知识库', '操作日志', '质量', '待办管理'] as const;

export default function Dashboard() {
  const { data, loading } = usePolling<DashboardData>(api.getDashboard, 60);
  const [tab, setTab] = useState<typeof tabs[number]>('概览');
  const [viewingPage, setViewingPage] = useState<string | null>(null);

  if (loading || !data) return (
    <div className="text-center py-20 text-gray-400">
      <div className="w-6 h-6 border-2 border-gray-200 border-t-accent rounded-full animate-spin mx-auto mb-3" />
      加载中...
    </div>
  );

  const { overview: ov, eval_trend, wiki_growth, todos: td, memory_dist, gaps, skills, wiki_pages, query_log, server_status: ss, quality: q } = data;
  const svc = ss.services; const gpu = ss.gpu; const sys = ss.system;
  const done = ov.todos_total - ov.todos_pending;

  return (
    <div className="max-w-6xl mx-auto p-4">
      {/* Tab 栏 */}
      <div className="flex gap-6 mb-6 border-b border-gray-200">
        {tabs.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative pb-2.5 text-sm transition-colors ${
              tab === t ? 'text-accent font-semibold' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {t}
            {tab === t && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent rounded-full" />
            )}
          </button>
        ))}
      </div>

      {/* ── 概览 ── */}
      {tab === '概览' && <>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <StatCard value={ov.wiki_pages.toString()} label="Wiki 页面" sub={`${ov.concepts} 概念`} onClick={() => setTab('知识库')} />
          <StatCard value={`⭐ ${ov.eval_avg}`} label="回答均分" sub={`${ov.eval_count} 次评估`} onClick={() => setTab('操作日志')} />
          <StatCard value={ov.memories.toString()} label="操作记忆" onClick={() => setTab('操作日志')} />
          <StatCard value={`${done}/${ov.todos_total}`} label="待办完成" sub={`剩余 ${ov.todos_pending} 项`} onClick={() => setTab('待办管理')} />
        </div>
        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
            <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">评估趋势</h3>
            <TrendChart data={eval_trend} lines={[{ key: 'avg', color: '#4d6bfe' }, { key: 'count', color: '#16a34a', yAxisId: 'y1' }]} />
          </div>
          <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
            <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">知识增长</h3>
            <TrendChart data={wiki_growth.map(r => ({ date: r.date.slice(5), pages: r.pages }))} lines={[{ key: 'pages', color: '#16a34a' }]} />
          </div>
          <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
            <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">记忆分布</h3>
            <DoughnutCard labels={memory_dist.labels} data={memory_dist.counts} />
          </div>
          <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
            <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">待办</h3>
            <DoughnutCard labels={['未完成', '已完成', '已取消']} data={[td.pending, td.done, td.cancelled]} />
          </div>
          <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
            <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">知识缺口</h3>
            {gaps.length === 0 ? <p className="text-sm text-gray-400">暂无</p> : (
              gaps.map(g => (
                <div key={g.topic} className="flex justify-between text-sm py-1.5 border-b border-gray-100">
                  <span className="text-gray-700">{g.topic}</span>
                  <span className="text-xs text-gray-500 bg-gray-100 px-2 rounded-full">{g.count}次</span>
                </div>
              ))
            )}
          </div>
          <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
            <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">DevMechin</h3>
            <div className="grid grid-cols-2 gap-1 text-xs mb-2">
              {Object.entries(svc).map(([k, v]) => (
                <div key={k} className="flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${v ? 'bg-emerald-500' : 'bg-red-500'}`} />
                  <span className="text-gray-700">{k}</span>
                </div>
              ))}
            </div>
            {gpu.name && <p className="text-[10px] text-gray-400">🎮 {gpu.name.split(' ').slice(-2).join(' ')} {gpu.util} | {gpu.mem_used} | {gpu.temp}°C</p>}
            <p className="text-[10px] text-gray-400 mt-1">⏱ {sys.uptime} | 📀 {sys.disk_pct}</p>
          </div>
        </div>
      </>}

      {/* ── Skills ── */}
      {tab === 'Skills' && <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
          <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">全部 Skills ({skills.length})</h3>
          {skills.map(s => (
            <div key={s.name} className="flex justify-between items-center text-sm py-1.5 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <span className="text-gray-700">{s.name}</span>
                <span className="text-[10px] bg-accent-light text-accent px-1.5 rounded">T{s.tier}</span>
              </div>
              <span className="text-xs text-gray-400">{s.count || 0}次</span>
            </div>
          ))}
        </div>
        <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
          <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">最近待办</h3>
          {td.recent.map((t, i) => (
            <div key={i} className="flex justify-between text-sm py-1.5 border-b border-gray-100">
              <span className={t.status === 'done' ? 'text-emerald-600' : t.status === 'cancelled' ? 'text-gray-400' : 'text-amber-600'}>
                {t.status === 'done' ? '✓' : '○'} {t.title}
              </span>
              <span className="text-[10px] text-gray-400">{t.created}{t.deadline ? ` · ⏰${t.deadline}` : ''}</span>
            </div>
          ))}
          {td.recent.length === 0 && <p className="text-sm text-gray-400">暂无</p>}
        </div>
      </div>}

      {/* ── 知识库 ── */}
      {tab === '知识库' && <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
        <div className="grid grid-cols-2 gap-3 mb-4 text-center">
          <StatCard value={wiki_pages.reduce((a, d) => a + d.count, 0).toString()} label="总页面" />
          <StatCard value={wiki_pages.length.toString()} label="目录数" />
        </div>
        {wiki_pages.map(d => (
          <div key={d.directory} className="mb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">{d.directory} <span className="text-xs text-gray-400">({d.count})</span></h4>
            <div className="flex flex-wrap gap-1.5">
              {d.pages.map(p => (
                <button key={p.title} onClick={() => setViewingPage(p.path)}
                  className="bg-gray-50 border border-gray-200 rounded-md px-2.5 py-1 text-[11px] text-gray-600 hover:bg-accent-light hover:border-accent/30 hover:text-accent cursor-pointer transition-colors">
                  {p.title}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>}

      {/* ── 操作日志 ── */}
      {tab === '操作日志' && <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
        <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">操作日志（最近 50 条）</h3>
        {query_log.map((l, i) => (
          <div key={i} className="flex justify-between text-sm py-1.5 border-b border-gray-100">
            <span className="text-gray-700">{l.summary}</span>
            <span className="text-xs text-gray-400">{l.score ? `⭐${l.score} ` : ''}{l.created}</span>
          </div>
        ))}
        {query_log.length === 0 && <p className="text-sm text-gray-400">暂无</p>}
      </div>}

      {/* ── 质量 ── */}
      {tab === '质量' && q && <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
          <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">评估概览</h3>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="text-center bg-gray-50 rounded-lg p-3">
              <div className="text-xl font-bold text-accent">{q.eval_avg}</div>
              <div className="text-[10px] text-gray-400 mt-0.5">均分 / 5</div>
            </div>
            <div className="text-center bg-gray-50 rounded-lg p-3">
              <div className="text-xl font-bold text-emerald-600">{q.eval_total}</div>
              <div className="text-[10px] text-gray-400 mt-0.5">评估次数</div>
            </div>
            <div className="text-center bg-gray-50 rounded-lg p-3">
              <div className="text-xl font-bold text-gray-700">{q.eval_stars}</div>
              <div className="text-[10px] text-gray-400 mt-0.5">评级</div>
            </div>
          </div>
          {q.low_score_domains.length > 0 && <>
            <h4 className="text-xs font-medium text-red-500 mb-2">低分领域排行</h4>
            {q.low_score_domains.map((d, i) => (
              <div key={i} className="flex justify-between text-sm py-1 border-b border-gray-100">
                <span className="text-gray-700">{d.domain}</span>
                <span className="text-xs bg-red-50 text-red-600 px-2 rounded-full">{d.count}次</span>
              </div>
            ))}
          </>}
        </div>
        <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
          <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">自动摄取</h3>
          <div className="flex items-center gap-2 mb-3">
            <div className="flex-1 bg-gray-100 rounded-full h-2">
              <div className="bg-accent rounded-full h-2 transition-all" style={{ width: `${Math.min(100, (q.auto_ingest.week_count / q.auto_ingest.week_limit) * 100)}%` }} />
            </div>
            <span className="text-xs text-gray-400">{q.auto_ingest.week_count}/{q.auto_ingest.week_limit}</span>
          </div>
          {q.auto_ingest.ingested.length > 0 ? (
            q.auto_ingest.ingested.map((item, i) => (
              <div key={i} className="text-xs py-1 border-b border-gray-100"><span className="text-emerald-600">✓</span> {item.topic}</div>
            ))
          ) : <p className="text-sm text-gray-400">本周暂无自动摄取</p>}
        </div>
        <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
          <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">反复缺口 ({q.recurring_gaps.length})</h3>
          {q.recurring_gaps.length === 0 ? <p className="text-sm text-gray-400">暂无反复出现的缺口</p> : (
            q.recurring_gaps.slice(0, 8).map((g, i) => (
              <div key={i} className="flex justify-between text-sm py-1.5 border-b border-gray-100">
                <span className="text-gray-700">{g.topic}</span>
                <span className={`text-xs px-2 rounded-full ${g.count >= 3 ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'}`}>{g.count}次{g.count >= 3 ? ' ⚠' : ''}</span>
              </div>
            ))
          )}
        </div>
        <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card">
          <h3 className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">关联建议</h3>
          {q.relation_suggestions.length === 0 ? <p className="text-sm text-gray-400">暂无关联建议</p> : (
            q.relation_suggestions.map((r, i) => (
              <div key={i} className="text-xs py-1.5 border-b border-gray-100">
                <span className={r.action === 'merge' ? 'text-amber-500' : 'text-accent'}>{r.action === 'merge' ? '↔' : '→'}</span>{' '}
                {r.page1} ↔ {r.page2} <span className="text-gray-400">({(r.similarity * 100).toFixed(0)}%)</span>
              </div>
            ))
          )}
          {q.unprocessed_raw.length > 0 && <div className="mt-3 pt-3 border-t border-gray-100">
            <h4 className="text-xs font-medium text-amber-500 mb-1">待摄取 ({q.unprocessed_raw.length})</h4>
            {q.unprocessed_raw.slice(0, 3).map((u, i) => <div key={i} className="text-[10px] text-gray-400 truncate">· {u}</div>)}
          </div>}
          {q.missing_concepts.length > 0 && <div className="mt-2">
            <h4 className="text-xs font-medium text-accent mb-1">缺失概念</h4>
            <div className="flex flex-wrap gap-1">
              {q.missing_concepts.slice(0, 5).map((c, i) => (
                <span key={i} className="text-[10px] bg-accent-light text-accent px-1.5 py-0.5 rounded">{c}</span>
              ))}
            </div>
          </div>}
        </div>
      </div>}

      {tab === '待办管理' && <div className="bg-white border border-gray-100 rounded-lg p-4 shadow-card"><TodoPanel /></div>}
      {viewingPage && <WikiPageViewer path={viewingPage} onClose={() => setViewingPage(null)} />}
    </div>
  );
}
