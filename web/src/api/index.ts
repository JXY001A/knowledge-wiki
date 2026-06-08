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
  sendMessage: (text: string) => post<{ reply: string }>('/chat', { text }),

  listConvs: () => get<ConvItem[]>('/chat/convs'),
  getConv: (id: string) => get<ConvDetail>(`/chat/convs/${id}`),
  saveConv: (conv: { id?: string; title: string; messages: ConvDetail['messages'] }) => post<{ id: string; ok: boolean }>('/chat/convs', conv),
  deleteConv: (id: string) => del(`/chat/convs/${id}`),
};
