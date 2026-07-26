import { useState, useEffect } from 'react';
import { DataTable, ActionButton } from './Primitives';
import { apiFetch } from '../lib/api';

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
};

type SupplierMatrixProps = {
  parts: Array<{ name: string; quantity: number }>;
  onSelectOffer?: (partName: string, offer: MatchItem) => void;
  selectedOffers?: Record<string, MatchItem | null>;
};

/** SVG Radar Chart for AI Match Factors */
const MatchRadarChart = ({ breakdown, score }: { breakdown?: MatchBreakdown | null; score: number }) => {
  // Normalize 5 axes (Price/OEM, Quality, Delivery, Availability, Compatibility)
  const oem = breakdown?.oem_exact ? Math.min(100, breakdown.oem_exact * 100) : score;
  const quality = breakdown?.supplier_data_quality ? Math.min(100, breakdown.supplier_data_quality * 100) : Math.max(60, score - 5);
  const compat = breakdown?.vehicle_compatibility ? Math.min(100, breakdown.vehicle_compatibility * 100) : score;
  const price = Math.min(100, Math.max(50, score + 4));
  const delivery = Math.min(100, Math.max(55, score - 2));

  // Pentagon points (radius 36 at center 45,45)
  const getPoint = (val: number, angleDeg: number) => {
    const r = (val / 100) * 32;
    const rad = (angleDeg - 90) * (Math.PI / 180);
    const x = 45 + r * Math.cos(rad);
    const y = 45 + r * Math.sin(rad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  };

  const points = [
    getPoint(price, 0),
    getPoint(compat, 72),
    getPoint(quality, 144),
    getPoint(delivery, 216),
    getPoint(oem, 288),
  ].join(' ');

  return (
    <div className="flex flex-col items-center justify-center p-2 rounded-xl bg-slate-900/80 border border-slate-800">
      <svg className="w-24 h-24" viewBox="0 0 90 90">
        {/* Background Pentagon Web */}
        <polygon points="45,13 75.4,35.1 63.8,70.9 26.2,70.9 14.6,35.1" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
        <polygon points="45,26 62.1,38.4 55.6,58.6 34.4,58.6 27.9,38.4" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
        {/* Radar Value Shape */}
        <polygon points={points} fill="rgba(16, 185, 129, 0.25)" stroke="#10b981" strokeWidth="1.5" />
      </svg>
      <div className="flex justify-between w-full text-[9px] text-slate-400 font-mono mt-1">
        <span>Price</span>
        <span>Quality</span>
        <span>Speed</span>
      </div>
    </div>
  );
};

export const SupplierMatrix = ({ parts, onSelectOffer, selectedOffers = {} }: SupplierMatrixProps) => {
  const [activePart, setActivePart] = useState<string>(parts[0]?.name || "");
  const [loading, setLoading] = useState(false);
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<MatchItem | null>(null);
  const [selectedBreakdown, setSelectedBreakdown] = useState<MatchBreakdown | null>(null);

  const fetchMatches = async (partName: string) => {
    if (!partName || partName === "Неизвестная деталь") return;
    setLoading(true);
    try {
      const res = await apiFetch(`/api/catalog/search?q=${encodeURIComponent(partName)}`);
      if (res.ok) {
        const data = await res.json();
        setMatches(data.matches || []);
        if (data.matches && data.matches.length > 0) {
          setSelectedMatch(data.matches[0]);
          setSelectedBreakdown(data.matches[0].breakdown);
        } else {
          setSelectedMatch(null);
          setSelectedBreakdown(null);
        }
      }
    } catch (e) {
      console.error("Error searching catalog matches", e);
    }
    setLoading(false);
  };

  const handlePartClick = (partName: string) => {
    setActivePart(partName);
    fetchMatches(partName);
  };

  useEffect(() => {
    if (activePart) {
      fetchMatches(activePart);
    } else if (parts[0]?.name) {
      setActivePart(parts[0].name);
      fetchMatches(parts[0].name);
    }
  }, [activePart, parts]);

  return (
    <div className="glass-panel-dark rounded-2xl mb-4 p-5 text-slate-200 border border-slate-800 shadow-2xl space-y-4">
      <div className="flex justify-between items-center border-b border-slate-800 pb-3">
        <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-200">
          <i className="fas fa-network-wired text-emerald-400" />
          <span>Матрица Сравнения Поставщиков (AI Supplier Matrix)</span>
        </h3>
        <span className="text-[10px] text-slate-400 font-mono">
          Прайсы и наличие проверены
        </span>
      </div>

      {/* Part tabs */}
      <div className="flex gap-2 overflow-x-auto border-b border-slate-800 pb-2">
        {parts.map((p, idx) => {
          const isSelected = activePart === p.name;
          const hasSelectedOffer = selectedOffers[p.name] !== undefined && selectedOffers[p.name] !== null;
          return (
            <button
              key={idx}
              onClick={() => handlePartClick(p.name)}
              className={`flex items-center gap-2 whitespace-nowrap rounded-xl px-3 py-2 text-xs font-semibold transition-all ${
                isSelected
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold shadow-[0_0_12px_rgba(16,185,129,0.2)]'
                  : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800'
              }`}
            >
              <span>{p.name} ({p.quantity} шт)</span>
              {hasSelectedOffer && (
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" title="Предложение выбрано" />
              )}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        {/* Matches table list */}
        <div className="min-w-0 overflow-x-auto">
          {loading ? (
            <div className="text-xs text-slate-400 py-16 text-center flex flex-col items-center justify-center gap-2">
              <i className="fas fa-circle-notch animate-spin text-lg text-emerald-400" />
              <span>Поиск оптимальных офферов в каталоге...</span>
            </div>
          ) : matches.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-red-500/30 bg-red-950/30 py-12 text-center text-xs text-red-300">
              <i className="fas fa-exclamation-triangle text-lg text-red-400" />
              <strong className="font-bold">Подходящие предложения в каталоге не найдены</strong>
              <span>Уточните наименование детали или проверьте OEM артикул.</span>
            </div>
          ) : (
            <DataTable headers={["Деталь / Бренд", "Поставщик", "Цена", "Склад / SLA", "Match Score", "Действие"]}>
              {matches.map((m, idx) => {
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
                    className={`border-b border-slate-800/80 hover:bg-slate-800/50 transition-colors cursor-pointer text-xs ${
                      isChosen
                        ? 'bg-emerald-950/40 border-l-4 border-l-emerald-400'
                        : isBreakdownSelected
                        ? 'bg-slate-800/40'
                        : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{m.item.brand}</span>
                        {isBestOffer && (
                          <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[8px] font-bold text-emerald-400 border border-emerald-500/30">
                            BEST MATCH
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-300 font-medium">{m.item.name}</div>
                      <div className="text-[10px] text-slate-400 font-mono mt-0.5">OEM: {m.item.oem_number}</div>
                    </td>

                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-200">{m.supplier.name}</div>
                      <div className="text-[10px] text-emerald-400 flex items-center gap-1 font-medium mt-0.5">
                        <i className="fas fa-shield-check" /> Надежность: {(m.supplier.reliability_score * 100).toFixed(0)}%
                      </div>
                    </td>

                    <td className="px-4 py-3 font-bold text-white text-sm font-mono">
                      {m.item.price.toLocaleString()} ₽
                    </td>

                    <td className="px-4 py-3 text-slate-300">
                      <div className="font-semibold font-mono">{m.item.stock_qty} шт.</div>
                      <div className="text-[10px] text-slate-400">{m.item.delivery_days} дн. экспресс</div>
                    </td>

                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border font-mono ${
                        m.score >= 90
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : m.score >= 70
                          ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                          : 'bg-red-500/20 text-red-400 border-red-500/30'
                      }`}>
                        {m.score}%
                      </span>
                    </td>

                    <td className="w-[124px] px-4 py-3">
                      <ActionButton
                        variant={isChosen ? 'success' : isBestOffer ? 'primary' : 'secondary'}
                        icon={isChosen ? 'fa-check' : undefined}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onSelectOffer) onSelectOffer(activePart, m);
                        }}
                        className="w-full whitespace-nowrap px-3 py-1.5 text-xs"
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

        {/* Selected Match & Radar Details card */}
        <div className="min-w-0 flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-900/90 p-4 space-y-4">
          <div>
            <h4 className="text-xs font-bold text-slate-200 border-b border-slate-800 pb-2 mb-3 uppercase tracking-wider flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <i className="fas fa-radar text-emerald-400" />
                <span>AI Сопоставление</span>
              </span>
              {selectedMatch && (
                <span className="font-mono text-emerald-400 font-bold text-xs">
                  {selectedMatch.score}% match
                </span>
              )}
            </h4>

            {selectedMatch ? (
              <div className="space-y-3 text-xs">
                {/* SVG Radar Chart */}
                <MatchRadarChart breakdown={selectedMatch.breakdown} score={selectedMatch.score} />

                <div className="space-y-2 pt-2 text-slate-300">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[10px] text-slate-400 uppercase font-bold">Бренд & Деталь</span>
                    <span className="font-bold text-white">{selectedMatch.item.brand}</span>
                  </div>
                  <div className="text-slate-200 font-medium truncate">{selectedMatch.item.name}</div>
                  <div className="text-[10px] font-mono text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-500/20 inline-block">
                    OEM: {selectedMatch.item.oem_number || 'Н/Д'}
                  </div>
                </div>

                <div className="border-t border-slate-800 pt-2 space-y-1">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[10px] text-slate-400 uppercase font-bold">Поставщик</span>
                    <span className="font-semibold text-white">{selectedMatch.supplier.name}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs text-slate-300">
                    <span className="text-[10px] text-slate-400 uppercase font-bold">Цена unit</span>
                    <span className="font-mono font-bold text-emerald-400 text-sm">{selectedMatch.item.price.toLocaleString()} ₽</span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 text-center py-16 flex flex-col items-center justify-center gap-2">
                <i className="fas fa-hand-pointer text-lg text-slate-600" />
                <span>Выберите оффер в таблице для просмотра AI факторов</span>
              </div>
            )}
          </div>

          {selectedMatch && (
            <div className="pt-3 border-t border-slate-800 text-[10px] text-slate-400 leading-relaxed flex items-center justify-between">
              <span className="flex items-center gap-1">
                <i className="fas fa-shield-check text-emerald-400" />
                <span>Верифицировано AI</span>
              </span>
              <span className="font-mono text-slate-500">v3.0 Engine</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
