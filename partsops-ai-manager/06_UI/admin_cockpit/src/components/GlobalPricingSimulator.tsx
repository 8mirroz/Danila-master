import React, { useState, useMemo, useEffect } from 'react';
import { SectionCard, Icon } from './Primitives';
import { type RequestItem } from '../lib/types';

type GlobalPricingSimulatorProps = {
  requests: RequestItem[];
  onSelectRequest: (req: RequestItem) => void;
  initialBaseCost?: number;
};

export const GlobalPricingSimulator: React.FC<GlobalPricingSimulatorProps> = ({
  requests,
  onSelectRequest,
  initialBaseCost,
}) => {
  const [baseCost, setBaseCost] = useState<number>(45000);
  const [marginPct, setMarginPct] = useState<number>(25);
  const [logisticsCost, setLogisticsCost] = useState<number>(3500);
  const [riskBufferPct, setRiskBufferPct] = useState<number>(5);
  const [vatRate, setVatRate] = useState<number>(20);
  const [selectedReqId, setSelectedReqId] = useState<string>('');

  useEffect(() => {
    if (initialBaseCost !== undefined) {
      setBaseCost(initialBaseCost);
    }
  }, [initialBaseCost]);

  const activeRequests = useMemo(() => {
    return requests.filter((r) => !['CLOSED', 'CANCELLED', 'FAILED'].includes(r.status));
  }, [requests]);

  const calculation = useMemo(() => {
    const riskAmount = Math.round(baseCost * (riskBufferPct / 100));
    const subtotalCost = baseCost + riskAmount + logisticsCost;
    const marginAmount = Math.round(subtotalCost * (marginPct / 100));
    const netSalePrice = subtotalCost + marginAmount;
    const vatAmount = Math.round(netSalePrice * (vatRate / 100));
    const finalClientPrice = netSalePrice + vatAmount;
    const grossProfit = marginAmount;
    const netMarginPct = finalClientPrice > 0 ? Math.round((grossProfit / finalClientPrice) * 100) : 0;

    return {
      riskAmount,
      subtotalCost,
      marginAmount,
      netSalePrice,
      vatAmount,
      finalClientPrice,
      grossProfit,
      netMarginPct,
    };
  }, [baseCost, marginPct, logisticsCost, riskBufferPct, vatRate]);

  const handleSelectReqChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setSelectedReqId(id);
    if (id) {
      const match = requests.find((r) => r.request_id === id);
      if (match) onSelectRequest(match);
    }
  };

  // Вычисление процентов для визуальной шкалы стоимости
  const basePct = calculation.finalClientPrice > 0 ? (baseCost / calculation.finalClientPrice) * 100 : 0;
  const riskPct = calculation.finalClientPrice > 0 ? (calculation.riskAmount / calculation.finalClientPrice) * 100 : 0;
  const logPct = calculation.finalClientPrice > 0 ? (logisticsCost / calculation.finalClientPrice) * 100 : 0;
  const margPct = calculation.finalClientPrice > 0 ? (calculation.marginAmount / calculation.finalClientPrice) * 100 : 0;
  const vatPct = calculation.finalClientPrice > 0 ? (calculation.vatAmount / calculation.finalClientPrice) * 100 : 0;

  return (
    <div className="space-y-4">
      <div className="panel-card p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-blue-700">
                <Icon name="pencil" size={12} /> Автономный симулятор
              </span>
              <span className="font-mono text-[10px] text-ink-muted">Margin & Price Engine v3.1</span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-ink-primary">
              Калькулятор цен, маржи и коммерческих предложений
            </h2>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-ink-secondary">
              Гибкое моделирование себестоимости, логистических расходов, риск-буфера и итоговой розничной стоимости. Рассчитывайте параметры автономно или загрузите данные активного заказа.
            </p>
          </div>

          {/* Quick Request Selector */}
          <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface-2 p-3">
            <div className="text-right shrink-0 hidden sm:block">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Контекст заявки</div>
              <div className="text-xs font-semibold text-ink-primary">Загрузить расчет в заявку</div>
            </div>
            <select
              value={selectedReqId}
              onChange={handleSelectReqChange}
              className="cursor-pointer rounded-xl border border-line bg-surface-1 px-3 py-2 text-xs font-semibold text-ink-primary focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
            >
              <option value="">-- Выберите запрос из очереди --</option>
              {activeRequests.map((r) => (
                <option key={r.request_id} value={r.request_id}>
                  {r.request_id} ({r.customer_name || 'Без имени'}) — {r.status}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Interactive Form (Inputs) */}
        <div className="lg:col-span-7 space-y-4">
          <SectionCard title="Параметры закупки и затрат" icon="pencil">
            <div className="space-y-4">
              {/* Base Cost */}
              <div>
                <div className="flex justify-between text-xs font-bold text-ink-secondary mb-1">
                  <span>Закупочная стоимость деталей (руб)</span>
                  <span className="font-mono text-blue-600">{baseCost.toLocaleString('ru-RU')} ₽</span>
                </div>
                <input
                  type="number"
                  value={baseCost || ''}
                  onChange={(e) => setBaseCost(Math.max(0, Number(e.target.value)))}
                  className="w-full px-3 py-2 bg-surface-2 border border-line rounded-xl text-xs font-mono font-bold text-ink-primary focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Logistics Cost */}
              <div>
                <div className="flex justify-between text-xs font-bold text-ink-secondary mb-1">
                  <span>Логистика и транспортные расходы (руб)</span>
                  <span className="font-mono text-ink-secondary">{logisticsCost.toLocaleString('ru-RU')} ₽</span>
                </div>
                <input
                  type="number"
                  value={logisticsCost || ''}
                  onChange={(e) => setLogisticsCost(Math.max(0, Number(e.target.value)))}
                  className="w-full px-3 py-2 bg-surface-2 border border-line rounded-xl text-xs font-mono font-bold text-ink-primary focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Risk Buffer */}
              <div className="pt-2">
                <div className="flex justify-between text-xs font-bold text-ink-secondary mb-1">
                  <span>Резерв на транспортные риски и колебания курса (%)</span>
                  <span className="font-mono text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">{riskBufferPct}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="20"
                  step="1"
                  value={riskBufferPct}
                  onChange={(e) => setRiskBufferPct(Number(e.target.value))}
                  className="w-full h-2 bg-surface-4 rounded-lg appearance-none cursor-pointer accent-amber-500"
                />
                <div className="flex justify-between text-[10px] text-ink-muted mt-1 font-mono">
                  <span>0%</span>
                  <span>10%</span>
                  <span>20%</span>
                </div>
              </div>

              {/* Margin Slider */}
              <div className="pt-2">
                <div className="flex justify-between text-xs font-bold text-ink-secondary mb-1">
                  <span>Целевая торговая наценка (%)</span>
                  <span className="font-mono text-purple-700 bg-purple-100 px-2 py-0.5 rounded border border-purple-300 shadow-sm">{marginPct}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={marginPct}
                  onChange={(e) => setMarginPct(Number(e.target.value))}
                  className="w-full h-2 bg-purple-100 rounded-lg appearance-none cursor-pointer accent-purple-600"
                />
                <div className="flex justify-between text-[10px] text-ink-muted mt-1 font-mono">
                  <span>0%</span>
                  <span>25%</span>
                  <span>50%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* VAT Selector */}
              <div className="pt-2">
                <label className="block text-xs font-bold text-ink-secondary mb-1">Режим НДС</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { rate: 20, label: 'НДС 20%' },
                    { rate: 0, label: 'НДС 0%' },
                    { rate: 0, label: 'Без НДС (УСН)' },
                  ].map((v, i) => {
                    const isSelected = vatRate === v.rate && (i !== 2 || vatRate === 0);
                    // Special visual logic to differentiate the two 0% options (Export vs simplified)
                    // For demo purposes, simply active/inactive check
                    return (
                      <button
                        key={i}
                        type="button"
                        onClick={() => setVatRate(v.rate)}
                        className={`py-2 px-3 rounded-xl text-xs font-bold transition-all border ${
                          isSelected
                            ? 'border-accent-primary bg-accent-primary text-white shadow-md scale-[1.02]'
                            : 'bg-surface-1 text-ink-secondary border-line hover:bg-surface-2'
                        }`}
                      >
                        {v.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </SectionCard>
        </div>

        {/* Right Financial Results Card */}
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-3xl border border-purple-200 bg-gradient-to-br from-purple-50/80 via-white to-indigo-50/50 p-6 shadow-md space-y-5">
            <div className="flex items-center justify-between border-b border-purple-100 pb-3">
              <h3 className="text-sm font-black uppercase tracking-wider text-purple-950">
                Финансовый расчет
              </h3>
              <span className="text-[10px] font-mono font-bold text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full">
                Симуляция КП
              </span>
            </div>

            {/* Total Big Client Price */}
            <div className="rounded-2xl bg-surface-1 p-5 border border-purple-100 shadow-sm text-center space-y-2 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-400 via-purple-500 to-indigo-500"></div>
              <div className="text-[10px] font-extrabold uppercase tracking-wider text-ink-muted">
                Итоговая стоимость для клиента
              </div>
              <div className="text-3xl font-black text-ink-primary font-mono tracking-tight">
                {calculation.finalClientPrice.toLocaleString('ru-RU')} ₽
              </div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-[11px] font-bold">
                <Icon name="check" size={12} />
                Чистая прибыль: +{calculation.grossProfit.toLocaleString('ru-RU')} ₽
              </div>
            </div>

            {/* Visual Breakdown Bar */}
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] font-bold uppercase text-ink-muted mb-1">
                <span>Структура цены</span>
                <span>{calculation.netMarginPct}% Маржа</span>
              </div>
              <div className="flex h-3 w-full rounded-full overflow-hidden bg-surface-3 shadow-inner">
                {basePct > 0 && <div style={{ width: `${basePct}%` }} className="bg-surface-5 transition-all duration-300" title="Закупка"></div>}
                {riskPct > 0 && <div style={{ width: `${riskPct}%` }} className="bg-amber-400 transition-all duration-300" title="Риск-буфер"></div>}
                {logPct > 0 && <div style={{ width: `${logPct}%` }} className="bg-blue-400 transition-all duration-300" title="Логистика"></div>}
                {margPct > 0 && <div style={{ width: `${margPct}%` }} className="bg-purple-500 transition-all duration-300" title="Наценка"></div>}
                {vatPct > 0 && <div style={{ width: `${vatPct}%` }} className="bg-ink-secondary transition-all duration-300" title="НДС"></div>}
              </div>
            </div>

            {/* Breakdown List */}
            <div className="space-y-2 text-xs pt-2">
              <div className="flex justify-between py-1.5 border-b border-line-subtle">
                <span className="text-ink-muted flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-surface-5"></span> Себестоимость:
                </span>
                <span className="font-mono font-bold text-ink-primary">{baseCost.toLocaleString('ru-RU')} ₽</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-line-subtle">
                <span className="text-ink-muted flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span> Риск-буфер ({riskBufferPct}%):
                </span>
                <span className="font-mono text-amber-700 font-semibold">+{calculation.riskAmount.toLocaleString('ru-RU')} ₽</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-line-subtle">
                <span className="text-ink-muted flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-blue-400"></span> Доставка:
                </span>
                <span className="font-mono text-ink-primary font-semibold">+{logisticsCost.toLocaleString('ru-RU')} ₽</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-purple-100 bg-purple-50/50 px-2 -mx-2 rounded-lg">
                <span className="font-bold text-purple-900 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-500"></span> Торговая маржа ({marginPct}%):
                </span>
                <span className="font-mono font-black text-purple-900">+{calculation.marginAmount.toLocaleString('ru-RU')} ₽</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-ink-muted flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-ink-secondary"></span> НДС ({vatRate}%):
                </span>
                <span className="font-mono text-ink-secondary">+{calculation.vatAmount.toLocaleString('ru-RU')} ₽</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
