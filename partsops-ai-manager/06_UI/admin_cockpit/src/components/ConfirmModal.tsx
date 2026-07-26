import React, { useState } from 'react';
import { useFocusTrap, useKeydown } from '../lib/focus';

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

  const getVariantButtonStyles = () => {
    switch (variant) {
      case 'danger':
        return 'bg-red-600 hover:bg-red-700 text-white shadow-red-500/20';
      case 'warning':
        return 'bg-amber-600 hover:bg-amber-700 text-white shadow-amber-500/20';
      case 'secondary':
        return 'bg-slate-700 hover:bg-slate-800 text-white shadow-slate-500/20';
      default:
        return 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-500/20';
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirm(requireReason ? reason : (reason || undefined));
    setReason('');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-fadeIn">
      <div
        ref={modalRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="w-full max-w-md rounded-2xl border border-[var(--border-default)] bg-[var(--surface-1)] p-6 shadow-2xl space-y-4 animate-scaleUp"
      >
        <div className="flex items-start gap-3">
          <div className={`p-2.5 rounded-xl text-lg flex items-center justify-center shrink-0 ${
            variant === 'danger' ? 'bg-red-100 text-red-600' :
            variant === 'warning' ? 'bg-amber-100 text-amber-600' :
            variant === 'secondary' ? 'bg-slate-100 text-slate-700' :
            'bg-emerald-100 text-emerald-600'
          }`}>
            <i className={`fas ${
              variant === 'danger' ? 'fa-triangle-exclamation' :
              variant === 'warning' ? 'fa-circle-exclamation' :
              'fa-shield-check'
            }`} />
          </div>
          <div>
            <h3 id="modal-title" className="text-sm font-bold text-[var(--text-primary)]">
              {title}
            </h3>
            {description && (
              <p className="mt-1 text-xs text-[var(--text-secondary)] leading-relaxed">
                {description}
              </p>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {requireReason && (
            <div>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={reasonPlaceholder}
                rows={3}
                required
                className="w-full rounded-xl border border-[var(--border-default)] bg-[var(--surface-2)] p-3 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
              />
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-xl border border-[var(--border-default)] hover:bg-[var(--surface-2)] transition-colors"
            >
              {cancelLabel}
            </button>
            <button
              type="submit"
              className={`px-4 py-2 text-xs font-semibold rounded-xl shadow-lg transition-all ${getVariantButtonStyles()}`}
            >
              {confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
