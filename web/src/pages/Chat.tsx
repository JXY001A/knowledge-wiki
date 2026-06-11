import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import { api } from '../api';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
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
  const chatEnd = useRef<HTMLDivElement>(null);
  const wakeRecognitionRef = useRef<any>(null);

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

  function startListening() {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event: any) => { setInput(event.results[0][0].transcript); setListening(false); };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    setListening(true);
    recognition.start();
  }

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
          command ? processVoiceCommand(command) : setWaitingCommand(true);
        } else if (waitingCommand) { processVoiceCommand(transcript); setWaitingCommand(false); }
      }
    };
    recognition.onerror = () => { if (voiceMode) setTimeout(startWakeWord, 1000); };
    recognition.onend = () => { if (voiceMode) setTimeout(startWakeWord, 500); };
    wakeRecognitionRef.current = recognition;
    recognition.start();
  }

  function stopWakeWord() {
    if (wakeRecognitionRef.current) { wakeRecognitionRef.current.stop(); wakeRecognitionRef.current = null; }
    setWaitingCommand(false);
  }

  async function processVoiceCommand(command: string) {
    if (!command.trim()) return;
    setInput(command); setSending(true);
    const now = new Date().toLocaleTimeString();
    const userMsg: ConvMsg = { role: 'user', text: `🎤 ${command}`, time: now };
    const updated = [...messages, userMsg];
    setMessages(updated);
    try {
      const resp = await fetch('/api/voice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: command, conversation_id: activeId || '' }) });
      const data = await resp.json();
      const reply = data.reply || '处理完成';
      const botMsg: ConvMsg = { role: 'bot', text: reply + (data.spoken ? ' 🔊' : ''), time: new Date().toLocaleTimeString() };
      const finalMessages = [...updated, botMsg];
      setMessages(finalMessages);
      api.saveConv({ id: activeId || undefined, title: command.slice(0, 30), messages: finalMessages.map(m => ({ role: m.role, text: m.text, time: m.time })) })
        .then(({ id }) => { if (!activeId) setActiveId(id); api.listConvs().then(setConvs); }).catch(() => {});
    } catch (err: any) {
      setMessages([...updated, { role: 'bot', text: `❌ ${err.message || '网络错误'}`, time: new Date().toLocaleTimeString() }]);
    } finally { setSending(false); }
  }

  function toggleVoiceMode() {
    if (voiceMode) { stopWakeWord(); setVoiceMode(false); }
    else { setVoiceMode(true); startWakeWord(); }
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
    const botMsg: ConvMsg = { role: 'bot', text: '  ', time: '' };
    const updated = [...messages, userMsg, botMsg];
    setMessages(updated);
    const botIndex = updated.length - 1;
    let firstToken = true;
    const ctrl = api.streamMessage(text, activeId,
      (token) => { setMessages(prev => { const next = [...prev]; if (next[botIndex]) { const cur = firstToken ? '' : next[botIndex].text; firstToken = false; next[botIndex] = { ...next[botIndex], text: cur + token, time: new Date().toLocaleTimeString() }; } return next; }); },
      (fullText) => { setSending(false); setMessages(prev => { const next = [...prev]; next[botIndex] = { ...next[botIndex], text: fullText, time: new Date().toLocaleTimeString() }; return next; }); const title = activeId ? undefined : text.slice(0, 30); api.saveConv({ id: activeId || undefined, title: title || '新对话', messages: [...updated.slice(0, -1), { role: 'bot' as const, text: fullText, time: new Date().toLocaleTimeString() }] }).then(({ id }) => { if (!activeId) setActiveId(id); api.listConvs().then(setConvs); }).catch(() => {}); },
      (err) => { setSending(false); setMessages(prev => { const next = [...prev]; next[botIndex] = { ...next[botIndex], text: `❌ ${err}`, time: new Date().toLocaleTimeString() }; return next; }); },
    );
    streamCtrl.current = ctrl;
  }

  async function newChat() { streamCtrl.current?.abort(); setActiveId(null); setMessages([]); setSending(false); }
  async function deleteConv() { if (!activeId) return; streamCtrl.current?.abort(); await api.deleteConv(activeId); setActiveId(null); setMessages([]); api.listConvs().then(setConvs); }

  function onKey(e: React.KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
  function quickSend(label: string) { send(label); }

  return (
    <div className="flex h-[calc(100vh-48px)]">
      {/* 深色侧边栏 */}
      <aside className="w-64 bg-sidebar flex flex-col flex-shrink-0">
        <div className="p-3">
          <Button onClick={newChat} variant="secondary" className="w-full justify-start">
            ＋ 新对话
          </Button>
        </div>
        <ScrollArea className="flex-1 px-2 pb-2">
          {convs.map(c => (
            <div key={c.id} onClick={() => loadConv(c.id)}
              className={cn(
                'px-3 py-2.5 rounded-lg cursor-pointer text-sm mb-0.5 transition-colors',
                c.id === activeId
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
              )}>
              <div className="truncate text-[13px]">{c.title || '新对话'}</div>
              <div className="text-[10px] text-sidebar-foreground/40 mt-0.5">{c.updated_at?.slice(0, 10)}</div>
            </div>
          ))}
          {convs.length === 0 && <p className="text-xs text-sidebar-foreground/40 text-center py-8">暂无历史对话</p>}
        </ScrollArea>
        {activeId && (
          <div className="p-3 border-t border-sidebar-border">
            <Button onClick={deleteConv} variant="ghost" size="sm" className="w-full text-xs text-muted-foreground hover:text-destructive">删除对话</Button>
          </div>
        )}
      </aside>

      {/* 主聊天区 */}
      <div className="flex-1 flex flex-col min-w-0 bg-background">
        <ScrollArea className="flex-1 px-4">
          <div className="max-w-3xl mx-auto py-4">
            {messages.length === 0 && (
              <div className="text-center pt-24 pb-8">
                <h2 className="text-2xl font-semibold text-foreground mb-2">有什么可以帮你的？</h2>
                <p className="text-sm text-muted-foreground mb-8">知识查询 · 待办管理 · 定时提醒 · 笔记记录</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {['查看待办', '知识查询', '今日日程', '创建待办', '设置提醒', '今日早报'].map(h => (
                    <Button key={h} onClick={() => quickSend(h)} variant="outline" size="sm" className="rounded-full">{h}</Button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={cn('flex gap-3 mb-6', m.role === 'user' && 'flex-row-reverse')}>
                <div className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0',
                  m.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                )}>
                  {m.role === 'user' ? '我' : 'AI'}
                </div>
                <div className={cn(
                  'max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed',
                  m.role === 'user'
                    ? 'bg-primary/10 text-foreground rounded-br-md'
                    : 'bg-muted text-foreground rounded-bl-md'
                )}>
                  {m.role === 'bot' && m.text.trim() === '' ? (
                    <div className="flex items-center gap-1.5 text-muted-foreground py-1">
                      <span className="w-2 h-2 bg-primary/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-primary/30 rounded-full animate-bounce" style={{ animationDelay: '120ms' }} />
                      <span className="w-2 h-2 bg-primary/30 rounded-full animate-bounce" style={{ animationDelay: '240ms' }} />
                    </div>
                  ) : (
                    <div className="prose prose-sm max-w-none prose-a:text-primary prose-code:bg-muted prose-code:px-1 prose-code:rounded prose-pre:bg-sidebar prose-pre:text-sidebar-foreground">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>{m.text}</ReactMarkdown>
                    </div>
                  )}
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-[10px] text-muted-foreground">{m.time}</span>
                    {m.role === 'bot' && m.text && (
                      <Button onClick={() => speakMessage(i, m.text)} variant="ghost" size="xs"
                        className={speaking === i ? 'text-primary' : 'text-muted-foreground'}>
                        {speaking === i ? '🔊' : '🔈'}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            <div ref={chatEnd} />
          </div>
        </ScrollArea>

        {/* 输入区 */}
        <div className="border-t border-border bg-background px-4 py-3">
          {voiceMode && (
            <div className="max-w-3xl mx-auto mb-2 flex items-center gap-2 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-muted-foreground">说 <strong className="text-primary">{ASSISTANT_NAME}</strong> 唤醒{waitingCommand && <span className="text-amber-500 ml-1">，等待指令...</span>}</span>
            </div>
          )}
          <div className="max-w-3xl mx-auto">
            <div className="flex items-end gap-2 bg-muted rounded-2xl px-4 py-3 border border-transparent transition-all focus-within:bg-background focus-within:border-primary/20 focus-within:ring-3 focus-within:ring-primary/10">
              <Button onClick={startListening} disabled={listening || voiceMode} variant="ghost" size="icon-sm"
                className={listening ? 'text-destructive' : 'text-muted-foreground'}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>
              </Button>
              <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey}
                placeholder={listening ? '正在聆听...' : voiceMode ? `说"${ASSISTANT_NAME}"唤醒我...` : '输入消息，Enter 发送'}
                disabled={sending}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50 py-0.5 text-foreground" />
              <Button onClick={() => send()} disabled={sending || !input.trim()} size="icon-sm">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M3.4 20.4 2 2l20 10L2 22l1.4-1.6L7 12Z"/></svg>
              </Button>
            </div>
            <div className="flex items-center justify-between mt-2">
              <Button onClick={toggleVoiceMode} variant="ghost" size="xs"
                className={voiceMode ? 'text-primary font-medium' : 'text-muted-foreground'}>
                {voiceMode ? '语音模式已开启' : '🎤 语音唤醒'}
              </Button>
              <div className="flex gap-1">
                {hints.map(h => (
                  <span key={h} onClick={() => quickSend(h)} className="text-[11px] text-muted-foreground cursor-pointer hover:text-foreground px-1.5 transition-colors">{h}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
