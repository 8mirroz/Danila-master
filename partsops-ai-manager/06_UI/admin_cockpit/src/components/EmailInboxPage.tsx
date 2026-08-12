import { useCallback, useEffect, useState } from 'react';
import { Button, Icon, InlineAlert, SectionCard, Skeleton, SoftPollPill } from './Primitives';
import { apiJson } from '../lib/api';
import { notify } from '../lib/notify';

type EmailMessage = {
  id: string;
  tenant_id: string;
  provider_message_id: string;
  from_masked: string;
  to_address: string;
  subject: string;
  received_at: string | null;
  body_masked_excerpt: string;
  status: string;
  request_id: string | null;
  rejection_reason: string | null;
  attachment_artifact_ids: string[];
  auth_results?: Record<string, unknown>;
  /** Webhook redelivery count (row status stays parsed/ingested). */
  duplicate_hits?: number;
};

type EmailConfig = {
  configured: boolean;
  tenant_id?: string;
  org_slug?: string;
  address?: string;
  auto_ingest?: boolean;
  default_priority?: string;
  allowed_senders?: string[];
};

type EmailStats = {
  total: number;
  parsed: number;
  ingested: number;
  rejected: number;
  received: number;
  ingesting: number;
  duplicate: number;
};

const STATUS_LABEL: Record<string, string> = {
  parsed: 'К разбору',
  received: 'Получено',
  ingested: 'В заявке',
  rejected: 'Отклонено',
  duplicate: 'Дубликат',
  ingesting: 'Импорт…',
};

const STATUS_CLASS: Record<string, string> = {
  parsed: 'border-amber-200 bg-amber-50 text-amber-800',
  received: 'border-line bg-surface-2 text-ink-secondary',
  ingested: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  rejected: 'border-red-200 bg-red-50 text-red-800',
  duplicate: 'border-line bg-surface-2 text-ink-muted',
  ingesting: 'border-sky-200 bg-sky-50 text-sky-800',
};

const STATS_CHIP_ORDER: Array<{ key: keyof EmailStats; label: string; className: string }> = [
  { key: 'total', label: 'Всего', className: 'border-line bg-surface-2 text-ink-secondary' },
  { key: 'parsed', label: 'К разбору', className: 'border-amber-200 bg-amber-50 text-amber-800' },
  { key: 'received', label: 'Получено', className: 'border-line bg-surface-2 text-ink-secondary' },
  { key: 'ingesting', label: 'Импорт', className: 'border-sky-200 bg-sky-50 text-sky-800' },
  { key: 'ingested', label: 'В заявке', className: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  { key: 'rejected', label: 'Отклонено', className: 'border-red-200 bg-red-50 text-red-800' },
  { key: 'duplicate', label: 'Дубликаты', className: 'border-line bg-surface-2 text-ink-muted' },
];

function redeliveryHits(row: Pick<EmailMessage, 'duplicate_hits' | 'auth_results'>): number {
  if (typeof row.duplicate_hits === 'number' && row.duplicate_hits > 0) {
    return row.duplicate_hits;
  }
  const raw = row.auth_results?.duplicate_hits;
  const n = typeof raw === 'number' ? raw : typeof raw === 'string' ? Number(raw) : 0;
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function RedeliveryBadge({ hits }: { hits: number }) {
  if (hits <= 0) return null;
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide text-violet-800"
      title={`Провайдер повторно доставил письмо ${hits}× (webhook redelivery)`}
      aria-label={`Повторных доставок: ${hits}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-violet-500" aria-hidden />
      ×{hits} redelivery
    </span>
  );
}

function EmailStatusChip({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold leading-none ${
        STATUS_CLASS[status] || STATUS_CLASS.received
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === 'parsed'
            ? 'bg-amber-500'
            : status === 'ingested'
              ? 'bg-emerald-500'
              : status === 'rejected'
                ? 'bg-red-500'
                : 'bg-slate-400'
        }`}
        aria-hidden
      />
      {STATUS_LABEL[status] || status}
    </span>
  );
}

type Props = {
  onOpenRequest?: (requestId: string) => void;
};

export function EmailInboxPage({ onOpenRequest }: Props) {
  const [messages, setMessages] = useState<EmailMessage[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<EmailMessage | null>(null);
  const [config, setConfig] = useState<EmailConfig | null>(null);
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [listRefreshing, setListRefreshing] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cfgForm, setCfgForm] = useState({
    org_slug: 'default',
    address: 'rfq+default@inbound.example',
    auto_ingest: false,
  });

  const loadMessages = useCallback(async (opts?: { background?: boolean }) => {
    const background = Boolean(opts?.background);
    if (background) {
      // Soft poll: no skeleton flash, only subtle indicator.
      setListRefreshing(true);
    } else {
      setError(null);
    }
    try {
      const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
      const rows = await apiJson<EmailMessage[]>(`/api/email/messages${qs}`);
      setMessages(rows);
      if (background) setError(null);
    } catch (cause) {
      if (!background) {
        setError(cause instanceof Error ? cause.message : 'Не удалось загрузить inbox');
        setMessages([]);
      }
      // Background poll failures stay silent to avoid toast spam every 20s.
    } finally {
      setListLoading(false);
      if (background) setListRefreshing(false);
    }
  }, [statusFilter]);

  const loadStats = useCallback(async () => {
    try {
      const data = await apiJson<EmailStats>('/api/email/stats');
      setStats(data);
    } catch {
      // non-critical — hide chips if endpoint fails
      setStats(null);
    }
  }, []);

  const loadConfig = useCallback(async () => {
    try {
      const cfg = await apiJson<EmailConfig>('/api/email/config');
      setConfig(cfg);
      if (cfg.configured && cfg.org_slug && cfg.address) {
        setCfgForm({
          org_slug: cfg.org_slug,
          address: cfg.address,
          auto_ingest: Boolean(cfg.auto_ingest),
        });
      }
    } catch {
      // admin-only endpoint — managers may get 403; keep silent
      setConfig({ configured: false });
    }
  }, []);

  useEffect(() => {
    // Cold start + status filter change: skeleton only when list not yet ready.
    setListLoading(true);
    void loadMessages();
    void loadConfig();
    void loadStats();
  }, [loadMessages, loadConfig, loadStats]);

  // Auto-refresh list + stats every 20s while mounted (background: no skeleton)
  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadMessages({ background: true });
      void loadStats();
    }, 20_000);
    return () => {
      window.clearInterval(timer);
    };
  }, [loadMessages, loadStats]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setDetailLoading(false);
      return;
    }
    let active = true;
    setDetailLoading(true);
    void apiJson<EmailMessage>(`/api/email/messages/${selectedId}`)
      .then((row) => {
        if (active) setDetail(row);
      })
      .catch(() => {
        if (active) setDetail(null);
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const patchLocalMessage = (id: string, patch: Partial<EmailMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
    setDetail((prev) => (prev && prev.id === id ? { ...prev, ...patch } : prev));
  };

  const ingest = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const result = await apiJson<{ request_id: string; status: string }>(
        `/api/email/messages/${id}/ingest`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
      );
      notify.success(`Создана заявка ${result.request_id}`);
      // Optimistic detail/list update — avoid blank flash while list reloads
      patchLocalMessage(id, {
        status: result.status || 'ingested',
        request_id: result.request_id ?? null,
      });
      setSelectedId(id);
      void loadMessages();
      void loadStats();
      if (result.request_id) onOpenRequest?.(result.request_id);
    } catch (cause) {
      const msg = cause instanceof Error ? cause.message : 'Не удалось создать заявку';
      setError(msg);
      notify.error(msg);
      // Race / concurrent claim: refresh so chips match server truth
      void loadMessages();
      void loadStats();
    } finally {
      setBusy(false);
    }
  };

  const reject = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const rejected = await apiJson<EmailMessage>(`/api/email/messages/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'operator_rejected' }),
      });
      notify.success('Письмо отклонено');
      patchLocalMessage(id, {
        status: rejected.status || 'rejected',
        rejection_reason: rejected.rejection_reason ?? 'operator_rejected',
      });
      setSelectedId(id);
      void loadMessages();
      void loadStats();
    } catch (cause) {
      const msg = cause instanceof Error ? cause.message : 'Не удалось отклонить';
      setError(msg);
      notify.error(msg);
      void loadMessages();
      void loadStats();
    } finally {
      setBusy(false);
    }
  };

  const saveConfig = async () => {
    setBusy(true);
    setError(null);
    try {
      const saved = await apiJson<EmailConfig>('/api/email/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          org_slug: cfgForm.org_slug.trim(),
          address: cfgForm.address.trim().toLowerCase(),
          auto_ingest: cfgForm.auto_ingest,
          provider: 'mailgun',
          default_priority: 'normal',
          allowed_senders: [],
        }),
      });
      setConfig(saved);
      notify.success('Конфиг inbox сохранён');
    } catch (cause) {
      const msg = cause instanceof Error ? cause.message : 'Не удалось сохранить конфиг (нужна роль admin)';
      setError(msg);
      notify.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const formatWhen = (iso: string | null) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  // Only parsed/received are operator-actionable; ingesting/duplicate/terminal are locked
  const canActOnDetail =
    Boolean(detail) && (detail!.status === 'parsed' || detail!.status === 'received');

  return (
    <section aria-label="Входящие email" className="space-y-4">
      <SectionCard title="Входящие email (RFQ)" icon="envelope">
        {/* Header: meta + actions */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1.5">
            <p className="max-w-2xl text-xs leading-relaxed text-ink-secondary">
              Письма с webhook{' '}
              <code className="rounded border border-line bg-surface-2 px-1 py-0.5 font-mono text-[10px] text-ink-primary">
                /api/integrations/email/inbound
              </code>{' '}
              попадают сюда. По умолчанию review-first: оператор создаёт заявку кнопкой «Создать
              заявку» (source=EMAIL).
            </p>
            <p className="flex flex-wrap items-center gap-2 text-[10px] font-semibold tabular-nums text-ink-muted">
              <span>
                {listLoading
                  ? 'Загрузка очереди…'
                  : messages.length > 0
                    ? `${messages.length} ${messages.length === 1 ? 'письмо' : messages.length < 5 ? 'письма' : 'писем'}${
                        statusFilter ? ` · фильтр: ${STATUS_LABEL[statusFilter] || statusFilter}` : ''
                      }`
                    : statusFilter
                      ? 'Нет писем с выбранным статусом'
                      : 'Очередь пуста'}
              </span>
              <SoftPollPill
                active={listRefreshing && !listLoading}
                size="sm"
                tone={error ? 'rose' : 'sky'}
                label={error ? 'Сбой опроса' : 'Обновление'}
              />
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <select
              aria-label="Фильтр статуса"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-control border border-line bg-surface-1 px-2.5 py-1.5 text-xs font-medium text-ink-primary"
            >
              <option value="">Все статусы</option>
              <option value="parsed">К разбору</option>
              <option value="ingested">В заявке</option>
              <option value="rejected">Отклонено</option>
              <option value="received">Получено</option>
              <option value="duplicate">Дубликаты</option>
            </select>
            <Button
              size="sm"
              variant="secondary"
              icon="rotate"
              disabled={busy || listRefreshing}
              onClick={() => {
                void loadMessages({ background: messages.length > 0 });
                void loadStats();
              }}
              aria-label="Обновить список писем"
              aria-busy={listRefreshing || listLoading}
            >
              {listRefreshing ? 'Обновляем…' : 'Обновить'}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mt-3">
            <InlineAlert type="danger" message={error} />
          </div>
        )}

        {stats && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5" aria-label="Статистика inbox">
            {STATS_CHIP_ORDER.map(({ key, label, className }) => (
              <span
                key={key}
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold ${className}`}
              >
                <span className="font-semibold text-ink-muted">{label}</span>
                <span className="font-mono tabular-nums">{stats[key]}</span>
              </span>
            ))}
          </div>
        )}

        {/* Config status strip */}
        {config && (
          <div
            className={`mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-control border px-3 py-2.5 text-[11px] ${
              config.configured
                ? 'border-line bg-surface-2 text-ink-secondary'
                : 'border-amber-200 bg-amber-50/80 text-amber-900'
            }`}
          >
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide ${
                config.configured
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-amber-300 bg-amber-100 text-amber-800'
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${config.configured ? 'bg-emerald-500' : 'bg-amber-500'}`}
                aria-hidden
              />
              {config.configured ? 'Настроен' : 'Не настроен'}
            </span>
            {config.configured ? (
              <>
                <span className="min-w-0 truncate">
                  Адрес:{' '}
                  <strong className="font-mono text-ink-primary">{config.address}</strong>
                </span>
                <span className="text-ink-muted">·</span>
                <span>
                  slug <strong className="font-mono text-ink-primary">{config.org_slug}</strong>
                </span>
                <span className="text-ink-muted">·</span>
                <span>
                  auto_ingest:{' '}
                  <strong className={config.auto_ingest ? 'text-emerald-700' : 'text-ink-primary'}>
                    {config.auto_ingest ? 'on' : 'off'}
                  </strong>
                </span>
              </>
            ) : (
              <span>Inbox не настроен для tenant — сохраните конфиг в блоке ниже (роль admin).</span>
            )}
          </div>
        )}

        {/* Master–detail */}
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,380px)]">
          {/* Message list */}
          <div className="overflow-hidden rounded-control border border-line bg-surface-1">
            <div className="flex items-center justify-between border-b border-line bg-surface-2 px-3 py-2">
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-ink-muted">
                Список писем
              </span>
              {selectedId && (
                <span className="text-[10px] font-semibold text-accent-primary">выбрано</span>
              )}
            </div>
            <div className="max-h-[min(520px,60vh)] overflow-auto custom-scrollbar">
              <table className="w-full text-left text-[11px]">
                <thead className="sticky top-0 z-[1] border-b border-line bg-surface-2/95 text-ink-muted backdrop-blur-sm">
                  <tr>
                    <th className="whitespace-nowrap px-3 py-2.5 font-semibold">Когда</th>
                    <th className="px-3 py-2.5 font-semibold">От</th>
                    <th className="px-3 py-2.5 font-semibold">Тема</th>
                    <th className="px-3 py-2.5 font-semibold">Статус</th>
                    <th className="whitespace-nowrap px-3 py-2.5 font-semibold" title="Вложения">
                      Влож.
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {listLoading && messages.length === 0 && (
                    <>
                      {[0, 1, 2, 3, 4].map((i) => (
                        <tr key={`sk-list-${i}`} className="border-t border-line-subtle" aria-hidden>
                          <td className="px-3 py-2.5">
                            <Skeleton className="h-3 w-14" />
                          </td>
                          <td className="px-3 py-2.5">
                            <Skeleton className="h-3 w-20" />
                          </td>
                          <td className="px-3 py-2.5">
                            <Skeleton className="h-3 w-36 max-w-full" />
                          </td>
                          <td className="px-3 py-2.5">
                            <Skeleton className="h-4 w-16 rounded-full" />
                          </td>
                          <td className="px-3 py-2.5">
                            <Skeleton className="h-3 w-6" />
                          </td>
                        </tr>
                      ))}
                      <tr className="sr-only">
                        <td colSpan={5} role="status" aria-live="polite">
                          Загрузка списка писем…
                        </td>
                      </tr>
                    </>
                  )}
                  {!listLoading && messages.length === 0 && (
                    <tr>
                      <td colSpan={5} className="p-0">
                        <div className="ds-empty m-3 border-0 bg-transparent p-6">
                          <div className="ds-empty__icon" aria-hidden>
                            <Icon name="inbox" size={18} />
                          </div>
                          <p className="ds-empty__title">Писем нет</p>
                          <p className="ds-empty__hint max-w-xs">
                            {statusFilter
                              ? 'Снимите фильтр или дождитесь новых писем с этим статусом.'
                              : (
                                <>
                                  Настройте webhook и адрес{' '}
                                  <span className="font-mono">rfq+&#123;slug&#125;@…</span>
                                </>
                              )}
                          </p>
                          {!statusFilter && !config?.configured && (
                            <p className="mt-2 text-[10px] font-semibold text-accent-primary">
                              → заполните конфиг inbox ниже
                            </p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                  {messages.map((row) => {
                    const selected = selectedId === row.id;
                    const hits = redeliveryHits(row);
                    return (
                      <tr
                        key={row.id}
                        tabIndex={0}
                        aria-selected={selected}
                        aria-label={`Письмо: ${row.subject || 'без темы'}, ${STATUS_LABEL[row.status] || row.status}${hits ? `, redelivery ×${hits}` : ''}`}
                        onClick={() => setSelectedId(row.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedId(row.id);
                          }
                        }}
                        className={`cursor-pointer border-t border-line-subtle transition-colors focus-visible:outline-none focus-visible:bg-[var(--state-hover)] ${
                          selected
                            ? 'bg-[var(--state-selected)] shadow-[inset_3px_0_0_0_var(--accent-primary)]'
                            : 'hover:bg-[var(--state-hover)]'
                        }`}
                      >
                        <td className="whitespace-nowrap px-3 py-2.5 font-mono tabular-nums text-ink-secondary">
                          {formatWhen(row.received_at)}
                        </td>
                        <td className="max-w-[110px] truncate px-3 py-2.5 text-ink-secondary" title={row.from_masked || undefined}>
                          {row.from_masked || '—'}
                        </td>
                        <td
                          className="max-w-[220px] truncate px-3 py-2.5 font-semibold text-ink-primary"
                          title={row.subject || undefined}
                        >
                          {row.subject || '(без темы)'}
                        </td>
                        <td className="px-3 py-2.5">
                          <div className="flex flex-wrap items-center gap-1">
                            <EmailStatusChip status={row.status} />
                            <RedeliveryBadge hits={hits} />
                          </div>
                        </td>
                        <td data-numeric className="px-3 py-2.5 font-mono tabular-nums text-ink-secondary">
                          {row.attachment_artifact_ids?.length ?? 0}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detail panel */}
          <div
            className="flex min-h-[300px] flex-col rounded-control border border-line bg-surface-2 p-4"
            aria-label="Просмотр письма"
          >
            {detailLoading && !detail && (
              <div className="flex flex-1 flex-col gap-3" role="status" aria-live="polite">
                <span className="sr-only">Загрузка письма…</span>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-2">
                    <Skeleton className="h-4 w-48 max-w-full" />
                    <Skeleton className="h-3 w-40" />
                    <Skeleton className="h-2.5 w-28" />
                  </div>
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
                <Skeleton className="h-28 w-full" />
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-8 w-full" />
                <div className="mt-auto space-y-2 border-t border-line-subtle pt-3">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              </div>
            )}
            {!detailLoading && !detail && (
              <div className="ds-empty flex-1 border-0 bg-transparent">
                <div className="ds-empty__icon" aria-hidden>
                  <Icon name="envelope" size={18} />
                </div>
                <p className="ds-empty__title">Выберите письмо</p>
                <p className="ds-empty__hint max-w-[220px]">
                  Кликните строку в списке слева, чтобы просмотреть тело, вложения и создать заявку.
                </p>
              </div>
            )}
            {detail && (
              <>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <p className="truncate text-sm font-bold leading-snug text-ink-primary" title={detail.subject || undefined}>
                      {detail.subject || '(без темы)'}
                    </p>
                    <p className="truncate text-[11px] text-ink-secondary">
                      <span className="font-semibold">{detail.from_masked || '—'}</span>
                      <span className="text-ink-muted"> · </span>
                      <span className="tabular-nums">{formatWhen(detail.received_at)}</span>
                    </p>
                    <p className="truncate font-mono text-[10px] text-ink-muted" title={detail.id}>
                      {detail.id}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <EmailStatusChip status={detail.status} />
                    <RedeliveryBadge hits={redeliveryHits(detail)} />
                  </div>
                </div>

                {redeliveryHits(detail) > 0 && (
                  <p className="mb-2 rounded-control border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-[11px] text-violet-900">
                    Провайдер повторно доставил это письмо{' '}
                    <strong className="font-bold tabular-nums">{redeliveryHits(detail)}</strong>× —
                    статус строки не меняется (parsed/ingested остаётся честным).
                  </p>
                )}

                {detail.request_id && (
                  <button
                    type="button"
                    className="mb-2 inline-flex w-fit items-center gap-1 rounded-control border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-800 transition-colors hover:bg-emerald-100"
                    onClick={() => onOpenRequest?.(detail.request_id!)}
                    aria-label={`Открыть заявку ${detail.request_id}`}
                  >
                    <Icon name="arrow-right" size={12} />
                    Заявка {detail.request_id}
                  </button>
                )}
                {detail.rejection_reason && (
                  <p className="mb-2 rounded-control border border-red-200 bg-red-50 px-2.5 py-1.5 text-[11px] text-[var(--accent-danger)]">
                    Причина отклонения: {detail.rejection_reason}
                  </p>
                )}
                {typeof detail.auth_results?.auto_ingest_error === 'string' && (
                  <p className="mb-2 rounded-control border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-900">
                    auto_ingest error: {detail.auth_results.auto_ingest_error}
                  </p>
                )}

                <div className="mb-3 max-h-40 overflow-y-auto rounded-md border border-line bg-surface-1 p-3 text-[11px] leading-relaxed text-ink-secondary whitespace-pre-wrap custom-scrollbar">
                  {detail.body_masked_excerpt || '— пустое тело —'}
                </div>

                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-ink-muted">
                    Вложения
                  </p>
                  <span className="rounded-full border border-line bg-surface-1 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-ink-secondary">
                    {detail.attachment_artifact_ids?.length ?? 0}
                  </span>
                </div>
                <ul className="mb-4 max-h-24 space-y-1 overflow-y-auto text-[10px] font-mono text-ink-secondary custom-scrollbar">
                  {(detail.attachment_artifact_ids || []).map((aid) => (
                    <li
                      key={aid}
                      className="truncate rounded border border-line-subtle bg-surface-1 px-2 py-1"
                      title={aid}
                    >
                      {aid}
                    </li>
                  ))}
                  {(detail.attachment_artifact_ids || []).length === 0 && (
                    <li className="px-1 text-ink-muted">нет вложений</li>
                  )}
                </ul>

                <div className="mt-auto space-y-2 border-t border-line-subtle pt-3">
                  {detail.status === 'ingesting' && (
                    <p className="text-[11px] font-medium text-sky-800">
                      Импорт уже выполняется — дождитесь статуса «В заявке» или обновите список.
                    </p>
                  )}
                  {detail.status === 'duplicate' && (
                    <p className="text-[11px] font-medium text-ink-muted">
                      Дубликат webhook — действия недоступны.
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="primary"
                      icon="plus"
                      disabled={busy || !canActOnDetail}
                      onClick={() => void ingest(detail.id)}
                      aria-label="Создать заявку из письма"
                    >
                      Создать заявку
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="x-mark"
                      disabled={busy || !canActOnDetail}
                      onClick={() => void reject(detail.id)}
                      aria-label="Отклонить письмо"
                    >
                      Отклонить
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Конфиг inbox (admin)" icon="circle-info">
        <p className="mb-3 text-[11px] leading-relaxed text-ink-secondary">
          Привязка inbound-адреса к tenant. Требуется роль admin. После сохранения webhook может
          принимать письма на указанный address.
        </p>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="grid gap-1.5 text-[11px] font-semibold text-ink-secondary">
            org_slug
            <input
              className="rounded-control border border-line bg-surface-1 px-2.5 py-1.5 font-mono text-xs text-ink-primary"
              value={cfgForm.org_slug}
              onChange={(e) => setCfgForm((f) => ({ ...f, org_slug: e.target.value }))}
              aria-label="org_slug"
            />
          </label>
          <label className="grid gap-1.5 text-[11px] font-semibold text-ink-secondary sm:col-span-2">
            address
            <input
              className="rounded-control border border-line bg-surface-1 px-2.5 py-1.5 font-mono text-xs text-ink-primary"
              value={cfgForm.address}
              onChange={(e) => setCfgForm((f) => ({ ...f, address: e.target.value }))}
              aria-label="address"
            />
          </label>
        </div>
        <label className="mt-3 flex cursor-pointer items-center gap-2 text-[11px] font-semibold text-ink-secondary">
          <input
            type="checkbox"
            className="rounded border-line"
            checked={cfgForm.auto_ingest}
            onChange={(e) => setCfgForm((f) => ({ ...f, auto_ingest: e.target.checked }))}
          />
          auto_ingest (сразу create_request после webhook)
        </label>
        <div className="mt-4">
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void saveConfig()}>
            Сохранить конфиг
          </Button>
        </div>
      </SectionCard>
    </section>
  );
}
