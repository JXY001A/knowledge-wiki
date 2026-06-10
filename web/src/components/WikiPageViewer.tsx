import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { api } from '../api';
import type { WikiPageContent } from '../types';

interface Props { path: string; onClose: () => void }

export default function WikiPageViewer({ path, onClose }: Props) {
  const [page, setPage] = useState<WikiPageContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    api.getWikiPage(path)
      .then(setPage)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [path]);

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-3xl w-full max-h-[80vh] overflow-y-auto shadow-xl" onClick={e => e.stopPropagation()}>
        {loading && <div className="flex items-center justify-center py-20 text-slate-400">加载中...</div>}
        {error && <div className="flex flex-col items-center justify-center py-20 gap-3"><p className="text-red-500">加载失败: {error}</p><button onClick={() => { setLoading(true); setError(null); api.getWikiPage(path).then(setPage).catch(e => setError(e.message)).finally(() => setLoading(false)); }} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">重试</button></div>}
        {page && (
          <div className="p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-lg font-bold text-slate-800">{page.title}</h2>
                <div className="flex gap-2 mt-1 text-xs text-slate-400">
                  {(page.frontmatter as any)?.type && <span>类型: {(page.frontmatter as any).type}</span>}
                  {page.updated && <span>更新: {page.updated}</span>}
                </div>
                {(page.frontmatter as any)?.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {(page.frontmatter as any).tags.map((t: string) => <span key={t} className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">{t}</span>)}
                  </div>
                )}
              </div>
              <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
            </div>
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                {page.content}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
