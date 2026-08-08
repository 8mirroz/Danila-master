import React from 'react';
import { Icon, TrafficDot, Button } from './Primitives';
import { TransitionActions } from './TransitionActions';
import { getStatusLabel, getTrafficLightLabel } from '../lib/workflow';
import type { Request } from '../lib/types';

interface RequestInspectorProps {
  request: Request;
  onTransition: (targetState: string, reason: string) => Promise<void>;
  onOpenFullWorkspace: (req: Request) => void;
}

export const RequestInspector: React.FC<RequestInspectorProps> = ({
  request,
  onTransition,
  onOpenFullWorkspace,
}) => {
  let partsCount = 0;
  let parsedParts: Array<{ name?: string; quantity?: number; oem?: string }> = [];
  try {
    parsedParts = request.parts_json ? JSON.parse(request.parts_json) : [];
    partsCount = Array.isArray(parsedParts) ? parsedParts.length : 0;
  } catch {
    partsCount = 0;
  }

  const allowedTargets = (request.allowed_actions ?? [])
    .filter((a) => a.kind === 'transition' && a.target_state)
    .map((a) => a.target_state as string);

  return (
    <div className="space-y-5 text-xs text-ink-primary">
      {/* Статус и Режим обработки */}
      <div className="rounded-2xl border border-line bg-surface-2/60 p-4 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold text-ink-muted uppercase tracking-wider">Текущий статус</span>
          <span className="font-mono text-[11px] font-bold text-accent-primary">{request.request_id}</span>
        </div>
        <div className="flex items-center gap-2">
          <TrafficDot status={request.status} showLabel />
        </div>
        <div className="text-[11px] text-ink-secondary border-t border-line-subtle pt-2">
          Состояние системы: <strong>{getTrafficLightLabel(request.status)}</strong> ({getStatusLabel(request.status)})
        </div>
      </div>

      {/* Заказчик и Автомобиль */}
      <div className="space-y-2">
        <h4 className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">Информация о клиенте</h4>
        <div className="rounded-2xl border border-line bg-surface-1 p-3.5 space-y-2">
          <div className="flex items-center justify-between font-bold text-ink-primary">
            <span>{request.customer_name || 'Заказчик не указан'}</span>
            {request.source && <span className="ds-chip uppercase">{request.source}</span>}
          </div>
          {request.vehicle_make && (
            <div className="flex items-center gap-1.5 text-ink-secondary">
              <Icon name="car" size={13} className="text-ink-muted" />
              <span>{request.vehicle_make} {request.vehicle_model || ''}</span>
            </div>
          )}
          {request.vehicle_vin_masked ? (
            <div className="flex items-center gap-1.5 font-mono text-[11px] text-accent-primary">
              <Icon name="barcode" size={13} />
              <span>VIN: {request.vehicle_vin_masked}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded text-[11px] font-semibold">
              <Icon name="exclamation-circle" size={12} />
              <span>VIN-код отсутствует в заявке</span>
            </div>
          )}
        </div>
      </div>

      {/* Детали заказа (Позиции) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h4 className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">Детали запроса ({partsCount} поз.)</h4>
        </div>
        <div className="rounded-2xl border border-line bg-surface-1 p-3 space-y-2 max-h-48 overflow-y-auto">
          {parsedParts.length > 0 ? (
            parsedParts.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between border-b border-line-subtle last:border-0 pb-1.5 last:pb-0">
                <span className="font-semibold text-ink-primary truncate max-w-[220px]">{item.name || `Позиция #${idx + 1}`}</span>
                <span className="font-mono text-ink-secondary">{item.quantity || 1} шт.</span>
              </div>
            ))
          ) : (
            <p className="text-ink-muted italic text-[11px]">Список запчастей не распознан</p>
          )}
        </div>
      </div>

      {/* Быстрое действие ИИ */}
      {request.recommended_action && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50/60 p-4 space-y-2">
          <div className="flex items-center gap-2 text-emerald-800 font-bold">
            <Icon name="robot" size={16} />
            <span>Рекомендация ИИ-Ассистента</span>
          </div>
          <p className="text-[11px] text-emerald-900 leading-relaxed">
            ИИ рекомендует автоматический переход в статус <strong>{getStatusLabel(request.recommended_action.target_state || '')}</strong>.
          </p>
          <Button
            variant="success"
            icon="check"
            className="w-full justify-center"
            onClick={() => {
              if (request.recommended_action?.target_state) {
                void onTransition(request.recommended_action.target_state, 'Одобрено по рекомендации ИИ (1-Click)');
              }
            }}
          >
            Принять рекомендацию (1-Click)
          </Button>
        </div>
      )}

      {/* Доступные переходы статуса */}
      <div className="space-y-2 pt-2 border-t border-line">
        <h4 className="text-[10px] font-bold uppercase tracking-wider text-ink-muted">Действия оператора</h4>
        <TransitionActions
          status={request.status}
          requestId={request.request_id}
          allowedTargets={allowedTargets}
          onTransition={(targetState, reason) => onTransition(targetState, reason)}
        />
      </div>

      {/* Переход в полный рабочий хаб */}
      <div className="pt-3">
        <Button
          variant="secondary"
          icon="arrow-right"
          className="w-full justify-center"
          onClick={() => onOpenFullWorkspace(request)}
        >
          Открыть полный хаб подбора и счетов
        </Button>
      </div>
    </div>
  );
};

export default RequestInspector;
