import { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import type { ConvItem, ConvMsg } from '../types';

const hints = ['待办列表', '? AI Workflow 是什么', '今天要做什么'];

export default function Chat() {
  const [convs, setConvs] = useState<ConvItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConvMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const sidebarOpen = true;
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => { api.listConvs().then(setConvs).catch(() => {}); }, []);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  async function loadConv(id: string) {
    try { const c = await api.getConv(id); setActiveId(id); setMessages(c.messages); } catch {}
  }

  async function send() {
    const text = input.trim(); if (!text || sending) return;
    setInput(''); setSending(true);
    const userMsg: ConvMsg = { role: 'user', text, time: new Date().toLocaleTimeString() };
    const updated = [...messages, userMsg];
    setMessages(updated);
    try {
      const { reply } = await api.sendMessage(text);
      const botMsg: ConvMsg = { role: 'bot', text: reply, time: new Date().toLocaleTimeString() };
      const final = [...updated, botMsg];
      setMessages(final);
      const title = activeId ? undefined : text.slice(0, 30);
      const { id } = await api.saveConv({ id: activeId || undefined, title: title || '新对话', messages: final });
      if (!activeId) setActiveId(id);
      api.listConvs().then(setConvs);
    } catch { setMessages(prev => [...prev, { role: 'bot', text: '网络错误', time: new Date().toLocaleTimeString() }]); }
    setSending(false);
  }

  async function newChat() { setActiveId(null); setMessages([]); }
  async function deleteConv() { if (!activeId) return; await api.deleteConv(activeId); setActiveId(null); setMessages([]); api.listConvs().then(setConvs); }

  function onKey(e: React.KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }

  return (
    <div className="flex h-[calc(100vh-56px)]">
      <aside className={`${sidebarOpen ? 'w-60' : 'w-0'} bg-white border-r border-slate-200 flex flex-col transition-all overflow-hidden flex-shrink-0`}>
        <div className="p-3">
          <button onClick={newChat} className="w-full py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm hover:bg-slate-100">＋ 新对话</button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {convs.map(c => (
            <div key={c.id} onClick={() => loadConv(c.id)}
              className={`px-3 py-2.5 rounded-lg cursor-pointer text-sm mb-0.5 ${c.id === activeId ? 'bg-blue-50 text-blue-600' : 'hover:bg-slate-50'}`}>
              <div className="font-medium truncate">{c.title || '新对话'}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">{c.updated_at?.slice(0, 10)}</div>
            </div>
          ))}
          {convs.length === 0 && <p className="text-xs text-slate-400 text-center py-8">暂无历史对话</p>}
        </div>
        {activeId && <div className="p-2 border-t border-slate-100"><button onClick={deleteConv} className="w-full text-xs text-red-500 py-1.5 rounded hover:bg-red-50">🗑 删除对话</button></div>}
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto px-4">
          <div className="max-w-2xl mx-auto py-4">
            {messages.length === 0 && (
              <div className="text-center py-16">
                <h2 className="text-xl font-bold text-slate-700 mb-2">有什么可以帮你的？</h2>
                <p className="text-sm text-slate-400 mb-6">知识查询、待办管理、定时提醒、笔记记录</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {['📋 查看待办', '🔍 知识查询', '📅 今日日程', '✅ 创建待办', '⏰ 设置提醒', '📋 今日早报'].map(h => (
                    <button key={h} onClick={() => { setInput(h.slice(2)); send(); }}
                      className="bg-white border border-slate-200 rounded-full px-4 py-2 text-sm hover:border-blue-300 hover:text-blue-600">{h}</button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 mb-4 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-blue-600'}`}>
                  {m.role === 'user' ? 'J' : '🤖'}
                </div>
                <div className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${m.role === 'user' ? 'bg-blue-50 rounded-br-md' : 'bg-white border border-slate-200 rounded-bl-md'}`}>
                  <div dangerouslySetInnerHTML={{ __html: m.text.replace(/\n/g, '<br>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
                  <div className="text-[10px] text-slate-400 mt-1">{m.time}</div>
                </div>
              </div>
            ))}
            <div ref={chatEnd} />
          </div>
        </div>

        <div className="border-t border-slate-200 bg-white p-3">
          <div className="max-w-2xl mx-auto flex gap-2">
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey}
              placeholder="输入消息，Enter 发送" disabled={sending}
              className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:opacity-50" />
            <button onClick={send} disabled={sending}
              className="bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50">发送</button>
          </div>
          <div className="text-center text-[11px] text-slate-400 mt-2">
            {hints.map(h => <span key={h} onClick={() => { setInput(h); send(); }} className="cursor-pointer hover:text-blue-500 mx-1">{h}</span>)}
          </div>
        </div>
      </div>
    </div>
  );
}
