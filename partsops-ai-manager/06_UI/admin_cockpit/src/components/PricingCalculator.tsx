import { useState, useEffect } from 'react';
import { ActionButton, InlineAlert } from './Primitives';
import { apiFetch } from '../lib/api';

type MatchItem = {
  item: { name: string; price: number };
  supplier: { name: string; reliability_score: number };
};

type PricingCalculatorProps = {
  parts: Array<{ 
    name: string; 
    quantity: number; 
    best_match?: MatchItem['item'] & { 
      price: number;
      price_deviation_from_median?: number;
    } 
  }>;
  onDraftInvoice: (invoiceData: any) => void;
  requestId: string;
  isApproved: boolean;
  allowedNextStates?: string[];
  onTransition?: (targetState: string, reason: string) => Promise<void>;
};

export const PricingCalculator = ({
  parts: _parts,
  onDraftInvoice,
  requestId,
  isApproved,
  allowedNextStates: _allowedNextStates = [],
  onTransition: _onTransition,
}: PricingCalculatorProps) => {
  const [logisticsCost, setLogisticsCost] = useState<number>(500);
  const [marginOverride, setMarginOverride] = useState<number>(15);
  const [urgency, setUrgency] = useState<string>("normal");

  const [subtotal, setSubtotal] = useState(0);
  const [tax, setTax] = useState(0);
  const [total, setTotal] = useState(0);
  const [marginPolicyPassed, setMarginPolicyPassed] = useState(true);
  const [violations, setViolations] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [_previewLoading, setPreviewLoading] = useState(false);


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
    <div className="glass-panel-dark rounded-2xl text-slate-200 p-5 space-y-5 border border-slate-800 shadow-2xl">
      {/* Header Banner */}
      {previewError && <InlineAlert type="danger" message={`Pricing preview недоступен: ${previewError}`} />}
      
      <div className="flex justify-between items-center border-b border-slate-800 pb-3">
        <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200">
          <i className="fas fa-calculator text-emerald-400" />
          <span>Калькулятор маржи & Консоль Синхронизации ERP</span>
        </h3>
        <span className="font-mono text-xs text-slate-400">
          Quotation Ref: <strong className="text-emerald-400 font-mono">#2026.170160</strong>
        </span>
      </div>

      {/* Main 2-Column Grid: Pricing Left, ERP Console Right */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Pricing Controls & Margin Guard */}
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/80 p-4">
          <div className="flex justify-between items-center border-b border-slate-800 pb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Параметры Ценообразования
            </span>
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold border ${
              marginPolicyPassed 
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' 
                : 'bg-red-500/20 text-red-400 border-red-500/30'
            }`}>
              <i className={`fas ${marginPolicyPassed ? 'fa-shield-check' : 'fa-triangle-exclamation'}`} />
              <span>{marginPolicyPassed ? 'Margin Policy Passed' : 'Policy Violation'}</span>
            </span>
          </div>

          {/* Slider Margin */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-semibold text-slate-300">
              <span className="text-[10px] uppercase font-bold text-slate-400">Целевая наценка (Margin Override)</span>
              <span className="font-mono text-emerald-400 font-bold">{marginOverride}%</span>
            </div>
            <input 
              type="range" 
              min="5" 
              max="40" 
              value={marginOverride}
              onChange={(e) => setMarginOverride(Number(e.target.value))}
              className="w-full h-2 rounded-lg bg-slate-800 accent-emerald-400 cursor-pointer"
            />
          </div>

          {/* Inputs: Logistics & Urgency */}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <div>
              <label className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">
                Логистика (Logistics Fee)
              </label>
              <input 
                type="number" 
                value={logisticsCost}
                onChange={(e) => setLogisticsCost(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white font-mono outline-none focus:border-emerald-400"
              />
            </div>
            <div>
              <label className="block text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">
                Срочность
              </label>
              <select 
                value={urgency} 
                onChange={(e) => setUrgency(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white outline-none focus:border-emerald-400"
              >
                <option value="normal">Обычная</option>
                <option value="urgent">Срочно (+5%)</option>
                <option value="critical">Критично (+10%)</option>
              </select>
            </div>
          </div>

          {/* Calculations Summary */}
          <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-800 text-center">
            <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-[9px] text-slate-400 block font-bold uppercase">Субтотал</span>
              <span className="font-mono text-xs text-slate-200 font-bold">{subtotal.toLocaleString()} ₽</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800">
              <span className="text-[9px] text-slate-400 block font-bold uppercase">НДС 20%</span>
              <span className="font-mono text-xs text-slate-300 font-bold">{tax.toLocaleString()} ₽</span>
            </div>
            <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/30">
              <span className="text-[9px] text-emerald-400 block font-bold uppercase">Итого к оплате</span>
              <span className="font-mono text-sm text-emerald-400 font-extrabold">{total.toLocaleString()} ₽</span>
            </div>
          </div>
        </div>

        {/* Right Column: ERP Sync Status Console */}
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/80 p-4 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center border-b border-slate-800 pb-3 mb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Консоль Синхронизации 1С/SAP ERP
              </span>
              <span className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-400">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>ONLINE</span>
              </span>
            </div>

            <div className="space-y-2.5 text-xs text-slate-300">
              <div className="flex justify-between items-center p-2.5 rounded-xl border border-slate-800 bg-slate-950/60">
                <span className="text-[10px] text-slate-400 font-bold uppercase">Quotation Reference</span>
                <span className="font-mono text-emerald-400 font-bold">#2026.170160</span>
              </div>

              <div className="flex justify-between items-center p-2.5 rounded-xl border border-slate-800 bg-slate-950/60">
                <span className="text-[10px] text-slate-400 font-bold uppercase">ERP Sync Status</span>
                <span className="font-mono text-white font-bold bg-slate-800 px-2 py-0.5 rounded">
                  {isApproved ? 'INVOICE_DRAFTED' : 'PENDING_APPROVAL'}
                </span>
              </div>
            </div>
          </div>

          {!marginPolicyPassed && (
            <InlineAlert 
              type="danger" 
              message={violations.join(', ')}
            />
          )}

          <div className="pt-3">
            <ActionButton 
              variant="primary" 
              icon="fa-file-invoice-dollar"
              loading={loading}
              disabled={!marginPolicyPassed || !isApproved}
              onClick={handleCreateDraft}
              className="w-full py-3 text-xs font-bold glow-emerald shadow-lg"
            >
              Draft Invoice in 1C / SAP ERP
            </ActionButton>
          </div>
        </div>
      </div>
    </div>
  );
};
