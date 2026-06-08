import { Link } from 'react-router-dom';
import { usePolling } from '../hooks/usePolling';
import { api } from '../api';
import { StatCard } from '../components/StatCard';
import type { DashboardData } from '../types';

const features = [
  { icon: '🔍', title: '知识查询', desc: '四阶段检索流水线 + LLM 综合回答' },
  { icon: '✅', title: '待办管理', desc: '自然语言创建，到点微信推送' },
  { icon: '⏰', title: '定时提醒', desc: 'threading.Timer 精准推送' },
  { icon: '📝', title: '快速笔记', desc: '自动打标签，FTS5 全文搜索' },
  { icon: '📥', title: '知识摄取', desc: 'URL 自动下载 → DeepSeek 分析' },
  { icon: '🔄', title: '自进化', desc: '评估 → 缺口检测 → 搜索建议' },
];

const layers = [
  { lvl: '5', title: '自进化闭环 — 缺口检测 · 自动摄取 · 自检报告', bg: 'bg-violet-50', dot: 'bg-violet-500' },
  { lvl: '4', title: '评估与反馈 — DeepSeek 评分 · 知识覆盖仪表盘', bg: 'bg-green-50', dot: 'bg-green-500' },
  { lvl: '3', title: '记忆系统 — 工作记忆 · 情景记忆 · 用户画像', bg: 'bg-blue-50', dot: 'bg-blue-500' },
  { lvl: '2', title: 'Agent 技能体系 — 14 Skills · LLM 意图分类', bg: 'bg-amber-50', dot: 'bg-amber-500' },
  { lvl: '1', title: '知识基座 — 76 页 · 检索流水线 · DeepSeek ingest', bg: 'bg-red-50', dot: 'bg-red-500' },
];

export default function Home() {
  const { data } = usePolling<DashboardData>(api.getDashboard, 120);
  const ov = data?.overview;

  return (
    <div>
      <section className="text-center py-16 px-4 max-w-2xl mx-auto">
        <span className="inline-block bg-blue-100 text-blue-600 px-3 py-1 rounded-full text-xs font-medium mb-4">v1.0 · 五层架构已全部建成</span>
        <h1 className="text-4xl font-extrabold text-slate-800 mb-3">AI 自进化知识系统</h1>
        <p className="text-slate-500 mb-8 leading-relaxed">不只是知识库。能查询、能待办、能提醒、能评估、能进化 — 让 AI 越用越懂你。</p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link to="/chat" className="bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 transition shadow-md shadow-blue-200">💬 开始对话</Link>
          <Link to="/admin" className="bg-white border border-slate-200 text-slate-700 px-6 py-3 rounded-lg font-semibold hover:bg-slate-50 transition">📊 管理后台</Link>
          <Link to="/status" className="bg-white border border-slate-200 text-slate-700 px-6 py-3 rounded-lg font-semibold hover:bg-slate-50 transition">🖥️ 服务器</Link>
        </div>
      </section>

      <section className="max-w-4xl mx-auto px-4 pb-8 grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard value={ov?.wiki_pages?.toString() ?? '—'} label="Wiki 页面" sub={ov ? `${ov.concepts} 个概念` : undefined} />
        <StatCard value={ov ? `⭐ ${ov.eval_avg}` : '—'} label="回答均分" sub={ov ? `${ov.eval_count} 次评估` : undefined} />
        <StatCard value={data?.skills?.length?.toString() ?? '—'} label="Skills" />
        <StatCard value={ov?.memories?.toString() ?? '—'} label="操作记忆" />
      </section>

      <section className="max-w-4xl mx-auto px-4 pb-16">
        <h2 className="text-xl font-bold text-center text-slate-800 mb-2">能做什么</h2>
        <p className="text-sm text-slate-400 text-center mb-8">一个入口，覆盖个人知识工作的全流程</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map(f => (
            <div key={f.title} className="bg-white border border-slate-200 rounded-xl p-5 hover:border-blue-300 transition-colors">
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-slate-800 mb-1">{f.title}</h3>
              <p className="text-sm text-slate-500">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-xl mx-auto px-4 pb-20">
        <h2 className="text-xl font-bold text-center text-slate-800 mb-8">五层架构</h2>
        <div className="flex flex-col gap-2">
          {layers.map(l => (
            <div key={l.lvl} className={`${l.bg} rounded-lg px-4 py-2.5 flex items-center gap-3 text-sm font-medium text-slate-700`}>
              <span className={`w-7 h-7 rounded-full ${l.dot} text-white flex items-center justify-center text-xs font-bold`}>{l.lvl}</span>
              {l.title}
            </div>
          ))}
        </div>
      </section>

      <footer className="text-center text-xs text-slate-400 py-6 border-t border-slate-100">
        AI 自进化知识系统 v1.0 · Powered by DeepSeek + Ollama · DevMechin RTX 4080 SUPER
      </footer>
    </div>
  );
}
