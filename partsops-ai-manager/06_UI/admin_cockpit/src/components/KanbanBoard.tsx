import React from 'react';
import { gsap } from 'gsap';
import { Icon } from './Primitives';
import { KanbanCard } from './KanbanCard';
import { canDropOnColumn, resolveColumnDropTarget } from '../lib/stateMachine';
import { notify } from '../lib/notify';

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

interface ColumnDef {
  id: string;
  title: string;
  icon: string;
  topBarClass: string;
  iconBgClass: string;
  badgeClass: string;
  description: string;
  statuses: string[];
  /** Preferred entry/advance status when multiple legal hops map to this column */
  targetStatus: string;
}

const COLUMNS: ColumnDef[] = [
  {
    id: 'intake',
    title: 'Прием & Нормализация',
    icon: 'file-arrow-up',
    topBarClass: 'bg-blue-500',
    iconBgClass: 'bg-blue-50 text-blue-700 border-blue-200',
    badgeClass: 'bg-blue-50 text-blue-700 border-blue-200',
    description: 'Входящие запросы клиентов',
    statuses: ['NEW', 'NORMALIZING', 'PARSING', 'VIN_CHECK', 'PART_EXTRACTION', 'NEEDS_MANUAL_PARSE', 'NEEDS_CLARIFICATION'],
    targetStatus: 'NORMALIZING',
  },
  {
    id: 'matching',
    title: 'Подбор поставщиков',
    icon: 'code-fork',
    topBarClass: 'bg-cyan-500',
    iconBgClass: 'bg-cyan-50 text-cyan-700 border-cyan-200',
    badgeClass: 'bg-cyan-50 text-cyan-700 border-cyan-200',
    description: 'Поиск и ранжирование аналогов',
    statuses: ['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'MANUAL_REVIEW', 'REWORK'],
    targetStatus: 'MATCHING',
  },
  {
    id: 'approval',
    title: 'Согласование цен',
    icon: 'circle-check',
    topBarClass: 'bg-amber-500',
    iconBgClass: 'bg-amber-50 text-amber-800 border-amber-200',
    badgeClass: 'bg-amber-50 text-amber-800 border-amber-200',
    description: 'Оценка маржинальности и рисков',
    statuses: ['PRICING_REVIEW', 'READY_FOR_APPROVAL', 'FINANCE_REVIEW'],
    targetStatus: 'PRICING_REVIEW',
  },
  {
    id: 'invoicing',
    title: 'Счета & ERP Sync',
    icon: 'folder-open',
    topBarClass: 'bg-emerald-500',
    iconBgClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    description: 'Выгрузка предложений и счетов',
    statuses: [
      'APPROVED',
      'ERP_SYNCING',
      'ERP_SYNCED',
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
      'SUPPLIER_ISSUE',
      'RETURN_CASE',
    ],
    targetStatus: 'APPROVED',
  },
];

interface KanbanBoardProps {
  requests: Request[];
  onSelectRequest: (request: Request) => void;
  onRunsChanged?: () => void;
  onTransitionRequest?: (targetState: string, reason: string, requestId: string) => Promise<void>;
}

export function KanbanBoard({
  requests,
  onSelectRequest,
  onTransitionRequest,
}: KanbanBoardProps) {
  const [recentlyMoved, setRecentlyMoved] = React.useState<Set<string>>(new Set());
  const [activeDragColumn, setActiveDragColumn] = React.useState<string | null>(null);
  const [draggingRequestId, setDraggingRequestId] = React.useState<string | null>(null);
  const [pendingDropId, setPendingDropId] = React.useState<string | null>(null);
  const previous = React.useRef<Request[]>(requests);
  const boardRef = React.useRef<HTMLDivElement>(null);

  const draggingRequest = React.useMemo(
    () => (draggingRequestId ? requests.find((item) => item.request_id === draggingRequestId) ?? null : null),
    [draggingRequestId, requests],
  );

  const validColumnIds = React.useMemo(() => {
    if (!draggingRequest) return null;
    const ids = new Set<string>();
    for (const column of COLUMNS) {
      if (canDropOnColumn(draggingRequest.status, column.statuses, column.targetStatus)) {
        ids.add(column.id);
      }
    }
    return ids;
  }, [draggingRequest]);

  React.useEffect(() => {
    const oldStatuses = new Map(previous.current.map((request) => [request.request_id, request.status]));
    const moved = new Set(
      requests
        .filter((request) => oldStatuses.get(request.request_id) && oldStatuses.get(request.request_id) !== request.status)
        .map((request) => request.request_id)
    );
    previous.current = requests;
    if (!moved.size) return;
    setRecentlyMoved(moved);
    const timer = window.setTimeout(() => setRecentlyMoved(new Set()), 2000);
    return () => window.clearTimeout(timer);
  }, [requests]);

  React.useEffect(() => {
    if (!boardRef.current) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) return;

    gsap.fromTo(
      boardRef.current.querySelectorAll('.kanban-column'),
      { opacity: 0, y: 16 },
      { opacity: 1, y: 0, duration: 0.4, stagger: 0.06, ease: 'power2.out' }
    );
  }, []);

  const clearDrag = () => {
    setActiveDragColumn(null);
    setDraggingRequestId(null);
  };

  const handleDragEnter = (e: React.DragEvent, columnId: string) => {
    e.preventDefault();
    setActiveDragColumn(columnId);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    if (e.clientX < rect.left || e.clientX >= rect.right || e.clientY < rect.top || e.clientY >= rect.bottom) {
      setActiveDragColumn(null);
    }
  };

  const handleDrop = async (event: React.DragEvent, column: ColumnDef) => {
    event.preventDefault();
    const requestId = event.dataTransfer.getData('text/plain') || draggingRequestId || '';
    clearDrag();
    if (!requestId || !onTransitionRequest) return;
    if (pendingDropId === requestId) return;

    const request = requests.find((item) => item.request_id === requestId);
    if (!request) return;

    const targetState = resolveColumnDropTarget(request.status, column.statuses, column.targetStatus);
    if (!targetState) {
      notify.warn(
        `Нельзя перенести ${requestId}: нет легального перехода из ${request.status} в этап «${column.title}»`,
      );
      return;
    }

    if (targetState === request.status) {
      notify.info(`Заявка ${requestId} уже в статусе ${request.status}`);
      return;
    }

    setPendingDropId(requestId);
    try {
      await onTransitionRequest(
        targetState,
        `Перенос карточки в этап «${column.title}» → ${targetState}`,
        requestId,
      );
    } catch {
      // Errors are surfaced by handleStateTransition / notify
    } finally {
      setPendingDropId(null);
    }
  };

  return (
    <div ref={boardRef} className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3.5 w-full">
      {COLUMNS.map((column) => {
        const cards = requests.filter((request) => column.statuses.includes(request.status));
        const isDraggingOver = activeDragColumn === column.id;
        const isValidTarget =
          !draggingRequest || (validColumnIds?.has(column.id) ?? false);
        const isInvalidTarget = Boolean(draggingRequest) && !isValidTarget;
        const dropHint = !draggingRequest
          ? 'Перетащите заявку сюда'
          : isValidTarget
            ? 'Отпустите — смена статуса'
            : 'Сюда нельзя';

        return (
          <section
            key={column.id}
            data-column-id={column.id}
            data-drop-valid={isValidTarget ? 'true' : 'false'}
            onDragOver={(event) => {
              if (isInvalidTarget) return;
              event.preventDefault();
            }}
            onDragEnter={(event) => handleDragEnter(event, column.id)}
            onDragLeave={handleDragLeave}
            onDrop={(event) => {
              if (isInvalidTarget) {
                event.preventDefault();
                clearDrag();
                notify.warn(`Сюда нельзя: нет легального перехода в «${column.title}»`);
                return;
              }
              void handleDrop(event, column);
            }}
            className={`kanban-column flex flex-col rounded-xl border border-slate-200/80 bg-slate-100/60 overflow-hidden transition-all duration-150 ${
              isDraggingOver && isValidTarget
                ? 'ring-2 ring-blue-500 bg-blue-50/40 border-blue-400'
                : isDraggingOver && isInvalidTarget
                  ? 'ring-2 ring-rose-300 bg-rose-50/30 border-rose-300'
                  : isInvalidTarget
                    ? 'opacity-50'
                    : draggingRequest && isValidTarget
                      ? 'ring-1 ring-emerald-300/80 border-emerald-300/70'
                      : ''
            }`}
            aria-label={`${column.title}: ${cards.length} запросов`}
          >
            <div className={`h-1 w-full ${column.topBarClass}`} />

            <header className="border-b border-slate-200/80 bg-white/80 px-3.5 py-2.5 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border text-xs font-bold ${column.iconBgClass}`}>
                  <Icon name={column.icon} size={13} />
                </div>
                <div className="min-w-0">
                  <h3 className="truncate text-xs font-bold tracking-tight text-slate-800">
                    {column.title}
                  </h3>
                  <p className="truncate text-[10px] font-medium text-slate-400">
                    {column.description}
                  </p>
                </div>
              </div>
              <span className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[10px] font-bold ${column.badgeClass}`}>
                {cards.length}
              </span>
            </header>

            <div className="flex-1 space-y-2 p-2 min-h-[100px]">
              {cards.length > 0 ? (
                cards.map((request) => (
                  <KanbanCard
                    key={request.request_id}
                    request={request}
                    onSelectRequest={onSelectRequest}
                    isHighlighted={recentlyMoved.has(request.request_id)}
                    onDragBegin={(id) => setDraggingRequestId(id)}
                    onDragFinish={clearDrag}
                    isDropPending={pendingDropId === request.request_id}
                  />
                ))
              ) : (
                <div
                  className={`flex flex-col items-center justify-center rounded-lg border border-dashed py-6 text-center bg-white/40 ${
                    isInvalidTarget
                      ? 'border-rose-200 text-rose-400'
                      : isValidTarget && draggingRequest
                        ? 'border-emerald-300 text-emerald-600'
                        : 'border-slate-300 text-slate-400'
                  }`}
                >
                  <Icon name={column.icon} size={14} className="mb-1 opacity-60" />
                  <span className="text-[11px] font-semibold">{dropHint}</span>
                </div>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}

export default KanbanBoard;
