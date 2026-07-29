import React, { useState } from 'react';
import { TRANSITION_META } from '../lib/stateMachine';
import { ActionButton } from './Primitives';
import { ConfirmModal } from './ConfirmModal';
import { notify } from '../lib/notify';

interface TransitionActionsProps {
  status: string;
  requestId: string;
  onTransition: (targetState: string, reason: string) => Promise<void>;
  compact?: boolean;
  allowedTargets?: string[];
}

export const TransitionActions: React.FC<TransitionActionsProps> = ({
  status,
  requestId: _requestId,
  onTransition,
  compact = false,
  allowedTargets = [],
}) => {
  const allowed = allowedTargets;
  const [activeTarget, setActiveTarget] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (allowed.length === 0) {
    return (
      <span className="text-[11px] text-[var(--text-muted)] italic">
        Нет подтверждённых действий ({status})
      </span>
    );
  }

  const handleConfirm = async (reason?: string) => {
    if (!activeTarget) return;
    setLoading(true);
    try {
      await onTransition(activeTarget, reason || `Переход в статус ${activeTarget}`);
      notify.transition(status, activeTarget);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Неизвестная ошибка при переходе статуса';
      notify.error(msg);
    } finally {
      setLoading(false);
      setActiveTarget(null);
    }
  };

  const getVariant = (target: string) => {
    const meta = TRANSITION_META[target];
    if (!meta) return 'secondary';
    return meta.variant;
  };

  return (
    <>
      <div className={`flex flex-wrap items-center gap-2 ${compact ? 'text-[11px]' : ''}`}>
        {allowed.map((target) => {
          const meta = TRANSITION_META[target] || {
            label: target,
            variant: 'secondary',
            icon: 'fa-arrow-right',
          };

          return (
            <ActionButton
              key={target}
              variant={meta.variant}
              disabled={loading}
              onClick={() => setActiveTarget(target)}
            >
              <i className={`fas ${meta.icon} text-[10px]`} />
              <span>{meta.label}</span>
            </ActionButton>
          );
        })}
      </div>

      {activeTarget && (
        <ConfirmModal
          isOpen={!!activeTarget}
          title={`Смена статуса: ${status} → ${activeTarget}`}
          description={`Вы действительно хотите перевести запрос в статус "${TRANSITION_META[activeTarget]?.label || activeTarget}"?`}
          variant={getVariant(activeTarget)}
          requireReason={['CANCELLED', 'REWORK', 'MANUAL_REVIEW'].includes(activeTarget)}
          reasonPlaceholder="Укажите причину или примечание оператора..."
          confirmLabel={TRANSITION_META[activeTarget]?.label || 'Подтвердить'}
          onConfirm={handleConfirm}
          onCancel={() => setActiveTarget(null)}
        />
      )}
    </>
  );
};
