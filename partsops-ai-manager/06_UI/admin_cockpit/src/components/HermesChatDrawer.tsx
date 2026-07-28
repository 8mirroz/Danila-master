import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import { apiFetch } from '../lib/api';
import { consumeSseBuffer, type HermesHealth, type HermesStreamEvent } from '../lib/hermes';
import { Icon } from './Primitives';
import { useFocusTrap } from '../lib/focus';

type SourceChip = { source_id: string; title: string };

type NavigationAction = {
  action: 'open_screen' | 'open_request' | 'focus_control';
  label: string;
  screen_id?: string;
  request_id?: string;
  element_id?: string;
};

type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceChip[];
  actions?: NavigationAction[];
  isStreaming?: boolean;
  state?: 'complete' | 'failed' | 'stopped';
};

type HermesChatDrawerProps = {
  activeScreen: string;
  selectedRequestId?: string;
  onNavigate?: (screenId: string, requestId?: string) => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  embedded?: boolean;
};

const emptyHealth: HermesHealth = {
  status: 'offline',
  profile: 'partsops',
  capabilities: [],
  skills: [],
};

const statusLabel: Record<HermesHealth['status'], string> = {
  online: 'Онлайн',
  degraded: 'Ограничен',
  offline: 'Недоступен',
};

const statusTone: Record<HermesHealth['status'], string> = {
  online: 'hermes-status--online',
  degraded: 'hermes-status--degraded',
  offline: 'hermes-status--offline',
};

export const HermesChatDrawer: React.FC<HermesChatDrawerProps> = ({
  activeScreen,
  selectedRequestId,
  onNavigate,
  open: controlledOpen,
  onOpenChange,
  embedded = false,
}) => {
  const [internalOpen, setInternalOpen] = useState(false);
  const isOpen = controlledOpen ?? internalOpen;
  const setIsOpen = useCallback((open: boolean) => {
    setInternalOpen(open);
    onOpenChange?.(open);
  }, [onOpenChange]);
  const [health, setHealth] = useState<HermesHealth>(emptyHealth);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [progressLabel, setProgressLabel] = useState('Готов к работе');
  const [selectedSourceDoc, setSelectedSourceDoc] = useState<{ title: string; content: string } | null>(null);

  const drawerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  useFocusTrap(drawerRef, isOpen);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const checkHealth = useCallback(async () => {
    try {
      const res = await apiFetch('/api/copilot/health');
      const data = (await res.json().catch(() => emptyHealth)) as Partial<HermesHealth>;
      setHealth(res.ok ? { ...emptyHealth, ...data } : { ...emptyHealth, status: 'offline', error: data.error });
    } catch {
      setHealth({ ...emptyHealth, status: 'offline', error: 'Broker недоступен' });
    }
  }, []);

  useEffect(() => {
    void checkHealth();
    const interval = window.setInterval(() => void checkHealth(), 20_000);
    return () => window.clearInterval(interval);
  }, [checkHealth]);

  const initConversation = useCallback(async () => {
    try {
      const res = await apiFetch('/api/copilot/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Диалог с Hermes' }),
      });
      if (!res.ok) throw new Error('Не удалось создать защищённый контекст Hermes');
      const data = await res.json();
      setConversationId(data.id);
      setProgressLabel('Контекст экрана синхронизирован');
      setMessages([{
        id: 'init-msg',
        role: 'assistant',
        content: 'Привет! Я **Hermes**, read-only операционный помощник PartsOps.\n\nОбъясню статус, блокировки и доступные шаги по текущему экрану.',
        state: 'complete',
      }]);
    } catch (error) {
      setProgressLabel(error instanceof Error ? error.message : 'Не удалось создать диалог');
    }
  }, []);

  useEffect(() => {
    if (isOpen && !conversationId) void initConversation();
  }, [conversationId, initConversation, isOpen]);

  useLayoutEffect(() => {
    if (!isOpen || !drawerRef.current) return;
    const root = drawerRef.current;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = gsap.context(() => {
      if (reduceMotion) {
        gsap.set(root, { opacity: 1, x: 0, y: 0 });
        return;
      }
      gsap.fromTo(root, { opacity: 0, x: 26 }, { opacity: 1, x: 0, duration: 0.36, ease: 'power3.out' });
      gsap.fromTo('[data-hermes-stagger]', { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.28, ease: 'power3.out', stagger: 0.05, delay: 0.08 });
    }, root);
    return () => ctx.revert();
  }, [isOpen]);

  const updateAssistant = useCallback((assistantMsgId: string, update: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((msg) => msg.id === assistantMsgId ? { ...msg, ...update } : msg));
  }, []);

  const applyStreamEvent = useCallback((event: HermesStreamEvent, assistantMsgId: string) => {
    if (event.type === 'assistant.delta') {
      setMessages((prev) => prev.map((msg) => msg.id === assistantMsgId ? { ...msg, content: msg.content + event.text } : msg));
    } else if (event.type === 'source') {
      setMessages((prev) => prev.map((msg) => msg.id === assistantMsgId ? { ...msg, sources: [...(msg.sources ?? []), { source_id: event.source_id, title: event.title }] } : msg));
    } else if (event.type === 'navigation.action') {
      const action = event.action as NavigationAction;
      setMessages((prev) => prev.map((msg) => msg.id === assistantMsgId ? { ...msg, actions: [...(msg.actions ?? []), action] } : msg));
    } else if (event.type === 'run.progress') {
      setProgressLabel(event.detail || event.label || 'Hermes анализирует контекст');
    } else if (event.type === 'run.completed') {
      setProgressLabel('Ответ подтверждён');
      updateAssistant(assistantMsgId, { isStreaming: false, state: 'complete' });
    } else if (event.type === 'run.failed') {
      setProgressLabel(event.message || 'Hermes завершил запрос с ошибкой');
      updateAssistant(assistantMsgId, { isStreaming: false, state: 'failed', content: event.message || 'Hermes не смог подтвердить ответ по доступным данным.' });
    } else if (event.type === 'run.stopped') {
      setProgressLabel('Запрос остановлен оператором');
      updateAssistant(assistantMsgId, { isStreaming: false, state: 'stopped', content: 'Запрос остановлен. Можно повторить его после проверки контекста.' });
    }
  }, [updateAssistant]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || inputMessage).trim();
    if (!query || !conversationId || isProcessing) return;

    setInputMessage('');
    setProgressLabel('Подготавливаем защищённый контекст');
    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: query, state: 'complete' },
      { id: assistantMsgId, role: 'assistant', content: '', isStreaming: true, sources: [], actions: [] },
    ]);
    setIsProcessing(true);
    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      const runRes = await apiFetch(`/api/copilot/conversations/${conversationId}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          context_ref: { screen_id: activeScreen, selected_request_id: selectedRequestId || undefined },
        }),
        signal: abortController.signal,
      });
      if (!runRes.ok) {
        const errorData = await runRes.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Не удалось запустить обработку запроса');
      }

      const runData = await runRes.json();
      setCurrentRunId(runData.run_id);
      setProgressLabel('Hermes подключает поток событий');
      const streamRes = await apiFetch(`/api/copilot/runs/${runData.run_id}/events`, { signal: abortController.signal });
      if (!streamRes.ok || !streamRes.body) throw new Error('Не удалось установить поток Hermes');

      const reader = streamRes.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let terminalEvent = false;
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const consumed = consumeSseBuffer(buffer);
        buffer = consumed.remainder;
        for (const event of consumed.events) {
          applyStreamEvent(event, assistantMsgId);
          terminalEvent = terminalEvent || event.type === 'run.completed' || event.type === 'run.failed' || event.type === 'run.stopped';
        }
        if (done) break;
      }
      if (!terminalEvent && !abortController.signal.aborted) {
        updateAssistant(assistantMsgId, { isStreaming: false, state: 'failed', content: 'Поток Hermes завершился без подтверждённого terminal-события.' });
      }
    } catch (error) {
      if (!abortController.signal.aborted) {
        const message = error instanceof Error ? error.message : 'Hermes временно недоступен';
        setProgressLabel(message);
        updateAssistant(assistantMsgId, { isStreaming: false, state: 'failed', content: message });
      }
    } finally {
      abortRef.current = null;
      setCurrentRunId(null);
      setIsProcessing(false);
    }
  };

  const handleStopRun = useCallback(async () => {
    const runId = currentRunId;
    if (!runId) return;
    try {
      await apiFetch(`/api/copilot/runs/${runId}/stop`, { method: 'POST' });
    } finally {
      abortRef.current?.abort();
      setProgressLabel('Останавливаем upstream Hermes');
    }
  }, [currentRunId]);

  const closeDrawer = useCallback(() => {
    if (isProcessing) void handleStopRun();
    abortRef.current?.abort();
    setIsOpen(false);
  }, [handleStopRun, isProcessing, setIsOpen]);

  const handleViewSource = async (sourceId: string) => {
    const res = await apiFetch(`/api/copilot/sources/${sourceId}`);
    if (res.ok) {
      const data = await res.json();
      setSelectedSourceDoc({ title: data.title, content: data.content });
    }
  };

  const handleActionClick = (action: NavigationAction) => {
    if (action.action === 'open_screen' && action.screen_id) onNavigate?.(action.screen_id);
    if (action.action === 'open_request' && action.request_id) onNavigate?.('order_details', action.request_id);
  };

  const resizeInput = (element: HTMLTextAreaElement) => {
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 132)}px`;
  };

  return (
    <>
      {!isOpen && controlledOpen === undefined && (
        <button
          data-testid="hermes-launcher"
          onClick={() => { setIsOpen(true); window.setTimeout(() => inputRef.current?.focus(), 120); }}
          className="hermes-launcher fixed bottom-6 right-6 z-[80] flex items-center gap-3 rounded-full px-4 py-3 text-white transition-transform duration-200 hover:-translate-y-1 active:scale-95"
          aria-label="Открыть Hermes Помощник"
        >
          <span className="hermes-launcher__icon relative"><Icon name="robot" size={18} weight="duotone" /><span className={`hermes-health-dot ${statusTone[health.status]}`} /></span>
          <span className="text-sm font-bold tracking-tight">Hermes</span>
          <span className="sr-only">{statusLabel[health.status]}</span>
        </button>
      )}

      {isOpen && (
        <div className={embedded ? 'hermes-embedded-shell' : 'hermes-overlay fixed inset-0 z-[80] flex justify-end'} onClick={embedded ? undefined : closeDrawer}>
          <div ref={drawerRef} data-testid="hermes-drawer" role={embedded ? 'region' : 'dialog'} aria-modal={embedded ? undefined : true} aria-label="Hermes — read-only помощник" className={embedded ? 'hermes-embedded-panel relative flex h-full w-full flex-col text-slate-100' : 'hermes-drawer relative flex h-full w-full flex-col text-slate-100'} onClick={(event) => event.stopPropagation()} onKeyDown={(event) => { if (event.key === 'Escape') closeDrawer(); }}>
            <div data-hermes-motion className="hermes-drawer__header flex items-center justify-between gap-3 px-5 py-4">
              <div className="flex min-w-0 items-center gap-3">
                <div className="hermes-avatar"><Icon name="robot" size={19} weight="duotone" /></div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2"><h3 className="truncate text-sm font-extrabold text-white">Hermes</h3><span className={`hermes-status ${statusTone[health.status]}`}><span className="hermes-status__dot" />{statusLabel[health.status]}</span></div>
                  <span className="text-[10px] text-slate-400">PartsOps Copilot · профиль {health.profile}</span>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button onClick={() => { setConversationId(null); setMessages([]); }} className="hermes-control-button px-2.5" title="Новый диалог"><Icon name="plus" size={13} /> Новый чат</button>
                <button onClick={closeDrawer} className="hermes-control-button h-8 w-8" aria-label="Закрыть Hermes"><Icon name="x-mark" size={15} /></button>
              </div>
            </div>

            <div data-hermes-stagger className="hermes-context mx-4 mt-4 flex items-center justify-between gap-3 rounded-2xl px-3.5 py-3">
              <div className="flex min-w-0 items-center gap-2 text-[11px] text-emerald-200"><Icon name="wave-square" size={14} className="shrink-0 text-emerald-400" /><span className="truncate">Экран <strong className="text-white">{activeScreen}</strong>{selectedRequestId && <> · заказ <strong className="font-mono text-emerald-300">#{selectedRequestId}</strong></>}</span></div>
              <span className="hermes-readonly shrink-0">READ-ONLY</span>
            </div>

            <div className="mx-4 mt-3 flex items-center justify-between text-[10px] text-slate-500"><span className="flex items-center gap-1.5"><span className={`hermes-health-dot ${statusTone[health.status]}`} />{progressLabel}</span><span>{health.capabilities.length ? `${health.capabilities.length} capabilities` : 'Проверка канала'}</span></div>

            <div className="hermes-messages flex-1 space-y-4 overflow-y-auto px-4 py-5" aria-live="polite">
              {messages.map((msg) => (
                <div key={msg.id} data-hermes-stagger className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div className={`hermes-message max-w-[92%] space-y-2 rounded-2xl p-3.5 ${msg.role === 'user' ? 'hermes-message--user rounded-br-md' : 'hermes-message--assistant rounded-bl-md'}`}>
                    <p className="whitespace-pre-wrap text-xs leading-relaxed">{msg.content || (msg.isStreaming ? 'Hermes формирует подтверждённый ответ…' : '')}</p>
                    {msg.isStreaming && <span className="hermes-stream-caret" aria-label="Ответ передаётся" />}
                    {msg.sources && msg.sources.length > 0 && <div className="hermes-message__section"><span className="hermes-eyebrow">Источники подтверждения</span><div className="flex flex-wrap gap-1.5">{msg.sources.map((src) => <button key={src.source_id} onClick={() => void handleViewSource(src.source_id)} className="hermes-chip"><Icon name="book-open" size={11} />{src.title}</button>)}</div></div>}
                    {msg.actions && msg.actions.length > 0 && <div className="hermes-message__section"><span className="hermes-eyebrow">Безопасные действия</span><div className="flex flex-wrap gap-1.5">{msg.actions.map((action, index) => <button key={`${action.action}-${index}`} onClick={() => handleActionClick(action)} className="hermes-action-chip"><Icon name="arrow-right" size={11} />{action.label}</button>)}</div></div>}
                    {msg.state === 'failed' && <div className="flex items-center gap-1.5 text-[10px] text-rose-300"><Icon name="warning" size={12} />Проверьте статус Hermes и повторите запрос.</div>}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {messages.length <= 1 && !isProcessing && <div data-hermes-stagger className="flex flex-wrap gap-1.5 px-4 pb-3">{['Что можно сделать на этом экране?', 'Почему этот заказ заблокирован?', 'Объясни текущий статус', 'Где посмотреть подтверждения?'].map((prompt) => <button key={prompt} onClick={() => void handleSendMessage(prompt)} className="hermes-prompt-chip">{prompt}</button>)}</div>}

            <div className="hermes-composer px-4 pb-4 pt-3">
              <form onSubmit={(event) => { event.preventDefault(); void handleSendMessage(); }} className="hermes-input-shell">
                <textarea ref={inputRef} rows={1} value={inputMessage} disabled={isProcessing} onChange={(event) => { setInputMessage(event.target.value); resizeInput(event.currentTarget); }} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); void handleSendMessage(); } }} placeholder="Спросить Hermes о функциях, статусе, блокировках…" aria-label="Сообщение Hermes" />
                {isProcessing ? <button type="button" onClick={() => void handleStopRun()} className="hermes-stop-button" aria-label="Остановить запрос"><Icon name="stop" size={14} /> Стоп</button> : <button type="submit" disabled={!inputMessage.trim()} className="hermes-send-button" aria-label="Отправить сообщение"><Icon name="paper-plane" size={15} weight="bold" /></button>}
              </form>
              <div className="mt-2 flex items-center justify-between px-1 text-[9px] text-slate-600"><span>Ответы основаны на серверном контексте и справке</span><span>⌘/Ctrl + Enter</span></div>
            </div>
          </div>
        </div>
      )}

      {selectedSourceDoc && <div className="hermes-source-overlay fixed inset-0 z-[90] flex items-center justify-center p-4" onClick={() => setSelectedSourceDoc(null)}><div className="hermes-source-card w-full max-w-lg rounded-2xl p-5 text-slate-200" onClick={(event) => event.stopPropagation()}><div className="flex items-center justify-between border-b border-slate-800 pb-3"><h3 className="flex items-center gap-2 text-sm font-bold text-white"><Icon name="book-open" size={15} className="text-emerald-400" />{selectedSourceDoc.title}</h3><button onClick={() => setSelectedSourceDoc(null)} aria-label="Закрыть источник"><Icon name="x-mark" size={15} /></button></div><p className="whitespace-pre-wrap pt-4 text-xs leading-relaxed text-slate-300">{selectedSourceDoc.content}</p></div></div>}
    </>
  );
};
