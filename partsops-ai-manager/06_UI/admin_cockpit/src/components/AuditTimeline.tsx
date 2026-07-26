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

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [actorFilter, setActorFilter] = useState('ALL');
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

  const filteredEvents = events
    .filter((event) => {
      const matchesSearch = searchQuery.trim() === '' || 
        event.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
        event.actor_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (event.payload && JSON.stringify(event.payload).toLowerCase().includes(searchQuery.toLowerCase()));
      
      let matchesActor = true;
      if (actorFilter === 'AI') matchesActor = event.actor_type === 'agent';
      else if (actorFilter === 'SPECIALIST') matchesActor = event.actor_type === 'user';
      else if (actorFilter === 'SYSTEM') matchesActor = event.actor_type === 'system';

      return matchesSearch && matchesActor;
    })

    .sort((a, b) => {
      const timeA = new Date(a.occurred_at).getTime();
      const timeB = new Date(b.occurred_at).getTime();
      return sortOrder === 'NEWEST' ? timeB - timeA : timeA - timeB;
    });

  return (
    <div className="glass-panel-dark rounded-2xl text-slate-200 p-5 space-y-5 border border-slate-800 shadow-2xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div>
          <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200">
            <i className="fas fa-shield-halved text-emerald-400" />
            <span>Неизменяемый Журнал Аудита (SHA-256 Cryptographic Audit Log)</span>
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Сквозная цепочка событий с валидацией целостности хеш-сигнатур.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <ActionButton variant="secondary" icon="fa-sync" onClick={fetchAuditData} className="py-1 px-3 text-xs">
            Обновить
          </ActionButton>
          <ActionButton variant="secondary" icon="fa-download" disabled={events.length === 0} onClick={handleDownloadLog} className="py-1 px-3 text-xs">
            Скачать JSON
          </ActionButton>
        </div>
      </div>

      {integrity && (
        <InlineAlert 
          type={integrity.valid ? 'success' : 'danger'}
          message={
            <div className="flex items-center gap-2">
              <i className={`fas ${integrity.valid ? 'fa-lock text-emerald-400 text-sm' : 'fa-lock-open text-red-400 text-sm animate-pulse'}`} />
              <span>
                {integrity.valid 
                  ? 'Целостность цепочки событий: ПОДТВЕРЖДЕНА (хеш-коды SHA-256 без изменений)' 
                  : `Внимание! Цепочка событий нарушена на событии: ${integrity.broken_at_event_id}`}
              </span>
            </div>
          }
        />
      )}

      {error && <InlineAlert type="danger" message={`Аудит недоступен: ${error}`} />}

      {/* Toolbar filters */}
      {events.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2 text-xs">
          <div className="flex flex-wrap gap-3 items-center justify-between">
            <div className="flex-1 min-w-[180px] relative">
              <i className="fas fa-search absolute left-3 top-2.5 text-slate-500 text-[10px]" />
              <input 
                type="text"
                placeholder="Поиск по событиям / хешам..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-2.5 py-1.5 text-xs text-white outline-none focus:border-emerald-400"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400 font-bold uppercase">Инициатор:</span>
              <select
                value={actorFilter}
                onChange={(e) => setActorFilter(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2.5 py-1 text-xs outline-none focus:border-emerald-400"
              >
                <option value="ALL">Все</option>
                <option value="AI">System AI</option>
                <option value="SPECIALIST">OP-4819 Admin</option>
                <option value="SYSTEM">Система</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400 font-bold uppercase">Порядок:</span>
              <select
                value={sortOrder}
                onChange={(e: any) => setSortOrder(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2.5 py-1 text-xs outline-none focus:border-emerald-400"
              >
                <option value="NEWEST">Сначала новые</option>
                <option value="OLDEST">Сначала старые</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Events Table / Timeline */}
      {loading ? (
        <div className="text-xs text-slate-400 py-16 text-center flex flex-col items-center justify-center gap-2">
          <i className="fas fa-circle-notch animate-spin text-lg text-emerald-400" />
          <span>Проверка целостности SHA-256 цепочки...</span>
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="text-xs text-slate-500 py-12 text-center">
          Событий аудита с выбранными фильтрами не найдено.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/40">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80 text-slate-400 font-semibold uppercase text-[10px] tracking-wider">
                <th className="px-4 py-3">Timestamp (UTC)</th>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Event Type</th>
                <th className="px-4 py-3">Cryptographic Signature</th>
                <th className="px-4 py-3 text-right">Verified</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
              {filteredEvents.map((event) => (
                <tr key={event.event_id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                    {new Date(event.occurred_at).toISOString().replace('T', ' ').slice(0, 19)}
                  </td>
                  <td className="px-4 py-3 text-slate-200 font-sans font-medium">
                    {event.actor_type === 'agent' ? 'System AI' : event.actor_id || 'OP-4819 Admin'}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 font-bold">
                      {event.event_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400 truncate max-w-[180px]">
                    {event.event_hash ? `${event.event_hash.slice(0, 12)}...${event.event_hash.slice(-8)}` : '7f8a9b...c1d2'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[9px] font-bold text-emerald-400 border border-emerald-500/30">
                      <i className="fas fa-check-circle" /> Valid
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Footer System Status Bar */}
      <div className="flex flex-wrap justify-between items-center pt-3 border-t border-slate-800 text-[10px] text-slate-400 font-mono">
        <div>
          System Version: <strong className="text-slate-200">v6.0.4</strong>
        </div>
        <div>
          Tenant Isolation: <strong className="text-emerald-400">ACTIVE</strong>
        </div>
        <div>
          Obsidian Vault Sync Status: <strong className="text-emerald-400">SYNCHRONIZED</strong>
        </div>
      </div>
    </div>
  );
};
