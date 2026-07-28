import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import { ActionButton, Icon, StatusBadge, RightQueueRail } from './Primitives';
import { apiFetch, uploadAttachment } from '../lib/api';

type Request = {
  id: number;
  request_id: string;
  source: string;
  status: string;
  customer_name: string;
  created_at: string;
  parts_json: string;
  customer_phone_masked?: string;
  customer_email_masked?: string;
  vehicle_vin_masked?: string;
  priority?: string;
};

type RightPanelProps = {
  requests: Request[];
  fetchRequests: () => Promise<void>;
  selectedRequestId: string | null;
  onSelectRequest: (req: Request) => void;
  fetchTrigger: number;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  drawerOpen?: boolean;
  onCloseDrawer?: () => void;
};

const triageStats = [
  { label: 'Черновик', value: '05', tone: 'neutral' as const },
  { label: 'Проверен', value: '08', tone: 'emerald' as const },
  { label: 'Отклонен', value: '02', tone: 'danger' as const },
];

export const RightPanel = ({ 
  requests, 
  fetchRequests, 
  selectedRequestId, 
  onSelectRequest, 
  fetchTrigger, 
  isCollapsed, 
  onToggleCollapse,
  drawerOpen = false,
  onCloseDrawer,
}: RightPanelProps) => {
  const collapsedRailRef = useRef<HTMLElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [newRequestText, setNewRequestText] = useState('');
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [composerMessage, setComposerMessage] = useState<string | null>(null);
  const [composerError, setComposerError] = useState<string | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragging(true);
    } else if (e.type === "dragleave") {
      setIsDragging(false);
    }
  };

  const handleSelectedFile = (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    const allowed = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'json', 'csv'];
    
    if (allowed.includes(ext || '')) {
      setComposerError(null);
      setAttachedFile(file);
      if (ext === 'txt' || ext === 'json') {
        const reader = new FileReader();
        reader.onload = (event) => {
          if (event.target?.result) {
            setNewRequestText(event.target.result as string);
          }
        };
        reader.readAsText(file);
      } else {
        setNewRequestText(`[Файл: ${file.name}] Распознавание спецификации и деталей запчастей...`);
      }
    } else {
      setComposerError("Разрешены только файлы PDF, Word (doc/docx), Excel (xls/xlsx), TXT, JSON или CSV");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const submitRequest = useCallback(async () => {
    if (!newRequestText && !attachedFile) return;
    setLoading(true);
    setComposerError(null);
    setComposerMessage(null);
    try {
      // If there's a file, upload it first
      if (attachedFile) {
        setComposerMessage('Загрузка файла...');
        await uploadAttachment(attachedFile);
        // artifact_id returned from backend, but we don't need it for request creation
        // it's linked to the request via Request-Id header during upload
        setComposerMessage('Файл загружен. Создание заказа...');
      }
      
      const res = await apiFetch('/api/requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: attachedFile ? attachedFile.name.split('.').pop()?.toUpperCase() || 'FILE' : 'UI_MOCK',
          text: newRequestText || `[Файл: ${attachedFile?.name}] Распознавание спецификации и деталей запчастей...`,
          customer_name: 'Постоянный клиent',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        onSelectRequest(data.request);
        setAttachedFile(null);
        setComposerMessage(`Заказ ${data.request.request_id} добавлен в активную очередь.`);
      } else {
        const errorText = await res.text();
        setComposerError(errorText || `Ошибка создания запроса (${res.status})`);
      }
      setNewRequestText('');
      void fetchRequests();
    } catch (error) {
      console.error('Error submitting', error);
      if (error instanceof Error && error.name === 'ApiError') {
        setComposerError(`Ошибка: ${error.message}`);
      } else {
        setComposerError('Не удалось отправить запрос. Проверьте backend и повторите.');
      }
    } finally {
      setLoading(false);
    }
  }, [attachedFile, fetchRequests, newRequestText, onSelectRequest]);

  useEffect(() => {
    void fetchRequests();
  }, [fetchRequests, fetchTrigger]);

  useLayoutEffect(() => {
    if (!isCollapsed || !collapsedRailRef.current) return;

    const rail = collapsedRailRef.current;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = gsap.context(() => {
      if (reduceMotion) {
        gsap.set('[data-queue-rail-reveal]', { opacity: 1, y: 0 });
        return;
      }

      gsap.fromTo(
        '[data-queue-rail-reveal]',
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: 0.28, ease: 'power3.out', stagger: 0.045 }
      );
    }, rail);

    return () => ctx.revert();
  }, [isCollapsed]);

  if (isCollapsed) {
    const draftCount = requests.filter(r => r.status === 'NEW' || r.status === 'NEEDS_CLARIFICATION').length;
    const approvedCount = requests.filter(r => r.status === 'APPROVED' || r.status === 'PART_EXTRACTION').length;
    
    return (
      <aside
        ref={collapsedRailRef}
        aria-label="Скрытая очередь заказов"
        className="queue-collapsed-rail w-16 border-l border-[var(--border-default)] flex flex-col justify-between items-center py-4 transition-[background-color,border-color] duration-300 ease-out flex-shrink-0 select-none h-full"
      >
        <div className="flex flex-col items-center gap-5 w-full">
          {/* Toggle Button */}
          <button
            onClick={onToggleCollapse}
            aria-expanded={false}
            aria-label="Развернуть очередь заказов"
            data-queue-rail-reveal
            className="queue-collapsed-rail__toggle w-8 h-8 rounded-full border flex items-center justify-center text-xs transition-transform duration-200 hover:scale-105 active:scale-95"
            title="Развернуть очередь"
          >
            <Icon name="chevron-left" size={12} />
          </button>

          {/* Refresh Button */}
          <button
            onClick={fetchRequests}
            aria-label="Обновить очередь заказов"
            data-queue-rail-reveal
            className="queue-collapsed-rail__refresh w-9 h-9 rounded-xl border flex items-center justify-center text-xs transition-transform duration-200 hover:-rotate-12 active:scale-95"
            title="Обновить очередь"
          >
            <Icon name="rotate" size={14} />
          </button>

          {/* Vertical Text Label */}
          <div className="flex flex-col items-center justify-center h-48 w-full relative" data-queue-rail-reveal>
            <span className="queue-collapsed-rail__label text-[9px] font-bold uppercase tracking-[0.22em] whitespace-nowrap origin-center">
              Очередь заказов
            </span>
          </div>

          {/* Mini Stats Badges */}
          <div className="flex flex-col gap-3" data-queue-rail-reveal>
            <div
              aria-label={`Проверено заказов: ${approvedCount}`}
              className="queue-collapsed-rail__badge relative group w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs cursor-help"
            >
              <span className="queue-collapsed-rail__pulse absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full" />
              <span>{approvedCount.toString().padStart(2, '0')}</span>
              <div className="queue-rail-tooltip absolute right-11 px-2.5 py-1.5 rounded-lg text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                Проверено заказов: {approvedCount}
              </div>
            </div>

            <div
              aria-label={`В очереди: ${draftCount}`}
              className="queue-collapsed-rail__badge queue-collapsed-rail__badge--muted relative group w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs cursor-help"
            >
              <span>{draftCount.toString().padStart(2, '0')}</span>
              <div className="queue-rail-tooltip absolute right-11 px-2.5 py-1.5 rounded-lg text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none z-50">
                В очереди: {draftCount}
              </div>
            </div>
          </div>
        </div>

        {/* Small Triage Icon */}
        <button
          type="button"
          aria-label="Развернуть очередь заказов"
          data-queue-rail-reveal
          className="queue-collapsed-rail__footer text-[var(--text-muted)] cursor-pointer"
          onClick={onToggleCollapse}
          title="Развернуть очередь"
        >
          <Icon name="list" size={17} />
        </button>
      </aside>
    );
  }

  return (
    <RightQueueRail drawerOpen={drawerOpen} onCloseDrawer={onCloseDrawer}>
      <div className="queue-rail-content flex flex-col h-full min-w-0 bg-[var(--surface-1)]">
        {/* Panel Header */}
        <div className="p-4 border-b border-[var(--border-default)] flex items-center justify-between bg-[var(--surface-1)]">
          <div className="flex items-center gap-2.5">
            <button 
              onClick={onToggleCollapse}
              aria-expanded={true}
              aria-label="Свернуть очередь заказов"
              className="w-7 h-7 rounded-full bg-[var(--surface-2)] border border-[var(--border-default)] hover:bg-[var(--state-hover)] hover:border-[var(--text-muted)] flex items-center justify-center text-xs text-[var(--text-secondary)] transition-all duration-200 shadow-sm"
              title="Свернуть очередь"
            >
              <Icon name="chevron-right" size={12} />
            </button>
            <div>
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider block">Обработка заказов</span>
              <h2 className="text-sm font-bold text-[var(--text-primary)]">Активная очередь</h2>
            </div>
          </div>
          <ActionButton 
            variant="secondary"
            icon="rotate"
            onClick={fetchRequests}
            className="p-1 px-2.5"
            title="Обновить очередь"
          />
        </div>

      {/* Stats Summary & Quick Intake */}
      <div className="p-4 border-b border-[var(--border-default)] bg-[var(--surface-2)] space-y-4">
        {/* Triage inline summary */}
        <div className="grid grid-cols-3 gap-2 text-[10px] select-none">
          {triageStats.map((item) => {
            const displayLabel = item.label === 'Черновик' ? 'Черн.' : item.label === 'Проверен' ? 'Пров.' : 'Откл.';
            const count = item.label === 'Черновик' 
              ? requests.filter(r => r.status === 'NEW' || r.status === 'NEEDS_CLARIFICATION').length.toString().padStart(2, '0')
              : item.label === 'Проверен'
              ? requests.filter(r => r.status === 'APPROVED' || r.status === 'PART_EXTRACTION').length.toString().padStart(2, '0')
              : requests.filter(r => r.status === 'Отклонен' || r.status === 'CANCELLED' || r.status === 'SUPPLIER_ISSUE').length.toString().padStart(2, '0');
            
            const badgeBg = item.tone === 'emerald' 
              ? 'bg-green-50 text-green-700 border-green-200' 
              : item.tone === 'danger' 
              ? 'bg-red-50 text-red-700 border-red-200' 
              : 'bg-slate-50 text-slate-600 border-slate-200';

            return (
              <div 
                key={item.label} 
                className={`min-w-0 flex items-center justify-center gap-1 border py-1 rounded-[10px] shadow-sm font-semibold ${badgeBg}`}
              >
                <span className={`w-1 h-1 rounded-full ${
                  item.tone === 'emerald' ? 'bg-green-500 animate-pulse' : item.tone === 'danger' ? 'bg-red-500' : 'bg-slate-400'
                }`} />
                <span>{displayLabel}</span>
                <span className="font-bold font-mono">{count}</span>
              </div>
            );
          })}
        </div>

        {/* Quick Intake Composer */}
        <div 
          className="flex flex-col gap-2"
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
        >
          {composerMessage && (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-2 text-[11px] font-medium text-emerald-700">
              {composerMessage}
            </div>
          )}
          {composerError && (
            <div className="rounded-md border border-rose-200 bg-rose-50 px-2.5 py-2 text-[11px] font-medium text-rose-700">
              {composerError}
            </div>
          )}
          <div className="flex items-center justify-between">
            <label className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Быстрый ввод</label>
            <span className="max-w-[58%] truncate text-right text-[9px] text-[var(--text-muted)] italic">drag & drop PDF/Excel/Word</span>
          </div>
          <div className="relative">
            <textarea
              className={`w-full min-h-[66px] border rounded-[10px] p-2.5 text-xs text-[var(--text-primary)] bg-[var(--surface-1)] outline-none focus:border-[var(--accent-primary)] font-sans resize-none transition-all ${
                isDragging 
                  ? 'border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)] bg-blue-50/30 border-dashed' 
                  : 'border-[var(--border-default)]'
              }`}
              placeholder="Введите текст запроса или перетащите файл (PDF, Excel, Word)..."
              rows={3}
              value={newRequestText}
              onChange={(event) => setNewRequestText(event.target.value)}
            />
            {isDragging && (
              <div className="absolute inset-0 bg-[var(--accent-primary)] bg-opacity-5 flex items-center justify-center pointer-events-none rounded-md">
                <div className="bg-white border border-[var(--accent-primary)] px-3 py-1.5 rounded-md shadow-sm text-xs font-semibold text-[var(--accent-primary)] flex items-center gap-1.5 animate-bounce">
                  <Icon name="file-arrow-up" size={14} /> Сбросьте файл сюда
                </div>
              </div>
            )}
          </div>

          {/* Attachment Badge */}
          {attachedFile && (
            <div className="flex items-center justify-between bg-blue-50 border border-blue-200 rounded px-2.5 py-1 text-[11px] font-medium text-blue-800">
              <span className="flex items-center gap-1.5 truncate">
                <Icon name="file-arrow-up" size={13} className="text-[var(--accent-primary)]" />
                <span className="truncate">{attachedFile.name}</span>
                <span className="text-[9px] text-blue-600">({(attachedFile.size / 1024).toFixed(1)} КБ)</span>
              </span>
              <button 
                onClick={() => { setAttachedFile(null); setNewRequestText(''); }}
                className="text-blue-500 hover:text-red-500 font-bold ml-2 text-[10px]"
                type="button"
                title="Удалить файл"
              >
                <Icon name="x-mark" size={12} />
              </button>
            </div>
          )}

          <div className="flex min-w-0 gap-2">
            <input 
              type="file" 
              id="right-panel-file-upload" 
              className="hidden" 
              accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.json,.csv"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleSelectedFile(e.target.files[0]);
                }
              }}
            />
            <label 
              htmlFor="right-panel-file-upload"
              className="queue-rail-attachment w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-[10px] border border-[var(--border-default)] bg-[var(--surface-1)] hover:bg-[var(--state-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer transition-all duration-200"
              aria-label="Загрузить файл"
              title="Загрузить файл"
            >
              <Icon name="paperclip" size={16} />
            </label>
            <ActionButton 
              variant="primary" 
              icon={attachedFile ? "fa-file-import" : "fa-paper-plane"} 
              loading={loading}
              disabled={!newRequestText.trim()}
              onClick={submitRequest}
              className="flex-1"
            >
              {attachedFile ? "Распознать файл" : "Отправить на обработку ИИ"}
            </ActionButton>
          </div>
        </div>
      </div>

      {/* Queue items section */}
      <div className="px-4 py-2 bg-[var(--surface-2)] border-b border-[var(--border-default)] flex items-center justify-between text-[11px] font-semibold text-[var(--text-secondary)] select-none">
        <span>ЗАКАЗЫ</span>
        <button className="text-[var(--accent-primary)] hover:underline text-[10px] font-bold">Сортировка</button>
      </div>

      {/* Queue list container */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-[var(--bg-app)]">
        {requests.length === 0 ? (
          <div className="text-center py-10 bg-[var(--surface-1)] border border-[var(--border-default)] rounded-md p-4">
              <Icon name="folder-open" size={24} className="mb-2 text-[var(--text-muted)]" />
            <strong className="text-xs text-[var(--text-primary)] block font-bold">Очередь пуста</strong>
            <p className="text-[10px] text-[var(--text-muted)] leading-relaxed mt-1">Создайте новый заказ или подключите бэкенд для наполнения очереди.</p>
          </div>
        ) : (
          requests.map((req) => {
            let parts: Array<{ name?: string }> = [];
            try {
              parts = JSON.parse(req.parts_json || '[]');
            } catch {
              parts = [];
            }

            const isSelected = selectedRequestId === req.request_id;

            return (
              <article
                key={req.id}
                onClick={() => onSelectRequest(req)}
                className={`queue-order-card group relative overflow-hidden rounded-xl p-3.5 cursor-pointer transition-all duration-300 flex justify-between items-start gap-3 ${
                  isSelected 
                    ? 'bg-white shadow-[0_8px_24px_-8px_rgba(0,0,0,0.12)] border-[var(--accent-primary)] ring-1 ring-[var(--accent-primary)]'
                    : 'bg-[var(--surface-1)] border border-[var(--border-default)] hover:border-slate-300 hover:shadow-md'
                }`}
              >
                {isSelected && (
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-[var(--accent-primary)]" />
                )}

                {/* Левая часть: вводные данные заказа */}
                <div className="queue-order-main flex flex-col gap-1.5 flex-1 min-w-0">
                  <div className="queue-order-meta flex min-w-0 flex-wrap items-start gap-x-2 gap-y-1" data-testid="queue-order-meta">
                    <StatusBadge status={req.status} />
                    <span className="whitespace-nowrap pt-1 text-[10px] font-medium text-slate-400 font-mono">
                      {new Date(req.created_at).toLocaleString('ru-RU', {
                        day: '2-digit', month: '2-digit',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </span>
                  </div>

                  <h3 className="mt-1 break-words text-sm font-semibold tracking-tight text-slate-800">
                    {req.customer_name || 'Без имени'}
                  </h3>

                  <span className="truncate text-[10px] font-mono font-bold tracking-wider text-slate-400">
                    {req.request_id}
                  </span>
                </div>

                {/* Правая часть: 2 иконкообразных элемента (объем и стоимость) */}
                <div className="queue-order-controls flex w-14 shrink-0 flex-col gap-2" data-testid="queue-order-controls">
                  <div
                    className="flex h-7 w-full items-center justify-center gap-1 rounded-[8px] border border-slate-100 bg-slate-50 px-1.5 py-1 text-[10px] font-medium text-slate-600"
                    title="Примерный объем (позиций)"
                  >
                    <Icon name="folder-open" size={12} className="text-slate-400" />
                    <span>{parts.length > 0 ? parts.length : '~'}</span>
                  </div>

                  <div
                    className="flex h-7 w-full items-center justify-center gap-1 rounded-[8px] border border-slate-100 bg-slate-50 px-1.5 py-1 text-[10px] font-medium text-slate-600"
                    title="Примерная стоимость"
                  >
                    <Icon name="circle-info" size={12} className="text-slate-400" />
                    <span>—</span>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  </RightQueueRail>
);
};
