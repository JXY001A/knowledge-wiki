import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import { api } from '../api';
import type { ConvItem, ConvMsg } from '../types';

const hints = ['查看待办', '知识查询', '创建待办', '今日早报'];
const ASSISTANT_NAME = '若愚';

export default function Chat() {
  const [convs, setConvs] = useState<ConvItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConvMsg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [speaking, setSpeaking] = useState<number | null>(null);
  const [listening, setListening] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [waitingCommand, setWaitingCommand] = useState(false);
  const sidebarOpen = true;
  const chatEnd = useRef<HTMLDivElement>(null);
  const wakeRecognitionRef = useRef<any>(null);

  // 语音合成
  function speakMessage(index: number, text: string) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    if (speaking === index) { setSpeaking(null); return; }
    const cleanText = text.replace(/[#*`\[\]|>_-]/g, ' ').replace(/\s+/g, ' ').trim();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'zh-CN';
    utterance.rate = 1.1;
    utterance.onend = () => setSpeaking(null);
    utterance.onerror = () => setSpeaking(null);
    setSpeaking(index);
    window.speechSynthesis.speak(utterance);
  }

  // 语音输入
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

  // 语音唤醒模式
  function startWakeWord() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (!event.results[i].isFinal) continue;
        const transcript: string = event.results[i][0].transcript;

        const wakeMarkers = ['若愚', '若鱼', '若雨', 'ruo yu', 'ruoyu'];
        const match = wakeMarkers.find(w => transcript.includes(w));
        if (match) {
          const idx = transcript.indexOf(match);
          const command = transcript.slice(idx + match.length).trim();
          if (command) {
            processVoiceCommand(command);
          } else {
            setWaitingCommand(true);
          }
        } else if (waitingCommand) {
          processVoiceCommand(transcript);
          setWaitingCommand(false);
        }
      }
    };

    recognition.onerror = () => {
      if (voiceMode) setTimeout(startWakeWord, 1000);
    };
    recognition.onend = () => {
      if (voiceMode) setTimeout(startWakeWord, 500);
    };

    wakeRecognitionRef.current = recognition;
    recognition.start();
  }

  function stopWakeWord() {
    if (wakeRecognitionRef.current) {
      wakeRecognitionRef.current.stop();
      wakeRecognitionRef.current = null;
    }
    setWaitingCommand(false);
  }

  async function processVoiceCommand(command: string) {
    if (!command.trim()) return;
    setInput(command);
    setSending(true);

    const now = new Date().toLocaleTimeString();
    const userMsg: ConvMsg = { role: 'user', text: `🎤 ${command}`, time: now };
    const updated = [...messages, userMsg];
    setMessages(updated);

    try {
      const resp = await fetch('/api/voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: command, conversation_id: activeId || '' }),
      });
      const data = await resp.json();
      const reply = data.reply || '处理完成';
      const botMsg: ConvMsg = {
        role: 'bot',
        text: reply + (data.spoken ? ' 🔊' : ''),
        time: new Date().toLocaleTimeString(),
      };
      const finalMessages = [...updated, botMsg];
      setMessages(finalMessages);

      api.saveConv({
        id: activeId || undefined,
        title: command.slice(0, 30),
        messages: finalMessages.map(m => ({ role: m.role, text: m.text, time: m.time })),
      }).then(({ id }) => { if (!activeId) setActiveId(id); api.listConvs().then(setConvs); }).catch(() => {});
    } catch (err: any) {
      const botMsg: ConvMsg = { role: 'bot', text: `❌ ${err.message || '网络错误'}`, time: new Date().toLocaleTimeString() };
      setMessages([...updated, botMsg]);
    } finally {
      setSending(false);
    }
  }

  function toggleVoiceMode() {
    if (voiceMode) {
      stopWakeWord();
      setVoiceMode(false);
    } else {
      setVoiceMode(true);
      startWakeWord();
    }
  }

  useEffect(() => { return () => stopWakeWord(); }, []);

  useEffect(() => { api.listConvs().then(setConvs).catch(() => {}); }, []);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  async function loadConv(id: string) {
    try { const c = await api.getConv(id); setActiveId(id); setMessages(c.messages); } catch {}
  }

  const streamCtrl = useRef<AbortController | null>(null);

  async function send(presetText?: string) {
    const text = (presetText || input).trim(); if (!text || sending) return;
    setInput(''); setSending(true);
    const now = new Date().toLocaleTimeString();
    const userMsg: ConvMsg = { role: 'user', text, time: now };
    const placeholder = '  ';
    const botMsg: ConvMsg = { role: 'bot', text: placeholder, time: '' };
    const updated = [...messages, userMsg, botMsg];
    setMessages(updated);

    const botIndex = updated.length - 1;
    let firstToken = true;

    const ctrl = api.streamMessage(
      text,
      activeId,
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
      (fullText) => {
        setSending(false);
        setMessages(prev => {
          const next = [...prev];
          next[botIndex] = { ...next[botIndex], text: fullText, time: new Date().toLocaleTimeString() };
          return next;
        });
        const title = activeId ? undefined : text.slice(0, 30);
        api.saveConv({ id: activeId || undefined, title: title || '新对话', messages: [...updated.slice(0, -1), { role: 'bot' as const, text: fullText, time: new Date().toLocaleTimeString() }] })
          .then(({ id }) => { if (!activeId) setActiveId(id); api.listConvs().then(setConvs); })
          .catch(() => {});
      },
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
    streamCtrl.current?.abort();
    setActiveId(null); setMessages([]); setSending(false);
  }
  async function deleteConv() { if (!activeId) return; streamCtrl.current?.abort(); await api.deleteConv(activeId); setActiveId(null); setMessages([]); api.listConvs().then(setConvs); }

  function onKey(e: React.KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
  function quickSend(label: string) { send(label); }

  return (
    <div className="flex h-[calc(100vh-48px)]">
      {/* ── 深色侧边栏 (DeepSeek 风格) ── */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-0'} bg-sidebar flex flex-col transition-all overflow-hidden flex-shrink-0`}>
        {/* Logo / 新对话 */}
        <div className="p-3">
          <button
            onClick={newChat}
            className="w-full py-2.5 border border-gray-600/40 text-gray-300 rounded-lg text-sm hover:bg-sidebar-hover transition-colors"
          >
            ＋ 新对话
          </button>
        </div>

        {/* 会话列表 */}
        <div className="flex-1 overflow-y-auto dark-scrollbar px-2 pb-2">
          {convs.map(c => (
            <div
              key={c.id}
              onClick={() => loadConv(c.id)}
              className={`px-3 py-2.5 rounded-lg cursor-pointer text-sm mb-0.5 transition-colors ${
                c.id === activeId
                  ? 'bg-sidebar-active text-white'
                  : 'text-gray-400 hover:bg-sidebar-hover hover:text-gray-200'
              }`}
            >
              <div className="truncate text-[13px]">{c.title || '新对话'}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">
                {c.updated_at?.slice(0, 10)}
                {c.channel && c.channel !== 'web' ? ` · ${c.channel}` : ''}
              </div>
            </div>
          ))}
          {convs.length === 0 && (
            <p className="text-xs text-gray-500 text-center py-8">暂无历史对话</p>
          )}
        </div>

        {/* 底部用户区 + 删除 */}
        {activeId && (
          <div className="p-3 border-t border-gray-700/50">
            <button
              onClick={deleteConv}
              className="w-full text-xs text-gray-500 py-1.5 rounded hover:text-red-400 hover:bg-sidebar-hover transition-colors"
            >
              删除对话
            </button>
          </div>
        )}
      </aside>

      {/* ── 主聊天区 ── */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">
        {/* 消息区域 */}
        <div className="flex-1 overflow-y-auto px-4">
          <div className="max-w-3xl mx-auto py-4">
            {/* 空状态 — 建议 chips */}
            {messages.length === 0 && (
              <div className="text-center pt-24 pb-8">
                <h2 className="text-2xl font-semibold text-gray-900 mb-2">有什么可以帮你的？</h2>
                <p className="text-sm text-gray-400 mb-8">知识查询 · 待办管理 · 定时提醒 · 笔记记录</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {['查看待办', '知识查询', '今日日程', '创建待办', '设置提醒', '今日早报'].map(h => (
                    <button
                      key={h}
                      onClick={() => quickSend(h)}
                      className="bg-white border border-gray-200 rounded-full px-4 py-2 text-[13px] text-gray-500 hover:text-accent hover:border-accent/30 transition-all"
                    >
                      {h}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 消息列表 */}
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 mb-6 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                {/* 头像 */}
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 ${
                  m.role === 'user'
                    ? 'bg-accent text-white'
                    : 'bg-gray-100 text-gray-400'
                }`}>
                  {m.role === 'user' ? '我' : 'AI'}
                </div>

                {/* 气泡 */}
                <div className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-accent-light text-gray-900 rounded-br-md'
                    : 'bg-gray-50 text-gray-900 rounded-bl-md'
                }`}>
                  {m.role === 'bot' && m.text.trim() === '' ? (
                    <div className="flex items-center gap-1.5 text-gray-400 py-1">
                      <span className="w-2 h-2 bg-accent/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-accent/30 rounded-full animate-bounce" style={{ animationDelay: '120ms' }} />
                      <span className="w-2 h-2 bg-accent/30 rounded-full animate-bounce" style={{ animationDelay: '240ms' }} />
                    </div>
                  ) : (
                    <div className="prose prose-sm max-w-none prose-a:text-accent prose-code:text-gray-900 prose-code:bg-gray-200 prose-code:px-1 prose-code:rounded prose-pre:bg-gray-900 prose-pre:text-gray-100">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                        {m.text}
                      </ReactMarkdown>
                    </div>
                  )}
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-[10px] text-gray-400">{m.time}</span>
                    {m.role === 'bot' && m.text && (
                      <button
                        onClick={() => speakMessage(i, m.text)}
                        className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                          speaking === i ? 'text-accent bg-accent-light' : 'text-gray-400 hover:text-gray-600'
                        }`}
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

        {/* ── 输入区 (DeepSeek 风格 — 大圆角) ── */}
        <div className="border-t border-gray-100 bg-white px-4 py-3">
          {/* 语音模式状态栏 */}
          {voiceMode && (
            <div className="max-w-3xl mx-auto mb-2 flex items-center gap-2 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-gray-500">
                说 <strong className="text-accent">{ASSISTANT_NAME}</strong> 唤醒
                {waitingCommand && <span className="text-amber-500 ml-1">，等待指令...</span>}
              </span>
            </div>
          )}

          <div className="max-w-3xl mx-auto">
            {/* 输入框 + 按钮行 */}
            <div className="flex items-end gap-2 bg-gray-100 rounded-2xl px-4 py-3 border border-transparent transition-all focus-within:bg-white focus-within:border-accent/30 focus-within:shadow-input">
              {/* 语音按钮 */}
              <button
                onClick={startListening}
                disabled={listening || voiceMode}
                className={`p-1.5 rounded-lg transition-colors flex-shrink-0 ${
                  listening
                    ? 'text-red-500 bg-red-50'
                    : 'text-gray-400 hover:text-gray-600 disabled:opacity-30'
                }`}
                title="语音输入"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
              </button>

              {/* 文本输入 */}
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder={listening ? '正在聆听...' : voiceMode ? `说"${ASSISTANT_NAME}"唤醒我...` : '输入消息，Enter 发送'}
                disabled={sending}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-gray-400 disabled:opacity-50 py-0.5"
              />

              {/* 发送按钮 */}
              <button
                onClick={() => send()}
                disabled={sending || !input.trim()}
                className="p-1.5 rounded-lg bg-accent text-white hover:bg-accent-dark disabled:opacity-30 disabled:hover:bg-accent transition-all flex-shrink-0"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M3.4 20.4 2 2l20 10L2 22l1.4-1.6L7 12Z"/></svg>
              </button>
            </div>

            {/* 语音模式 + 快捷提示 */}
            <div className="flex items-center justify-between mt-2">
              <button
                onClick={toggleVoiceMode}
                className={`text-[11px] px-2 py-0.5 rounded transition-colors ${
                  voiceMode
                    ? 'text-accent bg-accent-light font-medium'
                    : 'text-gray-400 hover:text-gray-600'
                }`}
              >
                {voiceMode ? '语音模式已开启' : '🎤 语音唤醒'}
              </button>
              <div className="flex gap-1">
                {hints.map(h => (
                  <span
                    key={h}
                    onClick={() => quickSend(h)}
                    className="text-[11px] text-gray-400 cursor-pointer hover:text-accent px-1.5 transition-colors"
                  >
                    {h}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
