import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { oidcEnabled } from '../lib/auth';
import { notify } from '../lib/notify';
import { Icon } from './Primitives';

export interface AnalogItem {
  id: string;
  position_id?: string;
  oem_part: string;
  oem_status: 'OUT_OF_STOCK' | 'DEGRADED' | 'DISCONTINUED' | 'PRICE_ANOMALY' | 'UNKNOWN' | string;
  analog_article: string;
  brand: string;
  quality_tier: 'OES' | 'PREMIUM_AFTERMARKET' | 'BUDGET' | 'SPEC_MATCH' | string;
  risk_score: number;
  risk_factors: string[];
  price_oem?: number;
  price_analog: number;
  delivery_days: number;
  status: 'recommended' | 'approved' | 'rejected' | 'pending' | string;
}

interface AnalogComparisonMatrixProps {
  requestId?: string;
  onSelectAnalog?: (item: AnalogItem) => void;
}

function mapOemStatus(raw: unknown): string {
  if (!raw) return 'UNKNOWN';
  if (typeof raw === 'string') return raw;
  if (typeof raw === 'object' && raw !== null) {
    const o = raw as Record<string, unknown>;
    return String(o.status || o.code || o.reason || 'UNKNOWN');
  }
  return 'UNKNOWN';
}

function mapTier(raw: unknown): AnalogItem['quality_tier'] {
  const s = String(raw || 'SPEC_MATCH').toUpperCase();
  if (s.includes('OES') || s.includes('OEM')) return 'OES';
  if (s.includes('PREMIUM')) return 'PREMIUM_AFTERMARKET';
  if (s.includes('BUDGET')) return 'BUDGET';
  return 'SPEC_MATCH';
}

function mapStatus(raw: unknown): AnalogItem['status'] {
  const s = String(raw || 'pending').toLowerCase();
  if (s === 'approved' || s === 'recommended' || s === 'rejected' || s === 'pending') return s;
  if (s.includes('approv')) return 'approved';
  if (s.includes('recommend')) return 'recommended';
  if (s.includes('reject')) return 'rejected';
  return 'pending';
}

function flattenReport(data: any): AnalogItem[] {
  const positions = Array.isArray(data?.positions) ? data.positions : [];
  const items: AnalogItem[] = [];
  for (const pos of positions) {
    const oemPart = String(pos.part_number || pos.oem || '—');
    const oemStatus = mapOemStatus(pos.oem_unavailability);
    const ranked = Array.isArray(pos.ranked_analogs) ? pos.ranked_analogs : [];
    for (const a of ranked) {
      const factorsRaw = a.risk_factors ?? a.risk_factors_json ?? [];
      let factors: string[] = [];
      if (Array.isArray(factorsRaw)) {
        factors = factorsRaw.map(String);
      } else if (typeof factorsRaw === 'string') {
        try {
          const parsed = JSON.parse(factorsRaw);
          factors = Array.isArray(parsed) ? parsed.map(String) : [factorsRaw];
        } catch {
          factors = factorsRaw ? [factorsRaw] : [];
        }
      }
      items.push({
        id: String(a.candidate_id || a.id || a.article || `${pos.position_id}-${a.article}`),
        position_id: pos.position_id ? String(pos.position_id) : undefined,
        oem_part: oemPart,
        oem_status: oemStatus,
        analog_article: String(a.article || a.analog_article || '—'),
        brand: String(a.brand || '—'),
        quality_tier: mapTier(a.quality_tier || a.tier),
        risk_score: Number(a.risk_score ?? 0) || 0,
        risk_factors: factors.length ? factors : ['Нет risk_factors в API'],
        price_oem: a.price_oem != null ? Number(a.price_oem) : undefined,
        price_analog: Number(a.price ?? a.price_analog ?? 0) || 0,
        delivery_days: Number(a.delivery_days ?? 0) || 0,
        status: mapStatus(a.manual_review_status || a.status),
      });
    }
  }
  return items;
}

export const AnalogComparisonMatrix: React.FC<AnalogComparisonMatrixProps> = ({
  requestId,
  onSelectAnalog,
}) => {
  const [analogs, setAnalogs] = useState<AnalogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<'live' | 'empty' | 'error'>('empty');

  const load = useCallback(async () => {
    if (!requestId) {
      setAnalogs([]);
      setSource('empty');
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID || 'default';
      const tenantQuery = oidcEnabled() ? '' : `?tenant_id=${encodeURIComponent(tenantId)}`;
      const res = await apiFetch(
        `/api/contracts/${encodeURIComponent(requestId)}/analogs-report${tenantQuery}`,
      );
      if (res.status === 404) {
        setAnalogs([]);
        setSource('empty');
        setError(null);
        return;
      }
      if (!res.ok) {
        throw new Error(`API ${res.status}`);
      }
      const data = await res.json();
      const items = flattenReport(data);
      setAnalogs(items);
      setSource(items.length ? 'live' : 'empty');
    } catch (e) {
      setAnalogs([]);
      setSource('error');
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSelect = async (item: AnalogItem) => {
    if (!requestId || !item.position_id) {
      notify.info('Нельзя утвердить аналог: нет position_id / requestId (только live API).');
      return;
    }
    try {
      const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID || 'default';
      const tenantQuery = oidcEnabled() ? '' : `?tenant_id=${encodeURIComponent(tenantId)}`;
      const res = await apiFetch(
        `/api/contracts/${encodeURIComponent(requestId)}/positions/${encodeURIComponent(item.position_id)}/select-analog${tenantQuery}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ candidate_id: item.id, actor: 'operator' }),
        },
      );
      if (!res.ok) {
        const text = await res.text();
        notify.error(`Select analog failed: ${res.status} ${text.slice(0, 120)}`);
        return;
      }
      setAnalogs((prev) =>
        prev.map((a) =>
          a.id === item.id
            ? { ...a, status: 'approved' }
            : a.position_id === item.position_id
              ? { ...a, status: 'pending' }
              : a,
        ),
      );
      notify.success(`Деталь ${item.analog_article} (${item.brand}) утверждена как замена.`);
      onSelectAnalog?.(item);
    } catch (e) {
      notify.error(e instanceof Error ? e.message : String(e));
    }
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
          <span className="bg-surface-3 text-ink-secondary border border-line px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-surface-5" />
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
    <div className="bg-surface-1 border border-line rounded-2xl p-5 shadow-[0_10px_30px_rgba(37,99,235,0.04)] space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-line-subtle pb-4 gap-3">
        <div>
          <h3 className="text-sm font-bold text-ink-primary flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100">
              <Icon name="code-fork" size={16} />
            </span>
            Матрица подбора аналогов (live API)
          </h3>
          <p className="text-xs text-ink-secondary mt-0.5">
            Данные из `/api/contracts/…/analogs-report` — без demo-строк
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] bg-surface-2 text-ink-secondary border border-line px-3 py-1 rounded-full font-mono font-medium">
            Заявка: {requestId || 'не выбрана'}
          </span>
          <button
            type="button"
            onClick={() => void load()}
            className="text-[11px] font-bold text-sky-700 border border-sky-200 bg-sky-50 px-2 py-1 rounded-lg"
          >
            {loading ? '…' : 'Обновить'}
          </button>
        </div>
      </div>

      {loading && (
        <div className="text-xs text-ink-muted py-6 text-center">Загрузка аналогов…</div>
      )}

      {!loading && source === 'error' && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-800">
          Не удалось загрузить аналоги: {error}. Demo-данные не подставляются.
        </div>
      )}

      {!loading && source === 'empty' && (
        <div className="rounded-xl border border-line bg-surface-2 px-4 py-6 text-center text-xs text-ink-secondary">
          {requestId
            ? 'Нет позиций/аналогов в БД для этой заявки. Запустите resolve-analogs или contract crawler.'
            : 'Выберите заявку, чтобы увидеть live-матрицу аналогов.'}
        </div>
      )}

      {!loading && analogs.length > 0 && (
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
                    : 'bg-surface-2/50 border-line hover:bg-surface-1 hover:border-blue-200 hover:shadow-md'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[11px] font-mono text-ink-muted font-medium">
                          OEM: {item.oem_part}
                        </span>
                        <span className="text-[9px] bg-rose-50 text-rose-700 border border-rose-200 px-1.5 py-0.2 rounded font-mono font-bold uppercase">
                          {item.oem_status}
                        </span>
                      </div>
                      <h4 className="text-sm font-bold text-ink-primary flex items-center gap-1.5">
                        {item.analog_article}
                        <span className="text-ink-muted text-xs font-semibold">({item.brand})</span>
                      </h4>
                    </div>
                    {getTierBadge(item.quality_tier)}
                  </div>

                  <div className="space-y-1 bg-surface-1 p-2.5 rounded-lg border border-line/70 text-[11px] text-ink-secondary">
                    {item.risk_factors.map((factor, idx) => (
                      <div key={idx} className="flex items-center gap-1.5">
                        <Icon name="check" size={12} className="text-emerald-500 shrink-0" />
                        <span>{factor}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-line">
                  <div>
                    <div className="flex items-center gap-2">
                      {getRiskBadge(item.risk_score)}
                      {discountPct > 0 && (
                        <span className="text-emerald-600 bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 rounded text-[10px] font-bold">
                          -{discountPct}%
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-ink-muted">
                      {item.price_analog > 0 ? `${item.price_analog.toLocaleString()} ₽` : 'цена н/д'}
                      {item.delivery_days > 0 ? ` · ${item.delivery_days} дн.` : ''}
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={isApproved}
                    onClick={() => void handleSelect(item)}
                    className={`text-[11px] font-bold px-3 py-1.5 rounded-lg border ${
                      isApproved
                        ? 'bg-emerald-100 text-emerald-800 border-emerald-200 cursor-default'
                        : 'bg-blue-600 text-white border-blue-700 hover:bg-blue-500'
                    }`}
                  >
                    {isApproved ? 'Утверждён' : 'Выбрать'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
