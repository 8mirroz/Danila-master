import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { apiFetch } from '../lib/api';
import { SectionCard, ActionButton, Icon, SoftPollPill } from './Primitives';

type Trace = {
  correlation_id: string;
  provider: string;
  model: string;
  status: string;
  latency_ms: number;
  total_tokens: number;
  cost_usd: number;
  created_at: string;
};

type HermesHealth = {
  status: 'online' | 'degraded' | 'offline';
  version: string;
  profile: string;
  capabilities: string[];
  model: string;
  skills: string[];
  error?: string;
  mode?: string;
  local_fallback?: boolean;
  prefer_local?: boolean;
  key_configured?: boolean;
  hermes_url?: string;
  hint?: string;
  latency_ms?: number;
};

function statusStripClasses(status: HermesHealth['status']) {
  if (status === 'online') {
    return {
      pill: 'border-emerald-200 bg-emerald-50 text-emerald-800',
      dot: 'bg-emerald-500 animate-pulse',
      label: 'Online',
    };
  }
  if (status === 'degraded') {
    return {
      pill: 'border-amber-200 bg-amber-50 text-amber-800',
      dot: 'bg-amber-500',
      label: 'Degraded',
    };
  }
  return {
    pill: 'border-rose-200 bg-rose-50 text-rose-800',
    dot: 'bg-rose-500',
    label: 'Offline',
  };
}

function statusHeadline(health: HermesHealth): string {
  if (health.status === 'online') return 'Hermes API Server готов';
  if (health.status === 'degraded') {
    return health.mode === 'local' ? 'Локальный grounded fallback' : 'Ограниченный режим';
  }
  return 'Сервис недоступен';
}

function traceStatusClass(status: string) {
  const s = (status || '').toLowerCase();
  if (s === 'ok' || s === 'success' || s === 'completed') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  }
  if (s === 'error' || s === 'failed') {
    return 'border-rose-200 bg-rose-50 text-rose-800';
  }
  if (s === 'timeout' || s === 'degraded') {
    return 'border-amber-200 bg-amber-50 text-amber-800';
  }
  return 'border-line bg-surface-2 text-ink-secondary';
}

type TracesLoadState = 'idle' | 'loading' | 'ready' | 'error';

export const AgentOSPanel: React.FC = () => {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [tracesState, setTracesState] = useState<TracesLoadState>('idle');
  const [tracesError, setTracesError] = useState<string | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  /** Soft 15s poll: pill only, no skeleton flash when data already loaded. */
  const [listRefreshing, setListRefreshing] = useState(false);
  const [hermesHealth, setHermesHealth] = useState<HermesHealth>({
    status: 'offline',
    version: 'unknown',
    profile: 'partsops',
    capabilities: [],
    model: 'partsops',
    skills: ['partsops-navigation', 'partsops-request-explainer', 'partsops-troubleshooting'],
    mode: 'unavailable',
    local_fallback: true,
  });

  const fetchHealth = useCallback(async () => {
    try {
      const res = await apiFetch('/api/copilot/health');
      if (res.ok) {
        const data = await res.json();
        setHealthError(null);
        setHermesHealth((prev) => ({
          ...prev,
          ...data,
          capabilities: Array.isArray(data.capabilities) ? data.capabilities : prev.capabilities,
          skills: Array.isArray(data.skills) ? data.skills : prev.skills,
        }));
      } else {
        setHealthError(`Health HTTP ${res.status}`);
        setHermesHealth((prev) => ({ ...prev, status: 'offline', mode: 'unavailable' }));
      }
    } catch {
      setHealthError('Не удалось связаться с /api/copilot/health');
      setHermesHealth((prev) => ({ ...prev, status: 'offline', mode: 'unavailable' }));
    }
  }, []);

  const fetchTraces = useCallback(async (opts?: { background?: boolean }) => {
    const background = Boolean(opts?.background);
    if (background) {
      // Soft poll: keep existing list, only subtle indicator.
      setListRefreshing(true);
    } else {
      setTracesState((prev) => (prev === 'ready' ? prev : 'loading'));
    }
    try {
      const res = await apiFetch('/api/admin/observability/traces');
      if (res.ok) {
        const data = await res.json();
        setTraces(Array.isArray(data) ? data : []);
        setTracesError(null);
        setTracesState('ready');
      } else {
        if (!background) {
          setTraces([]);
          setTracesError(`Traces HTTP ${res.status}`);
          setTracesState('error');
        }
        // Background poll failures stay silent to avoid flicker every 15s.
      }
    } catch (e) {
      console.warn('Backend traces endpoint offline:', e);
      if (!background) {
        setTraces([]);
        setTracesError('Эндпоинт трасс недоступен');
        setTracesState('error');
      }
    } finally {
      if (background) setListRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setTracesState('loading');
    fetchHealth();
    fetchTraces();
    const interval = setInterval(() => {
      fetchHealth();
      fetchTraces({ background: true });
    }, 15000);
    return () => clearInterval(interval);
  }, [fetchHealth, fetchTraces]);

  const totalCost = traces.reduce((acc, t) => acc + (t.cost_usd || 0), 0);
  const totalTokens = traces.reduce((acc, t) => acc + (t.total_tokens || 0), 0);
  const strip = useMemo(() => statusStripClasses(hermesHealth.status), [hermesHealth.status]);
  const skillsList = Array.isArray(hermesHealth.skills) ? hermesHealth.skills : [];

  const refreshAll = () => {
    setTracesState((prev) => (prev === 'ready' ? prev : 'loading'));
    fetchHealth();
    fetchTraces();
  };

  return (
    <div className="space-y-6">
      {/* Hero + status strip */}
      <section className="panel-card relative overflow-hidden p-6">
        <div className="relative z-10 flex w-full flex-col justify-between gap-5 xl:flex-row xl:items-start">
          <div className="min-w-0 space-y-3">
            {/* Compact status strip: brand · health · mode */}
            <div
              className="flex flex-wrap items-center gap-2"
              role="status"
              aria-live="polite"
              aria-label={`Статус Hermes: ${strip.label}`}
            >
              <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.16em] text-sky-800">
                Hermes Agent OS
              </span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold ${strip.pill}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${strip.dot}`} aria-hidden />
                {strip.label}
              </span>
              {hermesHealth.mode && (
                <span className="rounded-full border border-line bg-surface-2 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-ink-muted">
                  mode · {hermesHealth.mode}
                </span>
              )}
              {hermesHealth.local_fallback && hermesHealth.status !== 'online' && (
                <span className="rounded-full border border-line bg-surface-2 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-ink-secondary">
                  fallback ready
                </span>
              )}
              <SoftPollPill
                active={listRefreshing && tracesState === 'ready'}
                size="md"
              />
            </div>

            <div className="space-y-1.5">
              <h2 className="font-sans text-xl font-bold tracking-tight text-ink-primary sm:text-2xl">
                Операторская консоль и трассировка Hermes
              </h2>
              <p className="text-xs font-semibold text-ink-secondary">{statusHeadline(hermesHealth)}</p>
              <p className="max-w-xl text-xs leading-relaxed text-ink-secondary">
                Мониторинг профиля <code className="font-mono text-[10px]">partsops</code>, навыков,
                LLM-трасс и бюджета. Обновление каждые 15 с.
              </p>
              {hermesHealth.hint ? (
                <p className="max-w-xl rounded-control border border-line bg-surface-2 px-2.5 py-1.5 text-[11px] text-ink-muted">
                  {hermesHealth.hint}
                </p>
              ) : null}
              {hermesHealth.error ? (
                <p className="max-w-xl rounded-control border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-[11px] text-rose-800">
                  {hermesHealth.error}
                </p>
              ) : null}
              {healthError && !hermesHealth.error ? (
                <p className="max-w-xl rounded-control border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-[11px] text-rose-800">
                  {healthError}
                </p>
              ) : null}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <ActionButton
              variant="secondary"
              icon="sync-alt"
              onClick={refreshAll}
              aria-label="Обновить health и трассы"
            >
              Обновить данные
            </ActionButton>
          </div>
        </div>
      </section>

      {/* KPI metrics */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <div className="ui-metric-card ui-metric-card--erp">
          <div className="ui-metric-card__label">
            <Icon name="pulse" size={12} />
            Статус готовности
          </div>
          <div
            className={`ui-metric-card__value text-lg sm:text-xl ${
              hermesHealth.status === 'online'
                ? 'text-emerald-600'
                : hermesHealth.status === 'degraded'
                  ? 'text-amber-600'
                  : 'text-rose-600'
            }`}
          >
            {hermesHealth.status.toUpperCase()}
          </div>
          <div className="ui-metric-card__detail">Профиль: {hermesHealth.profile}</div>
        </div>

        <div className="ui-metric-card ui-metric-card--approvals">
          <div className="ui-metric-card__label">
            <Icon name="money-bill-wave" size={12} />
            Расход сессии
          </div>
          <div className="ui-metric-card__value text-lg sm:text-xl font-mono">
            ${totalCost.toFixed(4)}
          </div>
          <div className="ui-metric-card__detail">из дневного лимита $10.00</div>
        </div>

        <div className="ui-metric-card ui-metric-card--queue">
          <div className="ui-metric-card__label">
            <Icon name="terminal" size={12} />
            Токены
          </div>
          <div className="ui-metric-card__value text-lg sm:text-xl font-mono text-indigo-600">
            {totalTokens.toLocaleString('ru-RU')}
          </div>
          <div className="ui-metric-card__detail">вызовов: {traces.length}</div>
        </div>

        <div className="ui-metric-card ui-metric-card--suppliers">
          <div className="ui-metric-card__label">
            <Icon name="microchip" size={12} />
            Версия / канал
          </div>
          <div className="ui-metric-card__value text-lg sm:text-xl font-mono">
            v{hermesHealth.version || '—'}
          </div>
          <div className="ui-metric-card__detail truncate" title={hermesHealth.hermes_url}>
            {hermesHealth.hermes_url || 'http://127.0.0.1:8642'}
            {typeof hermesHealth.latency_ms === 'number' ? ` · ${hermesHealth.latency_ms} ms` : ''}
          </div>
        </div>
      </div>

      {/* Main dual panel */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LLM Traces */}
        <div className="space-y-4 lg:col-span-2">
          <SectionCard
            title="Реальные вызовы моделей (LLM Traces)"
            icon="terminal"
            headerActions={
              <ActionButton
                variant="secondary"
                icon="sync-alt"
                size="sm"
                onClick={() => fetchTraces()}
                aria-label="Обновить трассы"
              >
                Обновить
              </ActionButton>
            }
          >
            <div className="custom-scrollbar max-h-[500px] space-y-3 overflow-y-auto pr-0.5">
              {tracesState === 'loading' && traces.length === 0 ? (
                <div className="ds-empty" role="status" aria-live="polite">
                  <div className="ds-empty__icon" aria-hidden>
                    <Icon name="sync-alt" size={18} />
                  </div>
                  <p className="ds-empty__title">Загрузка LLM-трасс…</p>
                  <p className="ds-empty__hint max-w-sm">
                    Запрос к <code className="font-mono text-[10px]">/api/admin/observability/traces</code>
                  </p>
                </div>
              ) : tracesState === 'error' && traces.length === 0 ? (
                <div className="ds-empty" role="alert">
                  <div className="ds-empty__icon" aria-hidden>
                    <Icon name="triangle-exclamation" size={18} />
                  </div>
                  <p className="ds-empty__title">Не удалось загрузить трассы</p>
                  <p className="ds-empty__hint max-w-sm">
                    {tracesError || 'Проверьте доступ оператора и backend observability.'}
                  </p>
                  <div className="mt-3">
                    <ActionButton
                      variant="secondary"
                      icon="sync-alt"
                      size="sm"
                      onClick={() => {
                        setTracesState('loading');
                        fetchTraces();
                      }}
                      aria-label="Повторить загрузку трасс"
                    >
                      Повторить
                    </ActionButton>
                  </div>
                </div>
              ) : traces.length === 0 ? (
                <div className="ds-empty">
                  <div className="ds-empty__icon" aria-hidden>
                    <Icon name="inbox" size={18} />
                  </div>
                  <p className="ds-empty__title">Нет зафиксированных LLM-трасс</p>
                  <p className="ds-empty__hint max-w-sm">
                    Вызовите Hermes через чат-дровер — вызов появится здесь с latency, токенами и
                    стоимостью.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-[var(--border-subtle)] overflow-hidden rounded-control border border-line bg-surface-1">
                  {traces.map((trace) => (
                    <li
                      key={trace.correlation_id}
                      className="flex flex-col justify-between gap-3 px-3.5 py-3 transition-colors hover:bg-[var(--state-hover)] md:flex-row md:items-center"
                    >
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className="truncate font-mono text-[10px] font-bold text-ink-muted"
                            title={trace.correlation_id}
                          >
                            {trace.correlation_id}
                          </span>
                          <span className="truncate text-[11px] font-bold text-ink-primary">
                            {trace.model}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] text-ink-muted">
                          <span>
                            Провайдер:{' '}
                            <strong className="font-semibold text-ink-secondary">{trace.provider}</strong>
                          </span>
                          <span>
                            Токенов:{' '}
                            <strong className="font-mono font-semibold tabular-nums text-ink-secondary">
                              {trace.total_tokens}
                            </strong>
                          </span>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-3 md:gap-4">
                        <div className="text-right">
                          <span className="block font-mono text-xs font-bold tabular-nums text-ink-primary">
                            ${(trace.cost_usd || 0).toFixed(5)}
                          </span>
                          <span className="text-[10px] tabular-nums text-ink-muted">
                            {trace.latency_ms} ms
                          </span>
                        </div>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide ${traceStatusClass(
                            trace.status,
                          )}`}
                        >
                          {trace.status}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </SectionCard>
        </div>

        {/* Skills + security */}
        <div className="space-y-4">
          <SectionCard title="Подключенные навыки (PartsOps Skills)" icon="microchip">
            <div className="space-y-2.5 pt-0.5">
              <p className="text-[11px] leading-relaxed text-ink-secondary">
                Изолированный профиль <code className="font-mono text-[10px]">partsops</code> имеет
                доступ строго к одобренным skills:
              </p>

              {skillsList.length === 0 ? (
                <div className="ds-empty border-0 bg-transparent p-4">
                  <div className="ds-empty__icon" aria-hidden>
                    <Icon name="microchip" size={16} />
                  </div>
                  <p className="ds-empty__title">Список skills пуст</p>
                  <p className="ds-empty__hint max-w-xs">
                    Health не вернул skills — обновите панель или проверьте профиль Hermes.
                  </p>
                </div>
              ) : (
                <ul className="space-y-2">
                  {skillsList.map((skillName) => (
                    <li
                      key={skillName}
                      className="flex items-center justify-between gap-2 rounded-control border border-line bg-surface-1 px-3 py-2.5"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <Icon name="check-circle" size={14} className="shrink-0 text-emerald-600" />
                        <span
                          className="truncate font-mono text-[11px] font-bold text-ink-primary"
                          title={skillName}
                        >
                          {skillName}
                        </span>
                      </div>
                      <span className="shrink-0 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-emerald-700">
                        Read-only
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </SectionCard>

          <SectionCard title="Ограничения профиля и безопасность" icon="shield-halved">
            <ul className="space-y-0 text-[11px] text-ink-secondary">
              {[
                { label: 'Прямой доступ к CLI / Terminal', value: 'Отключён', ok: false },
                { label: 'Файловый доступ / File I/O', value: 'Отключён', ok: false },
                { label: 'Сетевой Web Search / Scraper', value: 'Отключён', ok: false },
                { label: 'Автоматическое редактирование skills', value: 'Заблокировано', ok: false },
                { label: 'Обезличивание PII (VIN / телефон)', value: 'Активно', ok: true },
              ].map((row, idx, arr) => (
                <li
                  key={row.label}
                  className={`flex items-center justify-between gap-3 py-2 ${
                    idx < arr.length - 1 ? 'border-b border-line-subtle' : ''
                  }`}
                >
                  <span className="min-w-0 leading-snug">{row.label}</span>
                  <span
                    className={`shrink-0 text-[10px] font-bold uppercase tracking-wide ${
                      row.ok ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {row.value}
                  </span>
                </li>
              ))}
            </ul>
          </SectionCard>
        </div>
      </div>
    </div>
  );
};
