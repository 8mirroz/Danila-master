import React from 'react';
import { gsap } from 'gsap';
import { StatusBadge } from './Primitives';

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

interface KanbanCardProps {
  request: Request;
  onSelectRequest: (req: Request) => void;
  onRunPipeline?: (req: Request) => void;
  isHighlighted?: boolean;
}

const formatRelativeTime = (dateStr?: string) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.max(0, Math.floor(diffMs / 1000));
  const diffMins = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'Только что';
  if (diffMins < 60) return `${diffMins} мин. назад`;
  if (diffHours < 24) return `${diffHours} ч. назад`;
  if (diffDays === 1) return 'Вчера';
  if (diffDays < 7) return `${diffDays} дн. назад`;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
};

export const KanbanCard: React.FC<KanbanCardProps> = ({
  request,
  onSelectRequest,
  onRunPipeline,
  isHighlighted = false,
}) => {
  const [isDragging, setIsDragging] = React.useState(false);
  const cardRef = React.useRef<HTMLDivElement>(null);

  const getPriorityStripe = (priority?: string) => {
    const p = (priority || '').toLowerCase();
    if (p === 'urgent' || p === 'high') return 'border-l-4 border-l-[#FF5C7A]';
    if (p === 'vip') return 'border-l-4 border-l-[#9B7CFF]';
    return 'border-l-4 border-l-slate-700';
  };

  // GSAP micro-interaction: smooth card lift and premium shadow on hover
  const handleMouseEnter = () => {
    if (cardRef.current && !isDragging) {
      gsap.to(cardRef.current, {
        y: -5,
        scale: 1.015,
        boxShadow: '0 16px 36px -10px rgba(0, 0, 0, 0.7), 0 0 15px rgba(46, 230, 214, 0.2)',
        borderColor: 'rgba(46, 230, 214, 0.4)',
        duration: 0.3,
        ease: 'power2.out'
      });
    }
  };

  const handleMouseLeave = () => {
    if (cardRef.current && !isDragging) {
      gsap.to(cardRef.current, {
        y: 0,
        scale: 1,
        boxShadow: isHighlighted ? '0 0 25px rgba(46, 230, 214, 0.3)' : '0 4px 20px rgba(0, 0, 0, 0.35)',
        borderColor: isHighlighted ? '#2EE6D6' : 'rgba(255, 255, 255, 0.08)',
        duration: 0.3,
        ease: 'power2.out'
      });
    }
  };

  // Animate highlight state updates via GSAP
  React.useEffect(() => {
    if (cardRef.current) {
      if (isHighlighted) {
        gsap.to(cardRef.current, {
          backgroundColor: 'rgba(46, 230, 214, 0.1)',
          borderColor: '#2EE6D6',
          boxShadow: '0 0 25px rgba(46, 230, 214, 0.35)',
          scale: 1.02,
          duration: 0.4,
          ease: 'power2.out'
        });
      } else {
        gsap.to(cardRef.current, {
          backgroundColor: '#0D131E',
          borderColor: 'rgba(255, 255, 255, 0.08)',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.35)',
          scale: 1,
          duration: 0.4,
          ease: 'power2.out'
        });
      }
    }
  }, [isHighlighted]);

  return (
    <div
      ref={cardRef}
      role="group"
      aria-label={`Запрос ${request.request_id}`}
      data-request-id={request.request_id}
      tabIndex={0}
      draggable={true}
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', request.request_id);
        setIsDragging(true);
      }}
      onDragEnd={() => {
        setIsDragging(false);
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={() => onSelectRequest(request)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelectRequest(request);
        }
      }}
      className={`kanban-card group relative cursor-pointer rounded-[20px] border p-4 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 ${getPriorityStripe(
        request.priority
      )} ${
        isDragging
          ? 'border-dashed border-[var(--accent-primary)] bg-blue-50 opacity-30 shadow-none'
          : isHighlighted
            ? 'border-[var(--accent-primary)] bg-blue-50'
            : 'border-[var(--border-default)] bg-[var(--surface-1)]'
      }`}
    >
      {/* Top row: Client Name & Status Badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 truncate text-[13px] font-bold leading-snug tracking-tight text-[var(--text-primary)]">
          {request.customer_name || 'Заказчик не указан'}
        </div>
        <div className="shrink-0 scale-90 origin-right">
          <StatusBadge status={request.status} />
        </div>
      </div>

      {/* Info fields */}
      <div className="space-y-1.5 pt-1.5">
        {/* Request ID */}
        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--accent-primary)]">
          <i className="fas fa-hashtag text-[9px] text-blue-400" />
          <span className="font-mono">{request.request_id}</span>
        </div>

        {/* Vehicle */}
        {request.vehicle_make && (
          <div className="flex items-center gap-1.5 text-[11px] text-[#53B6FF] font-medium bg-[#182335] px-2.5 py-0.5 rounded-md w-fit border border-[#1F2D44]">
            <i className="fas fa-car text-[10px] text-[#53B6FF]/70" />
            <span>
              {request.vehicle_make} {request.vehicle_model || ''}
            </span>
          </div>
        )}

        {/* Source */}
        {request.source && (
          <div className="flex items-center gap-1.5 text-[11px] text-[#9AA6B2]">
            <i className="fas fa-arrow-right-to-bracket text-[9px] text-[#5F6B78]" />
            <span className="capitalize">{request.source}</span>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="h-px bg-white/5 my-2.5" />

      {/* Footer: Date & Actions */}
      <div className="flex items-center justify-between text-[10px] text-[#5F6B78] font-medium">
        <div className="flex items-center gap-1 font-mono">
          <i className="far fa-clock text-[9px]" />
          <span>{formatRelativeTime(request.created_at)}</span>
        </div>
        <div className="flex items-center gap-2">
          {onRunPipeline && (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onRunPipeline(request);
              }}
              className="rounded-lg px-2.5 py-1 text-[10px] font-extrabold text-[#2EE6D6] bg-[#2EE6D6]/10 border border-[#2EE6D6]/30 transition-all hover:bg-[#2EE6D6]/20 focus:outline-none active:scale-95"
              aria-label={`Запустить pipeline для ${request.request_id}`}
            >
              Запуск
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
