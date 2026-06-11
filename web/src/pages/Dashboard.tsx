import { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { StatCard } from '../components/StatCard';
import { TrendChart, DoughnutCard } from '../components/ChartCard';
import WikiPageViewer from '../components/WikiPageViewer';
import TodoPanel from '../components/TodoPanel';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { DashboardData } from '../types';

const tabs = ['概览', 'Skills', '知识库', '操作日志', '质量', '待办管理'] as const;

export default function Dashboard() {
  const { data, loading } = usePolling<DashboardData>(api.getDashboard, 60);
  const [tab, setTab] = useState<typeof tabs[number]>('概览');
  const [viewingPage, setViewingPage] = useState<string | null>(null);

  if (loading || !data) return (
    <div className="flex items-center justify-center py-32 text-muted-foreground">
      <div className="w-6 h-6 border-2 border-border border-t-primary rounded-full animate-spin mr-3" />
      加载中...
    </div>
  );

  const { overview: ov, eval_trend, wiki_growth, todos: td, memory_dist, gaps, skills, wiki_pages, query_log, server_status: ss, quality: q } = data;
  const svc = ss.services; const gpu = ss.gpu; const sys = ss.system;
  const done = ov.todos_total - ov.todos_pending;

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* 页面头部 — 参考 Tasko 的 Dashboard 标题区域 */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-foreground">管理后台</h1>
          <p className="text-sm text-muted-foreground mt-1">知识库管理、技能监控、质量评估一站式面板</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">导入数据</Button>
          <Button size="sm">+ 新建</Button>
        </div>
      </div>

      {/* Tab 栏 */}
      <div className="flex gap-6 mb-6 border-b border-border">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={cn(
              'relative pb-2.5 text-sm font-medium transition-colors',
              tab === t ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
            )}>
            {t}
            {tab === t && <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />}
          </button>
        ))}
      </div>

      {/* ── 概览 ── */}
      {tab === '概览' && <>
        {/* 统计卡片 — 大号数字，参考 Tasko */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard value={ov.wiki_pages.toString()} label="Wiki 页面" sub={`${ov.concepts} 个概念`} onClick={() => setTab('知识库')} />
          <StatCard value={`${ov.eval_avg}`} label="回答均分" sub={`${ov.eval_count} 次评估`} onClick={() => setTab('操作日志')} />
          <StatCard value={ov.memories.toString()} label="操作记忆" onClick={() => setTab('操作日志')} />
          <StatCard value={`${done}/${ov.todos_total}`} label="待办完成" sub={`剩余 ${ov.todos_pending} 项`} onClick={() => setTab('待办管理')} />
        </div>

        {/* 图表区 */}
        <div className="grid md:grid-cols-2 gap-4 mb-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium">评估趋势</CardTitle>
              <span className="text-xs text-muted-foreground">均分趋势</span>
            </CardHeader>
            <CardContent>
              <TrendChart data={eval_trend} lines={[{ key: 'avg', color: '#10b981' }, { key: 'count', color: '#f59e0b', yAxisId: 'y1' }]} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium">知识增长</CardTitle>
              <span className="text-xs text-muted-foreground">累计页面</span>
            </CardHeader>
            <CardContent>
              <TrendChart data={wiki_growth.map(r => ({ date: r.date.slice(5), pages: r.pages }))} lines={[{ key: 'pages', color: '#10b981' }]} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">记忆分布</CardTitle>
            </CardHeader>
            <CardContent>
              <DoughnutCard labels={memory_dist.labels} data={memory_dist.counts} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">待办统计</CardTitle>
            </CardHeader>
            <CardContent>
              <DoughnutCard labels={['未完成', '已完成', '已取消']} data={[td.pending, td.done, td.cancelled]} />
            </CardContent>
          </Card>
        </div>

        {/* 底部：知识缺口 + 服务器状态 */}
        <div className="grid md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">知识缺口</CardTitle>
            </CardHeader>
            <CardContent>
              {gaps.length === 0 ? <p className="text-sm text-muted-foreground py-4">暂无</p> : (
                <div className="space-y-0.5">
                  {gaps.slice(0, 6).map(g => (
                    <div key={g.topic} className="flex justify-between items-center py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors">
                      <span className="text-sm text-foreground">{g.topic}</span>
                      <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">{g.count}次</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">DevMechin 服务器</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                {Object.entries(svc).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-2 py-1">
                    <span className={`w-2 h-2 rounded-full ${v ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    <span className="text-foreground">{k}</span>
                  </div>
                ))}
              </div>
              {gpu.name && <p className="text-xs text-muted-foreground">{gpu.name.split(' ').slice(-2).join(' ')} · {gpu.util} · {gpu.mem_used} · {gpu.temp}°C</p>}
              <p className="text-xs text-muted-foreground mt-1">⏱ {sys.uptime} · 📀 {sys.disk_pct}</p>
            </CardContent>
          </Card>
        </div>
      </>}

      {/* ── Skills ── */}
      {tab === 'Skills' && <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">全部 Skills ({skills.length})</CardTitle></CardHeader>
          <CardContent>
            {skills.map(s => (
              <div key={s.name} className="flex justify-between items-center py-2.5 px-3 rounded-lg hover:bg-muted/50 transition-colors">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-foreground">{s.name}</span>
                  <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded font-medium">T{s.tier}</span>
                </div>
                <span className="text-xs text-muted-foreground">{s.count || 0}次</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">最近待办</CardTitle></CardHeader>
          <CardContent>
            {td.recent.map((t, i) => (
              <div key={i} className="flex justify-between items-center py-2.5 px-3 rounded-lg hover:bg-muted/50 transition-colors">
                <span className={cn('text-sm', t.status === 'done' ? 'text-emerald-600' : t.status === 'cancelled' ? 'text-muted-foreground' : 'text-amber-600')}>
                  {t.status === 'done' ? '✓' : '○'} {t.title}
                </span>
                <span className="text-xs text-muted-foreground">{t.created}{t.deadline ? ` · ⏰${t.deadline}` : ''}</span>
              </div>
            ))}
            {td.recent.length === 0 && <p className="text-sm text-muted-foreground py-4">暂无</p>}
          </CardContent>
        </Card>
      </div>}

      {/* ── 知识库 ── */}
      {tab === '知识库' && <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-2 gap-4 mb-6">
            <StatCard value={wiki_pages.reduce((a, d) => a + d.count, 0).toString()} label="总页面" />
            <StatCard value={wiki_pages.length.toString()} label="目录数" />
          </div>
          {wiki_pages.map(d => (
            <div key={d.directory} className="mb-5">
              <h4 className="text-sm font-medium text-foreground mb-2.5">{d.directory} <span className="text-xs text-muted-foreground">({d.count})</span></h4>
              <div className="flex flex-wrap gap-1.5">
                {d.pages.map(p => (
                  <button key={p.title} onClick={() => setViewingPage(p.path)}
                    className="bg-muted border border-border rounded-lg px-3 py-1.5 text-[13px] text-foreground hover:bg-primary/10 hover:text-primary hover:border-primary/20 cursor-pointer transition-colors">
                    {p.title}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>}

      {/* ── 操作日志 ── */}
      {tab === '操作日志' && <Card>
        <CardHeader><CardTitle className="text-sm font-medium">操作日志（最近 50 条）</CardTitle></CardHeader>
        <CardContent>
          {query_log.map((l, i) => (
            <div key={i} className="flex justify-between items-center py-2.5 px-3 rounded-lg hover:bg-muted/50 transition-colors">
              <span className="text-sm text-foreground">{l.summary}</span>
              <span className="text-xs text-muted-foreground">{l.score ? `⭐${l.score} ` : ''}{l.created}</span>
            </div>
          ))}
          {query_log.length === 0 && <p className="text-sm text-muted-foreground py-4">暂无</p>}
        </CardContent>
      </Card>}

      {/* ── 质量 ── */}
      {tab === '质量' && q && <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">评估概览</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="text-center bg-muted rounded-xl p-4">
                <div className="text-2xl font-bold text-primary">{q.eval_avg}</div>
                <div className="text-xs text-muted-foreground mt-1">均分 / 5</div>
              </div>
              <div className="text-center bg-muted rounded-xl p-4">
                <div className="text-2xl font-bold text-emerald-600">{q.eval_total}</div>
                <div className="text-xs text-muted-foreground mt-1">评估次数</div>
              </div>
              <div className="text-center bg-muted rounded-xl p-4">
                <div className="text-2xl font-bold text-foreground">{q.eval_stars}</div>
                <div className="text-xs text-muted-foreground mt-1">评级</div>
              </div>
            </div>
            {q.low_score_domains.length > 0 && <>
              <h4 className="text-xs font-medium text-destructive mb-2">低分领域排行</h4>
              {q.low_score_domains.map((d, i) => (
                <div key={i} className="flex justify-between items-center py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <span className="text-sm text-foreground">{d.domain}</span>
                  <span className="text-xs bg-red-50 text-destructive px-2 py-0.5 rounded-full font-medium">{d.count}次</span>
                </div>
              ))}
            </>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">自动摄取</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-1 bg-muted rounded-full h-2.5">
                <div className="bg-primary rounded-full h-2.5 transition-all" style={{ width: `${Math.min(100, (q.auto_ingest.week_count / q.auto_ingest.week_limit) * 100)}%` }} />
              </div>
              <span className="text-sm text-muted-foreground font-medium">{q.auto_ingest.week_count}/{q.auto_ingest.week_limit}</span>
            </div>
            {q.auto_ingest.ingested.length > 0 ? (
              q.auto_ingest.ingested.map((item, i) => (
                <div key={i} className="text-sm py-1.5 px-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <span className="text-emerald-600">✓</span> {item.topic}
                </div>
              ))
            ) : <p className="text-sm text-muted-foreground py-4">本周暂无自动摄取</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">反复缺口 ({q.recurring_gaps.length})</CardTitle></CardHeader>
          <CardContent>
            {q.recurring_gaps.length === 0 ? <p className="text-sm text-muted-foreground py-4">暂无</p> : (
              q.recurring_gaps.slice(0, 8).map((g, i) => (
                <div key={i} className="flex justify-between items-center py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <span className="text-sm text-foreground">{g.topic}</span>
                  <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', g.count >= 3 ? 'bg-red-50 text-destructive' : 'bg-amber-50 text-amber-600')}>
                    {g.count}次{g.count >= 3 ? ' ⚠' : ''}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm font-medium">关联建议</CardTitle></CardHeader>
          <CardContent>
            {q.relation_suggestions.length === 0 ? <p className="text-sm text-muted-foreground py-4">暂无关联建议</p> : (
              q.relation_suggestions.map((r, i) => (
                <div key={i} className="text-sm py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors">
                  <span className={r.action === 'merge' ? 'text-amber-500' : 'text-primary'}>{r.action === 'merge' ? '↔' : '→'}</span>{' '}
                  {r.page1} ↔ {r.page2} <span className="text-muted-foreground">({(r.similarity * 100).toFixed(0)}%)</span>
                </div>
              ))
            )}
            {q.unprocessed_raw.length > 0 && (
              <div className="mt-4 pt-4 border-t border-border">
                <h4 className="text-xs font-medium text-amber-500 mb-2">待摄取 ({q.unprocessed_raw.length})</h4>
                {q.unprocessed_raw.slice(0, 3).map((u, i) => <div key={i} className="text-xs text-muted-foreground truncate py-0.5">· {u}</div>)}
              </div>
            )}
            {q.missing_concepts.length > 0 && (
              <div className="mt-3">
                <h4 className="text-xs font-medium text-primary mb-2">缺失概念</h4>
                <div className="flex flex-wrap gap-1.5">
                  {q.missing_concepts.slice(0, 5).map((c, i) => (
                    <span key={i} className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-lg font-medium">{c}</span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>}

      {tab === '待办管理' && <Card><CardContent className="pt-6"><TodoPanel /></CardContent></Card>}
      {viewingPage && <WikiPageViewer path={viewingPage} onClose={() => setViewingPage(null)} />}
    </div>
  );
}
