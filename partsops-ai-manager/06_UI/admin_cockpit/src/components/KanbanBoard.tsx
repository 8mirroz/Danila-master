import React from 'react';
import { KanbanCard } from './KanbanCard';


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
  onTransitionRequest?: (requestId: string, targetState: string, reason: string) => Promise<void>;
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

  // Columns definition mapping
  const columns = [
    {
      id: 'intake',
      title: 'Входящие',
      icon: 'fa-file-arrow-up text-blue-500',
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
      icon: 'fa-arrows-split-up-and-left text-sky-500',
      bgClass: 'bg-sky-50/40 border-sky-100',
      statuses: ['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'MANUAL_REVIEW', 'REWORK'],
    },
    {
      id: 'approval',
      title: 'Согласование',
      icon: 'fa-circle-check text-amber-500',
      bgClass: 'bg-amber-50/40 border-amber-100',
      statuses: ['PRICING_REVIEW', 'READY_FOR_APPROVAL'],
    },
    {
      id: 'invoicing',
      title: 'Счета в ERP',
      icon: 'fa-file-invoice-dollar text-emerald-500',
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
      if (onTransitionRequest) {
        try {
          await onTransitionRequest(
            requestId,
            targetState,
            `Перенос карточки в колонку "${column?.title ?? targetColumnId}"`
          );
        } catch (err) {
          console.error(err);
        }
      }
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
                  <i className={`fas ${col.icon} text-sm`}></i>
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
                    onTransitionRequest={onTransitionRequest}
                    isHighlighted={recentlyMoved.has(req.request_id)}
                  />
                ))

              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
