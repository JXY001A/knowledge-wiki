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
    <div
      className="fixed inset-0 z-50 bg-black/20 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl max-w-3xl w-full max-h-[80vh] overflow-y-auto shadow-elevated"
        onClick={e => e.stopPropagation()}
      >
        {loading && (
          <div className="flex items-center justify-center py-20 text-gray-400">
            <div className="w-6 h-6 border-2 border-gray-200 border-t-accent rounded-full animate-spin" />
          </div>
        )}
        {error && (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <p className="text-red-500 text-sm">加载失败: {error}</p>
            <button
              onClick={() => {
                setLoading(true); setError(null);
                api.getWikiPage(path)
                  .then(setPage)
                  .catch(e => setError(e.message))
                  .finally(() => setLoading(false));
              }}
              className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-dark"
            >
              重试
            </button>
          </div>
        )}
        {page && (
          <div className="p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-lg font-bold text-gray-900">{page.title}</h2>
                <div className="flex gap-3 mt-1 text-xs text-gray-400">
                  {(page.frontmatter as any)?.type && <span>类型: {(page.frontmatter as any).type}</span>}
                  {page.updated && <span>更新: {page.updated}</span>}
                </div>
                {(page.frontmatter as any)?.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {(page.frontmatter as any).tags.map((t: string) => (
                      <span key={t} className="text-[10px] bg-accent-light text-accent px-1.5 py-0.5 rounded">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none transition-colors">&times;</button>
            </div>
            <div className="prose prose-sm max-w-none prose-a:text-accent prose-code:text-gray-900 prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded prose-pre:bg-gray-900 prose-pre:text-gray-100">
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
