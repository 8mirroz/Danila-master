import { useCallback, useEffect, useState } from 'react';
import { ActionButton, InlineAlert } from './Primitives';
import { apiFetch } from '../lib/api';

type PricingCalculatorProps = {
  requestId: string;
  version?: string | null;
  isApproved: boolean;
  canCreateInvoice: boolean;
  canSyncErp: boolean;
  erpQuotationRef?: string | null;
  /** Skip pricing preview call when workspace has no selected offers yet. */
  hasSelectedOffers?: boolean;
  onDraftInvoice: (invoiceData: any) => void;
};

type ErpStatus = {
  sync_status: string;
  invoice_ref?: string | null;
  quotation_ref?: string | null;
  last_error?: string | null;
};

export const PricingCalculator = ({
  requestId,
  version,
  isApproved,
  canCreateInvoice,
  canSyncErp,
  erpQuotationRef,
  hasSelectedOffers = true,
  onDraftInvoice,
}: PricingCalculatorProps) => {
  const [preview, setPreview] = useState<any | null>(null);
  const [erpStatus, setErpStatus] = useState<ErpStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [drafting, setDrafting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const erpResponse = await apiFetch(`/api/erp/status/${requestId}`);
      if (erpResponse.ok) setErpStatus(await erpResponse.json());
      else setErpStatus(null);

      if (!hasSelectedOffers) {
        setPreview(null);
        setError('Нет выбранных офферов — pricing preview недоступен до шага подбора.');
        return;
      }

      const pricingResponse = await apiFetch(`/api/erp/pricing/preview/${requestId}`, { method: 'POST' });
      if (pricingResponse.ok) {
        setPreview((await pricingResponse.json()).pricing ?? null);
        setError(null);
      } else {
        const body = await pricingResponse.json().catch(() => null);
        const detail = typeof body?.detail === 'string'
          ? body.detail
          : `Pricing preview недоступен (HTTP ${pricingResponse.status})`;
        setPreview(null);
        setError(detail);
      }
    } catch (cause) {
      setPreview(null);
      setErpStatus(null);
      setError(cause instanceof Error ? cause.message : 'Не удалось загрузить pricing');
    } finally {
      setLoading(false);
    }
  }, [requestId, hasSelectedOffers]);

  useEffect(() => { void load(); }, [load]);

  const createDraft = async () => {
    setDrafting(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/requests/${requestId}/actions/create_invoice`, {
        method: 'POST', headers: version ? { 'X-Request-Version': version } : undefined,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || `Не удалось создать черновик (HTTP ${response.status})`);
      onDraftInvoice(payload);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Backend недоступен: черновик не создан');
    } finally {
      setDrafting(false);
    }
  };

  const syncErp = async () => {
    setSyncing(true);
    setError(null);
    try {
      const response = await apiFetch(`/api/erp/sync/${requestId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(version ? { 'X-Request-Version': version } : {}) },
        body: '{}',
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || `ERP недоступна (HTTP ${response.status})`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'ERP sync не выполнен');
    } finally {
      setSyncing(false);
    }
  };

  const policyPassed = Boolean(preview?.margin_policy_passed) && !(preview?.margin_violations?.length);
  const invoiceAvailable = Boolean(erpStatus?.invoice_ref);
  const syncFailed = ['FAILED', 'RETRYING'].includes((erpStatus?.sync_status ?? '').toUpperCase());

  return <section className="glass-panel-dark rounded-2xl border border-line p-5 text-ink-primary shadow-2xl space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider">Pricing и ERP</h3>
        <p className="mt-1 text-[11px] text-ink-muted">Расчёт выполняется серверной policy; ручные client-side overrides отключены.</p>
      </div>
      <span className="font-mono text-[10px] text-ink-muted">{erpStatus?.quotation_ref || erpQuotationRef || 'Quotation не создана'}</span>
    </div>
    {error && <InlineAlert type="danger" message={error} />}
    {loading ? <p className="text-xs text-ink-muted">Загрузка подтверждённого расчёта…</p> : preview ? <>
      <div className="grid grid-cols-3 gap-2 text-center">
        <Metric label="Субтотал" value={preview.subtotal_before_tax} />
        <Metric label="НДС" value={preview.tax_amount} />
        <Metric label="Итого" value={preview.client_price} emphasis />
      </div>
      <div className={`rounded-xl border p-3 text-xs ${policyPassed ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'}`}>
        {policyPassed ? 'Pricing policy пройдена.' : (preview.margin_violations ?? preview.warnings ?? ['Pricing policy блокирует создание счета.']).join(' ')}
      </div>
    </> : <InlineAlert type="warning" message="Pricing evidence отсутствует или недоступен. Создание счета заблокировано." />}
    <div className="rounded-xl border border-line bg-surface-2 p-3 text-xs">
      <div className="flex justify-between gap-3"><span className="text-ink-muted">ERP status</span><span className={syncFailed ? 'text-rose-700' : 'text-ink-primary'}>{erpStatus?.sync_status ?? 'недоступен'}</span></div>
      {erpStatus?.invoice_ref && <div className="mt-1 flex justify-between gap-3"><span className="text-ink-muted">Invoice</span><span className="font-mono text-emerald-700">{erpStatus.invoice_ref}</span></div>}
      {erpStatus?.last_error && <p className="mt-2 text-rose-700">{erpStatus.last_error}</p>}
    </div>
    <div className="flex flex-wrap gap-2">
      <ActionButton variant="primary" icon="file-invoice-dollar" loading={drafting} disabled={!isApproved || !canCreateInvoice || !policyPassed} onClick={() => void createDraft()}>
        Создать черновик счета
      </ActionButton>
      {invoiceAvailable && canSyncErp && <ActionButton variant="secondary" icon="rotate" loading={syncing} onClick={() => void syncErp()}>
        {syncFailed ? 'Повторить ERP sync' : 'Синхронизировать ERP'}
      </ActionButton>}
    </div>
    {!isApproved && <p className="text-[11px] text-amber-700">Черновик доступен только после finance approval.</p>}
  </section>;
};

function Metric({ label, value, emphasis = false }: { label: string; value?: number; emphasis?: boolean }) {
  return <div className={`rounded-lg border border-line p-2 ${emphasis ? 'bg-emerald-50 text-emerald-700' : 'bg-surface-2 text-ink-primary'}`}>
    <span className="block text-[9px] font-bold uppercase text-ink-muted">{label}</span>
    <span className="font-mono text-xs font-bold">{typeof value === 'number' ? `${Math.round(value).toLocaleString()} ₽` : '—'}</span>
  </div>;
}
