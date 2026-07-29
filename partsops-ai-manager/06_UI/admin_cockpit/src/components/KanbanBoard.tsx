import React from 'react';
import { gsap } from 'gsap';
import { Icon } from './Primitives';
import { KanbanCard } from './KanbanCard';
import { PipelineRunDialog } from './PipelineRunDialog';

type Request = {
  id: number; request_id: string; source: string; status: string; customer_name: string; created_at: string; parts_json: string;
  customer_phone_masked?: string; customer_email_masked?: string; vehicle_vin_masked?: string; priority?: string; vehicle_make?: string; vehicle_model?: string;
};

const COLUMNS = [
  { id: 'intake', title: 'Входящие', icon: 'file-arrow-up', iconColor: 'text-[#53B6FF]', bgClass: 'bg-[rgba(83,182,255,0.03)] border-[rgba(83,182,255,0.12)]', statuses: ['NEW', 'NORMALIZING', 'PARSING', 'VIN_CHECK', 'PART_EXTRACTION', 'NEEDS_MANUAL_PARSE', 'NEEDS_CLARIFICATION'] },
  { id: 'matching', title: 'Подбор', icon: 'code-fork', iconColor: 'text-[#2EE6D6]', bgClass: 'bg-[rgba(46,230,214,0.03)] border-[rgba(46,230,214,0.12)]', statuses: ['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'MANUAL_REVIEW', 'REWORK'] },
  { id: 'approval', title: 'Согласование', icon: 'circle-check', iconColor: 'text-[#F5C84C]', bgClass: 'bg-[rgba(245,200,76,0.03)] border-[rgba(245,200,76,0.12)]', statuses: ['PRICING_REVIEW', 'READY_FOR_APPROVAL'] },
  { id: 'invoicing', title: 'Счета в ERP', icon: 'folder-open', iconColor: 'text-[#3EE985]', bgClass: 'bg-[rgba(62,233,133,0.03)] border-[rgba(62,233,133,0.12)]', statuses: ['APPROVED', 'ERP_SYNCING', 'INVOICE_DRAFTED', 'SENT_TO_CLIENT', 'PAID', 'PURCHASE_ORDERED', 'FULFILLED', 'CLOSED', 'CANCELLED', 'FAILED', 'ERP_SYNC_FAILED', 'CLIENT_REJECTED', 'EXPIRED'] },
];

export function KanbanBoard({ requests, onSelectRequest, onRunsChanged }: {
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

  // Track status changes to animate moved cards
  React.useEffect(() => {
    const oldStatuses = new Map(previous.current.map((request) => [request.request_id, request.status]));
    const moved = new Set(requests.filter((request) => oldStatuses.get(request.request_id) && oldStatuses.get(request.request_id) !== request.status).map((request) => request.request_id));
    previous.current = requests;
    if (!moved.size) return;
    setRecentlyMoved(moved);
    const timer = window.setTimeout(() => setRecentlyMoved(new Set()), 2000);
    return () => window.clearTimeout(timer);
  }, [requests]);

  // GSAP entrance animation for columns and cards on mount
  React.useEffect(() => {
    if (boardRef.current) {
      // 1. Column stagger entrance
      gsap.fromTo(
        boardRef.current.querySelectorAll('.kanban-column'),
        { opacity: 0, y: 35 },
        { opacity: 1, y: 0, duration: 0.7, stagger: 0.12, ease: 'power3.out' }
      );
      
      // 2. Cards stagger entrance
      gsap.fromTo(
        boardRef.current.querySelectorAll('.kanban-card'),
        { opacity: 0, scale: 0.95, y: 15 },
        { opacity: 1, scale: 1, y: 0, duration: 0.5, stagger: 0.04, delay: 0.25, ease: 'power2.out' }
      );
    }
  }, []);

  // GSAP feedback animation on moved cards
  React.useEffect(() => {
    if (recentlyMoved.size > 0 && boardRef.current) {
      recentlyMoved.forEach((reqId) => {
        const cardEl = boardRef.current?.querySelector(`[data-request-id="${reqId}"]`);
        if (cardEl) {
          gsap.timeline()
            .fromTo(cardEl, 
              { scale: 0.9, borderColor: '#2EE6D6', boxShadow: '0 0 25px rgba(46, 230, 214, 0.5)' },
              { scale: 1.04, duration: 0.25, ease: 'power2.out' }
            )
            .to(cardEl, { rotation: 1.5, duration: 0.06, yoyo: true, repeat: 3 })
            .to(cardEl, { rotation: 0, scale: 1, duration: 0.15, ease: 'power2.inOut' });
        }
      });
    }
  }, [recentlyMoved]);

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

  // Drag over columns micro-interactions with GSAP
  const handleDragEnter = (e: React.DragEvent, columnId: string) => {
    e.preventDefault();
    setActiveDragColumn(columnId);
    
    const colEl = boardRef.current?.querySelector(`[data-column-id="${columnId}"]`);
    if (colEl) {
      gsap.to(colEl, {
        scale: 1.015,
        borderColor: 'rgba(46, 230, 214, 0.4)',
        backgroundColor: 'rgba(46, 230, 214, 0.06)',
        boxShadow: '0 0 25px rgba(46, 230, 214, 0.15)',
        duration: 0.25,
        ease: 'power2.out'
      });
    }
  };

  const handleDragLeave = (e: React.DragEvent, columnId: string) => {
    e.preventDefault();
    // Verify we are leaving the actual container boundary
    const rect = e.currentTarget.getBoundingClientRect();
    if (e.clientX < rect.left || e.clientX >= rect.right || e.clientY < rect.top || e.clientY >= rect.bottom) {
      setActiveDragColumn(null);
      const colEl = boardRef.current?.querySelector(`[data-column-id="${columnId}"]`);
      if (colEl) {
        gsap.to(colEl, {
          scale: 1,
          borderColor: '',
          backgroundColor: '',
          boxShadow: '',
          duration: 0.25,
          ease: 'power2.out'
        });
      }
    }
  };

  const handleDrop = (event: React.DragEvent, lane: string, columnId: string) => {
    event.preventDefault();
    setActiveDragColumn(null);
    
    const colEl = boardRef.current?.querySelector(`[data-column-id="${columnId}"]`);
    if (colEl) {
      gsap.timeline()
        .to(colEl, { scale: 0.98, duration: 0.1, ease: 'power2.out' })
        .to(colEl, { scale: 1, borderColor: '', backgroundColor: '', boxShadow: '', duration: 0.25, ease: 'back.out(2)' });
    }

    const id = event.dataTransfer.getData('text/plain');
    const request = requests.find((item) => item.request_id === id);
    if (request) requestRun(request, lane);
  };

  return <>
    <div ref={boardRef} className="grid min-h-[calc(100vh-250px)] grid-cols-1 gap-5 overflow-hidden pb-2 md:grid-cols-2 xl:grid-cols-4">
      {COLUMNS.map((column) => {
        const cards = requests.filter((request) => column.statuses.includes(request.status));
        return <section 
          key={column.id} 
          data-column-id={column.id}
          onDragOver={(event) => event.preventDefault()} 
          onDragEnter={(event) => handleDragEnter(event, column.id)}
          onDragLeave={(event) => handleDragLeave(event, column.id)}
          onDrop={(event) => handleDrop(event, column.title, column.id)} 
          className={`kanban-column flex min-h-[420px] flex-col rounded-[26px] border p-4 shadow-[0_4px_24px_rgba(0,0,0,0.4)] backdrop-blur-md transition-all duration-300 ${column.bgClass} ${activeDragColumn === column.id ? 'border-[#2EE6D6]/40 bg-[#2EE6D6]/10' : ''}`} 
          aria-label={`${column.title}: ${cards.length} запросов`}
        >
          <header className="mb-4 flex items-center justify-between border-b border-white/10 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8.5 w-8.5 items-center justify-center rounded-xl border border-white/10 bg-white/5 shadow-inner">
                <Icon name={column.icon} className={column.iconColor} size={15} />
              </div>
              <div>
                <h3 className="text-[13px] font-bold text-[#F4F7FB] tracking-tight">{column.title}</h3>
                <p className="text-[10px] text-[#9AA6B2] font-semibold uppercase tracking-wider">Перенос запускает pipeline</p>
              </div>
            </div>
            <span className="rounded-full bg-white/10 px-2.5 py-1 text-[10px] font-bold font-mono text-[#2EE6D6] border border-white/10">{cards.length}</span>
          </header>
          
          <div className="custom-scrollbar flex-1 space-y-3 overflow-y-auto pr-1">
            {cards.length ? cards.map((request) => (
              <KanbanCard 
                key={request.request_id} 
                request={request} 
                onSelectRequest={onSelectRequest} 
                onRunPipeline={(item) => requestRun(item, column.title)} 
                isHighlighted={recentlyMoved.has(request.request_id)} 
              />
            )) : (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] py-10 text-center text-[11px] font-medium text-[#5F6B78]">
                Нет запросов на этом этапе
              </div>
            )}
          </div>
        </section>;
      })}
    </div>
    <PipelineRunDialog request={pending?.request ?? null} targetLane={pending?.lane ?? null} restoreRunId={pending?.runId ?? null} open={dialogOpen} onClose={() => setDialogOpen(false)} onCompleted={onRunsChanged} />
  </>;
}
