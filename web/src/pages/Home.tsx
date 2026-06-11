import { Link } from 'react-router-dom';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { StatCard } from '../components/StatCard';
import type { DashboardData } from '../types';

const features = [
  { label: '知识查询', desc: '四阶段检索流水线 + LLM 综合回答' },
  { label: '待办管理', desc: '自然语言创建，到点微信推送提醒' },
  { label: '定时提醒', desc: 'threading.Timer 精准推送' },
  { label: '快速笔记', desc: '自动打标签，FTS5 全文搜索' },
  { label: '知识摄取', desc: 'URL 自动下载 → DeepSeek 分析' },
  { label: '自进化', desc: '评估 → 缺口检测 → 搜索建议' },
];

const layers = [
  { lvl: '5', title: '自进化闭环 — 缺口检测 · 自动摄取 · 自检报告', bg: 'bg-accent-light', dot: 'bg-accent' },
  { lvl: '4', title: '评估与反馈 — DeepSeek 评分 · 知识覆盖仪表盘', bg: 'bg-emerald-50', dot: 'bg-emerald-500' },
  { lvl: '3', title: '记忆系统 — 工作记忆 · 情景记忆 · 用户画像', bg: 'bg-sky-50', dot: 'bg-sky-500' },
  { lvl: '2', title: 'Agent 技能体系 — 14 Skills · LLM 意图分类', bg: 'bg-amber-50', dot: 'bg-amber-500' },
  { lvl: '1', title: '知识基座 — 76 页 · 检索流水线 · DeepSeek ingest', bg: 'bg-rose-50', dot: 'bg-rose-500' },
];

export default function Home() {
  const { data } = usePolling<DashboardData>(api.getDashboard, 120);
  const ov = data?.overview;

  return (
    <div>
      {/* Hero */}
      <section className="text-center pt-20 pb-12 px-4 max-w-2xl mx-auto">
        <span className="inline-block text-[11px] text-muted tracking-widest uppercase mb-6">
          AI 自进化知识系统
        </span>
        <h1 className="text-5xl font-serif font-semibold text-ink leading-tight mb-4 tracking-tight">
          不只是知识库
        </h1>
        <p className="text-muted text-base leading-relaxed mb-10 max-w-lg mx-auto">
          能查询、能待办、能提醒、能评估、能进化 — 让 AI 越用越懂你
        </p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link
            to="/chat"
            className="bg-ink text-white px-6 py-2.5 rounded-md text-sm font-medium hover:opacity-85 transition-opacity shadow-elevated"
          >
            开始对话
          </Link>
          <Link
            to="/admin"
            className="bg-white border border-border text-ink px-6 py-2.5 rounded-md text-sm font-medium hover:bg-paper transition-colors"
          >
            管理后台
          </Link>
          <Link
            to="/status"
            className="bg-white border border-border text-ink px-6 py-2.5 rounded-md text-sm font-medium hover:bg-paper transition-colors"
          >
            服务器状态
          </Link>
        </div>
      </section>

      {/* 指标卡片 */}
      <section className="max-w-4xl mx-auto px-4 pb-12 grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          value={ov?.wiki_pages?.toString() ?? '—'}
          label="Wiki 页面"
          sub={ov ? `${ov.concepts} 个概念` : undefined}
        />
        <StatCard
          value={ov ? `⭐ ${ov.eval_avg}` : '—'}
          label="回答均分"
          sub={ov ? `${ov.eval_count} 次评估` : undefined}
        />
        <StatCard value={data?.skills?.length?.toString() ?? '—'} label="Skills" />
        <StatCard value={ov?.memories?.toString() ?? '—'} label="操作记忆" />
      </section>

      {/* 功能网格 */}
      <section className="max-w-4xl mx-auto px-4 pb-16">
        <h2 className="text-lg font-serif font-semibold text-center text-ink mb-2">能做什么</h2>
        <p className="text-sm text-muted text-center mb-8">
          一个入口，覆盖个人知识工作的全流程
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {features.map((f) => (
            <div
              key={f.label}
              className="bg-white border border-border rounded-md p-5 hover:shadow-card transition-shadow duration-150"
            >
              <h3 className="font-medium text-ink text-sm mb-1.5">{f.label}</h3>
              <p className="text-xs text-muted leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 五层架构 */}
      <section className="max-w-xl mx-auto px-4 pb-20">
        <h2 className="text-lg font-serif font-semibold text-center text-ink mb-8">五层架构</h2>
        <div className="flex flex-col gap-1.5">
          {layers.map((l) => (
            <div
              key={l.lvl}
              className={`${l.bg} rounded-md px-4 py-2.5 flex items-center gap-3 text-sm text-ink`}
            >
              <span
                className={`w-7 h-7 rounded-full ${l.dot} text-white flex items-center justify-center text-xs font-medium`}
              >
                {l.lvl}
              </span>
              {l.title}
            </div>
          ))}
        </div>
      </section>

      {/* 页脚 */}
      <footer className="text-center text-[11px] text-faint py-6 border-t border-border">
        mindbase v1.0 · Powered by DeepSeek + Ollama · DevMechin RTX 4080 SUPER
      </footer>
    </div>
  );
}
