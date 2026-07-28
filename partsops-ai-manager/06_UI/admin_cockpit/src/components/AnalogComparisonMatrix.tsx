import React, { useState } from 'react';
import { notify } from '../lib/notify';
import { Icon } from './Primitives';

export interface AnalogItem {
  id: string;
  oem_part: string;
  oem_status: 'OUT_OF_STOCK' | 'DEGRADED' | 'DISCONTINUED' | 'PRICE_ANOMALY';
  analog_article: string;
  brand: string;
  quality_tier: 'OES' | 'PREMIUM_AFTERMARKET' | 'BUDGET' | 'SPEC_MATCH';
  risk_score: number;
  risk_factors: string[];
  price_oem?: number;
  price_analog: number;
  delivery_days: number;
  status: 'recommended' | 'approved' | 'rejected' | 'pending';
}

interface AnalogComparisonMatrixProps {
  requestId?: string;
  onSelectAnalog?: (item: AnalogItem) => void;
}

export const AnalogComparisonMatrix: React.FC<AnalogComparisonMatrixProps> = ({ requestId = 'CON-LIVE', onSelectAnalog }) => {
  const [analogs, setAnalogs] = useState<AnalogItem[]>([
    {
      id: 'AN-001',
      oem_part: '34116858047',
      oem_status: 'OUT_OF_STOCK',
      analog_article: '24.0100-0100.1',
      brand: 'ATE',
      quality_tier: 'OES',
      risk_score: 5,
      risk_factors: ['Прямой конвейерный поставщик BMW AG', 'Гарантия 100% совместимости'],
      price_oem: 8500,
      price_analog: 5200,
      delivery_days: 1,
      status: 'recommended',
    },
    {
      id: 'AN-002',
      oem_part: '11427953129',
      oem_status: 'DISCONTINUED',
      analog_article: 'HU 816 x',
      brand: 'MANN-FILTER',
      quality_tier: 'OES',
      risk_score: 5,
      risk_factors: ['Официальный дистрибьютор TecDoc', 'Фильтрация OE уровня'],
      price_oem: 1800,
      price_analog: 1250,
      delivery_days: 1,
      status: 'approved',
    },
    {
      id: 'AN-003',
      oem_part: '31126855743',
      oem_status: 'PRICE_ANOMALY',
      analog_article: '27110 01',
      brand: 'LEMFÖRDER',
      quality_tier: 'OES',
      risk_score: 5,
      risk_factors: ['Усиленный сайлентблок (Heavy Duty)', 'Заводской конвейер VAG/BMW'],
      price_oem: 14500,
      price_analog: 8900,
      delivery_days: 2,
      status: 'recommended',
    },
    {
      id: 'AN-004',
      oem_part: '12120037607',
      oem_status: 'OUT_OF_STOCK',
      analog_article: 'BKR6EIX',
      brand: 'NGK',
      quality_tier: 'PREMIUM_AFTERMARKET',
      risk_score: 15,
      risk_factors: ['Иридиевый центральный электрод', 'Высокий ресурс 100k km'],
      price_oem: 2200,
      price_analog: 1400,
      delivery_days: 1,
      status: 'pending',
    },
  ]);

  const handleSelect = (item: AnalogItem) => {
    setAnalogs((prev) =>
      prev.map((a) => (a.id === item.id ? { ...a, status: 'approved' } : a))
    );
    notify.success(`Деталь ${item.analog_article} (${item.brand}) установлена как эквивалент замены.`);
    if (onSelectAnalog) onSelectAnalog(item);
  };

  const getTierBadge = (tier: AnalogItem['quality_tier']) => {
    switch (tier) {
      case 'OES':
        return (
          <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Tier 1: OES Конвейер
          </span>
        );
      case 'PREMIUM_AFTERMARKET':
        return (
          <span className="bg-sky-50 text-sky-700 border border-sky-200 px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-500" />
            Tier 2: Premium
          </span>
        );
      case 'BUDGET':
        return (
          <span className="bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            Tier 3: Budget
          </span>
        );
      default:
        return (
          <span className="bg-slate-100 text-slate-700 border border-slate-200 px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
            Tier 4: Spec Match
          </span>
        );
    }
  };

  const getRiskBadge = (score: number) => {
    if (score <= 10) {
      return (
        <span className="text-emerald-600 font-mono font-bold text-xs inline-flex items-center gap-1">
          <Icon name="check-circle" size={14} className="text-emerald-500" /> Риск {score}%
        </span>
      );
    }
    if (score <= 25) {
      return (
        <span className="text-sky-600 font-mono font-bold text-xs inline-flex items-center gap-1">
          <Icon name="circle-info" size={14} className="text-sky-500" /> Риск {score}%
        </span>
      );
    }
    return (
      <span className="text-amber-600 font-mono font-bold text-xs inline-flex items-center gap-1">
        <Icon name="warning" size={14} className="text-amber-500" /> Риск {score}%
      </span>
    );
  };

  return (
    <div className="bg-white border border-[var(--border-default)] rounded-2xl p-5 shadow-[0_10px_30px_rgba(37,99,235,0.04)] space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-4 gap-3">
        <div>
          <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100">
              <Icon name="code-fork" size={16} />
            </span>
            Матрица подбора аналогов (Smart Fallback Engine)
          </h3>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Автоматический подбор проверенных заменителей с оценкой рисков и ценовой выгоды
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] bg-slate-50 text-slate-600 border border-slate-200 px-3 py-1 rounded-full font-mono font-medium">
            Заявка: {requestId}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {analogs.map((item) => {
          const discountPct = item.price_oem
            ? Math.round(((item.price_oem - item.price_analog) / item.price_oem) * 100)
            : 0;

          const isApproved = item.status === 'approved';

          return (
            <div
              key={item.id}
              className={`p-4 rounded-xl border transition-all duration-200 flex flex-col justify-between space-y-3 ${
                isApproved
                  ? 'bg-emerald-50/40 border-emerald-300/80 shadow-[0_4px_16px_rgba(14,159,110,0.08)]'
                  : 'bg-slate-50/50 border-slate-200/80 hover:bg-white hover:border-blue-200 hover:shadow-md'
              }`}
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[11px] font-mono text-slate-500 font-medium">OEM: {item.oem_part}</span>
                      <span className="text-[9px] bg-rose-50 text-rose-700 border border-rose-200 px-1.5 py-0.2 rounded font-mono font-bold uppercase">
                        {item.oem_status}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                      {item.analog_article}
                      <span className="text-slate-500 text-xs font-semibold">({item.brand})</span>
                    </h4>
                  </div>
                  {getTierBadge(item.quality_tier)}
                </div>

                <div className="space-y-1 bg-white p-2.5 rounded-lg border border-slate-200/70 text-[11px] text-slate-600">
                  {item.risk_factors.map((factor, idx) => (
                    <div key={idx} className="flex items-center gap-1.5">
                      <Icon name="check" size={12} className="text-emerald-500 shrink-0" />
                      <span>{factor}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-200/60">
                <div>
                  <div className="flex items-center gap-2">
                    {getRiskBadge(item.risk_score)}
                    {discountPct > 0 && (
                      <span className="text-emerald-600 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded text-[10px] font-bold">
                        -{discountPct}%
                      </span>
                    )}
                  </div>
                  <div className="text-sm font-mono font-bold text-[var(--text-primary)] mt-0.5">
                    {item.price_analog.toLocaleString()} ₽{' '}
                    <span className="text-[10px] text-slate-500 font-sans font-normal">
                      (SLA: {item.delivery_days} дн.)
                    </span>
                  </div>
                </div>

                <div>
                  {isApproved ? (
                    <span className="text-xs font-bold text-emerald-700 bg-emerald-100/80 px-2.5 py-1 rounded-lg flex items-center gap-1 border border-emerald-200">
                      <Icon name="check-circle" size={14} className="text-emerald-600" /> Выбрано
                    </span>
                  ) : (
                    <button
                      onClick={() => handleSelect(item)}
                      className="px-3 py-1.5 rounded-lg bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-strong)] text-white font-semibold text-xs transition-all flex items-center gap-1.5 shadow-sm active:scale-95"
                    >
                      <Icon name="check" size={13} />
                      Заменить
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

