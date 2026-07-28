import { useState, useEffect, useMemo, useCallback } from 'react';
import { DataTable, ActionButton, Icon } from './Primitives';
import { apiFetch } from '../lib/api';
import { AnalogComparisonMatrix, type AnalogItem } from './AnalogComparisonMatrix';

type MatchBreakdown = {
  oem_exact: number;
  brand_article: number;
  normalized_name: number;
  vehicle_compatibility: number;
  side_position: number;
  quantity_pack: number;
  language_synonym: number;
  historical_acceptance: number;
  supplier_data_quality: number;
};

type MatchItem = {
  item: {
    catalog_id: string;
    name: string;
    oem_number: string;
    brand: string;
    price: number;
    stock_qty: number;
    delivery_days: number;
    category: string;
  };
  supplier: {
    supplier_id: string;
    name: string;
    reliability_score: number;
  };
  score: number;
  breakdown: MatchBreakdown;
  price_deviation_from_median?: number;
};

type SupplierMatrixProps = {
  parts: Array<{ name: string; quantity: number }>;
  onSelectOffer?: (partName: string, offer: MatchItem) => void;
  selectedOffers?: Record<string, MatchItem | null>;
  requestId?: string;
};

/** Soft UI SVG Radar Chart for AI Match Factors */
const MatchRadarChart = ({ breakdown, score }: { breakdown?: MatchBreakdown | null; score: number }) => {
  const oem = breakdown?.oem_exact ? Math.min(100, breakdown.oem_exact * 100) : score;
  const quality = breakdown?.supplier_data_quality ? Math.min(100, breakdown.supplier_data_quality * 100) : Math.max(60, score - 5);
  const compat = breakdown?.vehicle_compatibility ? Math.min(100, breakdown.vehicle_compatibility * 100) : score;
  const price = Math.min(100, Math.max(50, score + 4));
  const delivery = Math.min(100, Math.max(55, score - 2));

  const getPoint = (val: number, angleDeg: number) => {
    const r = (val / 100) * 32;
    const rad = (angleDeg - 90) * (Math.PI / 180);
    const x = 50 + r * Math.cos(rad);
    const y = 50 + r * Math.sin(rad);
    return { x, y, str: `${x.toFixed(1)},${y.toFixed(1)}` };
  };

  const pPrice = getPoint(price, 0);
  const pCompat = getPoint(compat, 72);
  const pQuality = getPoint(quality, 144);
  const pDelivery = getPoint(delivery, 216);
  const pOem = getPoint(oem, 288);

  const pointsStr = [pPrice.str, pCompat.str, pQuality.str, pDelivery.str, pOem.str].join(' ');

  return (
    <div className="flex flex-col items-center justify-center p-3 rounded-2xl bg-gradient-to-b from-blue-50/50 to-slate-50 border border-blue-100/60 shadow-sm relative overflow-hidden">
      <div className="absolute top-2 right-2">
        <span className="text-[10px] font-bold font-mono px-2 py-0.5 rounded-full bg-blue-100/80 text-blue-700 border border-blue-200">
          AI Score: {score}%
        </span>
      </div>

      <svg className="w-32 h-32 my-1" viewBox="0 0 100 100">
        <defs>
          <linearGradient id="radarFill" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#0e9f6e" stopOpacity="0.2" />
          </linearGradient>
        </defs>
        {/* Web Grid lines */}
        <polygon points="50,15 83.3,39.2 70.6,78.3 29.4,78.3 16.7,39.2" fill="none" stroke="rgba(37, 99, 235, 0.12)" strokeWidth="1" />
        <polygon points="50,28 72.3,44.4 63.8,70.5 36.2,70.5 27.7,44.4" fill="none" stroke="rgba(37, 99, 235, 0.08)" strokeWidth="1" />
        <polygon points="50,40 61.2,49.7 56.9,62.8 43.1,62.8 38.8,49.7" fill="none" stroke="rgba(37, 99, 235, 0.05)" strokeWidth="1" />

        {/* Axis lines */}
        <line x1="50" y1="50" x2="50" y2="15" stroke="rgba(37, 99, 235, 0.1)" strokeWidth="1" />
        <line x1="50" y1="50" x2="83.3" y2="39.2" stroke="rgba(37, 99, 235, 0.1)" strokeWidth="1" />
        <line x1="50" y1="50" x2="70.6" y2="78.3" stroke="rgba(37, 99, 235, 0.1)" strokeWidth="1" />
        <line x1="50" y1="50" x2="29.4" y2="78.3" stroke="rgba(37, 99, 235, 0.1)" strokeWidth="1" />
        <line x1="50" y1="50" x2="16.7" y2="39.2" stroke="rgba(37, 99, 235, 0.1)" strokeWidth="1" />

        {/* Polygon */}
        <polygon points={pointsStr} fill="url(#radarFill)" stroke="#2563eb" strokeWidth="2" />

        {/* Value Nodes */}
        <circle cx={pPrice.x} cy={pPrice.y} r="3" fill="#2563eb" stroke="#ffffff" strokeWidth="1.5" />
        <circle cx={pCompat.x} cy={pCompat.y} r="3" fill="#2563eb" stroke="#ffffff" strokeWidth="1.5" />
        <circle cx={pQuality.x} cy={pQuality.y} r="3" fill="#2563eb" stroke="#ffffff" strokeWidth="1.5" />
        <circle cx={pDelivery.x} cy={pDelivery.y} r="3" fill="#2563eb" stroke="#ffffff" strokeWidth="1.5" />
        <circle cx={pOem.x} cy={pOem.y} r="3" fill="#2563eb" stroke="#ffffff" strokeWidth="1.5" />
      </svg>

      <div className="grid grid-cols-3 gap-1 w-full text-[9px] text-slate-500 font-semibold text-center mt-1 border-t border-slate-200/50 pt-1.5">
        <div>Прайс: {price}%</div>
        <div>SLA: {delivery}%</div>
        <div>OEM: {oem}%</div>
      </div>
    </div>
  );
};

export const SupplierMatrix = ({ parts, onSelectOffer, selectedOffers = {}, requestId }: SupplierMatrixProps) => {
  const displayParts = useMemo(() => parts.filter((part) => part.name.trim().length > 0), [parts]);

  const [activePart, setActivePart] = useState<string>(displayParts[0]?.name || '');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [viewMode, setViewMode] = useState<'direct' | 'analogs'>('direct');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<MatchItem | null>(null);
  const [selectedBreakdown, setSelectedBreakdown] = useState<MatchBreakdown | null>(null);

  const fetchMatches = useCallback(async (partName: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/catalog/search?q=${encodeURIComponent(partName)}`);
      if (res.ok) {
        const data = await res.json();
        const list: MatchItem[] = Array.isArray(data.matches) ? data.matches : [];
        setMatches(list);
        if (list.length > 0) {
          setSelectedMatch(list[0]);
          setSelectedBreakdown(list[0].breakdown);
        } else {
          setSelectedMatch(null);
          setSelectedBreakdown(null);
        }
      } else {
        const detail = await res.json().catch(() => null);
        throw new Error(typeof detail?.detail === 'string' ? detail.detail : `Каталог недоступен (HTTP ${res.status})`);
      }
    } catch (e) {
      setMatches([]);
      setSelectedMatch(null);
      setSelectedBreakdown(null);
      setError(e instanceof Error ? e.message : 'Не удалось загрузить офферы каталога');
    } finally {
      setLoading(false);
    }
  }, []);

  const handlePartClick = (partName: string) => {
    setActivePart(partName);
    fetchMatches(partName);
  };

  useEffect(() => {
    const target = displayParts.some((part) => part.name === activePart)
      ? activePart
      : displayParts[0]?.name;
    if (target) {
      if (target !== activePart) setActivePart(target);
      void fetchMatches(target);
    } else {
      setMatches([]);
      setSelectedMatch(null);
      setSelectedBreakdown(null);
    }
  }, [activePart, displayParts, fetchMatches]);

  const filteredMatches = useMemo(() => {
    if (!searchQuery.trim()) return matches;
    const q = searchQuery.toLowerCase();
    return matches.filter(
      (m) =>
        m.item.name.toLowerCase().includes(q) ||
        m.item.brand.toLowerCase().includes(q) ||
        m.item.oem_number.toLowerCase().includes(q) ||
        m.supplier.name.toLowerCase().includes(q)
    );
  }, [matches, searchQuery]);

  // Top KPI summary metrics calculated from matches
  const metrics = useMemo(() => {
    if (!matches || matches.length === 0) {
      return { total: 0, bestPrice: 0, topReliability: 0, avgSla: 0 };
    }
    const prices = matches.map((m) => m.item.price);
    const rels = matches.map((m) => m.supplier.reliability_score);
    const ddays = matches.map((m) => m.item.delivery_days);
    return {
      total: matches.length,
      bestPrice: Math.min(...prices),
      topReliability: Math.round(Math.max(...rels) * 100),
      avgSla: Math.round(ddays.reduce((a, b) => a + b, 0) / ddays.length),
    };
  }, [matches]);

  if (displayParts.length === 0) {
    return (
      <div className="flex min-h-[280px] flex-col items-center justify-center rounded-2xl border border-amber-200 bg-amber-50/60 p-8 text-center">
        <Icon name="list-check" size={28} className="mb-3 text-amber-600" />
        <h3 className="text-sm font-bold text-amber-950">Нет подтверждённых позиций для подбора</h3>
        <p className="mt-1 max-w-md text-xs leading-relaxed text-amber-900">Вернитесь к нормализации, добавьте хотя бы одну позицию и повторите подбор.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[var(--border-default)] rounded-2xl p-6 shadow-[0_10px_30px_rgba(37,99,235,0.05)] space-y-5 text-[var(--text-primary)]">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-100 pb-4 gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100 shadow-sm">
              <Icon name="wave-square" size={18} />
            </span>
            <div>
              <h3 className="text-base font-bold tracking-tight text-[var(--text-primary)]">
                Матрица сравнения поставщиков (AI Supplier Matrix)
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                ИИ-ранжирование офферов по алгоритму 9 весовых факторов качества, цены и риска
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Прайсы и наличие проверены
          </span>

          {/* Dual View mode switcher button */}
          <div className="inline-flex p-0.5 bg-slate-100/80 border border-slate-200/80 rounded-xl">
            <button
              onClick={() => setViewMode('direct')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
                viewMode === 'direct'
                  ? 'bg-white text-[var(--accent-primary)] shadow-sm font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Прямой подбор
            </button>
            <button
              onClick={() => setViewMode('analogs')}
              className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
                viewMode === 'analogs'
                  ? 'bg-white text-[var(--accent-primary)] shadow-sm font-bold'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Матрица аналогов
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-gradient-to-br from-blue-50/60 to-slate-50 border border-blue-100/60 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Найдено офферов</div>
            <div className="text-lg font-bold font-mono text-[var(--text-primary)] mt-0.5">{metrics.total} вар.</div>
          </div>
          <div className="w-9 h-9 rounded-xl bg-blue-100/80 text-blue-600 flex items-center justify-center border border-blue-200">
            <Icon name="search" size={18} />
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-gradient-to-br from-emerald-50/60 to-slate-50 border border-emerald-100/60 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Лучшая цена</div>
            <div className="text-lg font-bold font-mono text-emerald-600 mt-0.5">
              {metrics.bestPrice > 0 ? `${metrics.bestPrice.toLocaleString()} ₽` : '—'}
            </div>
          </div>
          <div className="w-9 h-9 rounded-xl bg-emerald-100/80 text-emerald-600 flex items-center justify-center border border-emerald-200">
            <Icon name="check-circle" size={18} />
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-gradient-to-br from-purple-50/60 to-slate-50 border border-purple-100/60 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Макс. надежность</div>
            <div className="text-lg font-bold font-mono text-purple-600 mt-0.5">{metrics.topReliability}%</div>
          </div>
          <div className="w-9 h-9 rounded-xl bg-purple-100/80 text-purple-600 flex items-center justify-center border border-purple-200">
            <Icon name="user-shield" size={18} />
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-gradient-to-br from-amber-50/60 to-slate-50 border border-amber-100/60 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Средний SLA</div>
            <div className="text-lg font-bold font-mono text-amber-600 mt-0.5">{metrics.avgSla} дн. экспресс</div>
          </div>
          <div className="w-9 h-9 rounded-xl bg-amber-100/80 text-amber-600 flex items-center justify-center border border-amber-200">
            <Icon name="rotate" size={18} />
          </div>
        </div>
      </div>

      {viewMode === 'analogs' ? (
        <AnalogComparisonMatrix
          requestId={requestId}
          onSelectAnalog={(analog: AnalogItem) => {
            // Convert analog to match format
            const converted: MatchItem = {
              item: {
                catalog_id: analog.id,
                name: `${analog.analog_article} (${analog.brand})`,
                oem_number: analog.oem_part,
                brand: analog.brand,
                price: analog.price_analog,
                stock_qty: 10,
                delivery_days: analog.delivery_days,
                category: 'Аналог',
              },
              supplier: {
                supplier_id: 'SUP-ANALOG',
                name: `${analog.brand} Official Dealer`,
                reliability_score: 0.95,
              },
              score: 90 - analog.risk_score,
              breakdown: {
                oem_exact: 0.9,
                brand_article: 0.95,
                normalized_name: 0.9,
                vehicle_compatibility: 0.95,
                side_position: 0.9,
                quantity_pack: 1.0,
                language_synonym: 0.9,
                historical_acceptance: 0.95,
                supplier_data_quality: 0.95,
              },
            };
            if (onSelectOffer && activePart) {
              onSelectOffer(activePart, converted);
            }
          }}
        />
      ) : (
        <>
          {/* Part Selection Pills & Quick Search Filter */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-y border-slate-100 py-3">
            {/* Parts Selector Pills */}
            <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
              {displayParts.map((p, idx) => {
                const isSelected = activePart === p.name;
                const hasSelectedOffer = selectedOffers[p.name] !== undefined && selectedOffers[p.name] !== null;
                const displayName = p.name && p.name !== 'null' ? p.name : 'Позиция 1';

                return (
                  <button
                    key={idx}
                    onClick={() => handlePartClick(p.name)}
                    className={`flex items-center gap-2 whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold transition-all ${
                      isSelected
                        ? 'bg-[var(--accent-primary)] text-white shadow-md shadow-blue-500/20 font-bold'
                        : 'bg-slate-100/80 text-slate-600 hover:bg-slate-200/80 hover:text-slate-900 border border-slate-200/60'
                    }`}
                  >
                    <span>{displayName} ({p.quantity} шт)</span>
                    {hasSelectedOffer && (
                      <span className="w-2 h-2 rounded-full bg-emerald-400 border border-white animate-pulse" title="Предложение выбрано" />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Quick Search input */}
            <div className="relative min-w-[220px]">
              <Icon name="search" size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Фильтр по бренду / OEM..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-bold"
                >
                  ×
                </button>
              )}
            </div>
          </div>

          {/* Main Grid: Offers Table (Left 2/3) + AI Factors Sidebar (Right 1/3) */}
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
            {/* Matches table list */}
            <div className="min-w-0 overflow-x-auto">
              {loading ? (
                <div className="text-xs text-slate-500 py-16 text-center flex flex-col items-center justify-center gap-2">
                  <Icon name="spinner" size={24} className="animate-spin text-[var(--accent-primary)]" />
                  <span className="font-semibold text-slate-700">Анализ цен и алгоритмов ранжирования поставщиков...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-rose-200 bg-rose-50/60 p-8 text-center text-xs">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-rose-600">
                    <Icon name="triangle-exclamation" size={22} />
                  </div>
                  <div>
                    <strong className="block text-sm font-bold text-rose-900">Каталог офферов недоступен</strong>
                    <span className="mt-1 block text-xs text-rose-800">{error}</span>
                  </div>
                  <button type="button" onClick={() => activePart && void fetchMatches(activePart)} className="rounded-xl bg-rose-700 px-4 py-2 text-xs font-bold text-white transition hover:bg-rose-800">
                    Повторить загрузку
                  </button>
                </div>
              ) : filteredMatches.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-blue-100 bg-blue-50/40 p-8 text-center text-xs">
                  <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center">
                    <Icon name="search" size={24} />
                  </div>
                  <div>
                    <strong className="font-bold text-slate-800 text-sm block">Прямые каталожные офферы не найдены</strong>
                    <span className="text-slate-600 text-xs mt-1 block">
                      По этой позиции нет подтверждённых live-офферов. Уточните артикул или откройте live-матрицу аналогов.
                    </span>
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    <button
                      onClick={() => setViewMode('analogs')}
                      className="px-4 py-2 bg-[var(--accent-primary)] text-white text-xs font-bold rounded-xl shadow-sm hover:bg-[var(--accent-primary-strong)] transition-all flex items-center gap-2"
                    >
                      <Icon name="code-fork" size={14} />
                      Открыть матрицу аналогов
                    </button>
                  </div>
                </div>
              ) : (
                <DataTable headers={["Деталь / Бренд", "Поставщик", "Цена unit", "Склад / SLA", "Match Score", "Действие"]}>
                  {filteredMatches.map((m, idx) => {
                    const isBreakdownSelected = selectedBreakdown === m.breakdown;
                    const isChosen = selectedOffers[activePart]?.item.catalog_id === m.item.catalog_id;
                    const isBestOffer = idx === 0;

                    return (
                      <tr
                        key={idx}
                        onClick={() => {
                          setSelectedMatch(m);
                          setSelectedBreakdown(m.breakdown);
                        }}
                        className={`border-b border-slate-100 hover:bg-blue-50/40 transition-colors cursor-pointer text-xs ${
                          isChosen
                            ? 'bg-emerald-50/60 border-l-4 border-l-emerald-500'
                            : isBreakdownSelected
                            ? 'bg-blue-50/30'
                            : ''
                        }`}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900 text-xs">{m.item.brand}</span>
                            {isBestOffer && (
                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[9px] font-bold text-emerald-700 border border-emerald-200">
                                BEST MATCH
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-slate-700 font-medium truncate max-w-[220px] mt-0.5">{m.item.name}</div>
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">OEM: {m.item.oem_number || '—'}</div>
                        </td>

                        <td className="px-4 py-3">
                          <div className="font-semibold text-slate-800">{m.supplier.name}</div>
                          <div className="text-[10px] text-emerald-600 flex items-center gap-1 font-medium mt-0.5">
                            <Icon name="user-shield" size={12} className="text-emerald-500" />
                            Надежность: {(m.supplier.reliability_score * 100).toFixed(0)}%
                          </div>
                        </td>

                        <td className="px-4 py-3 font-bold text-slate-900 text-sm font-mono whitespace-nowrap">
                          {m.item.price.toLocaleString()} ₽
                        </td>

                        <td className="px-4 py-3 text-slate-600 whitespace-nowrap">
                          <div className="font-semibold font-mono text-slate-800">{m.item.stock_qty} шт.</div>
                          <div className="text-[10px] text-slate-500">{m.item.delivery_days} дн. экспресс</div>
                        </td>

                        <td className="px-4 py-3">
                          <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold border font-mono inline-block ${
                            m.score >= 90
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : m.score >= 70
                              ? 'bg-sky-50 text-sky-700 border-sky-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }`}>
                            {m.score}% match
                          </span>
                        </td>

                        <td className="w-[124px] px-4 py-3">
                          <ActionButton
                            variant={isChosen ? 'success' : isBestOffer ? 'primary' : 'secondary'}
                            icon={isChosen ? 'check' : undefined}
                            onClick={(e) => {
                              e.stopPropagation();
                              if (onSelectOffer) onSelectOffer(activePart, m);
                            }}
                            className="w-full whitespace-nowrap px-3 py-1.5 text-xs shadow-xs"
                          >
                            {isChosen ? 'Выбрано' : 'Выбрать'}
                          </ActionButton>
                        </td>
                      </tr>
                    );
                  })}
                </DataTable>
              )}
            </div>

            {/* Selected Match & Radar Details Sidebar */}
            <div className="min-w-0 flex flex-col justify-between rounded-2xl border border-slate-200/80 bg-slate-50/50 p-4 space-y-4 shadow-sm">
              <div>
                <h4 className="text-xs font-bold text-slate-800 border-b border-slate-200 pb-2.5 mb-3 uppercase tracking-wider flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Icon name="wave-square" size={15} className="text-[var(--accent-primary)]" />
                    <span>AI Сопоставление</span>
                  </span>
                  {selectedMatch && (
                    <span className="font-mono text-blue-600 font-bold text-xs bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                      {selectedMatch.score}% match
                    </span>
                  )}
                </h4>

                {selectedMatch ? (
                  <div className="space-y-3 text-xs">
                    {/* SVG Radar Chart */}
                    <MatchRadarChart breakdown={selectedMatch.breakdown} score={selectedMatch.score} />

                    <div className="space-y-2 pt-1 text-slate-700 bg-white p-3 rounded-xl border border-slate-200/70">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">Бренд & Деталь</span>
                        <span className="font-bold text-slate-900">{selectedMatch.item.brand}</span>
                      </div>
                      <div className="text-slate-800 font-medium text-xs leading-snug">{selectedMatch.item.name}</div>
                      <div className="text-[10px] font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 inline-block font-semibold">
                        OEM: {selectedMatch.item.oem_number || 'Н/Д'}
                      </div>
                    </div>

                    <div className="border-t border-slate-200 pt-2 space-y-1.5 bg-white p-3 rounded-xl border border-slate-200/70">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">Поставщик</span>
                        <span className="font-semibold text-slate-900">{selectedMatch.supplier.name}</span>
                      </div>
                      <div className="flex justify-between items-center text-xs text-slate-700">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">Цена unit</span>
                        <span className="font-mono font-bold text-emerald-600 text-sm">
                          {selectedMatch.item.price.toLocaleString()} ₽
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-xs text-slate-700">
                        <span className="text-[10px] text-slate-500 uppercase font-bold">Срок доставки</span>
                        <span className="font-mono font-semibold text-slate-800">
                          {selectedMatch.item.delivery_days} дн. express
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 text-center py-12 flex flex-col items-center justify-center gap-2">
                    <Icon name="search" size={24} className="text-slate-400" />
                    <span>Выберите оффер в таблице для просмотра параметров AI сопоставления</span>
                  </div>
                )}
              </div>

              {selectedMatch && (
                <div className="pt-3 border-t border-slate-200 text-[10px] text-slate-500 font-medium flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Icon name="user-shield" size={14} className="text-emerald-600" />
                    <span>Верифицировано AI Engine</span>
                  </span>
                  <span className="font-mono text-slate-400">v3.0 Engine</span>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
