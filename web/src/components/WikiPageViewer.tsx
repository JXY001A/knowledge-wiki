import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { api } from '../api';
import { Button } from '@/components/ui/button';
import type { WikiPageContent } from '../types';

interface Props { path: string; onClose: () => void }

export default function WikiPageViewer({ path, onClose }: Props) {
  const [page, setPage] = useState<WikiPageContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    api.getWikiPage(path).then(setPage).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [path]);

  return (
    <div className="fixed inset-0 z-50 bg-black/20 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-card rounded-xl max-w-3xl w-full max-h-[80vh] overflow-y-auto ring-1 ring-border shadow-xl" onClick={e => e.stopPropagation()}>
        {loading && <div className="flex items-center justify-center py-20 text-muted-foreground"><div className="w-6 h-6 border-2 border-border border-t-primary rounded-full animate-spin" /></div>}
        {error && <div className="flex flex-col items-center justify-center py-20 gap-3"><p className="text-destructive text-sm">加载失败: {error}</p><Button onClick={() => { setLoading(true); setError(null); api.getWikiPage(path).then(setPage).catch(e => setError(e.message)).finally(() => setLoading(false)); }}>重试</Button></div>}
        {page && (
          <div className="p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-lg font-bold text-foreground">{page.title}</h2>
                <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                  {(page.frontmatter as any)?.type && <span>类型: {(page.frontmatter as any).type}</span>}
                  {page.updated && <span>更新: {page.updated}</span>}
                </div>
                {(page.frontmatter as any)?.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {(page.frontmatter as any).tags.map((t: string) => <span key={t} className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">{t}</span>)}
                  </div>
                )}
              </div>
              <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg leading-none transition-colors">&times;</button>
            </div>
            <div className="prose prose-sm max-w-none prose-a:text-primary prose-code:bg-muted prose-code:px-1 prose-code:rounded prose-pre:bg-sidebar prose-pre:text-sidebar-foreground">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{page.content}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
