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
      {/* 侧边栏 */}
      <aside className={`${sidebarOpen ? 'w-56' : 'w-0'} bg-white border-r border-border flex flex-col transition-all overflow-hidden flex-shrink-0`}>
        <div className="p-3">
          <button
            onClick={newChat}
            className="w-full py-2 bg-ink text-white rounded-md text-sm font-medium hover:opacity-85 transition-opacity"
          >
            ＋ 新对话
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {convs.map(c => (
            <div
              key={c.id}
              onClick={() => loadConv(c.id)}
              className={`px-3 py-2 rounded-md cursor-pointer text-sm mb-0.5 transition-colors ${
                c.id === activeId
                  ? 'bg-accent-light text-accent'
                  : 'hover:bg-paper text-ink'
              }`}
            >
              <div className="font-medium truncate flex items-center gap-1 text-[13px]">
                {c.title || '新对话'}
                {c.channel && c.channel !== 'web' && (
                  <span className="text-[10px] bg-emerald-50 text-emerald-600 px-1 rounded-sm">
                    {c.channel === 'wecom' ? '💬' : '🔧'}
                  </span>
                )}
              </div>
              <div className="text-[10px] text-muted mt-0.5">
                {c.updated_at?.slice(0, 10)}
                {c.channel && c.channel !== 'web' ? ` · ${c.channel}` : ''}
              </div>
            </div>
          ))}
          {convs.length === 0 && (
            <p className="text-xs text-muted text-center py-8">暂无历史对话</p>
          )}
        </div>
        {activeId && (
          <div className="p-2 border-t border-border">
            <button
              onClick={deleteConv}
              className="w-full text-xs text-red-500 py-1.5 rounded hover:bg-red-50 transition-colors"
            >
              删除对话
            </button>
          </div>
        )}
      </aside>

      {/* 主聊天区 */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto px-4">
          <div className="max-w-2xl mx-auto py-4">
            {messages.length === 0 && (
              <div className="text-center pt-20 pb-8">
                <h2 className="text-2xl font-serif font-semibold text-ink mb-2">有什么可以帮你的？</h2>
                <p className="text-sm text-muted mb-8">知识查询 · 待办管理 · 定时提醒 · 笔记记录</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {['查看待办', '知识查询', '今日日程', '创建待办', '设置提醒', '今日早报'].map(h => (
                    <button
                      key={h}
                      onClick={() => quickSend(h)}
                      className="bg-white border border-border rounded-full px-4 py-2 text-[13px] text-muted hover:text-ink hover:border-accent/30 transition-all"
                    >
                      {h}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={`flex gap-2.5 mb-4 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                {/* 头像 */}
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] flex-shrink-0 font-medium ${
                  m.role === 'user'
                    ? 'bg-ink text-white'
                    : voiceMode
                      ? 'bg-accent-light text-accent'
                      : 'bg-paper text-muted'
                }`}>
                  {m.role === 'user' ? 'J' : voiceMode ? ASSISTANT_NAME[0] : 'AI'}
                </div>

                {/* 气泡 */}
                <div className={`max-w-[80%] px-3.5 py-2.5 rounded-lg text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-accent-light text-ink rounded-br-sm'
                    : 'bg-white border border-border text-ink rounded-bl-sm'
                }`}>
                  {m.role === 'bot' && m.text.trim() === '' ? (
                    <div className="flex items-center gap-1.5 text-muted py-1">
                      <span className="w-1.5 h-1.5 bg-accent/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 bg-accent/40 rounded-full animate-bounce" style={{ animationDelay: '120ms' }} />
                      <span className="w-1.5 h-1.5 bg-accent/40 rounded-full animate-bounce" style={{ animationDelay: '240ms' }} />
                    </div>
                  ) : (
                    <div className="prose prose-sm max-w-none prose-headings:text-ink prose-a:text-accent prose-code:text-ink prose-code:bg-border prose-code:px-1 prose-code:rounded-sm prose-pre:bg-ink prose-pre:text-paper prose-ul:list-disc prose-ol:list-decimal prose-table:border-collapse">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                        {m.text}
                      </ReactMarkdown>
                    </div>
                  )}
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-[10px] text-faint">{m.time}</span>
                    {m.role === 'bot' && m.text && (
                      <button
                        onClick={() => speakMessage(i, m.text)}
                        className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                          speaking === i
                            ? 'text-accent bg-accent-light'
                            : 'text-muted hover:text-ink'
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

        {/* 输入区 */}
        <div className="border-t border-border bg-white p-3">
          {/* 语音模式状态栏 */}
          {voiceMode && (
            <div className="max-w-2xl mx-auto mb-2 flex items-center gap-2 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-muted">
                说 <strong className="text-accent font-medium">{ASSISTANT_NAME}</strong> 唤醒
                {waitingCommand && <span className="text-amber-500 ml-1">，等待指令...</span>}
              </span>
            </div>
          )}
          <div className="max-w-2xl mx-auto flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder={listening ? '正在聆听...' : voiceMode ? `说"${ASSISTANT_NAME}"唤醒我...` : '输入消息，Enter 发送'}
              disabled={sending}
              className="flex-1 bg-paper border border-border rounded-md px-4 py-2.5 text-sm outline-none placeholder:text-faint focus:border-accent/40 focus:ring-2 focus:ring-accent/10 disabled:opacity-50 transition-all"
            />
            <button
              onClick={startListening}
              disabled={listening || voiceMode}
              className={`px-3 py-2.5 rounded-md text-sm border transition-colors ${
                listening
                  ? 'bg-red-50 border-red-300 text-red-600 animate-pulse'
                  : 'border-border text-muted hover:text-ink hover:bg-paper disabled:opacity-30'
              }`}
              title="语音输入"
            >
              🎤
            </button>
            <button
              onClick={toggleVoiceMode}
              className={`px-3 py-2.5 rounded-md text-sm border transition-colors font-medium ${
                voiceMode
                  ? 'bg-accent text-white border-accent'
                  : 'border-accent/30 text-accent hover:bg-accent-light'
              }`}
              title={voiceMode ? '关闭语音模式' : '开启语音模式'}
            >
              若愚
            </button>
            <button
              onClick={() => send()}
              disabled={sending}
              className="bg-ink text-white px-5 py-2.5 rounded-md text-sm font-medium hover:opacity-85 disabled:opacity-50 transition-opacity"
            >
              发送
            </button>
          </div>
          <div className="text-center text-[11px] text-faint mt-2">
            {hints.map(h => (
              <span
                key={h}
                onClick={() => quickSend(h)}
                className="cursor-pointer hover:text-ink mx-1.5 transition-colors"
              >
                {h}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
