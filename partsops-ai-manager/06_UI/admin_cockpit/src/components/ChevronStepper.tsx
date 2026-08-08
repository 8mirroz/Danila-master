import React from 'react';
import { Icon } from './Primitives';

interface ChevronStepperProps {
  status: string;
  activeIndex?: number;
  onStepClick?: (index: number) => void;
  canOpenStep?: (index: number) => boolean;
}

export const ChevronStepper: React.FC<ChevronStepperProps> = ({ status, activeIndex, onStepClick, canOpenStep }) => {
  const stages = [
    { id: 'INTAKE', label: 'Входящая', icon: 'inbox' },
    { id: 'AI_PARSE', label: 'ИИ Разбор', icon: 'robot' },
    { id: 'VERIFICATION', label: 'Проверка', icon: 'user-check' },
    { id: 'MATCHING', label: 'Метчинг', icon: 'shuffle' },
    { id: 'PRICING', label: 'Прайсинг', icon: 'calculator' },
    { id: 'APPROVAL', label: 'Согласование', icon: 'file-signature' },
    { id: 'INVOICE', label: 'Счет', icon: 'file-invoice-dollar' },
    { id: 'FULFILLED', label: 'Исполнено', icon: 'circle-check' },
  ];

  const getChevronStepIndex = (statusStr: string): number => {
    const s = statusStr.toUpperCase();
    if (['NEW', 'NORMALIZING', 'PARSING'].includes(s)) return 0;
    if (['VIN_CHECK', 'PART_EXTRACTION'].includes(s)) return 1;
    if (['NEEDS_MANUAL_PARSE', 'NEEDS_CLARIFICATION', 'MANUAL_REVIEW', 'VALIDATED'].includes(s)) return 2;
    if (['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'SUPPLIER_ISSUE'].includes(s)) return 3;
    if (['PRICING_REVIEW', 'REWORK', 'FINANCE_REVIEW'].includes(s)) return 4;
    if (['READY_FOR_APPROVAL', 'APPROVED'].includes(s)) return 5;
    if (['ERP_SYNCING', 'INVOICE_DRAFTED'].includes(s)) return 6;
    if (['SENT_TO_CLIENT', 'PAID', 'PURCHASE_ORDERED', 'FULFILLED', 'CLOSED'].includes(s)) return 7;
    return 0;
  };

  const isCancelled = ['CANCELLED', 'FAILED', 'CLIENT_REJECTED', 'EXPIRED'].includes(status.toUpperCase());
  const isError = status.toUpperCase() === 'ERP_SYNC_FAILED';
  const currentIndex = activeIndex ?? getChevronStepIndex(status);

  if (isCancelled) {
    return (
      <div className="w-full bg-rose-50 border border-rose-200 text-rose-800 px-4 py-3 rounded-xl flex items-center gap-3 mb-3 shadow-xs">
        <Icon name="circle-xmark" size={18} className="text-rose-600" />
        <div>
          <span className="font-extrabold text-xs uppercase tracking-wider block">Заявка отменена или отклонена</span>
          <span className="text-[11px] font-medium opacity-90">Текущий статус: {status}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full mb-3 rounded-2xl border border-slate-200/90 bg-white p-2 shadow-xs select-none">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-1.5">
        {stages.map((stage, idx) => {
          const isCompleted = idx < currentIndex;
          const isCurrent = idx === currentIndex;
          const isStepError = isError && stage.id === 'INVOICE';
          const isEnabled = !canOpenStep || canOpenStep(idx);

          return (
            <button
              type="button"
              key={stage.id}
              disabled={!isEnabled}
              aria-current={isCurrent ? 'step' : undefined}
              aria-label={`${stage.label}${isCompleted ? ', завершён' : isCurrent ? ', текущий шаг' : ''}`}
              onClick={() => onStepClick?.(idx)}
              className={`flex items-center justify-center gap-1.5 py-2 px-2 rounded-xl text-[11px] font-bold transition-all duration-150 ${
                isCurrent
                  ? 'bg-blue-600 text-white shadow-sm font-extrabold scale-[1.02]'
                  : isCompleted
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200/80 hover:bg-emerald-100/80'
                  : isStepError
                  ? 'bg-rose-600 text-white animate-pulse'
                  : 'bg-slate-100 text-slate-600 border border-slate-200/80 hover:bg-slate-200/60'
              } ${onStepClick && isEnabled ? 'cursor-pointer active:scale-95' : 'cursor-default'} disabled:cursor-not-allowed disabled:opacity-40`}
            >
              {isStepError ? (
                <Icon name="triangle-exclamation" size={13} className="text-white" />
              ) : isCompleted ? (
                <span className="w-3.5 h-3.5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[8px] font-extrabold shrink-0">
                  ✓
                </span>
              ) : isCurrent ? (
                <span className="w-2 h-2 rounded-full bg-white animate-pulse shrink-0" />
              ) : (
                <span className="w-3.5 h-3.5 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center text-[9px] font-bold shrink-0">
                  {idx + 1}
                </span>
              )}
              <span className="truncate">{stage.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default ChevronStepper;
