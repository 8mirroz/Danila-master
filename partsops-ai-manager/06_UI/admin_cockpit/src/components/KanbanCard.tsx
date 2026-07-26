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

export const KanbanCard: React.FC<KanbanCardProps> = ({
  request,
  onSelectRequest,
  onTransitionRequest,
  isHighlighted = false,
}) => {
  const getPriorityStripe = (priority?: string) => {
    const p = (priority || '').toLowerCase();
    if (p === 'urgent' || p === 'high') return 'border-l-4 border-l-red-500';
    if (p === 'vip') return 'border-l-4 border-l-purple-500';
    return 'border-l-4 border-l-slate-300';
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
      className={`group relative rounded-xl border p-3.5 shadow-sm transition-all duration-500 space-y-3 cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500/50 ${getPriorityStripe(
        request.priority
      )} ${
        isHighlighted
          ? 'bg-blue-50/80 border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.3)] scale-[1.02] z-10'
          : 'bg-[var(--surface-1)] border-[var(--border-default)] hover:shadow-md'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
          {request.request_id}
        </span>
        <StatusBadge status={request.status} />
      </div>

      <div className="space-y-1 text-xs text-[var(--text-secondary)]">
        <div className="font-semibold text-[var(--text-primary)] truncate">
          {request.customer_name || 'Заказчик не указан'}
        </div>
        {request.vehicle_make && (
          <div className="text-[11px] text-blue-600 font-medium flex items-center gap-1">
            <i className="fas fa-car text-[10px]" />
            <span>
              {request.vehicle_make} {request.vehicle_model || ''}
            </span>
          </div>
        )}
      </div>

      {onTransitionRequest && (
        <div
          className="pt-2 border-t border-[var(--border-subtle)]"
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
