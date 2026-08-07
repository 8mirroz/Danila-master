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
          source: attachedFile ? attachedFile.name.split('.').pop()?.toUpperCase() || 'FILE' : 'UI_MANUAL',
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
        className="queue-collapsed-rail w-16 border-l border-line flex flex-col justify-between items-center py-4 transition-[background-color,border-color] duration-300 ease-out flex-shrink-0 select-none h-full"
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
          className="queue-collapsed-rail__footer text-ink-muted cursor-pointer"
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
      <div className="queue-rail-content flex flex-col h-full min-w-0 bg-surface-1">
        {/* Panel Header */}
        <div className="p-4 border-b border-line flex items-center justify-between bg-surface-1">
          <div className="flex items-center gap-2.5">
            <button 
              onClick={onToggleCollapse}
              aria-expanded={true}
              aria-label="Свернуть очередь заказов"
              className="w-7 h-7 rounded-full bg-surface-2 border border-line hover:bg-state-hover hover:border-[var(--text-muted)] flex items-center justify-center text-xs text-ink-secondary transition-all duration-200 shadow-sm"
              title="Свернуть очередь"
            >
              <Icon name="chevron-right" size={12} />
            </button>
            <div>
              <span className="text-[10px] text-ink-muted font-bold uppercase tracking-wider block">Обработка заказов</span>
              <h2 className="text-sm font-bold text-ink-primary">Активная очередь</h2>
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
      <div className="p-4 border-b border-line bg-surface-2 space-y-4">
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
              ? 'bg-[var(--accent-success)]/10 text-[var(--accent-success)] border-[var(--accent-success)]/30' 
              : item.tone === 'danger' 
              ? 'bg-[var(--accent-danger)]/10 text-[var(--accent-danger)] border-[var(--accent-danger)]/30' 
              : 'bg-surface-3 text-ink-secondary border-line';

            return (
              <div 
                key={item.label} 
                className={`min-w-0 flex items-center justify-center gap-1 border py-1 rounded-[10px] shadow-sm font-semibold ${badgeBg}`}
              >
                <span className={`w-1 h-1 rounded-full ${
                  item.tone === 'emerald' ? 'bg-[var(--accent-success)] animate-pulse' : item.tone === 'danger' ? 'bg-[var(--accent-danger)]' : 'bg-[var(--text-muted)]'
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
            <div className="rounded-md border border-[var(--accent-success)]/30 bg-[var(--accent-success)]/10 px-2.5 py-2 text-[11px] font-medium text-[var(--accent-success)]">
              {composerMessage}
            </div>
          )}
          {composerError && (
            <div className="rounded-md border border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10 px-2.5 py-2 text-[11px] font-medium text-[var(--accent-danger)]">
              {composerError}
            </div>
          )}
          <div className="flex items-center justify-between">
            <label className="text-[10px] text-ink-muted font-bold uppercase tracking-wider">Быстрый ввод</label>
            <span className="max-w-[58%] truncate text-right text-[9px] text-ink-muted italic">drag & drop PDF/Excel/Word</span>
          </div>
          <div className="relative">
            <textarea
              className={`w-full min-h-[66px] border rounded-[10px] p-2.5 text-xs text-ink-primary bg-surface-1 outline-none focus:border-accent-primary font-sans resize-none transition-all ${
                isDragging 
                  ? 'border-accent-primary ring-2 ring-[var(--accent-primary)] bg-accent-primary/10 border-dashed' 
                  : 'border-line'
              }`}
              placeholder="Введите текст запроса или перетащите файл (PDF, Excel, Word)..."
              rows={3}
              value={newRequestText}
              onChange={(event) => setNewRequestText(event.target.value)}
            />
            {isDragging && (
              <div className="absolute inset-0 bg-accent-primary bg-opacity-5 flex items-center justify-center pointer-events-none rounded-md">
                <div className="bg-surface-2 border border-accent-primary px-3 py-1.5 rounded-md shadow-sm text-xs font-semibold text-accent-primary flex items-center gap-1.5 animate-bounce">
                  <Icon name="file-arrow-up" size={14} /> Сбросьте файл сюда
                </div>
              </div>
            )}
          </div>

          {/* Attachment Badge */}
          {attachedFile && (
            <div className="flex items-center justify-between bg-accent-primary/10 border border-accent-primary/30 rounded px-2.5 py-1 text-[11px] font-medium text-accent-primary">
              <span className="flex items-center gap-1.5 truncate">
                <Icon name="file-arrow-up" size={13} className="text-accent-primary" />
                <span className="truncate">{attachedFile.name}</span>
                <span className="text-[9px] opacity-80">({(attachedFile.size / 1024).toFixed(1)} КБ)</span>
              </span>
              <button 
                onClick={() => { setAttachedFile(null); setNewRequestText(''); }}
                className="text-ink-muted hover:text-[var(--accent-danger)] font-bold ml-2 text-[10px]"
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
              className="queue-rail-attachment w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-[10px] border border-line bg-surface-1 hover:bg-state-hover text-ink-secondary hover:text-ink-primary cursor-pointer transition-all duration-200"
              aria-label="Загрузить файл"
              title="Загрузить файл"
            >
              <Icon name="paperclip" size={16} />
            </label>
            <ActionButton 
              variant="primary" 
              icon={attachedFile ? 'file-import' : 'paper-plane'} 
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
      <div className="px-4 py-2 bg-surface-2 border-b border-line flex items-center justify-between text-[11px] font-semibold text-ink-secondary select-none">
        <span>ЗАКАЗЫ</span>
        <button className="text-accent-primary hover:underline text-[10px] font-bold">Сортировка</button>
      </div>

      {/* Queue list container */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-app-bg">
        {requests.length === 0 ? (
          <div className="text-center py-10 bg-surface-1 border border-line rounded-md p-4">
              <Icon name="folder-open" size={24} className="mb-2 text-ink-muted" />
            <strong className="text-xs text-ink-primary block font-bold">Очередь пуста</strong>
            <p className="text-[10px] text-ink-muted leading-relaxed mt-1">Создайте новый заказ или подключите бэкенд для наполнения очереди.</p>
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
                    ? 'bg-surface-2 shadow-md border-accent-primary ring-1 ring-[var(--accent-primary)]'
                    : 'bg-surface-1 border border-line hover:border-line-strong hover:bg-surface-2'
                }`}
              >
                {isSelected && (
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-accent-primary" />
                )}

                {/* Левая часть: вводные данные заказа */}
                <div className="queue-order-main flex flex-col gap-1.5 flex-1 min-w-0">
                  <div className="queue-order-meta flex min-w-0 flex-wrap items-start gap-x-2 gap-y-1" data-testid="queue-order-meta">
                    <StatusBadge status={req.status} />
                    <span className="whitespace-nowrap pt-1 text-[10px] font-medium text-ink-muted font-mono">
                      {new Date(req.created_at).toLocaleString('ru-RU', {
                        day: '2-digit', month: '2-digit',
                        hour: '2-digit', minute: '2-digit',
                      })}
                    </span>
                  </div>

                  <h3 className="mt-1 break-words text-sm font-semibold tracking-tight text-ink-primary">
                    {req.customer_name || 'Без имени'}
                  </h3>

                  <span className="truncate text-[10px] font-mono font-bold tracking-wider text-ink-muted">
                    {req.request_id}
                  </span>
                </div>

                {/* Правая часть: 2 иконкообразных элемента (объем и стоимость) */}
                <div className="queue-order-controls flex w-14 shrink-0 flex-col gap-2" data-testid="queue-order-controls">
                  <div
                    className="flex h-7 w-full items-center justify-center gap-1 rounded-[8px] border border-line bg-surface-2 px-1.5 py-1 text-[10px] font-medium text-ink-secondary"
                    title="Примерный объем (позиций)"
                  >
                    <Icon name="folder-open" size={12} className="text-ink-muted" />
                    <span>{parts.length > 0 ? parts.length : '~'}</span>
                  </div>

                  <div
                    className="flex h-7 w-full items-center justify-center gap-1 rounded-[8px] border border-line bg-surface-2 px-1.5 py-1 text-[10px] font-medium text-ink-secondary"
                    title="Примерная стоимость"
                  >
                    <Icon name="circle-info" size={12} className="text-ink-muted" />
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
