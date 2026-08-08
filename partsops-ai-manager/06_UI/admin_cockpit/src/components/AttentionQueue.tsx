import React from 'react';
import { TrafficDot, Icon, Button, EmptyState } from './Primitives';
import { getStatusLabel, isBlockedRequestStatus, isApprovalPendingStatus } from '../lib/workflow';
import type { Request } from '../lib/types';

interface AttentionQueueProps {
  requests: Request[];
  onSelectRequest: (req: Request) => void;
  onTransitionRequest: (requestId: string, targetState: string, reason: string) => Promise<void>;
  onInspectRequest: (req: Request) => void;
}

export const AttentionQueue: React.FC<AttentionQueueProps> = ({
  requests,
  onSelectRequest,
  onTransitionRequest,
  onInspectRequest,
}) => {
  // Фильтруем заявки, требующие активного вмешательства оператора
  const attentionItems = requests.filter((r) => {
    const status = (r.status || '').toUpperCase();
    return (
      r.is_blocked === true ||
      isBlockedRequestStatus(status) ||
      isApprovalPendingStatus(status) ||
      Boolean(r.recommended_action) ||
      !r.vehicle_vin_masked
    );
  });

  const getReasonText = (req: Request) => {
    const status = (req.status || '').toUpperCase();
    if (status === 'NEEDS_CLARIFICATION' || !req.vehicle_vin_masked) {
      return 'Требуется уточнение данных (VIN не указан)';
    }
    if (status === 'ERP_SYNC_FAILED') {
      return 'Ошибка синхронизации с 1С / ERP системой';
    }
    if (status === 'MANUAL_REVIEW' || status === 'FAILED') {
      return 'Требуется ручное подтверждение закупщика';
    }
    if (status === 'PRICING_REVIEW' || status === 'READY_FOR_APPROVAL') {
      return 'Заявка готова к проверке цены и согласованию';
    }
    return 'Требует внимания оператора';
  };

  return (
    <div className="space-y-4 max-w-5xl mx-auto p-4">
      {/* Шапка очереди внимания */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-xl bg-amber-100 text-amber-800 text-xs font-bold border border-amber-200">
              <Icon name="lightning" size={16} />
            </span>
            <h2 className="text-base font-bold text-ink-primary">Очередь внимания «Автопилот»</h2>
          </div>
          <p className="text-xs text-ink-secondary mt-0.5">
            Здесь собраны только те заявки, которые требуют ручного решения закупщика. Все остальные заказы обрабатываются ИИ автоматически.
          </p>
        </div>
        <span className="font-mono text-xs font-bold text-amber-800 bg-amber-50 border border-amber-200 px-3 py-1 rounded-full">
          {attentionItems.length} позиций требуют действия
        </span>
      </div>

      {/* Список внимания */}
      {attentionItems.length === 0 ? (
        <EmptyState
          title="Заявок, требующих вашего внимания, нет!"
          description="Все текущие заказы успешно обрабатываются ИИ-агентами в автоматическом режиме «Зелёный коридор»."
          icon="shield-check"
        />
      ) : (
        <div className="space-y-3">
          {attentionItems.map((req) => (
            <div
              key={req.request_id}
              className="group rounded-2xl border border-line bg-surface-1 p-4 shadow-sm hover:border-accent-primary transition-all duration-200 flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <TrafficDot status={req.status} />
                  <span className="font-mono text-xs font-bold text-accent-primary">{req.request_id}</span>
                  <span className="text-xs font-bold text-ink-primary">{req.customer_name || 'Заказчик не указан'}</span>
                  <span className="text-[10px] font-semibold text-amber-800 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                    {getStatusLabel(req.status)}
                  </span>
                </div>

                <div className="text-xs text-rose-700 bg-rose-50/60 border border-rose-100 px-2.5 py-1 rounded-xl flex items-center gap-1.5 font-medium">
                  <Icon name="exclamation-circle" size={13} />
                  <span>{getReasonText(req)}</span>
                </div>
              </div>

              {/* Правый блок быстрых действий */}
              <div className="flex items-center gap-2 shrink-0">
                {req.recommended_action && req.recommended_action.target_state && (
                  <Button
                    variant="success"
                    icon="check"
                    onClick={() => {
                      if (req.recommended_action?.target_state) {
                        void onTransitionRequest(req.request_id, req.recommended_action.target_state, 'Одобрено в 1-Click');
                      }
                    }}
                  >
                    Быстрое одобрение (1-Click)
                  </Button>
                )}

                <Button
                  variant="secondary"
                  icon="eye"
                  onClick={() => onInspectRequest(req)}
                >
                  Просмотр
                </Button>

                <Button
                  variant="primary"
                  icon="arrow-right"
                  onClick={() => onSelectRequest(req)}
                >
                  В хаб
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AttentionQueue;
