import { useCallback, useEffect, useState } from 'react';
import { ActionButton, StatusBadge } from './Primitives';
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
  onToggleCollapse 
}: RightPanelProps) => {
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

  if (isCollapsed) {
    const draftCount = requests.filter(r => r.status === 'NEW' || r.status === 'NEEDS_CLARIFICATION').length;
    const approvedCount = requests.filter(r => r.status === 'APPROVED' || r.status === 'PART_EXTRACTION').length;
    
    return (
      <aside 
        className="w-16 border-l border-[var(--border-default)] bg-[var(--surface-1)]/85 backdrop-blur-md flex flex-col justify-between items-center py-4 transition-all duration-300 ease-in-out flex-shrink-0 select-none h-full"
      >
        <div className="flex flex-col items-center gap-6 w-full">
          {/* Toggle Button */}
          <button 
            onClick={onToggleCollapse}
            className="w-7 h-7 rounded-full bg-[var(--surface-2)] border border-[var(--border-default)] hover:bg-[var(--state-hover)] hover:border-[var(--text-muted)] flex items-center justify-center text-xs text-[var(--text-secondary)] transition-all duration-200 shadow-sm hover:scale-105 active:scale-95 animate-fadeIn"
            title="Развернуть очередь"
          >
            <i className="fas fa-chevron-left text-[10px]"></i>
          </button>

          {/* Refresh Button */}
          <button 
            onClick={fetchRequests}
            className="w-8 h-8 rounded-md bg-[var(--surface-2)] border border-[var(--border-default)] hover:bg-[var(--state-hover)] flex items-center justify-center text-xs text-[var(--text-secondary)] transition-all duration-200"
            title="Обновить очередь"
          >
            <i className="fas fa-rotate text-sm"></i>
          </button>

          {/* Vertical Text Label */}
          <div className="flex flex-col items-center justify-center h-48 w-full relative">
            <span className="text-[9px] font-bold uppercase tracking-widest text-[var(--text-muted)] rotate-270 whitespace-nowrap origin-center">
              Очередь заказов
            </span>
          </div>

          {/* Mini Stats Badges */}
          <div className="flex flex-col gap-3">
            <div 
              className="relative group w-8 h-8 rounded-full border border-green-200 bg-green-50 text-green-700 flex items-center justify-center font-bold text-xs cursor-help"
            >
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-500 animate-ping" />
              <span>{approvedCount.toString().padStart(2, '0')}</span>
              <div className="absolute right-10 px-2.5 py-1 rounded bg-emerald-950 text-emerald-100 text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-emerald-800 z-50 shadow-md">
                Проверено заказов: {approvedCount}
              </div>
            </div>
            
            <div 
              className="relative group w-8 h-8 rounded-full border border-slate-200 bg-slate-50 text-slate-700 flex items-center justify-center font-bold text-xs cursor-help"
            >
              <span>{draftCount.toString().padStart(2, '0')}</span>
              <div className="absolute right-10 px-2.5 py-1 rounded bg-slate-900 text-slate-100 text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity border border-slate-700 z-50 shadow-md">
                В очереди: {draftCount}
              </div>
            </div>
          </div>
        </div>

        {/* Small Triage Icon */}
        <div className="text-[var(--text-muted)] opacity-60 hover:opacity-100 cursor-pointer" onClick={onToggleCollapse} title="Развернуть очередь">
          <i className="fas fa-layer-group text-[16px]"></i>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-[340px] border-l border-[var(--border-default)] bg-[var(--surface-1)] flex-shrink-0 transition-all duration-300 ease-in-out">
      <div className="flex flex-col h-full bg-[var(--surface-1)]">
        {/* Panel Header */}
        <div className="p-4 border-b border-[var(--border-default)] flex items-center justify-between bg-[var(--surface-1)]">
          <div className="flex items-center gap-2.5">
            <button 
              onClick={onToggleCollapse}
              className="w-7 h-7 rounded-full bg-[var(--surface-2)] border border-[var(--border-default)] hover:bg-[var(--state-hover)] hover:border-[var(--text-muted)] flex items-center justify-center text-xs text-[var(--text-secondary)] transition-all duration-200 shadow-sm"
              title="Свернуть очередь"
            >
              <i className="fas fa-chevron-right text-[10px]"></i>
            </button>
            <div>
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider block">Обработка заказов</span>
              <h2 className="text-sm font-bold text-[var(--text-primary)]">Активная очередь</h2>
            </div>
          </div>
          <ActionButton 
            variant="secondary"
            icon="fa-rotate"
            onClick={fetchRequests}
            className="p-1 px-2.5"
            title="Обновить очередь"
          />
        </div>

      {/* Stats Summary & Quick Intake */}
      <div className="p-4 border-b border-[var(--border-default)] bg-[var(--surface-2)] space-y-4">
        {/* Triage inline summary */}
        <div className="flex items-center justify-between gap-2 text-[10px] select-none">
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
                className={`flex-1 flex items-center justify-center gap-1 border py-1 rounded shadow-sm font-semibold ${badgeBg}`}
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
            <span className="text-[9px] text-[var(--text-muted)] italic">drag & drop PDF/Excel/Word</span>
          </div>
          <div className="relative">
            <textarea
              className={`w-full border rounded-md p-2 text-xs text-[var(--text-primary)] bg-[var(--surface-1)] outline-none focus:border-[var(--accent-primary)] font-sans resize-none transition-all ${
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
                  <i className="fas fa-file-arrow-up"></i> Сбросьте файл сюда
                </div>
              </div>
            )}
          </div>

          {/* Attachment Badge */}
          {attachedFile && (
            <div className="flex items-center justify-between bg-blue-50 border border-blue-200 rounded px-2.5 py-1 text-[11px] font-medium text-blue-800">
              <span className="flex items-center gap-1.5 truncate">
                <i className={`fas ${
                  attachedFile.name.endsWith('.pdf') ? 'fa-file-pdf text-red-500' :
                  attachedFile.name.endsWith('.xls') || attachedFile.name.endsWith('.xlsx') ? 'fa-file-excel text-green-600' :
                  attachedFile.name.endsWith('.doc') || attachedFile.name.endsWith('.docx') ? 'fa-file-word text-blue-500' :
                  'fa-file-code text-slate-500'
                } text-[12px]`}></i>
                <span className="truncate">{attachedFile.name}</span>
                <span className="text-[9px] text-blue-600">({(attachedFile.size / 1024).toFixed(1)} КБ)</span>
              </span>
              <button 
                onClick={() => { setAttachedFile(null); setNewRequestText(''); }}
                className="text-blue-500 hover:text-red-500 font-bold ml-2 text-[10px]"
                type="button"
                title="Удалить файл"
              >
                <i className="fas fa-times"></i>
              </button>
            </div>
          )}

          <div className="flex gap-2">
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
              className="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-md border border-[var(--border-default)] bg-[var(--surface-1)] hover:bg-[var(--state-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] cursor-pointer transition-all duration-200"
              title="Загрузить файл"
            >
              <i className="fas fa-paperclip text-sm"></i>
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
            <i className="fas fa-inbox text-2xl text-[var(--text-muted)] mb-2"></i>
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
            const partNames = parts.map((part) => part.name).filter(Boolean).join(', ');

            return (
              <article
                key={req.id}
                onClick={() => onSelectRequest(req)}
                className={`border rounded-lg p-3 cursor-pointer transition-all shadow-sm flex flex-col gap-2.5 ${
                  isSelected 
                    ? 'bg-[var(--surface-1)] border-[var(--accent-primary)] ring-1 ring-[var(--accent-primary)]' 
                    : 'bg-[var(--surface-1)] border-[var(--border-default)] hover:border-[var(--text-muted)]'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="text-xs font-bold text-[var(--text-primary)] truncate">{req.customer_name}</h3>
                    <p className="text-[11px] text-[var(--text-secondary)] truncate mt-0.5 leading-normal">
                      {partNames || 'Ожидает распознавания деталей...'}
                    </p>
                  </div>
                  <StatusBadge status={req.status} />
                </div>

                <div className="flex items-center justify-between text-[10px] text-[var(--text-muted)] border-t border-[var(--border-subtle)] pt-2 font-mono">
                  <span>ID: {req.request_id}</span>
                  <span>
                    {new Date(req.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-1 text-[10px]">
                  <span className="bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded text-[var(--text-secondary)] font-mono font-semibold uppercase">{req.source}</span>
                  <button
                    className="text-[var(--accent-primary)] font-bold hover:underline"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelectRequest(req);
                    }}
                  >
                    Открыть заказ →
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  </aside>
);
};
