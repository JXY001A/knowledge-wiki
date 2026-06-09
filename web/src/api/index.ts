import type { DashboardData, ConvItem, ConvDetail } from '../types';

const BASE = '';

async function get<T>(url: string): Promise<T> {
  const r = await fetch(BASE + url);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

async function del(url: string): Promise<void> {
  await fetch(BASE + url, { method: 'DELETE' });
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
};
