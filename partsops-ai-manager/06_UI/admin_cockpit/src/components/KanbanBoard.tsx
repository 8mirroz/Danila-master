import React from 'react';
import { gsap } from 'gsap';
import { Icon } from './Primitives';
import { KanbanCard } from './KanbanCard';
import { PipelineRunDialog } from './PipelineRunDialog';

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
}

const COLUMNS: ColumnDef[] = [
  {
    id: 'intake',
    title: 'Прием & Нормализация',
    icon: 'file-arrow-up',
    topBarClass: 'bg-accent-primary',
    iconBgClass: 'bg-blue-50 text-accent-primary border-blue-200',
    badgeClass: 'bg-blue-50 text-accent-primary border-blue-200',
    description: 'Входящие запросы клиентов',
    statuses: ['NEW', 'NORMALIZING', 'PARSING', 'VIN_CHECK', 'PART_EXTRACTION', 'NEEDS_MANUAL_PARSE', 'NEEDS_CLARIFICATION'],
  },
  {
    id: 'matching',
    title: 'Подбор поставщиков',
    icon: 'code-fork',
    topBarClass: 'bg-accent-info',
    iconBgClass: 'bg-cyan-50 text-accent-info border-cyan-200',
    badgeClass: 'bg-cyan-50 text-accent-info border-cyan-200',
    description: 'Поиск и ранжирование аналогов',
    statuses: ['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'MANUAL_REVIEW', 'REWORK'],
  },
  {
    id: 'approval',
    title: 'Согласование цен',
    icon: 'circle-check',
    topBarClass: 'bg-accent-warning',
    iconBgClass: 'bg-amber-50 text-accent-warning border-amber-200',
    badgeClass: 'bg-amber-50 text-accent-warning border-amber-200',
    description: 'Оценка маржинальности и рисков',
    statuses: ['PRICING_REVIEW', 'READY_FOR_APPROVAL'],
  },
  {
    id: 'invoicing',
    title: 'Счета & ERP Sync',
    icon: 'folder-open',
    topBarClass: 'bg-accent-success',
    iconBgClass: 'bg-emerald-50 text-accent-success border-emerald-200',
    badgeClass: 'bg-emerald-50 text-accent-success border-emerald-200',
    description: 'Выгрузка коммерческих предложений',
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

export function KanbanBoard({
  requests,
  onSelectRequest,
  onRunsChanged,
}: {
  requests: Request[];
  onSelectRequest: (request: Request) => void;
  onRunsChanged: () => void;
}) {
  const [pending, setPending] = React.useState<{ request: Request; lane: string; runId?: string } | null>(null);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [recentlyMoved, setRecentlyMoved] = React.useState<Set<string>>(new Set());
  const [activeDragColumn, setActiveDragColumn] = React.useState<string | null>(null);
  const previous = React.useRef<Request[]>(requests);
  const restored = React.useRef(false);
  const boardRef = React.useRef<HTMLDivElement>(null);

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
      { opacity: 0, y: 24 },
      { opacity: 1, y: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out' }
    );

    gsap.fromTo(
      boardRef.current.querySelectorAll('.kanban-card'),
      { opacity: 0, scale: 0.97, y: 10 },
      { opacity: 1, scale: 1, y: 0, duration: 0.4, stagger: 0.03, delay: 0.15, ease: 'power2.out' }
    );
  }, []);

  React.useEffect(() => {
    if (restored.current || !requests.length) return;
    restored.current = true;
    try {
      const stored = JSON.parse(localStorage.getItem('partsops.activePipelineRun') || 'null') as {
        requestId?: string;
        runId?: string;
        targetLane?: string;
      } | null;
      const request = requests.find((item) => item.request_id === stored?.requestId);
      if (request && stored?.runId && stored.targetLane) {
        setPending({ request, lane: stored.targetLane, runId: stored.runId });
        setDialogOpen(true);
      }
    } catch {
      localStorage.removeItem('partsops.activePipelineRun');
    }
  }, [requests]);

  const requestRun = (request: Request, lane: string) => {
    setPending({ request, lane });
    setDialogOpen(true);
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

  const handleDrop = (event: React.DragEvent, lane: string) => {
    event.preventDefault();
    setActiveDragColumn(null);

    const id = event.dataTransfer.getData('text/plain');
    const request = requests.find((item) => item.request_id === id);
    if (request) requestRun(request, lane);
  };

  return (
    <>
      <div ref={boardRef} className="grid grid-cols-1 gap-4 pb-4 md:grid-cols-2 xl:grid-cols-4">
        {COLUMNS.map((column) => {
          const cards = requests.filter((request) => column.statuses.includes(request.status));
          const isDraggingOver = activeDragColumn === column.id;

          return (
            <section
              key={column.id}
              data-column-id={column.id}
              onDragOver={(event) => event.preventDefault()}
              onDragEnter={(event) => handleDragEnter(event, column.id)}
              onDragLeave={handleDragLeave}
              onDrop={(event) => handleDrop(event, column.title)}
              className={`kanban-column ds-kanban-column ${isDraggingOver ? 'ds-kanban-column--drop' : ''}`}
              aria-label={`${column.title}: ${cards.length} запросов`}
            >
              <div className={`h-1.5 w-full rounded-t-2xl ${column.topBarClass}`} />

              <header className="border-b border-line bg-surface-2/60 p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2.5">
                    <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-control border shadow-ds-sm ${column.iconBgClass}`}>
                      <Icon name={column.icon} size={14} />
                    </div>
                    <div className="min-w-0">
                      <h3 className="truncate text-xs font-bold tracking-tight text-ink-primary">
                        {column.title}
                      </h3>
                      <p className="truncate text-[10px] font-medium text-ink-muted">
                        {column.description}
                      </p>
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[11px] font-bold ${column.badgeClass}`}>
                    {cards.length}
                  </span>
                </div>
              </header>

              <div className="custom-scrollbar max-h-[calc(100vh-280px)] flex-1 space-y-2.5 overflow-y-auto p-3">
                {cards.length > 0 ? (
                  cards.map((request) => (
                    <KanbanCard
                      key={request.request_id}
                      request={request}
                      onSelectRequest={onSelectRequest}
                      onRunPipeline={(item) => requestRun(item, column.title)}
                      isHighlighted={recentlyMoved.has(request.request_id)}
                    />
                  ))
                ) : (
                  <div className="ds-empty">
                    <div className="ds-empty__icon">
                      <Icon name={column.icon} size={16} />
                    </div>
                    <p className="ds-empty__title">Нет активных заявок</p>
                    <p className="ds-empty__hint">Перетащите заказ сюда для запуска этапа</p>
                  </div>
                )}
              </div>
            </section>
          );
        })}
      </div>

      <PipelineRunDialog
        request={pending?.request ?? null}
        targetLane={pending?.lane ?? null}
        restoreRunId={pending?.runId ?? null}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCompleted={onRunsChanged}
      />
    </>
  );
}

export default KanbanBoard;
