import type { DashboardData, ConvItem, ConvDetail, WikiPageContent, TodoItem, WikiSearchResult } from '../types';

const BASE = '';

async function get<T>(url: string): Promise<T> {
  const r = await fetch(BASE + url);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

async function post<T>(url: string, body: unknown, method = 'POST'): Promise<T> {
  const r = await fetch(BASE + url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

async function del(url: string): Promise<void> {
  const r = await fetch(BASE + url, { method: 'DELETE' });
  if (!r.ok) throw new Error(`${r.status}`);
}

export const api = {
  getDashboard: () => get<DashboardData>('/admin/data'),
  sendMessage: (text: string, conversationId?: string) => post<{ reply: string }>('/chat', { text, conversation_id: conversationId || '' }),

  /** 流式聊天 — 返回 AbortController 用于取消 */
  streamMessage: (
    text: string,
    conversationId: string | null,
    onToken: (token: string) => void,
    onDone: (fullText: string) => void,
    onError: (err: string) => void,
  ): AbortController => {
    const controller = new AbortController();
    const fullParts: string[] = [];

    fetch('/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, conversation_id: conversationId || '' }),
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) throw new Error(`${response.status}`);
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No readable stream');
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.token) { fullParts.push(data.token); onToken(data.token); }
              else if (data.done) { onDone(fullParts.join('')); return; }
              else if (data.error) { onError(data.error); return; }
            } catch { /* skip */ }
          }
        }
      }
      onDone(fullParts.join(''));
    }).catch((err) => {
      if (err.name !== 'AbortError') onError(err.message || '网络错误');
    });

    return controller;
  },

  listConvs: () => get<ConvItem[]>('/chat/convs'),
  getConv: (id: string) => get<ConvDetail>(`/chat/convs/${id}`),
  saveConv: (conv: { id?: string; title: string; messages: ConvDetail['messages'] }) => post<{ id: string; ok: boolean }>('/chat/convs', conv),
  deleteConv: (id: string) => del(`/chat/convs/${id}`),

  // Wiki 页面
  getWikiPage: (path: string) => get<WikiPageContent>(`/api/wiki/page?path=${encodeURIComponent(path)}`),
  getWikiPageByTitle: (title: string) => get<WikiPageContent>(`/api/wiki/page?title=${encodeURIComponent(title)}`),

  // 待办管理
  listTodos: (status?: string) => get<{ todos: TodoItem[] }>(`/api/todos${status ? `?status=${status}` : ''}`),
  createTodo: (data: { title: string; priority?: string; deadline?: string; tags?: string[] }) => post<{ id: string; ok: boolean }>('/api/todos', data),
  updateTodo: (id: string, data: Partial<TodoItem>) => post<{ ok: boolean }>(`/api/todos/${id}`, data, 'PATCH'),
  deleteTodo: (id: string) => del(`/api/todos/${id}`),

  // 知识检索
  searchKnowledge: (query: string, topN?: number) => post<{ results: WikiSearchResult[]; context: string; has_relevant: boolean }>('/api/knowledge/search', { query, top_n: topN || 5 }),

  // 工具执行
  executeAction: (tool: string, args: Record<string, unknown>) => post<{ reply: string; success: boolean }>('/api/action/execute', { tool, args }),

  // 语音
  voiceProcess: (text: string, conversationId?: string) => post<{ reply: string; spoken: boolean }>('/api/voice', { text, conversation_id: conversationId || '' }),
};
