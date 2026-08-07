import React, { useState } from 'react';
import { useFocusTrap, useKeydown } from '../lib/focus';
import { Button, Icon } from './Primitives';

interface ConfirmModalProps {
  isOpen: boolean;
  title: string;
  description?: string;
  variant?: 'primary' | 'warning' | 'danger' | 'secondary';
  requireReason?: boolean;
  reasonPlaceholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: (reason?: string) => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  title,
  description,
  variant = 'primary',
  requireReason = false,
  reasonPlaceholder = 'Укажите причину или примечание...',
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  onConfirm,
  onCancel,
}) => {
  const [reason, setReason] = useState('');
  const modalRef = React.useRef<HTMLDivElement>(null);

  useFocusTrap(modalRef, isOpen);
  useKeydown('Escape', onCancel, [isOpen]);

  if (!isOpen) return null;

  const buttonVariant =
    variant === 'danger' ? 'danger' :
    variant === 'warning' ? 'warning' :
    variant === 'secondary' ? 'secondary' :
    'success';

  const iconTone =
    variant === 'danger' ? 'bg-rose-50 text-accent-danger border-rose-200' :
    variant === 'warning' ? 'bg-amber-50 text-accent-warning border-amber-200' :
    variant === 'secondary' ? 'bg-surface-3 text-ink-secondary border-line' :
    'bg-emerald-50 text-accent-success border-emerald-200';

  const iconName =
    variant === 'danger' ? 'exclamation-triangle' :
    variant === 'warning' ? 'circle-info' :
    'file-shield';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(requireReason ? reason : (reason || undefined));
    setReason('');
  };

  return (
    <div className="ds-modal-backdrop animate-fadeIn">
      <div
        ref={modalRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="modal-panel w-full max-w-md p-6 space-y-4"
      >
        <div className="flex items-start gap-3">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-control border ${iconTone}`}>
            <Icon name={iconName} size={18} />
          </div>
          <div>
            <h3 id="modal-title" className="text-sm font-bold text-ink-primary">
              {title}
            </h3>
            {description && (
              <p className="mt-1 text-xs text-ink-secondary leading-relaxed">
                {description}
              </p>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {requireReason && (
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={reasonPlaceholder}
              rows={3}
              required
              className="ds-input min-h-[84px] resize-y"
            />
          )}

          <div className="flex items-center justify-end gap-2.5 pt-1">
            <Button type="button" variant="secondary" onClick={onCancel}>
              {cancelLabel}
            </Button>
            <Button type="submit" variant={buttonVariant}>
              {confirmLabel}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
