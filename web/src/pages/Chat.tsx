import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import { api } from '../api';
import type { ConvItem, ConvMsg } from '../types';

const hints = ['待办列表', '? AI Workflow 是什么', '今天要做什么'];

export default function Chat() {
  const [convs, setConvs] = useState<ConvItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConvMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [speaking, setSpeaking] = useState<number | null>(null);  // 正在朗读的消息索引
  const [listening, setListening] = useState(false);  // 语音输入中
  const sidebarOpen = true;
  const chatEnd = useRef<HTMLDivElement>(null);

  // 语音合成 — 朗读 bot 消息
  function speakMessage(index: number, text: string) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    if (speaking === index) { setSpeaking(null); return; }
    // 清理 Markdown 语法后再朗读
    const cleanText = text.replace(/[#*`\[\]|>_-]/g, ' ').replace(/\s+/g, ' ').trim();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'zh-CN';
    utterance.rate = 1.1;
    utterance.onend = () => setSpeaking(null);
    utterance.onerror = () => setSpeaking(null);
    setSpeaking(index);
    window.speechSynthesis.speak(utterance);
  }

  // 语音输入 — 浏览器 SpeechRecognition
  function startListening() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event: any) => {
      const text = event.results[0][0].transcript;
      setInput(text);
      setListening(false);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    setListening(true);
    recognition.start();
  }

  useEffect(() => { api.listConvs().then(setConvs).catch(() => {}); }, []);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  async function loadConv(id: string) {
    try { const c = await api.getConv(id); setActiveId(id); setMessages(c.messages); } catch {}
  }

  const streamCtrl = useRef<AbortController | null>(null);

  // 发送消息（支持直接传文本参数，避免 setState 异步问题）
  async function send(presetText?: string) {
    const text = (presetText || input).trim(); if (!text || sending) return;
    setInput(''); setSending(true);
    const now = new Date().toLocaleTimeString();
    const userMsg: ConvMsg = { role: 'user', text, time: now };
    const placeholder = '  '; // 占位符，保证消息气泡可见
    const botMsg: ConvMsg = { role: 'bot', text: placeholder, time: '' };
    const updated = [...messages, userMsg, botMsg];
    setMessages(updated);

    const botIndex = updated.length - 1;
    let firstToken = true;

    // 获取流式回复
    const ctrl = api.streamMessage(
      text,
      activeId,
      // onToken — 逐字追加（首次替换占位符）
      (token) => {
        setMessages(prev => {
          const next = [...prev];
          if (next[botIndex]) {
            const cur = firstToken ? '' : next[botIndex].text;
            firstToken = false;
            next[botIndex] = { ...next[botIndex], text: cur + token, time: new Date().toLocaleTimeString() };
          }
          return next;
        });
      },
      // onDone — 流完成，保存会话
      (fullText) => {
        setSending(false);
        setMessages(prev => {
          const next = [...prev];
          next[botIndex] = { ...next[botIndex], text: fullText, time: new Date().toLocaleTimeString() };
          return next;
        });
        // 保存到 DB
        const title = activeId ? undefined : text.slice(0, 30);
        api.saveConv({ id: activeId || undefined, title: title || '新对话', messages: [...updated.slice(0, -1), { role: 'bot' as const, text: fullText, time: new Date().toLocaleTimeString() }] })
          .then(({ id }) => { if (!activeId) setActiveId(id); api.listConvs().then(setConvs); })
          .catch(() => {});
      },
      // onError
      (err) => {
        setSending(false);
        setMessages(prev => {
          const next = [...prev];
          next[botIndex] = { ...next[botIndex], text: `❌ ${err}`, time: new Date().toLocaleTimeString() };
          return next;
        });
      },
    );
    streamCtrl.current = ctrl;
  }

  async function newChat() {
    streamCtrl.current?.abort();  // 取消进行中的流
    setActiveId(null); setMessages([]); setSending(false);
  }
  async function deleteConv() { if (!activeId) return; streamCtrl.current?.abort(); await api.deleteConv(activeId); setActiveId(null); setMessages([]); api.listConvs().then(setConvs); }

  function onKey(e: React.KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
  function quickSend(label: string) { send(label.slice(2)); }

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
              <div className="font-medium truncate flex items-center gap-1">
                {c.title || '新对话'}
                {c.channel && c.channel !== 'web' && (
                  <span className="text-[10px] bg-green-50 text-green-600 px-1 rounded">{c.channel === 'wecom' ? '💬' : '🔧'}</span>
                )}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">{c.updated_at?.slice(0, 10)}{c.channel && c.channel !== 'web' ? ` · ${c.channel}` : ''}</div>
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
                    <button key={h} onClick={() => quickSend(h)}
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
                  {m.role === 'bot' && m.text.trim() === '' ? (
                    <div className="flex items-center gap-1 text-slate-400 py-1">
                      <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  ) : (
                    <div className="prose prose-sm max-w-none prose-headings:text-slate-700 prose-a:text-blue-600 prose-code:text-rose-600 prose-code:bg-slate-100 prose-code:px-1 prose-code:rounded prose-pre:bg-slate-900 prose-pre:text-slate-100 prose-ul:list-disc prose-ol:list-decimal prose-table:border-collapse">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                        {m.text}
                      </ReactMarkdown>
                    </div>
                  )}
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-[10px] text-slate-400">{m.time}</span>
                    {m.role === 'bot' && m.text && (
                      <button
                        onClick={() => speakMessage(i, m.text)}
                        className={`text-xs px-2 py-0.5 rounded transition ${speaking === i ? 'text-blue-600 bg-blue-50' : 'text-slate-400 hover:text-slate-600'}`}
                        title={speaking === i ? '停止朗读' : '朗读'}
                      >
                        {speaking === i ? '🔊' : '🔈'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={chatEnd} />
          </div>
        </div>

        <div className="border-t border-slate-200 bg-white p-3">
          <div className="max-w-2xl mx-auto flex gap-2">
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey}
              placeholder={listening ? '正在聆听...' : '输入消息，Enter 发送'} disabled={sending}
              className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 disabled:opacity-50" />
            <button onClick={startListening} disabled={listening}
              className={`px-3 py-2.5 rounded-xl text-sm border transition ${listening ? 'bg-red-50 border-red-300 text-red-600 animate-pulse' : 'border-slate-200 hover:bg-slate-50'}`}
              title="语音输入">
              🎤
            </button>
            <button onClick={() => send()} disabled={sending}
              className="bg-blue-600 text-white px-5 py-2.5 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50">发送</button>
          </div>
          <div className="text-center text-[11px] text-slate-400 mt-2">
            {hints.map(h => <span key={h} onClick={() => quickSend(h)} className="cursor-pointer hover:text-blue-500 mx-1">{h}</span>)}
          </div>
        </div>
      </div>
    </div>
  );
}
