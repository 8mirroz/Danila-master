import React from 'react';

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

interface KanbanBoardProps {
  requests: Request[];
  onSelectRequest: (req: Request) => void;
  onTransitionRequest?: (requestId: string, targetState: string, reason: string) => Promise<void>;
  resolveDropTarget?: (request: Request, columnStatuses: string[]) => string | null;
}

export const KanbanBoard: React.FC<KanbanBoardProps> = ({
  requests,
  onSelectRequest,
  onTransitionRequest,
  resolveDropTarget,
}) => {
  // Columns definition mapping
  const columns = [
    {
      id: 'intake',
      title: 'Входящие',
      icon: 'fa-file-arrow-up text-blue-500',
      bgClass: 'bg-blue-50/40 border-blue-100',
      statuses: [
        'NEW',
        'NORMALIZING',
        'PARSING',
        'VIN_CHECK',
        'PART_EXTRACTION',
        'NEEDS_MANUAL_PARSE',
        'NEEDS_CLARIFICATION',
      ],
    },
    {
      id: 'matching',
      title: 'Подбор',
      icon: 'fa-arrows-split-up-and-left text-sky-500',
      bgClass: 'bg-sky-50/40 border-sky-100',
      statuses: ['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING', 'MANUAL_REVIEW', 'REWORK'],
    },
    {
      id: 'approval',
      title: 'Согласование',
      icon: 'fa-circle-check text-amber-500',
      bgClass: 'bg-amber-50/40 border-amber-100',
      statuses: ['PRICING_REVIEW', 'READY_FOR_APPROVAL'],
    },
    {
      id: 'invoicing',
      title: 'Счета в ERP',
      icon: 'fa-file-invoice-dollar text-emerald-500',
      bgClass: 'bg-emerald-50/40 border-emerald-100',
      statuses: [
        'APPROVED',
        'ERP_SYNCING',
        'INVOICE_DRAFTED',
        'SENT_TO_CLIENT',
        'PAID',
        'PURCHASE_ORDERED',
        'FULFILLED',
        'CLOSED',
        'CANCELLED',
        'FAILED',
        'ERP_SYNC_FAILED',
        'CLIENT_REJECTED',
        'EXPIRED',
      ],
    },
  ];

  // Helper to get number of items in order
  const getPartsCount = (partsJson: string) => {
    try {
      const parsed = JSON.parse(partsJson || '[]');
      return Array.isArray(parsed) ? parsed.length : 0;
    } catch {
      return 0;
    }
  };

  const formatCreatedAt = (value: string) => {
    if (!value) return 'нет данных';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;

    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsed);
  };

  // Helper for rendering human-readable status badge
  const renderStatus = (status: string) => {
    const statusesMap: Record<string, { label: string; cls: string }> = {
      NEW: { label: 'Новый', cls: 'bg-slate-100 text-slate-700 border-slate-200' },
      NORMALIZING: { label: 'Нормализация', cls: 'bg-blue-50 text-blue-700 border-blue-100' },
      PARSING: { label: 'Анализ текста', cls: 'bg-blue-50 text-blue-700 border-blue-100' },
      VIN_CHECK: { label: 'Проверка VIN', cls: 'bg-blue-50 text-blue-700 border-blue-100' },
      PART_EXTRACTION: { label: 'Извлечение деталей', cls: 'bg-blue-50 text-blue-700 border-blue-100' },
      MATCHING: { label: 'Подбор предложений', cls: 'bg-sky-50 text-sky-700 border-sky-100' },
      SUPPLIER_SEARCH: { label: 'Поиск поставщика', cls: 'bg-sky-50 text-sky-700 border-sky-100' },
      OFFER_RANKING: { label: 'Ранжирование', cls: 'bg-sky-50 text-sky-700 border-sky-100' },
      MANUAL_REVIEW: { label: 'Ручная проверка', cls: 'bg-rose-50 text-rose-700 border-rose-100 font-bold' },
      PRICING_REVIEW: { label: 'Калькуляция цен', cls: 'bg-amber-50 text-amber-700 border-amber-100' },
      READY_FOR_APPROVAL: { label: 'Ожидает апрува', cls: 'bg-amber-50 text-amber-700 border-amber-100 animate-pulse font-bold' },
      APPROVED: { label: 'Согласован', cls: 'bg-emerald-50 text-emerald-700 border-emerald-100' },
      ERP_SYNCING: { label: 'Синхронизация ERP', cls: 'bg-cyan-50 text-cyan-700 border-cyan-100' },
      INVOICE_DRAFTED: { label: 'Счёт выставлен', cls: 'bg-emerald-50 text-emerald-700 border-emerald-100' },
      SENT_TO_CLIENT: { label: 'Отправлен клиенту', cls: 'bg-teal-50 text-teal-700 border-teal-100' },
      PAID: { label: 'Оплачен', cls: 'bg-green-100 text-green-800 border-green-200' },
      PURCHASE_ORDERED: { label: 'Закупка', cls: 'bg-slate-100 text-slate-700 border-slate-200' },
      FULFILLED: { label: 'Выполнен', cls: 'bg-slate-100 text-slate-700 border-slate-200' },
      CLOSED: { label: 'Закрыт', cls: 'bg-slate-100 text-slate-700 border-slate-200' },
      CANCELLED: { label: 'Отменен', cls: 'bg-red-50 text-red-700 border-red-100' },
      FAILED: { label: 'Сбой', cls: 'bg-red-50 text-red-700 border-red-100' },
      ERP_SYNC_FAILED: { label: 'Ошибка ERP', cls: 'bg-red-50 text-red-700 border-red-100 font-bold' },
    };

    const config = statusesMap[status] || { label: status, cls: 'bg-slate-100 text-slate-700 border-slate-200' };

    return (
      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${config.cls}`}>
        {config.label}
      </span>
    );
  };

  // Drag over handler to allow dropping
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  // Drop handler
  const handleDrop = async (e: React.DragEvent, targetColumnId: string) => {
    e.preventDefault();
    const requestId = e.dataTransfer.getData('text/plain');
    if (!requestId) return;

    const req = requests.find((r) => r.request_id === requestId);
    if (!req) return;

    const column = columns.find((item) => item.id === targetColumnId);
    const candidateStates = column?.statuses ?? [];
    const targetState = resolveDropTarget
      ? resolveDropTarget(req, candidateStates)
      : candidateStates.find((state) => state !== req.status) ?? null;

    if (targetState && req.status !== targetState) {
      if (onTransitionRequest) {
        try {
          await onTransitionRequest(
            requestId,
            targetState,
            `Перенос карточки в колонку "${column?.title ?? targetColumnId}"`
          );
        } catch (err) {
          console.error(err);
        }
      }
    }
  };

  const handleDragStart = (e: React.DragEvent, reqId: string) => {
    e.dataTransfer.setData('text/plain', reqId);
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="grid h-[calc(100vh-210px)] grid-cols-1 gap-4 overflow-hidden md:grid-cols-4">
      {columns.map((col) => {
        const columnRequests = requests.filter((r) => col.statuses.includes(r.status));

        return (
          <div
            key={col.id}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, col.id)}
            className={`flex h-full flex-col rounded-[24px] border p-3 shadow-sm ${col.bgClass}`}
          >
            <div className="mb-3 flex items-center justify-between border-b border-[var(--border-default)] pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-white/70 bg-white/80 shadow-sm">
                  <i className={`fas ${col.icon} text-sm`}></i>
                </div>
                <div>
                  <span className="block text-xs font-bold text-[var(--text-primary)]">{col.title}</span>
                  <span className="text-[10px] text-[var(--text-muted)]">Статусов: {col.statuses.length}</span>
                </div>
              </div>
              <span className="rounded-full bg-white/85 px-2.5 py-1 text-[10px] font-bold text-[var(--text-secondary)] shadow-sm">
                {columnRequests.length}
              </span>
            </div>

            <div className="custom-scrollbar flex-1 space-y-2.5 overflow-y-auto pr-1">
              {columnRequests.length === 0 ? (
                <div className="rounded-[18px] border border-dashed border-[var(--border-default)] bg-white/60 py-8 text-center text-[10px] italic text-[var(--text-muted)]">
                  Нет заказов на этом этапе
                </div>
              ) : (
                columnRequests.map((req) => {
                  const isHighPriority = req.priority?.toLowerCase() === 'high' || req.priority?.toLowerCase() === 'высокий';
                  const partCount = getPartsCount(req.parts_json);

                  return (
                    <div
                      key={req.request_id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, req.request_id)}
                      onClick={() => onSelectRequest(req)}
                      className="group relative flex cursor-pointer flex-col gap-2.5 overflow-hidden rounded-[20px] border border-white/80 bg-white/92 p-3 shadow-sm transition-all hover:-translate-y-0.5 hover:border-[var(--accent-primary)] hover:shadow-md active:scale-[0.98]"
                    >
                      {isHighPriority && (
                        <div className="absolute left-0 right-0 top-0 h-1 bg-red-500 animate-pulse"></div>
                      )}

                      <div className="flex justify-between items-start gap-1">
                        <strong className="text-[11px] font-bold text-[var(--text-primary)] font-mono">
                          {req.request_id}
                        </strong>
                        <div className="flex items-center gap-1.5">
                          {isHighPriority && (
                            <span className="rounded-full border border-red-200 bg-red-50 px-1.5 py-0.5 text-[8px] font-extrabold uppercase text-red-600 animate-pulse">
                              Срочно
                            </span>
                          )}
                          {req.vehicle_vin_masked && (
                            <span className="rounded-full border border-sky-200 bg-sky-50 px-1.5 py-0.5 text-[8px] font-mono text-sky-600">
                              VIN
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <div className="text-xs font-bold text-[var(--text-primary)] truncate">
                          {req.customer_name}
                        </div>
                        {req.vehicle_make && (
                          <div className="text-[10px] text-[var(--text-muted)] font-medium">
                            {req.vehicle_make} {req.vehicle_model || ''}
                          </div>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-2)] px-2.5 py-2 text-[10px]">
                          <span className="block text-[var(--text-muted)]">Деталей</span>
                          <span className="mt-1 block font-extrabold text-[var(--text-primary)]">{partCount} шт.</span>
                        </div>
                        <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-2)] px-2.5 py-2 text-[10px]">
                          <span className="block text-[var(--text-muted)]">Источник</span>
                          <span className="mt-1 block truncate font-semibold text-[var(--text-primary)]">{req.source}</span>
                        </div>
                      </div>

                      <div className="flex justify-between items-center rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-2)] px-2 py-1.5 text-[10px]">
                        <span className="font-medium text-[var(--text-secondary)]">
                          Статус:
                        </span>
                        <span className="font-extrabold text-[var(--text-primary)]">
                          {renderStatus(req.status)}
                        </span>
                      </div>

                      <div className="flex justify-between items-center gap-1.5 border-t border-[var(--border-subtle)] pt-1.5">
                        <span className="text-[9px] font-medium text-[var(--text-muted)]">
                          Создан: {formatCreatedAt(req.created_at)}
                        </span>
                        <span className="flex items-center gap-1 text-[9px] font-bold text-[var(--text-muted)] transition-all group-hover:text-[var(--accent-primary)]">
                          Открыть <i className="fas fa-arrow-right text-[8px] transform group-hover:translate-x-0.5 transition-transform"></i>
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
