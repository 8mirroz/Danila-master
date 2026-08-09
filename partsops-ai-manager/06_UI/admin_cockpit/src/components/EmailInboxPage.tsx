import { useCallback, useEffect, useState } from 'react';
import { Button, Icon, InlineAlert, SectionCard } from './Primitives';
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

const STATUS_LABEL: Record<string, string> = {
  parsed: 'К разбору',
  received: 'Получено',
  ingested: 'В заявке',
  rejected: 'Отклонено',
  duplicate: 'Дубликат',
};

const STATUS_CLASS: Record<string, string> = {
  parsed: 'border-amber-200 bg-amber-50 text-amber-800',
  received: 'border-line bg-surface-2 text-ink-secondary',
  ingested: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  rejected: 'border-red-200 bg-red-50 text-red-800',
  duplicate: 'border-line bg-surface-2 text-ink-muted',
};

function EmailStatusChip({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-bold ${
        STATUS_CLASS[status] || STATUS_CLASS.received
      }`}
    >
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
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cfgForm, setCfgForm] = useState({
    org_slug: 'default',
    address: 'rfq+default@inbound.example',
    auto_ingest: false,
  });

  const loadMessages = useCallback(async () => {
    setError(null);
    try {
      const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
      const rows = await apiJson<EmailMessage[]>(`/api/email/messages${qs}`);
      setMessages(rows);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось загрузить inbox');
      setMessages([]);
    }
  }, [statusFilter]);

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
    void loadMessages();
    void loadConfig();
  }, [loadMessages, loadConfig]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let active = true;
    void apiJson<EmailMessage>(`/api/email/messages/${selectedId}`)
      .then((row) => {
        if (active) setDetail(row);
      })
      .catch(() => {
        if (active) setDetail(null);
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const ingest = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const result = await apiJson<{ request_id: string; status: string }>(
        `/api/email/messages/${id}/ingest`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' },
      );
      notify.success(`Создана заявка ${result.request_id}`);
      await loadMessages();
      setSelectedId(id);
      setDetail(await apiJson<EmailMessage>(`/api/email/messages/${id}`));
      if (result.request_id) onOpenRequest?.(result.request_id);
    } catch (cause) {
      const msg = cause instanceof Error ? cause.message : 'Не удалось создать заявку';
      setError(msg);
      notify.error(msg);
    } finally {
      setBusy(false);
    }
  };

  const reject = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await apiJson(`/api/email/messages/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'operator_rejected' }),
      });
      notify.success('Письмо отклонено');
      await loadMessages();
      setSelectedId(id);
      setDetail(await apiJson<EmailMessage>(`/api/email/messages/${id}`));
    } catch (cause) {
      const msg = cause instanceof Error ? cause.message : 'Не удалось отклонить';
      setError(msg);
      notify.error(msg);
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

  return (
    <section aria-label="Входящие email" className="space-y-4">
      <SectionCard title="Входящие email (RFQ)" icon="envelope">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="max-w-2xl text-xs leading-relaxed text-ink-secondary">
            Письма с webhook <code className="font-mono text-[10px]">/api/integrations/email/inbound</code>
            {' '}попадают сюда. По умолчанию review-first: оператор создаёт заявку кнопкой
            «Создать заявку» (source=EMAIL).
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Фильтр статуса"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-control border border-line bg-surface-1 px-2 py-1.5 text-xs text-ink-primary"
            >
              <option value="">Все статусы</option>
              <option value="parsed">К разбору</option>
              <option value="ingested">В заявке</option>
              <option value="rejected">Отклонено</option>
              <option value="received">Получено</option>
            </select>
            <Button size="sm" variant="secondary" icon="rotate" disabled={busy} onClick={() => void loadMessages()}>
              Обновить
            </Button>
          </div>
        </div>

        {error && (
          <div className="mt-3">
            <InlineAlert type="danger" message={error} />
          </div>
        )}

        {config && (
          <div className="mt-3 rounded-control border border-line bg-surface-2 px-3 py-2 text-[11px] text-ink-secondary">
            {config.configured ? (
              <>
                Адрес: <strong className="font-mono text-ink-primary">{config.address}</strong>
                {' · '}slug <strong className="font-mono">{config.org_slug}</strong>
                {' · '}auto_ingest:{' '}
                <strong>{config.auto_ingest ? 'on' : 'off'}</strong>
              </>
            ) : (
              <span>Inbox не настроен для tenant (admin: сохраните конфиг ниже).</span>
            )}
          </div>
        )}

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,380px)]">
          <div className="overflow-hidden rounded-control border border-line bg-surface-1">
            <table className="w-full text-left text-[11px]">
              <thead className="border-b border-line bg-surface-2 text-ink-muted">
                <tr>
                  <th className="px-3 py-2 font-semibold">Когда</th>
                  <th className="px-3 py-2 font-semibold">От</th>
                  <th className="px-3 py-2 font-semibold">Тема</th>
                  <th className="px-3 py-2 font-semibold">Статус</th>
                  <th className="px-3 py-2 font-semibold">Влож.</th>
                </tr>
              </thead>
              <tbody>
                {messages.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-8 text-center text-ink-muted">
                      Писем нет. Настройте webhook и адрес <span className="font-mono">rfq+&#123;slug&#125;@…</span>
                    </td>
                  </tr>
                )}
                {messages.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    className={`cursor-pointer border-t border-line-subtle transition-colors hover:bg-surface-2 ${
                      selectedId === row.id ? 'bg-accent-primary/5' : ''
                    }`}
                  >
                    <td className="px-3 py-2 font-mono text-ink-secondary">{formatWhen(row.received_at)}</td>
                    <td className="max-w-[120px] truncate px-3 py-2 text-ink-secondary">{row.from_masked || '—'}</td>
                    <td className="max-w-[200px] truncate px-3 py-2 font-semibold text-ink-primary">
                      {row.subject || '(без темы)'}
                    </td>
                    <td className="px-3 py-2">
                      <EmailStatusChip status={row.status} />
                    </td>
                    <td data-numeric className="px-3 py-2 font-mono">
                      {row.attachment_artifact_ids?.length ?? 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex min-h-[280px] flex-col rounded-control border border-line bg-surface-2 p-4">
            {!detail && (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center text-ink-muted">
                <Icon name="envelope" size={22} />
                <p className="text-xs">Выберите письмо в списке</p>
              </div>
            )}
            {detail && (
              <>
                <div className="mb-3 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-ink-primary">{detail.subject || '(без темы)'}</p>
                    <p className="mt-0.5 text-[10px] text-ink-muted">
                      {detail.from_masked} · {formatWhen(detail.received_at)}
                    </p>
                    <p className="mt-0.5 font-mono text-[10px] text-ink-muted">{detail.id}</p>
                  </div>
                  <EmailStatusChip status={detail.status} />
                </div>

                {detail.request_id && (
                  <button
                    type="button"
                    className="mb-2 text-left text-[11px] font-semibold text-accent-primary hover:underline"
                    onClick={() => onOpenRequest?.(detail.request_id!)}
                  >
                    Заявка {detail.request_id} →
                  </button>
                )}
                {detail.rejection_reason && (
                  <p className="mb-2 text-[11px] text-[var(--accent-danger)]">
                    Причина: {detail.rejection_reason}
                  </p>
                )}

                <div className="mb-3 max-h-40 overflow-y-auto rounded-md border border-line bg-surface-1 p-2 text-[11px] leading-relaxed text-ink-secondary whitespace-pre-wrap">
                  {detail.body_masked_excerpt || '— пустое тело —'}
                </div>

                <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-ink-muted">
                  Вложения ({detail.attachment_artifact_ids?.length ?? 0})
                </p>
                <ul className="mb-4 space-y-1 text-[10px] font-mono text-ink-secondary">
                  {(detail.attachment_artifact_ids || []).map((aid) => (
                    <li key={aid}>{aid}</li>
                  ))}
                  {(detail.attachment_artifact_ids || []).length === 0 && <li className="text-ink-muted">нет</li>}
                </ul>

                <div className="mt-auto flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    icon="plus"
                    disabled={busy || detail.status === 'ingested' || detail.status === 'rejected'}
                    onClick={() => void ingest(detail.id)}
                  >
                    Создать заявку
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    icon="x-mark"
                    disabled={busy || detail.status === 'ingested' || detail.status === 'rejected'}
                    onClick={() => void reject(detail.id)}
                  >
                    Отклонить
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Конфиг inbox (admin)" icon="circle-info">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="grid gap-1 text-[11px] font-semibold text-ink-secondary">
            org_slug
            <input
              className="rounded-control border border-line bg-surface-1 px-2 py-1.5 font-mono text-xs text-ink-primary"
              value={cfgForm.org_slug}
              onChange={(e) => setCfgForm((f) => ({ ...f, org_slug: e.target.value }))}
              aria-label="org_slug"
            />
          </label>
          <label className="grid gap-1 text-[11px] font-semibold text-ink-secondary sm:col-span-2">
            address
            <input
              className="rounded-control border border-line bg-surface-1 px-2 py-1.5 font-mono text-xs text-ink-primary"
              value={cfgForm.address}
              onChange={(e) => setCfgForm((f) => ({ ...f, address: e.target.value }))}
              aria-label="address"
            />
          </label>
        </div>
        <label className="mt-3 flex items-center gap-2 text-[11px] font-semibold text-ink-secondary">
          <input
            type="checkbox"
            checked={cfgForm.auto_ingest}
            onChange={(e) => setCfgForm((f) => ({ ...f, auto_ingest: e.target.checked }))}
          />
          auto_ingest (сразу create_request после webhook)
        </label>
        <div className="mt-3">
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void saveConfig()}>
            Сохранить конфиг
          </Button>
        </div>
      </SectionCard>
    </section>
  );
}
