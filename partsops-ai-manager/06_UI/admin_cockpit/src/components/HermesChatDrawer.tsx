import React, { useEffect, useState, useRef, useCallback } from 'react';
import { apiFetch } from '../lib/api';

type SourceChip = {
  source_id: string;
  title: string;
};

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
};

type HermesChatDrawerProps = {
  activeScreen: string;
  selectedRequestId?: string;
  onNavigate?: (screenId: string, requestId?: string) => void;
};

export const HermesChatDrawer: React.FC<HermesChatDrawerProps> = ({
  activeScreen,
  selectedRequestId,
  onNavigate,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [hermesStatus, setHermesStatus] = useState<'online' | 'degraded' | 'offline'>('offline');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [selectedSourceDoc, setSelectedSourceDoc] = useState<{ title: string; content: string } | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Check Hermes Health
  const checkHealth = useCallback(async () => {
    try {
      const res = await apiFetch('/api/copilot/health');
      if (res.ok) {
        const data = await res.json();
        setHermesStatus(data.status || 'offline');
      } else {
        setHermesStatus('offline');
      }
    } catch {
      setHermesStatus('offline');
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // Initialize Conversation
  const initConversation = useCallback(async () => {
    try {
      const res = await apiFetch('/api/copilot/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Диалог с Hermes' }),
      });
      if (res.ok) {
        const data = await res.json();
        setConversationId(data.id);
        setMessages([
          {
            id: 'init-msg',
            role: 'assistant',
            content: `Привет! Я **Hermes**, твой read-only операционный помощник PartsOps.\nЧем могу помочь по текущему экрану?`,
          },
        ]);
      }
    } catch (e) {
      console.error('Failed to init conversation:', e);
    }
  }, []);

  useEffect(() => {
    if (isOpen && !conversationId) {
      initConversation();
    }
  }, [isOpen, conversationId, initConversation]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || inputMessage.trim();
    if (!query || !conversationId || isProcessing) return;

    setInputMessage('');
    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `asst-${Date.now()}`;

    // Append User Message
    const newMessages: ChatMessage[] = [
      ...messages,
      { id: userMsgId, role: 'user', content: query },
      { id: assistantMsgId, role: 'assistant', content: '', isStreaming: true, sources: [], actions: [] },
    ];
    setMessages(newMessages);
    setIsProcessing(true);

    try {
      // 1. Post Run
      const runRes = await apiFetch(`/api/copilot/conversations/${conversationId}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          context_ref: {
            screen_id: activeScreen,
            selected_request_id: selectedRequestId || undefined,
          },
        }),
      });

      if (!runRes.ok) {
        throw new Error('Не удалось запустить обработку запроса');
      }

      const runData = await runRes.json();
      const runId = runData.run_id;
      setCurrentRunId(runId);

      // 2. Stream SSE events
      const eventSource = new EventSource(`/api/copilot/runs/${runId}/events`);

      eventSource.onmessage = (event) => {
        try {
          const evtData = JSON.parse(event.data);

          if (evtData.type === 'assistant.delta') {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? { ...msg, content: msg.content + evtData.text }
                  : msg
              )
            );
          } else if (evtData.type === 'source') {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      sources: [
                        ...(msg.sources || []),
                        { source_id: evtData.source_id, title: evtData.title },
                      ],
                    }
                  : msg
              )
            );
          } else if (evtData.type === 'navigation.action') {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      actions: [...(msg.actions || []), evtData.action],
                    }
                  : msg
              )
            );
          } else if (evtData.type === 'run.completed' || evtData.type === 'run.failed') {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId ? { ...msg, isStreaming: false } : msg
              )
            );
            eventSource.close();
            setIsProcessing(false);
            setCurrentRunId(null);
          }
        } catch (e) {
          console.error('Error parsing SSE event:', e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setIsProcessing(false);
        setCurrentRunId(null);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: msg.content || 'Произошла ошибка при получении ответа от Hermes.',
                  isStreaming: false,
                }
              : msg
          )
        );
      };
    } catch (err: any) {
      setIsProcessing(false);
      setCurrentRunId(null);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: err?.message || 'Сервис Hermes недоступен.',
                isStreaming: false,
              }
            : msg
        )
      );
    }
  };

  const handleStopRun = async () => {
    if (!currentRunId) return;
    try {
      await apiFetch(`/api/copilot/runs/${currentRunId}/stop`, { method: 'POST' });
    } catch (e) {
      console.error('Failed to stop run:', e);
    }
  };

  const handleViewSource = async (sourceId: string) => {
    try {
      const res = await apiFetch(`/api/copilot/sources/${sourceId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedSourceDoc({ title: data.title, content: data.content });
      }
    } catch (e) {
      console.error('Failed to load help source:', e);
    }
  };

  const handleActionClick = (action: NavigationAction) => {
    if (onNavigate) {
      if (action.action === 'open_screen' && action.screen_id) {
        onNavigate(action.screen_id);
      } else if (action.action === 'open_request' && action.request_id) {
        onNavigate('order_details', action.request_id);
      }
    }
  };

  return (
    <>
      {/* Floating Hermes Launcher Button */}
      {!isOpen && (
        <button
          onClick={() => {
            setIsOpen(true);
            setTimeout(() => inputRef.current?.focus(), 100);
          }}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-full bg-slate-900 text-white border border-emerald-500/40 shadow-2xl hover:bg-slate-800 hover:scale-105 active:scale-95 transition-all duration-200"
          aria-label="Открыть Hermes Помощник"
        >
          <div className="relative">
            <i className="fas fa-[#fae8ff] fa-robot text-lg text-emerald-400" />
            <span
              className={`absolute -top-1 -right-1 h-3 w-3 rounded-full border-2 border-slate-900 ${
                hermesStatus === 'online'
                  ? 'bg-emerald-500'
                  : hermesStatus === 'degraded'
                  ? 'bg-amber-500'
                  : 'bg-rose-500'
              }`}
            />
          </div>
          <span className="text-sm font-bold tracking-tight">Hermes</span>
        </button>
      )}

      {/* Slide-over Hermes Drawer */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity animate-fade-in">
          <div className="w-full sm:w-[480px] h-full bg-slate-950 text-slate-100 flex flex-col border-l border-slate-800 shadow-2xl relative">
            
            {/* Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold">
                  <i className="fas fa-robot text-base" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-extrabold text-white">Hermes</h3>
                    <span
                      className={`text-[9px] font-extrabold uppercase px-2 py-0.5 rounded-full border ${
                        hermesStatus === 'online'
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : hermesStatus === 'degraded'
                          ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                          : 'bg-rose-500/20 text-rose-400 border-rose-500/30'
                      }`}
                    >
                      {hermesStatus}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400">Read-Only Copilot • PartsOps</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={initConversation}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700"
                  title="Новый диалог"
                >
                  <i className="fas fa-plus text-[10px] mr-1" /> Новый чат
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="h-8 w-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center transition-colors border border-slate-700"
                  aria-label="Закрыть"
                >
                  <i className="fas fa-xmark text-sm" />
                </button>
              </div>
            </div>

            {/* Context Chip Banner */}
            <div className="px-4 py-2 bg-emerald-950/30 border-b border-emerald-800/30 flex items-center justify-between text-[11px] text-emerald-300">
              <div className="flex items-center gap-2 truncate">
                <i className="fas fa-layer-group text-xs text-emerald-400" />
                <span>Экран: <strong className="text-white">{activeScreen}</strong></span>
                {selectedRequestId && (
                  <span className="text-slate-400">| Заказ: <strong className="text-emerald-300 font-mono">#{selectedRequestId}</strong></span>
                )}
              </div>
              <span className="text-[9px] text-emerald-400/80 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-bold">
                READ-ONLY
              </span>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs leading-relaxed" aria-live="polite">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <div
                    className={`max-w-[90%] rounded-2xl p-3.5 space-y-2 border ${
                      msg.role === 'user'
                        ? 'bg-emerald-600 text-white border-emerald-500 rounded-br-none'
                        : 'bg-slate-900 text-slate-200 border-slate-800 rounded-bl-none shadow-md'
                    }`}
                  >
                    <p className="whitespace-pre-wrap font-sans">{msg.content}</p>

                    {/* Sources Chips */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="pt-2 border-t border-slate-800 space-y-1">
                        <span className="text-[9px] uppercase font-bold text-slate-400 tracking-wider block">
                          Подтверждающие источники:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.sources.map((src) => (
                            <button
                              key={src.source_id}
                              onClick={() => handleViewSource(src.source_id)}
                              className="text-[10px] font-medium bg-slate-800 hover:bg-slate-700 text-emerald-400 px-2 py-1 rounded-md border border-slate-700 flex items-center gap-1 transition-colors"
                            >
                              <i className="fas fa-book-open text-[9px]" />
                              <span>{src.title}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Navigation Actions */}
                    {msg.actions && msg.actions.length > 0 && (
                      <div className="pt-2 border-t border-slate-800 space-y-1">
                        <span className="text-[9px] uppercase font-bold text-slate-400 tracking-wider block">
                          Рекомендуемые действия:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.actions.map((act, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleActionClick(act)}
                              className="text-[10px] font-bold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2.5 py-1 rounded-md flex items-center gap-1.5 transition-all"
                            >
                              <i className="fas fa-arrow-right text-[9px]" />
                              <span>{act.label}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              <div ref={messagesEndRef} />
            </div>

            {/* Quick Prompt Suggestions */}
            {messages.length <= 2 && !isProcessing && (
              <div className="px-4 pb-2 flex flex-wrap gap-1.5">
                {[
                  'Что можно сделать на этом экране?',
                  'Почему этот заказ заблокирован?',
                  'Объясни текущий статус',
                  'Где посмотреть подтверждения?',
                ].map((promptText, i) => (
                  <button
                    key={i}
                    onClick={() => handleSendMessage(promptText)}
                    className="text-[10px] font-semibold bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 px-2.5 py-1.5 rounded-xl transition-all"
                  >
                    {promptText}
                  </button>
                ))}
              </div>
            )}

            {/* Input Controls */}
            <div className="p-3 border-t border-slate-800 bg-slate-900/90 backdrop-blur-md">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendMessage();
                }}
                className="flex items-center gap-2"
              >
                <input
                  ref={inputRef}
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  placeholder="Спросить Hermes о функциях, статусе, блокировках..."
                  disabled={isProcessing}
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors"
                />

                {isProcessing ? (
                  <button
                    type="button"
                    onClick={handleStopRun}
                    className="px-3 py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-bold text-xs flex items-center gap-1 transition-all"
                  >
                    <i className="fas fa-stop text-[10px]" /> Stop
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!inputMessage.trim()}
                    className="px-3.5 py-2.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-slate-950 font-extrabold rounded-xl text-xs flex items-center gap-1 transition-all"
                  >
                    <i className="fas fa-paper-plane text-[10px]" />
                  </button>
                )}
              </form>
            </div>

          </div>
        </div>
      )}

      {/* Help Source Document View Modal */}
      {selectedSourceDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-5 space-y-4 text-slate-200 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <i className="fas fa-book-open text-emerald-400" />
                {selectedSourceDoc.title}
              </h3>
              <button
                onClick={() => setSelectedSourceDoc(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                <i className="fas fa-xmark" />
              </button>
            </div>
            <p className="text-xs leading-relaxed text-slate-300 whitespace-pre-wrap">
              {selectedSourceDoc.content}
            </p>
            <div className="pt-2 text-right">
              <button
                onClick={() => setSelectedSourceDoc(null)}
                className="px-4 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 transition-colors"
              >
                Понятно
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
