import { useCallback, useEffect, useState } from 'react';
import { InlineAlert, ActionButton } from './Primitives';
import { apiFetch } from '../lib/api';

type AuditEvent = {
  event_id: string;
  event_type: string;
  actor_type: string;
  actor_id: string;
  occurred_at: string;
  payload: any;
  event_hash: string;
};

type AuditTimelineProps = {
  requestId: string;
};

export const AuditTimeline = ({ requestId }: AuditTimelineProps) => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [integrity, setIntegrity] = useState<{ valid: boolean; broken_at_event_id: string | null } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters state
  const [searchQuery, setSearchQuery] = useState('');
  const [actorFilter, setActorFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [sortOrder, setSortOrder] = useState<'NEWEST' | 'OLDEST'>('NEWEST');

  const fetchAuditData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [resEvents, resAudit] = await Promise.all([
        apiFetch(`/api/requests/${requestId}/events`),
        apiFetch(`/api/requests/${requestId}/audit`),
      ]);

      if (!resEvents.ok) {
        throw new Error(`events: ${resEvents.status} ${resEvents.statusText}`);
      }
      if (!resAudit.ok) {
        throw new Error(`audit: ${resAudit.status} ${resAudit.statusText}`);
      }

      const [eventsData, auditData] = await Promise.all([resEvents.json(), resAudit.json()]);
      setEvents(eventsData.events || []);
      setIntegrity(auditData);
    } catch (e) {
      console.error("Error fetching audit data", e);
      setError(e instanceof Error ? e.message : 'Не удалось загрузить аудит');
      setEvents([]);
      setIntegrity(null);
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    void fetchAuditData();
  }, [fetchAuditData]);

  const handleDownloadLog = () => {
    if (events.length === 0) return;
    const logData = {
      request_id: requestId,
      integrity: integrity,
      downloaded_at: new Date().toISOString(),
      events: events,
    };
    const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(logData, null, 2)
    )}`;
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', jsonString);
    downloadAnchor.setAttribute('download', `audit-log-${requestId}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'REQUEST_RECEIVED': return 'fa-file-import text-blue-500';
      case 'PART_INTENT_EXTRACTED': return 'fa-microchip text-sky-500';
      case 'STATE_CHANGED': return 'fa-shuffle text-cyan-500';
      case 'ERP_DOCUMENT_CREATED': return 'fa-file-invoice-dollar text-green-500';
      case 'ERP_SYNC_FAILED': return 'fa-triangle-exclamation text-red-500';
      default: return 'fa-circle-info text-slate-500';
    }
  };

  const getEventLabel = (type: string) => {
    switch (type) {
      case 'REQUEST_RECEIVED': return 'Запрос получен';
      case 'PART_INTENT_EXTRACTED': return 'Детали распознаны';
      case 'STATE_CHANGED': return 'Статус изменен';
      case 'ERP_DOCUMENT_CREATED': return 'Счет в ERP создан';
      case 'ERP_SYNC_FAILED': return 'Ошибка синхронизации ERP';
      case 'IDEMPOTENCY_HIT': return 'Повторный запрос (идемпотентность)';
      case 'PART_INTENT_EXTRACT_FAILED': return 'Ошибка распознавания деталей';
      default: return type;
    }
  };

  const getActorLabel = (actorType: string, actorId: string) => {
    const role = actorType === 'agent' ? 'Агент ИИ' : actorType === 'user' ? 'Специалист' : 'Система';
    return `${role} (${actorId})`;
  };

  // Filter and sort events
  const filteredEvents = events
    .filter((event) => {
      // 1. Text search
      const matchesSearch = searchQuery.trim() === '' || 
        event.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
        event.actor_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (event.payload && JSON.stringify(event.payload).toLowerCase().includes(searchQuery.toLowerCase()));
      
      // 2. Actor filter
      let matchesActor = true;
      if (actorFilter === 'AI') matchesActor = event.actor_type === 'agent';
      else if (actorFilter === 'SPECIALIST') matchesActor = event.actor_type === 'user';
      else if (actorFilter === 'SYSTEM') matchesActor = event.actor_type === 'system';

      // 3. Event Type filter
      let matchesType = true;
      if (typeFilter === 'REQUEST') matchesType = event.event_type === 'REQUEST_RECEIVED';
      else if (typeFilter === 'NORMALIZATION') matchesType = event.event_type.includes('PART_INTENT');
      else if (typeFilter === 'STATE') matchesType = event.event_type === 'STATE_CHANGED';
      else if (typeFilter === 'ERP') matchesType = event.event_type.includes('ERP');

      return matchesSearch && matchesActor && matchesType;
    })
    .sort((a, b) => {
      const timeA = new Date(a.occurred_at).getTime();
      const timeB = new Date(b.occurred_at).getTime();
      return sortOrder === 'NEWEST' ? timeB - timeA : timeA - timeB;
    });

  return (
    <div className="panel-card-tight p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-[var(--border-subtle)] pb-3">
        <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[var(--text-secondary)]">
          <i className="fas fa-history text-[var(--accent-primary)]"></i> История аудита и Цепочка событий
        </h3>
        <div className="flex gap-2">
          <ActionButton 
            variant="secondary" 
            icon="fa-sync" 
            onClick={fetchAuditData}
            className="py-1 px-2.5 text-xs"
          >
            Обновить
          </ActionButton>
        </div>
      </div>

      {integrity && (
        <InlineAlert 
          type={integrity.valid ? 'success' : 'danger'}
          message={
            <div className="flex items-center gap-2">
              <i className={`fas ${integrity.valid ? 'fa-lock text-green-700 text-sm' : 'fa-lock-open text-red-700 text-sm animate-pulse'}`}></i>
              <span>
                {integrity.valid 
                  ? 'Целостность цепочки событий: ПОДТВЕРЖДЕНА (хеш-код SHA-256 не изменен)' 
                  : `Внимание! Цепочка событий нарушена на ID события: ${integrity.broken_at_event_id}`}
              </span>
            </div>
          }
        />
      )}

      {error && (
        <InlineAlert
          type="danger"
          message={`Аудит недоступен: ${error}`}
        />
      )}

      {/* Toolbar с фильтрами */}
      {events.length > 0 && (
        <div className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-xl p-3 mb-5 space-y-3 text-xs shadow-inner">
          <div className="flex flex-wrap gap-3 items-center justify-between">
            {/* Текстовый поиск */}
            <div className="flex-1 min-w-[200px] relative">
              <i className="fas fa-magnifying-glass absolute left-3 top-2 text-[var(--text-muted)] text-[10px]"></i>
              <input 
                type="text"
                placeholder="Поиск по событиям/данным..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg pl-8 pr-2.5 py-1 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)] font-sans"
              />
            </div>

            {/* Выбор актора */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Инициатор:</span>
              <select
                value={actorFilter}
                onChange={(e) => setActorFilter(e.target.value)}
                className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg px-2 py-1 text-xs outline-none focus:border-[var(--accent-primary)]"
              >
                <option value="ALL">Все</option>
                <option value="AI">ИИ Агент</option>
                <option value="SPECIALIST">Специалист</option>
                <option value="SYSTEM">Система</option>
              </select>
            </div>

            {/* Выбор типа события */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Событие:</span>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg px-2 py-1 text-xs outline-none focus:border-[var(--accent-primary)]"
              >
                <option value="ALL">Все типы</option>
                <option value="REQUEST">Запросы</option>
                <option value="NORMALIZATION">Распознавание</option>
                <option value="STATE">Статусы</option>
                <option value="ERP">Интеграция ERP</option>
              </select>
            </div>

            {/* Выбор направления сортировки */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Порядок:</span>
              <select
                value={sortOrder}
                onChange={(e: any) => setSortOrder(e.target.value)}
                className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-lg px-2 py-1 text-xs outline-none focus:border-[var(--accent-primary)]"
              >
                <option value="NEWEST">Сначала новые</option>
                <option value="OLDEST">Сначала старые</option>
              </select>
            </div>

            {/* Скачать лог */}
            <ActionButton 
              variant="secondary"
              icon="fa-download"
              disabled={events.length === 0}
              onClick={handleDownloadLog}
              className="py-1 px-3 ml-auto text-[11px] font-bold"
              title="Скачать лог в формате JSON"
            >
              Скачать лог
            </ActionButton>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-xs text-[var(--text-secondary)] py-12 text-center flex flex-col items-center justify-center gap-2">
          <i className="fas fa-spinner animate-spin text-lg text-[var(--accent-primary)]"></i>
          <span>Загрузка проверенных логов аудита...</span>
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="text-xs text-[var(--text-muted)] py-12 text-center">
          Событий аудита с выбранными фильтрами не найдено.
        </div>
      ) : (
        <div className="relative ml-4 space-y-5 border-l border-[var(--border-strong)] pl-6 py-2">
          {filteredEvents.map((event) => (
            <div key={event.event_id} className="relative group">
              {/* Dot Icon */}
              <span className="absolute -left-[37px] top-0 flex h-6 w-6 items-center justify-center rounded-full border border-[var(--border-strong)] bg-[var(--surface-1)] text-[10px] shadow-sm transition-all group-hover:border-[var(--accent-primary)]">
                <i className={`fas ${getEventIcon(event.event_type)}`}></i>
              </span>

              {/* Event Info */}
              <div className="text-xs font-bold text-[var(--text-primary)]">
                {getEventLabel(event.event_type)}
                <span className="ml-2 rounded-full bg-[var(--surface-3)] px-2 py-0.5 font-mono text-[10px] font-medium text-[var(--text-muted)]">
                  {getActorLabel(event.actor_type, event.actor_id)}
                </span>
              </div>
              
              <div className="text-[10px] text-[var(--text-muted)] font-semibold mt-0.5">
                {new Date(event.occurred_at).toLocaleString()}
              </div>

              {event.payload && Object.keys(event.payload).length > 0 && (
                <div className="mt-2 max-h-36 overflow-y-auto rounded-[16px] border border-[var(--border-default)] bg-[var(--surface-2)] p-2.5 font-mono text-[11px] leading-relaxed text-[var(--text-secondary)] shadow-inner">
                  {event.event_type === 'STATE_CHANGED' ? (
                    <div className="space-y-1 font-sans">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="px-2 py-0.5 rounded bg-red-100 text-red-800 line-through font-mono">
                          {event.payload.from}
                        </span>
                        <i className="fas fa-arrow-right text-[var(--text-muted)] text-[10px]"></i>
                        <span className="px-2 py-0.5 rounded bg-green-100 text-green-800 font-mono">
                          {event.payload.to}
                        </span>
                      </div>
                      {event.payload.reason && (
                        <div className="text-[10px] text-[var(--text-secondary)] mt-1">
                          <strong>Причина:</strong> {event.payload.reason}
                        </div>
                      )}
                    </div>
                  ) : (
                    <pre className="whitespace-pre-wrap">{JSON.stringify(event.payload, null, 2)}</pre>
                  )}
                </div>
              )}

              <div className="mt-1.5 inline-block rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[9px] text-[var(--text-muted)]">
                SHA-256: {event.event_hash.slice(0, 8)}...
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
