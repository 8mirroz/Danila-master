import React from 'react';
import { StatusBadge, Icon } from './Primitives';

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

interface KanbanCardProps {
  request: Request;
  onSelectRequest: (req: Request) => void;
  onRunPipeline?: (req: Request) => void;
  isHighlighted?: boolean;
  onDragBegin?: (requestId: string) => void;
  onDragFinish?: () => void;
  isDropPending?: boolean;
}

const formatRelativeTime = (dateStr?: string) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.max(0, Math.floor(diffMs / 1000));
  const diffMins = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'Только что';
  if (diffMins < 60) return `${diffMins} м. назад`;
  if (diffHours < 24) return `${diffHours} ч. назад`;
  if (diffDays === 1) return 'Вчера';
  if (diffDays < 7) return `${diffDays} дн.`;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
};

export const KanbanCard: React.FC<KanbanCardProps> = ({
  request,
  onSelectRequest,
  onRunPipeline,
  isHighlighted = false,
  onDragBegin,
  onDragFinish,
  isDropPending = false,
}) => {
  const [isDragging, setIsDragging] = React.useState(false);

  let partsCount = 0;
  try {
    const parsed = request.parts_json ? JSON.parse(request.parts_json) : [];
    partsCount = Array.isArray(parsed) ? parsed.length : 0;
  } catch {
    partsCount = 0;
  }

  const getPriorityBadge = (priority?: string) => {
    const p = (priority || '').toLowerCase();
    if (p === 'urgent' || p === 'high') {
      return (
        <span className="inline-flex items-center gap-0.5 rounded bg-rose-50 px-1.5 py-0.5 text-[9px] font-extrabold text-rose-700 border border-rose-200">
          <Icon name="exclamation-triangle" size={9} /> СРОЧНО
        </span>
      );
    }
    if (p === 'vip') {
      return (
        <span className="inline-flex items-center gap-0.5 rounded bg-violet-50 px-1.5 py-0.5 text-[9px] font-extrabold text-violet-700 border border-violet-200">
          <Icon name="user-shield" size={9} /> VIP
        </span>
      );
    }
    return null;
  };

  const getBlockerBadges = (req: Request) => {
    const badges = [];
    const status = (req.status || '').toUpperCase();

    if (status === 'NEEDS_CLARIFICATION' || (!req.vehicle_vin_masked && status === 'NORMALIZING')) {
      badges.push(
        <span key="vin" className="inline-flex items-center gap-0.5 rounded bg-amber-50 px-1.5 py-0.5 text-[9px] font-bold text-amber-800 border border-amber-200">
          <Icon name="exclamation-circle" size={9} /> Без VIN
        </span>
      );
    }
    if (status === 'ERP_SYNC_FAILED') {
      badges.push(
        <span key="erp" className="inline-flex items-center gap-0.5 rounded bg-red-50 px-1.5 py-0.5 text-[9px] font-bold text-red-800 border border-red-200">
          <Icon name="exclamation-triangle" size={9} /> Ошибка 1С
        </span>
      );
    }
    if (status === 'MANUAL_REVIEW' || status === 'FAILED') {
      badges.push(
        <span key="blocked" className="inline-flex items-center gap-0.5 rounded bg-rose-50 px-1.5 py-0.5 text-[9px] font-bold text-rose-800 border border-rose-200">
          <Icon name="user-check" size={9} /> Ручной контроль
        </span>
      );
    }

    if (req.created_at) {
      const createdDate = new Date(req.created_at);
      const hoursAgo = (new Date().getTime() - createdDate.getTime()) / (1000 * 3600);
      if (hoursAgo > 24 && !['CLOSED', 'CANCELLED', 'PAID', 'FULFILLED'].includes(status)) {
        badges.push(
          <span key="sla" className="inline-flex items-center gap-0.5 rounded bg-orange-50 px-1.5 py-0.5 text-[9px] font-bold text-orange-800 border border-orange-200">
            <Icon name="clock" size={9} /> Зависло &gt;24ч
          </span>
        );
      }
    }

    return badges;
  };

  return (
    <div
      role="group"
      aria-label={`Запрос ${request.request_id}`}
      data-request-id={request.request_id}
      tabIndex={0}
      draggable={!isDropPending}
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', request.request_id);
        e.dataTransfer.effectAllowed = 'move';
        setIsDragging(true);
        onDragBegin?.(request.request_id);
      }}
      onDragEnd={() => {
        setIsDragging(false);
        onDragFinish?.();
      }}
      onClick={() => {
        if (!isDragging && !isDropPending) onSelectRequest(request);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelectRequest(request);
        }
      }}
      className={`group relative rounded-xl border border-slate-200/90 bg-white p-3 shadow-xs hover:shadow-md hover:border-blue-400 transition-all duration-150 cursor-grab active:cursor-grabbing ${
        isDropPending
          ? 'opacity-60 pointer-events-none ring-2 ring-amber-300'
          : isDragging
            ? 'opacity-40 scale-95 border-dashed border-blue-500'
            : isHighlighted
              ? 'ring-2 ring-blue-500 bg-blue-50/20'
              : ''
      }`}
      aria-busy={isDropPending || undefined}
    >
      {/* Шапка карточки */}
      <div className="flex items-start justify-between gap-1.5 mb-1.5 min-w-0">
        <div className="flex flex-wrap items-center gap-1 min-w-0 flex-1">
          <span className="font-mono text-[11px] font-extrabold text-blue-600 tracking-tight shrink-0">
            {request.request_id}
          </span>
          {getPriorityBadge(request.priority)}
          {getBlockerBadges(request)}
        </div>
        <div className="shrink-0">
          <StatusBadge status={request.status} />
        </div>
      </div>

      {/* Имя заказчика */}
      <div className="text-xs font-bold text-slate-800 truncate mb-2 leading-tight">
        {request.customer_name || 'Заказчик не указан'}
      </div>

      {/* Информационные чипы */}
      <div className="flex flex-wrap items-center gap-1.5 mb-2.5">
        {request.vehicle_make && (
          <div className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
            <Icon name="car" size={10} className="text-slate-400" />
            <span className="max-w-[120px] truncate">
              {request.vehicle_make} {request.vehicle_model || ''}
            </span>
          </div>
        )}

        {partsCount > 0 && (
          <span className="inline-flex items-center rounded-md bg-blue-50 border border-blue-100 px-1.5 py-0.5 text-[10px] font-bold text-blue-700">
            {partsCount} поз.
          </span>
        )}

        {request.source && (
          <span className="inline-flex items-center rounded-md bg-slate-50 border border-slate-200 px-1.5 py-0.5 text-[9px] font-bold uppercase text-slate-500 tracking-wider">
            {request.source}
          </span>
        )}
      </div>

      {/* Подвал карточки */}
      <div className="flex items-center justify-between border-t border-slate-100 pt-2 text-[10px] font-medium text-slate-400">
        <div className="flex items-center gap-1 font-mono">
          <Icon name="clock" size={10} />
          <span>{formatRelativeTime(request.created_at)}</span>
        </div>

        {onRunPipeline && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRunPipeline(request);
            }}
            className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-700 hover:bg-blue-100"
            title="Запустить мультиагентный ИИ-пайплайн"
            aria-label={`Запустить pipeline для ${request.request_id}`}
          >
            <Icon name="play" size={8} />
            Запуск ИИ
          </button>
        )}
      </div>
    </div>
  );
};

export default KanbanCard;
