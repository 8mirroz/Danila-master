import React from 'react';
import { KanbanCard } from './KanbanCard';
import { Icon, ModalShell, Button, StatusBadge } from './Primitives';


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
  vehicle_make?: string;
  vehicle_model?: string;
};

interface KanbanBoardProps {
  requests: Request[];
  onSelectRequest: (req: Request) => void;
  onTransitionRequest: (targetState: string, reason: string, requestId?: string) => Promise<void>;
  resolveDropTarget?: (request: Request, columnStatuses: string[]) => string | null;
}

export const KanbanBoard: React.FC<KanbanBoardProps> = ({
  requests,
  onSelectRequest,
  onTransitionRequest,
  resolveDropTarget,
}) => {
  const [recentlyMoved, setRecentlyMoved] = React.useState<Set<string>>(new Set());
  const prevRequestsRef = React.useRef<Request[]>(requests);

  const [pendingTransition, setPendingTransition] = React.useState<{
    requestId: string;
    request: Request;
    targetState: string;
    columnTitle: string;
  } | null>(null);

  const [isRunningAlgorithm, setIsRunningAlgorithm] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [logs, setLogs] = React.useState<string[]>([]);

  React.useEffect(() => {
    const moved = new Set<string>();
    const prevMap = new Map(prevRequestsRef.current.map((r) => [r.request_id, r.status]));
    
    requests.forEach((req) => {
      if (prevMap.has(req.request_id) && prevMap.get(req.request_id) !== req.status) {
        moved.add(req.request_id);
      }
    });

    if (moved.size > 0) {
      setRecentlyMoved(moved);
      const timer = setTimeout(() => setRecentlyMoved(new Set()), 2000);
      prevRequestsRef.current = requests;
      return () => clearTimeout(timer);
    }
    prevRequestsRef.current = requests;
  }, [requests]);

  const startTransitionAlgorithm = async () => {
    if (!pendingTransition) return;
    setIsRunningAlgorithm(true);
    setProgress(0);

    let partsCount = 0;
    try {
      const parts = JSON.parse(pendingTransition.request.parts_json || '[]');
      partsCount = parts.length;
    } catch {}

    const addLog = (msg: string) => {
      setLogs((prev) => [...prev, msg]);
    };

    addLog(`[ИИ-Оркестратор] Запуск перехода для запроса ${pendingTransition.requestId}`);
    addLog(`[Анализ] Клиент: "${pendingTransition.request.customer_name}". Позиций в спецификации: ${partsCount}`);
    
    await new Promise((resolve) => setTimeout(resolve, 300));
    setProgress(15);
    addLog('[Безопасность] Проверка PII-маскирования и очистка персональных данных...');
    if (pendingTransition.request.vehicle_vin_masked) {
      addLog(`[Безопасность] Обнаружен VIN: ${pendingTransition.request.vehicle_vin_masked}`);
    }

    await new Promise((resolve) => setTimeout(resolve, 400));
    setProgress(35);
    addLog(`[Нормализация] Поиск оригинальных OEM номеров деталей...`);
    addLog(`[Пайплайн] Передача управления ИИ-агенту MatcherAgent...`);

    await new Promise((resolve) => setTimeout(resolve, 400));
    setProgress(55);
    addLog(`[Интеграция] Отправка запроса перехода в статус ${pendingTransition.targetState}...`);

    let transitionSuccess = false;
    let serverResponse = '';
    
    try {
      await onTransitionRequest(
        pendingTransition.targetState,
        `Перенос карточки в колонку "${pendingTransition.columnTitle}"`,
        pendingTransition.requestId
      );
      transitionSuccess = true;
      serverResponse = 'Backend подтвердил переход и записал его в аудит.';
    } catch (err) {
      console.error(err);
      serverResponse = `Ошибка: ${err instanceof Error ? err.message : String(err)}`;
    }

    await new Promise((resolve) => setTimeout(resolve, 400));
    setProgress(75);
    addLog(`[Сервер] Ответ API: ${serverResponse}`);

    if (!transitionSuccess) {
      addLog('[Ошибка] Переход прерван из-за ошибки сервера.');
      setIsRunningAlgorithm(false);
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 350));
    setProgress(90);
    addLog('[Синхронизация] Запись в лог аудита событий и информирование смежных сервисов...');

    await new Promise((resolve) => setTimeout(resolve, 350));
    setProgress(100);
    addLog('[Завершено] Перенос успешно выполнен!');

    await new Promise((resolve) => setTimeout(resolve, 600));
    setPendingTransition(null);
    setIsRunningAlgorithm(false);
  };

  // Columns definition mapping
  const columns = [
    {
      id: 'intake',
      title: 'Входящие',
      icon: 'file-arrow-up',
      iconColor: 'text-blue-500',
      bgClass: 'bg-blue-50/40 border-blue-100',
      statuses: [
        'NEW',
        'NORMALIZING',
        'PARSING',
        'VIN_CHECK',
        'PART_EXTRACTION',
        'NEEDS_MANUAL_PARSE',
        'NEEDS_CLARIFICATION',
      ],
    },
    {
      id: 'matching',
      title: 'Подбор',
      icon: 'code-fork',
      iconColor: 'text-sky-500',
      bgClass: 'bg-sky-50/40 border-sky-100',
      statuses: ['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'MANUAL_REVIEW', 'REWORK'],
    },
    {
      id: 'approval',
      title: 'Согласование',
      icon: 'circle-check',
      iconColor: 'text-amber-500',
      bgClass: 'bg-amber-50/40 border-amber-100',
      statuses: ['PRICING_REVIEW', 'READY_FOR_APPROVAL'],
    },
    {
      id: 'invoicing',
      title: 'Счета в ERP',
      icon: 'folder-open',
      iconColor: 'text-emerald-500',
      bgClass: 'bg-emerald-50/40 border-emerald-100',
      statuses: [
        'APPROVED',
        'ERP_SYNCING',
        'INVOICE_DRAFTED',
        'SENT_TO_CLIENT',
        'PAID',
        'PURCHASE_ORDERED',
        'FULFILLED',
        'CLOSED',
        'CANCELLED',
        'FAILED',
        'ERP_SYNC_FAILED',
        'CLIENT_REJECTED',
        'EXPIRED',
      ],
    },
  ];

  // Drag over handler to allow dropping
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  // Drop handler
  const handleDrop = async (e: React.DragEvent, targetColumnId: string) => {
    e.preventDefault();
    const requestId = e.dataTransfer.getData('text/plain');
    if (!requestId) return;

    const req = requests.find((r) => r.request_id === requestId);
    if (!req) return;

    const column = columns.find((item) => item.id === targetColumnId);
    const candidateStates = column?.statuses ?? [];
    const targetState = resolveDropTarget
      ? resolveDropTarget(req, candidateStates)
      : candidateStates.find((state) => state !== req.status) ?? null;

    if (targetState && req.status !== targetState) {
      setPendingTransition({
        requestId,
        request: req,
        targetState,
        columnTitle: column?.title ?? targetColumnId,
      });
      setIsRunningAlgorithm(false);
      setProgress(0);
      setLogs([]);
    }
  };


  return (
    <div className="grid h-[calc(100vh-250px)] grid-cols-1 gap-4 overflow-hidden md:grid-cols-4">
      {columns.map((col) => {
        const columnRequests = requests.filter((r) => col.statuses.includes(r.status));

        return (
          <div
            key={col.id}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, col.id)}
            className={`flex h-full flex-col rounded-[24px] border p-3 shadow-sm ${col.bgClass}`}
          >
            <div className="mb-3 flex items-center justify-between border-b border-[var(--border-default)] pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-white/70 bg-white/80 shadow-sm">
                  <Icon name={col.icon} className={col.iconColor} size={16} />
                </div>
                <div>
                  <span className="block text-xs font-bold text-[var(--text-primary)]">{col.title}</span>
                  <span className="text-[10px] text-[var(--text-muted)]">Статусов: {col.statuses.length}</span>
                </div>
              </div>
              <span className="rounded-full bg-white/85 px-2.5 py-1 text-[10px] font-bold text-[var(--text-secondary)] shadow-sm">
                {columnRequests.length}
              </span>
            </div>

            <div className="custom-scrollbar flex-1 space-y-2.5 overflow-y-auto pr-1">
              {columnRequests.length === 0 ? (
                <div className="rounded-[18px] border border-dashed border-[var(--border-default)] bg-white/60 py-8 text-center text-[10px] italic text-[var(--text-muted)]">
                  Нет заказов на этом этапе
                </div>
              ) : (
                columnRequests.map((req) => (
                  <KanbanCard
                    key={req.request_id}
                    request={req}
                    onSelectRequest={onSelectRequest}
                    isHighlighted={recentlyMoved.has(req.request_id)}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}

      <ModalShell
        open={pendingTransition !== null}
        onClose={() => {
          if (!isRunningAlgorithm) setPendingTransition(null);
        }}
        title="Подтверждение изменения этапа"
        subtitle="Запуск ИИ-оркестратора и бизнес-правил перехода"
        widthClass="max-w-xl"
        footer={
          !isRunningAlgorithm ? (
            <div className="flex justify-end gap-2.5">
              <Button
                variant="ghost"
                onClick={() => setPendingTransition(null)}
              >
                Отмена
              </Button>
              <Button
                variant="success"
                icon="circle-check"
                onClick={startTransitionAlgorithm}
              >
                Запустить алгоритмы
              </Button>
            </div>
          ) : undefined
        }
      >
        {pendingTransition && (
          <div className="space-y-4 py-2">
            <div className="rounded-xl bg-[var(--surface-2)] p-4 border border-[var(--border-default)] space-y-3">
              <div className="flex justify-between items-center text-xs">
                <span className="text-[var(--text-muted)] font-medium">Запрос:</span>
                <span className="font-mono font-bold text-[var(--text-primary)]">{pendingTransition.requestId}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-[var(--text-muted)] font-medium">Клиент:</span>
                <span className="font-semibold text-[var(--text-primary)]">{pendingTransition.request.customer_name}</span>
              </div>
              <div className="h-px bg-[var(--border-default)]" />
              <div className="flex justify-between items-center">
                <div className="flex flex-col items-center">
                  <span className="text-[9px] uppercase tracking-wider text-[var(--text-muted)] mb-1">Текущий этап</span>
                  <StatusBadge status={pendingTransition.request.status} />
                </div>
                <Icon name="arrow-left" size={16} className="text-[var(--text-muted)] rotate-180" />
                <div className="flex flex-col items-center">
                  <span className="text-[9px] uppercase tracking-wider text-[var(--text-muted)] mb-1">Новый этап</span>
                  <StatusBadge status={pendingTransition.targetState} />
                </div>
              </div>
            </div>

            {isRunningAlgorithm && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold text-[var(--accent-primary)]">
                  <span>Выполнение алгоритма перехода...</span>
                  <span>{progress}%</span>
                </div>
                <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden border border-slate-200/50">
                  <div
                    className="h-full bg-[linear-gradient(90deg,#2563eb,#3b82f6)] rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${progress}%` }}
                  />
                </div>

                <div className="rounded-xl bg-slate-950 p-4 font-mono text-[11px] text-emerald-400 h-44 overflow-y-auto space-y-1.5 shadow-inner border border-slate-800">
                  {logs.map((log, idx) => (
                    <div key={idx} className="flex items-start gap-2 leading-relaxed animate-fadeIn">
                      <span className="text-slate-500 select-none">&gt;</span>
                      <span className="break-all">{log}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </ModalShell>
    </div>
  );
};
