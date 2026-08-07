import React from 'react';
import { StatusBadge, Icon } from './Primitives';

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

  let partsCount = 0;
  try {
    const parsed = request.parts_json ? JSON.parse(request.parts_json) : [];
    partsCount = Array.isArray(parsed) ? parsed.length : 0;
  } catch {
    partsCount = 0;
  }

  const getPriorityBadge = (priority?: string) => {
    const p = (priority || '').toLowerCase();
    if (p === 'urgent' || p === 'high') {
      return (
        <span className="inline-flex items-center gap-1 rounded border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[9px] font-bold text-accent-danger">
          <Icon name="exclamation-triangle" size={9} /> СРОЧНО
        </span>
      );
    }
    if (p === 'vip') {
      return (
        <span className="inline-flex items-center gap-1 rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[9px] font-bold text-violet-700">
          <Icon name="user-shield" size={9} /> VIP
        </span>
      );
    }
    return null;
  };

  return (
    <div
      role="group"
      aria-label={`Запрос ${request.request_id}`}
      data-request-id={request.request_id}
      tabIndex={0}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', request.request_id);
        setIsDragging(true);
      }}
      onDragEnd={() => setIsDragging(false)}
      onClick={() => onSelectRequest(request)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelectRequest(request);
        }
      }}
      className={`kanban-card ds-kanban-card focus:outline-none focus-visible:shadow-ds-focus ${
        isDragging ? 'ds-kanban-card--dragging' : isHighlighted ? 'ds-kanban-card--highlight' : ''
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[11px] font-bold text-accent-primary">
            {request.request_id}
          </span>
          {getPriorityBadge(request.priority)}
        </div>
        <div className="origin-right scale-90 shrink-0">
          <StatusBadge status={request.status} />
        </div>
      </div>

      <div className="mb-2 truncate text-xs font-bold leading-snug text-ink-primary">
        {request.customer_name || 'Заказчик не указан'}
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {request.vehicle_make && (
          <div className="ds-chip">
            <Icon name="car" size={10} className="text-ink-muted" />
            <span className="max-w-[140px] truncate">
              {request.vehicle_make} {request.vehicle_model || ''}
            </span>
          </div>
        )}

        {partsCount > 0 && (
          <span className="ds-chip ds-chip--accent">{partsCount} поз.</span>
        )}

        {request.source && (
          <span className="ds-chip uppercase tracking-wide">{request.source}</span>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-line-subtle pt-2.5 text-[10px] font-medium text-ink-muted">
        <div className="flex items-center gap-1 font-mono">
          <Icon name="clock" size={10} />
          <span>{formatRelativeTime(request.created_at)}</span>
        </div>

        {onRunPipeline && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRunPipeline(request);
            }}
            className="inline-flex items-center gap-1 rounded-control border border-blue-200 bg-blue-50 px-2.5 py-1 text-[10px] font-extrabold text-accent-primary transition-all hover:bg-blue-100 active:scale-95"
            aria-label={`Запустить pipeline для ${request.request_id}`}
          >
            <Icon name="play" size={8} />
            Запуск
          </button>
        )}
      </div>
    </div>
  );
};

export default KanbanCard;
