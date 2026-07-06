import React from 'react';

interface ChevronStepperProps {
  status: string;
}

export const ChevronStepper: React.FC<ChevronStepperProps> = ({ status }) => {
  const stages = [
    { id: 'INTAKE', label: 'Входящая', icon: 'fa-inbox' },
    { id: 'AI_PARSE', label: 'ИИ Разбор', icon: 'fa-robot' },
    { id: 'VERIFICATION', label: 'Проверка', icon: 'fa-user-check' },
    { id: 'MATCHING', label: 'Метчинг', icon: 'fa-shuffle' },
    { id: 'PRICING', label: 'Прайсинг', icon: 'fa-calculator' },
    { id: 'APPROVAL', label: 'Согласование', icon: 'fa-file-signature' },
    { id: 'INVOICE', label: 'Счет', icon: 'fa-file-invoice-dollar' },
    { id: 'FULFILLED', label: 'Исполнено', icon: 'fa-circle-check' }
  ];

  const getChevronStepIndex = (statusStr: string): number => {
    const s = statusStr.toUpperCase();
    
    // Stage 1: INTAKE (Входящая)
    if (['NEW', 'NORMALIZING', 'PARSING'].includes(s)) return 0;
    
    // Stage 2: AI_PARSE (ИИ Разбор)
    if (['VIN_CHECK', 'PART_EXTRACTION'].includes(s)) return 1;
    
    // Stage 3: VERIFICATION (Проверка)
    if (['NEEDS_MANUAL_PARSE', 'NEEDS_CLARIFICATION', 'MANUAL_REVIEW', 'VALIDATED'].includes(s)) return 2;
    
    // Stage 4: MATCHING (Метчинг)
    if (['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'SUPPLIER_ISSUE'].includes(s)) return 3;
    
    // Stage 5: PRICING (Прайсинг)
    if (['PRICING_REVIEW', 'REWORK', 'FINANCE_REVIEW'].includes(s)) return 4;
    
    // Stage 6: APPROVAL (Согласование)
    if (['READY_FOR_APPROVAL', 'APPROVED'].includes(s)) return 5;
    
    // Stage 7: INVOICE (Счет)
    if (['ERP_SYNCING', 'INVOICE_DRAFTED'].includes(s)) return 6;
    
    // Stage 8: FULFILLED (Исполнено)
    if (['SENT_TO_CLIENT', 'PAID', 'PURCHASE_ORDERED', 'FULFILLED', 'CLOSED'].includes(s)) return 7;
    
    return 0;
  };

  const isCancelled = ['CANCELLED', 'FAILED', 'CLIENT_REJECTED', 'EXPIRED'].includes(status.toUpperCase());
  const isError = status.toUpperCase() === 'ERP_SYNC_FAILED';
  const currentIndex = getChevronStepIndex(status);

  if (isCancelled) {
    return (
      <div className="w-full bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-3 mb-4 shadow-sm">
        <i className="fas fa-circle-xmark text-lg"></i>
        <div>
          <span className="font-bold text-xs uppercase tracking-wider block">Заявка отменена или отклонена</span>
          <span className="text-[11px] opacity-90">Текущий статус: {status}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full flex mb-4 rounded-xl overflow-hidden border border-slate-200 bg-slate-50 shadow-inner select-none">
      {stages.map((stage, idx) => {
        const isCompleted = idx < currentIndex;
        const isCurrent = idx === currentIndex;
        const isStepError = isError && stage.id === 'INVOICE';

        let bgClass = 'bg-slate-50 text-slate-500';
        let zIndex = stages.length - idx;

        if (isCompleted) {
          bgClass = 'bg-emerald-50 text-emerald-700 border-emerald-100';
        }
        if (isCurrent) {
          bgClass = 'bg-[var(--accent-primary)] text-white shadow-md border-transparent';
        }
        if (isStepError) {
          bgClass = 'bg-red-600 text-white border-transparent';
        }

        return (
          <div
            key={stage.id}
            style={{ zIndex }}
            className={`flex-1 relative flex items-center justify-center py-2.5 text-[10px] font-bold uppercase tracking-wider transition-all ${bgClass} ${idx !== 0 ? 'pl-5' : 'pl-2'} pr-2 border-r border-slate-200 last:border-r-0`}
          >
            {/* Chevron Arrow Divider */}
            {idx !== stages.length - 1 && (
              <div className="absolute right-[-12px] top-0 h-full w-4 overflow-hidden z-10 pointer-events-none">
                <div className="h-[50%] origin-top-left rotate-[45deg] translate-y-[-4px] border-r border-t border-slate-200 bg-inherit absolute w-[16px] left-0 top-0"></div>
                <div className="h-[50%] origin-bottom-left -rotate-[45deg] translate-y-[4px] border-r border-b border-slate-200 bg-inherit absolute w-[16px] left-0 bottom-0"></div>
              </div>
            )}
            <div className="flex items-center gap-1.5 z-20">
              {isStepError ? (
                <i className="fas fa-triangle-exclamation text-white animate-pulse" />
              ) : isCompleted ? (
                <i className="fas fa-circle-check text-emerald-600" />
              ) : isCurrent ? (
                <i className={`fas ${stage.icon} text-white`} />
              ) : (
                <span className="w-3.5 h-3.5 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center text-[8px]">
                  {idx + 1}
                </span>
              )}
              <span className="truncate">{stage.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
