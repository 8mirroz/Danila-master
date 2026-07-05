import { useState, useEffect } from 'react';
import { ActionButton, InlineAlert, DataTable } from './Primitives';
import { apiFetch } from '../lib/api';

type MatchItem = {
  item: { name: string; price: number };
  supplier: { name: string; reliability_score: number };
};

type PricingCalculatorProps = {
  parts: Array<{ name: string; quantity: number; best_match?: MatchItem['item'] & { price: number } }>;
  onDraftInvoice: (invoiceData: any) => void;
  requestId: string;
  isApproved: boolean; // Gated pricing step
  allowedNextStates?: string[];
  onTransition?: (targetState: string, reason: string) => Promise<void>;
};

const transitionLabel: Record<string, string> = {
  APPROVED: 'Согласовать заказ',
  CANCELLED: 'Отклонить заказ',
  REWORK: 'Вернуть на доработку',
  FINANCE_REVIEW: 'Финансовая проверка',
  READY_FOR_APPROVAL: 'Готово к согласованию',
  ERP_SYNCING: 'Отправить в ERP',
  INVOICE_DRAFTED: 'Создать черновик',
  CLIENT_REJECTED: 'Отклонено клиентом',
};

export const PricingCalculator = ({
  parts,
  onDraftInvoice,
  requestId,
  isApproved,
  allowedNextStates = [],
  onTransition,
}: PricingCalculatorProps) => {
  const [logisticsCost, setLogisticsCost] = useState<number>(500);
  const [marginOverride, setMarginOverride] = useState<number>(15); // default 15%
  const [urgency, setUrgency] = useState<string>("normal");

  const [subtotal, setSubtotal] = useState(0);
  const [tax, setTax] = useState(0);
  const [total, setTotal] = useState(0);
  const [marginPolicyPassed, setMarginPolicyPassed] = useState(true);
  const [violations, setViolations] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    if (!requestId) {
      setSubtotal(0);
      setTax(0);
      setTotal(0);
      return;
    }

    const loadPreview = async () => {
      setPreviewLoading(true);
      setPreviewError(null);
      try {
        const res = await apiFetch(`/api/pricing/preview/${requestId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            logistics_cost: logisticsCost,
            target_margin_override: marginOverride / 100,
            urgency_level: urgency,
          }),
        });

        if (!res.ok) {
          const errorBody = await res.json().catch(() => null);
          throw new Error(errorBody?.detail || `Request failed: ${res.status} ${res.statusText}`);
        }

        const data = await res.json();
        if (cancelled) return;

        const pricing = data.pricing || {};
        setSubtotal(Math.round(pricing.subtotal_before_tax || 0));
        setTax(Math.round(pricing.tax_amount || 0));
        setTotal(Math.round(pricing.client_price || 0));
        setMarginPolicyPassed(Boolean(pricing.margin_policy_passed));
        setViolations([
          ...(pricing.violations || []),
          ...(pricing.margin_violations || []),
          ...(pricing.warnings || []),
        ]);
      } catch (error) {
        if (cancelled) return;
        setPreviewError(error instanceof Error ? error.message : 'Не удалось получить pricing preview');
        setSubtotal(0);
        setTax(0);
        setTotal(0);
        setViolations([]);
        setMarginPolicyPassed(false);
      } finally {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      }
    };

    void loadPreview();

    return () => {
      cancelled = true;
    };
  }, [logisticsCost, marginOverride, requestId, urgency]);

  const handleCreateDraft = async () => {
    if (!isApproved) {
      alert("Заказ должен быть согласован перед выпиской счета.");
      return;
    }
    setLoading(true);
    try {
      const res = await apiFetch(`/api/erp/invoice/${requestId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          logistics_cost: logisticsCost,
          target_margin_override: marginOverride / 100,
          urgency_level: urgency,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        onDraftInvoice(data);
      } else {
        const err = await res.json().catch(() => null);
        const detail = typeof err?.detail === 'string'
          ? err.detail
          : err?.detail?.reason || err?.detail?.message || 'ошибка API';
        alert(`Не удалось создать счет: ${detail}`);
      }
    } catch (e) {
      console.error("Error drafting invoice", e);
      alert("Не удалось создать счет: backend недоступен");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel-card-tight space-y-5 p-5">
      {/* Block 1: Status Gate / Customer Approval info */}
      {previewError && <InlineAlert type="danger" message={`Pricing preview недоступен: ${previewError}`} />}
      <div className={`rounded-[20px] p-4 border transition-all ${
        isApproved 
          ? 'bg-emerald-50/50 border-emerald-200 text-emerald-800' 
          : 'bg-amber-50/50 border-amber-200 text-amber-800'
      }`}>
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3">
          <div className="flex-1">
            <h4 className="text-xs font-bold flex items-center gap-1.5 uppercase tracking-wider mb-1">
              {isApproved ? (
                <>
                  <i className="fas fa-circle-check text-emerald-600"></i> Заказ успешно согласован
                </>
              ) : (
                <>
                  <i className="fas fa-exclamation-triangle text-amber-600 animate-pulse"></i> Требуется согласование с клиентом
                </>
              )}
            </h4>
            <p className="text-[11px] leading-normal font-medium text-slate-600">
              {isApproved 
                ? 'Условия и цены подтверждены. Вы можете выставить финальный черновик счета в ERP-систему.'
                : 'Для выставления коммерческого счёта в ERP-систему необходимо подтвердить согласие клиента с рассчитанной ценой.'
              }
            </p>
          </div>
          {previewLoading && (
            <div className="mt-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
              Обновляем pricing preview...
            </div>
          )}
          {onTransition && allowedNextStates.length > 0 && (
            <div className="flex flex-wrap gap-2 shrink-0">
              {allowedNextStates.map((state) => (
                <ActionButton 
                  key={state}
                  variant={state === 'CANCELLED' || state === 'FAILED' || state === 'CLIENT_REJECTED' ? 'danger' : state === 'APPROVED' ? 'primary' : 'secondary'}
                  icon={state === 'APPROVED' ? 'fa-circle-check' : state === 'CANCELLED' ? 'fa-triangle-exclamation' : 'fa-arrow-right'}
                  onClick={() => {
                    const reason = prompt(`Укажите причину для перехода ${state}:`);
                    if (reason !== null) onTransition(state, reason || transitionLabel[state] || `Переход в ${state}`);
                  }}
                >
                  {transitionLabel[state] || state}
                </ActionButton>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Block 2: Invoice items summary */}
      <div className="overflow-hidden rounded-[18px] border border-[var(--border-default)] bg-[var(--surface-1)]">
        <div className="border-b border-[var(--border-default)] bg-[var(--surface-2)] px-4 py-3 font-bold text-[10px] uppercase tracking-[0.18em] text-[var(--text-muted)]">
          Спецификация коммерческого предложения
        </div>
        <DataTable headers={["Деталь", "Кол-во", "Выбранное предложение", "Закупка", "Итого (закупка)"]}>
          {parts.map((p, idx) => {
            const price = p.best_match?.price || 0;
            return (
              <tr key={idx} className="border-b border-[var(--border-subtle)] text-xs">
                <td className="px-4 py-2.5 font-semibold text-[var(--text-primary)]">{p.name}</td>
                <td className="px-4 py-2.5 font-bold text-[var(--text-secondary)]">{p.quantity} шт.</td>
                <td className="px-4 py-2.5 text-[var(--text-muted)] italic">{p.best_match?.name || 'Аналог не подобран'}</td>
                <td className="px-4 py-2.5 text-[var(--text-secondary)] font-mono">{price.toLocaleString()} ₽</td>
                <td className="px-4 py-2.5 font-bold text-[var(--text-primary)] font-mono">{(price * p.quantity).toLocaleString()} ₽</td>
              </tr>
            );
          })}
        </DataTable>
      </div>

      {/* Block 3: Pricing Controls */}
      <div className="grid grid-cols-1 gap-4 border-t border-[var(--border-subtle)] pt-4 md:grid-cols-3">
        {/* Logistics cost input */}
        <div>
          <label className="block text-[10px] text-[var(--text-muted)] mb-1.5 uppercase font-bold tracking-wider">Логистические расходы (₽)</label>
          <input 
            type="number" 
            value={logisticsCost}
            onChange={(e) => setLogisticsCost(Number(e.target.value))}
            className="w-full rounded-[16px] border border-[var(--border-default)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text-primary)] outline-none transition-all focus:border-[var(--accent-primary)] font-sans"
          />
        </div>

        {/* Target margin input */}
        <div>
          <label className="block text-[10px] text-[var(--text-muted)] mb-1.5 uppercase font-bold tracking-wider">Целевая наценка (%)</label>
          <div className="flex items-center gap-3">
            <input 
              type="range" 
              min="5" 
              max="40" 
              value={marginOverride}
              onChange={(e) => setMarginOverride(Number(e.target.value))}
              className="h-1.5 flex-1 cursor-pointer appearance-none rounded-lg bg-slate-200 accent-[var(--accent-primary)]"
            />
            <span className="text-xs font-bold w-10 text-right text-[var(--text-primary)]">{marginOverride}%</span>
          </div>
        </div>

        {/* Urgency selection */}
        <div>
          <label className="block text-[10px] text-[var(--text-muted)] mb-1.5 uppercase font-bold tracking-wider">Срочность поставки</label>
          <select 
            value={urgency} 
            onChange={(e) => setUrgency(e.target.value)}
            className="w-full rounded-[16px] border border-[var(--border-default)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--text-primary)] outline-none transition-all focus:border-[var(--accent-primary)] font-sans"
          >
            <option value="low">Низкая (без буфера)</option>
            <option value="normal">Обычная</option>
            <option value="urgent">Срочно (+5% к себестоимости)</option>
            <option value="critical">Критично (+10% к себестоимости)</option>
          </select>
        </div>
      </div>

      {/* Block 4: Bill calculations */}
      <div className="grid grid-cols-2 gap-4 rounded-[20px] border border-[var(--border-default)] bg-[var(--surface-2)] p-4 text-xs shadow-inner md:grid-cols-4">
        <div>
          <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold block mb-1">Доставка и буферы</div>
          <div className="font-bold text-sm text-[var(--text-secondary)]">+{logisticsCost} ₽</div>
        </div>
        <div>
          <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold block mb-1">Субтотал до НДС</div>
          <div className="font-bold text-sm text-[var(--text-primary)]">{subtotal.toLocaleString()} ₽</div>
        </div>
        <div>
          <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold block mb-1">НДС (20%)</div>
          <div className="font-bold text-sm text-[var(--text-secondary)]">{tax.toLocaleString()} ₽</div>
        </div>
        <div>
          <div className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-bold block mb-1">Итог к оплате</div>
          <div className="font-black text-base text-[var(--accent-success)]">{total.toLocaleString()} ₽</div>
        </div>
      </div>

      {/* Margin Guard Alert */}
      {!marginPolicyPassed && (
        <InlineAlert 
          type="danger" 
          message={violations.join(', ')}
        />
      )}

      {/* Action buttons */}
      <div className="flex justify-end gap-2.5 pt-3 border-t border-[var(--border-subtle)]">
        <ActionButton 
          variant="primary" 
          icon="fa-file-invoice-dollar"
          loading={loading}
          disabled={!marginPolicyPassed || !isApproved}
          onClick={handleCreateDraft}
        >
          Выставить черновик счёта в ERP
        </ActionButton>
      </div>
    </div>
  );
};
