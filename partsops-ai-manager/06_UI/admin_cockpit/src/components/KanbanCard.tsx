import React from 'react';
import { StatusBadge } from './Primitives';
import { TransitionActions } from './TransitionActions';

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
  onTransitionRequest?: (requestId: string, targetState: string, reason: string) => Promise<void>;
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
  onTransitionRequest,
  isHighlighted = false,
}) => {
  const getPriorityStripe = (priority?: string) => {
    const p = (priority || '').toLowerCase();
    if (p === 'urgent' || p === 'high') return 'border-l-4 border-l-rose-500';
    if (p === 'vip') return 'border-l-4 border-l-violet-500';
    return 'border-l-4 border-l-slate-200';
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelectRequest(request)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelectRequest(request);
        }
      }}
      className={`group relative rounded-[20px] border p-3.5 shadow-[0_2px_8px_rgba(15,23,42,0.03)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500/50 ${getPriorityStripe(
        request.priority
      )} ${
        isHighlighted
          ? 'bg-blue-50/80 border-blue-400 shadow-[0_4px_16px_rgba(59,130,246,0.15)] scale-[1.02] z-10'
          : 'bg-white border-slate-100 hover:border-slate-200'
      }`}
    >
      {/* Top row: Client Name & Status Badge */}
      <div className="flex items-start justify-between gap-3">
        <div className="font-bold text-[13px] text-slate-800 leading-tight truncate flex-1">
          {request.customer_name || 'Заказчик не указан'}
        </div>
        <div className="shrink-0 scale-90 origin-right">
          <StatusBadge status={request.status} />
        </div>
      </div>

      {/* Info fields */}
      <div className="space-y-1.5 pt-1">
        {/* Request ID */}
        <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-medium">
          <i className="fas fa-hashtag text-[9px] text-slate-300" />
          <span className="font-mono">{request.request_id}</span>
        </div>

        {/* Vehicle */}
        {request.vehicle_make && (
          <div className="flex items-center gap-1.5 text-[11px] text-slate-600 font-medium bg-slate-50 px-2 py-0.5 rounded-md w-fit border border-slate-100">
            <i className="fas fa-car text-[10px] text-slate-400" />
            <span>
              {request.vehicle_make} {request.vehicle_model || ''}
            </span>
          </div>
        )}

        {/* Source */}
        {request.source && (
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <i className="fas fa-arrow-right-to-bracket text-[9px] text-slate-400" />
            <span className="capitalize">{request.source}</span>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="h-px bg-slate-100/80 my-2" />

      {/* Footer: Date & Icons */}
      <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium">
        <div className="flex items-center gap-1">
          <i className="far fa-clock text-[9px]" />
          <span>{formatRelativeTime(request.created_at)}</span>
        </div>
        <div className="flex items-center gap-2 text-slate-300">
          <i className="fas fa-paperclip hover:text-slate-400 transition-colors" />
          <i className="far fa-comment hover:text-slate-400 transition-colors" />
        </div>
      </div>

      {/* Actions (reveal on hover) */}
      {onTransitionRequest && (
        <div
          className="pt-3 mt-2 border-t border-slate-100 opacity-0 max-h-0 group-hover:opacity-100 group-hover:max-h-32 overflow-hidden transition-all duration-300 ease-in-out"
          onClick={(e) => e.stopPropagation()}
        >
          <TransitionActions
            status={request.status}
            requestId={request.request_id}
            onTransition={(targetState, reason) =>
              onTransitionRequest(request.request_id, targetState, reason)
            }
            compact
          />
        </div>
      )}
    </div>
  );
};
