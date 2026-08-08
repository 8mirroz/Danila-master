import React, { useEffect, useRef } from 'react';
import { Icon, TrafficDot } from './Primitives';

interface SlideOverInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  status?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

export const SlideOverInspector: React.FC<SlideOverInspectorProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  status,
  children,
  footer,
}) => {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs transition-opacity animate-fadeIn">
      <div className="absolute inset-0" onClick={onClose} aria-hidden="true" />
      <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          className="w-screen max-w-md transform bg-surface-1 border-l border-line shadow-2xl transition-transform duration-300 ease-in-out flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-line px-5 py-4 bg-surface-2/60">
            <div className="flex items-center gap-2.5 min-w-0">
              {status && <TrafficDot status={status} />}
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-ink-primary truncate">{title}</h3>
                {subtitle && <p className="text-[11px] font-medium text-ink-secondary truncate">{subtitle}</p>}
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-control p-1.5 text-ink-muted hover:bg-surface-3 hover:text-ink-primary transition-colors focus:outline-none"
              title="Закрыть (Esc)"
              aria-label="Закрыть панель"
            >
              <Icon name="xmark" size={16} />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {children}
          </div>

          {/* Footer */}
          {footer && (
            <div className="border-t border-line p-4 bg-surface-2/80 flex items-center justify-end gap-2">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SlideOverInspector;
