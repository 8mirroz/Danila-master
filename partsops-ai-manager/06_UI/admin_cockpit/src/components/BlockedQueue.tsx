import React from 'react';
import { StatusBadge, EmptyState } from './Primitives';
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
  allowed_targets?: string[];
  allowed_actions?: Array<{ id: string; kind: string; target_state?: string }>;
  recommended_action?: { id: string; kind: string; target_state?: string } | null;
  is_blocked?: boolean;
  version?: string | null;
};

interface BlockedQueueProps {
  requests: Request[];
  onSelectRequest: (req: Request) => void;
  onTransitionRequest: (requestId: string, targetState: string, reason: string, version?: string | null) => Promise<void>;
}

export const BlockedQueue: React.FC<BlockedQueueProps> = ({
  requests,
  onSelectRequest,
  onTransitionRequest,
}) => {
  const actionableRequests = requests.filter((r) => r.is_blocked === true || r.recommended_action);

  return (
    <section className="panel-card-tight overflow-hidden p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--border-default)] pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-100 text-amber-700 text-xs font-bold">
            <i className="fas fa-triangle-exclamation" />
          </span>
          <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
            Следующие действия ({actionableRequests.length})
          </h3>
        </div>
        <span className="text-[10px] text-[var(--text-muted)] font-mono">
          Подтверждено backend capabilities
        </span>
      </div>

      {actionableRequests.length === 0 ? (
        <EmptyState
          title="Действий, требующих оператора, нет"
          description="Все текущие запросы проходят этапы обработки в штатном режиме."
          icon="fa-shield-check"
        />
      ) : (
        <div className="space-y-3">
          {actionableRequests.map((req) => (
            <div
              key={req.request_id}
              className="group flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl border border-amber-200/80 bg-amber-50/40 hover:bg-amber-50/80 transition-all shadow-sm hover:shadow-md"
            >
              <div
                className="space-y-1.5 cursor-pointer flex-1"
                onClick={() => onSelectRequest(req)}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-[var(--text-primary)]">
                    {req.request_id}
                  </span>
                  <StatusBadge status={req.status} />
                  {req.priority && (
                    <span
                      className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase ${
                        req.priority.toLowerCase() === 'high' || req.priority.toLowerCase() === 'urgent'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-slate-200 text-slate-700'
                      }`}
                    >
                      {req.priority}
                    </span>
                  )}
                </div>

                <div className="text-xs font-medium text-[var(--text-secondary)] flex flex-wrap items-center gap-3">
                  <span>
                    <i className="fas fa-user text-[10px] mr-1 text-slate-400" />
                    {req.customer_name || 'Клиент'}
                  </span>
                  {req.vehicle_make && (
                    <span>
                      <i className="fas fa-car text-[10px] mr-1 text-slate-400" />
                      {req.vehicle_make} {req.vehicle_model || ''}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2 md:pt-0 border-t md:border-t-0 border-amber-200/60 shrink-0">
                {(req.allowed_targets?.length ?? 0) > 0 ? (
                  <TransitionActions
                    status={req.status}
                    requestId={req.request_id}
                    onTransition={(targetState, reason) =>
                      onTransitionRequest(req.request_id, targetState, reason, req.version)
                    }
                    allowedTargets={req.allowed_targets ?? []}
                    compact
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => onSelectRequest(req)}
                    className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-blue-700 hover:bg-blue-100"
                  >
                    Открыть заявку
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
