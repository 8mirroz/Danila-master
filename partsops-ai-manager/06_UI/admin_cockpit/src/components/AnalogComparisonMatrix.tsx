import React, { useState } from 'react';
import { notify } from '../lib/notify';

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
  requestId: string;
}

export const AnalogComparisonMatrix: React.FC<AnalogComparisonMatrixProps> = ({ requestId }) => {
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

  const handleSelect = (id: string, brand: string, article: string) => {
    setAnalogs((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, status: 'approved' } : item
      )
    );
    notify.success(`Деталь ${article} (${brand}) установлена как эквивалент замены.`);
  };

  const getTierBadge = (tier: AnalogItem['quality_tier']) => {
    switch (tier) {
      case 'OES':
        return <span className="bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 px-2 py-0.5 rounded text-[10px] font-bold">Tier 1: OES Конвейер</span>;
      case 'PREMIUM_AFTERMARKET':
        return <span className="bg-sky-950/80 text-sky-300 border border-sky-500/40 px-2 py-0.5 rounded text-[10px] font-bold">Tier 2: Premium</span>;
      case 'BUDGET':
        return <span className="bg-amber-950/80 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded text-[10px] font-bold">Tier 3: Budget</span>;
      default:
        return <span className="bg-rose-950/80 text-rose-300 border border-rose-500/40 px-2 py-0.5 rounded text-[10px] font-bold">Tier 4: Spec Match</span>;
    }
  };

  const getRiskBadge = (score: number) => {
    if (score <= 10) {
      return <span className="text-emerald-400 font-mono font-bold text-xs"><i className="fas fa-shield-check mr-1" />Риск {score}%</span>;
    }
    if (score <= 25) {
      return <span className="text-sky-400 font-mono font-bold text-xs"><i className="fas fa-check-circle mr-1" />Риск {score}%</span>;
    }
    if (score <= 45) {
      return <span className="text-amber-400 font-mono font-bold text-xs"><i className="fas fa-exclamation-triangle mr-1" />Риск {score}%</span>;
    }
    return <span className="text-rose-400 font-mono font-bold text-xs"><i className="fas fa-radiation mr-1" />Риск {score}%</span>;
  };

  return (
    <div className="glass-panel-dark rounded-2xl p-6 space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <i className="fas fa-code-branch text-emerald-400" />
            Матрица подбора аналогов и альтернатив (Smart Fallback Engine)
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Автоматическое определение дефицита OEM и ранжирование эквивалентов по рискам и качеству
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] bg-slate-800 text-slate-300 px-3 py-1 rounded-lg font-mono">
            Заявка: {requestId}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {analogs.map((item) => {
          const discountPct = item.price_oem
            ? Math.round(((item.price_oem - item.price_analog) / item.price_oem) * 100)
            : 0;

          return (
            <div
              key={item.id}
              className={`p-4 rounded-xl border transition-all duration-200 ${
                item.status === 'approved'
                  ? 'bg-emerald-950/20 border-emerald-500/50 shadow-lg shadow-emerald-950/20'
                  : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-slate-400">OEM: {item.oem_part}</span>
                    <span className="text-[10px] bg-rose-950/60 text-rose-300 border border-rose-500/30 px-1.5 py-0.5 rounded font-mono">
                      {item.oem_status}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                    {item.analog_article}
                    <span className="text-slate-400 text-xs font-normal">({item.brand})</span>
                  </h4>
                </div>
                {getTierBadge(item.quality_tier)}
              </div>

              <div className="my-3 space-y-1 bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/50 text-[11px] text-slate-300">
                {item.risk_factors.map((factor, idx) => (
                  <div key={idx} className="flex items-center gap-1.5">
                    <i className="fas fa-angle-right text-emerald-400 text-[10px]" />
                    <span>{factor}</span>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800/60">
                <div>
                  <div className="flex items-center gap-2">
                    {getRiskBadge(item.risk_score)}
                    {discountPct > 0 && (
                      <span className="text-emerald-400 text-[11px] font-bold">
                        Экономия {discountPct}%
                      </span>
                    )}
                  </div>
                  <div className="text-xs font-mono text-slate-200 mt-0.5">
                    {item.price_analog.toLocaleString()} ₽{' '}
                    <span className="text-[10px] text-slate-500 font-sans">
                      (Срок: {item.delivery_days} дн.)
                    </span>
                  </div>
                </div>

                <div>
                  {item.status === 'approved' ? (
                    <span className="text-xs font-bold text-emerald-400 flex items-center gap-1">
                      <i className="fas fa-check-circle" /> Утвержден
                    </span>
                  ) : (
                    <button
                      onClick={() => handleSelect(item.id, item.brand, item.analog_article)}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition-colors flex items-center gap-1.5 shadow-sm"
                    >
                      <i className="fas fa-check" /> Выбрать аналог
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
