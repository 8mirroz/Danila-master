import React from 'react';
import { Icon } from './Primitives';
import { KanbanCard } from './KanbanCard';
import { PipelineRunDialog } from './PipelineRunDialog';

type Request = {
  id: number; request_id: string; source: string; status: string; customer_name: string; created_at: string; parts_json: string;
  customer_phone_masked?: string; customer_email_masked?: string; vehicle_vin_masked?: string; priority?: string; vehicle_make?: string; vehicle_model?: string;
};

const COLUMNS = [
  { id: 'intake', title: 'Входящие', icon: 'file-arrow-up', iconColor: 'text-blue-500', bgClass: 'bg-blue-50/40 border-blue-100', statuses: ['NEW', 'NORMALIZING', 'PARSING', 'VIN_CHECK', 'PART_EXTRACTION', 'NEEDS_MANUAL_PARSE', 'NEEDS_CLARIFICATION'] },
  { id: 'matching', title: 'Подбор', icon: 'code-fork', iconColor: 'text-sky-500', bgClass: 'bg-sky-50/40 border-sky-100', statuses: ['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'MANUAL_REVIEW', 'REWORK'] },
  { id: 'approval', title: 'Согласование', icon: 'circle-check', iconColor: 'text-amber-500', bgClass: 'bg-amber-50/40 border-amber-100', statuses: ['PRICING_REVIEW', 'READY_FOR_APPROVAL'] },
  { id: 'invoicing', title: 'Счета в ERP', icon: 'folder-open', iconColor: 'text-emerald-500', bgClass: 'bg-emerald-50/40 border-emerald-100', statuses: ['APPROVED', 'ERP_SYNCING', 'INVOICE_DRAFTED', 'SENT_TO_CLIENT', 'PAID', 'PURCHASE_ORDERED', 'FULFILLED', 'CLOSED', 'CANCELLED', 'FAILED', 'ERP_SYNC_FAILED', 'CLIENT_REJECTED', 'EXPIRED'] },
];

export function KanbanBoard({ requests, onSelectRequest, onRunsChanged }: {
  requests: Request[];
  onSelectRequest: (request: Request) => void;
  onRunsChanged: () => void;
}) {
  const [pending, setPending] = React.useState<{ request: Request; lane: string; runId?: string } | null>(null);
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const [recentlyMoved, setRecentlyMoved] = React.useState<Set<string>>(new Set());
  const previous = React.useRef<Request[]>(requests);
  const restored = React.useRef(false);

  React.useEffect(() => {
    const oldStatuses = new Map(previous.current.map((request) => [request.request_id, request.status]));
    const moved = new Set(requests.filter((request) => oldStatuses.get(request.request_id) && oldStatuses.get(request.request_id) !== request.status).map((request) => request.request_id));
    previous.current = requests;
    if (!moved.size) return;
    setRecentlyMoved(moved);
    const timer = window.setTimeout(() => setRecentlyMoved(new Set()), 2000);
    return () => window.clearTimeout(timer);
  }, [requests]);

  React.useEffect(() => {
    if (restored.current || !requests.length) return;
    restored.current = true;
    try {
      const stored = JSON.parse(localStorage.getItem('partsops.activePipelineRun') || 'null') as { requestId?: string; runId?: string; targetLane?: string } | null;
      const request = requests.find((item) => item.request_id === stored?.requestId);
      if (request && stored?.runId && stored.targetLane) {
        setPending({ request, lane: stored.targetLane, runId: stored.runId });
        setDialogOpen(true);
      }
    } catch {
      localStorage.removeItem('partsops.activePipelineRun');
    }
  }, [requests]);

  const requestRun = (request: Request, lane: string) => { setPending({ request, lane }); setDialogOpen(true); };
  const handleDrop = (event: React.DragEvent, lane: string) => {
    event.preventDefault();
    const id = event.dataTransfer.getData('text/plain');
    const request = requests.find((item) => item.request_id === id);
    if (request) requestRun(request, lane);
  };

  return <>
    <div className="grid min-h-[calc(100vh-250px)] grid-cols-1 gap-4 overflow-auto pb-2 md:grid-cols-2 xl:grid-cols-4">
      {COLUMNS.map((column) => {
        const cards = requests.filter((request) => column.statuses.includes(request.status));
        return <section key={column.id} onDragOver={(event) => event.preventDefault()} onDrop={(event) => handleDrop(event, column.title)} className={`flex min-h-[420px] flex-col rounded-[24px] border p-3 shadow-sm ${column.bgClass}`} aria-label={`${column.title}: ${cards.length} запросов`}>
          <header className="mb-3 flex items-center justify-between border-b border-[var(--border-default)] pb-3"><div className="flex items-center gap-2"><div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-white/70 bg-white/80 shadow-sm"><Icon name={column.icon} className={column.iconColor} size={16} /></div><div><h3 className="text-xs font-bold text-[var(--text-primary)]">{column.title}</h3><p className="text-[10px] text-[var(--text-muted)]">Перенос запускает pipeline</p></div></div><span className="rounded-full bg-white/85 px-2.5 py-1 text-[10px] font-bold text-[var(--text-secondary)] shadow-sm">{cards.length}</span></header>
          <div className="custom-scrollbar flex-1 space-y-2.5 overflow-y-auto pr-1">{cards.length ? cards.map((request) => <KanbanCard key={request.request_id} request={request} onSelectRequest={onSelectRequest} onRunPipeline={(item) => requestRun(item, column.title)} isHighlighted={recentlyMoved.has(request.request_id)} />) : <div className="rounded-[18px] border border-dashed border-[var(--border-default)] bg-white/60 px-4 py-8 text-center text-[10px] text-[var(--text-muted)]">Нет запросов на этом этапе</div>}</div>
        </section>;
      })}
    </div>
    <PipelineRunDialog request={pending?.request ?? null} targetLane={pending?.lane ?? null} restoreRunId={pending?.runId ?? null} open={dialogOpen} onClose={() => setDialogOpen(false)} onCompleted={onRunsChanged} />
  </>;
}
