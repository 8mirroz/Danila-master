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

  // Fetch initial matches on mount or when activePart/parts change
  useEffect(() => {
    if (activePart) {
      fetchMatches(activePart);
    } else if (parts[0]?.name) {
      setActivePart(parts[0].name);
      fetchMatches(parts[0].name);
    }
  }, [activePart, parts]);

  return (
    <div className="panel-card-tight mb-4 p-5">
      <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-[var(--text-secondary)]">
        <i className="fas fa-th text-[var(--accent-primary)]"></i> Матрица подбора предложений поставщиков
      </h3>

      {/* Part tabs */}
      <div className="mb-4 flex gap-2 overflow-x-auto border-b border-[var(--border-default)]">
        {parts.map((p, idx) => {
          const isSelected = activePart === p.name;
          const hasSelectedOffer = selectedOffers[p.name] !== undefined && selectedOffers[p.name] !== null;
          return (
            <button
              key={idx}
              onClick={() => handlePartClick(p.name)}
              className={`mr-2 flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-xs font-semibold transition-all ${
                isSelected
                  ? 'border-[var(--accent-primary)] text-[var(--accent-primary)] font-bold'
                  : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
            >
              {p.name} ({p.quantity} шт)
              {hasSelectedOffer && (
                <span className="w-2 h-2 rounded-full bg-green-500" title="Предложение выбрано"></span>
              )}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        {/* Matches table list */}
        <div className="min-w-0 overflow-x-auto">
          {loading ? (
            <div className="text-xs text-[var(--text-secondary)] py-12 text-center flex flex-col items-center justify-center gap-2">
              <i className="fas fa-spinner animate-spin text-lg text-[var(--accent-primary)]"></i>
              <span>Поиск предложений в каталоге...</span>
            </div>
          ) : matches.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-1.5 rounded-[18px] border border-red-200 bg-red-50 py-10 text-center text-xs text-red-700">
              <i className="fas fa-exclamation-circle text-base"></i>
              <strong className="font-bold">Не найдено подходящих предложений в каталоге.</strong>
              <span>Проверьте правильность написания названия детали.</span>
            </div>
          ) : (
            <DataTable headers={["Деталь и Бренд", "Поставщик", "Цена", "Наличие и Срок", "Совпадение", "Действие"]}>
              {matches.map((m, idx) => {
                const isBreakdownSelected = selectedBreakdown === m.breakdown;
                const isChosen = selectedOffers[activePart]?.item.catalog_id === m.item.catalog_id;
                return (
                  <tr
                    key={idx}
                    onClick={() => {
                      setSelectedMatch(m);
                      setSelectedBreakdown(m.breakdown);
                    }}
                    className={`border-b border-[var(--border-subtle)] hover:bg-[var(--surface-2)] transition-colors cursor-pointer text-xs ${
                      isBreakdownSelected ? 'bg-[var(--state-selected)]' : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="font-bold text-[var(--text-primary)]">{m.item.brand}</div>
                      <div className="text-[11px] text-[var(--text-secondary)] font-medium leading-tight">{m.item.name}</div>
                      <div className="text-[10px] text-[var(--text-muted)] font-mono mt-0.5">OEM: {m.item.oem_number}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-[var(--text-primary)]">{m.supplier.name}</div>
                      <div className="text-[10px] text-green-700 flex items-center gap-1 font-medium">
                        <i className="fas fa-circle-check"></i> Надежность: {m.supplier.reliability_score.toFixed(2)}
                      </div>
                    </td>
                    <td className="px-4 py-3 font-bold text-[var(--text-primary)] text-sm">
                      {m.item.price.toLocaleString()} ₽
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">
                      <div className="font-semibold">{m.item.stock_qty} шт.</div>
                      <div className="text-[11px] text-[var(--text-muted)]">{m.item.delivery_days} дн. доставки</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border inline-block ${
                        m.score >= 90
                          ? 'bg-green-50 text-green-700 border-green-200'
                          : m.score >= 70
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-red-50 text-red-700 border-red-200'
                      }`}>
                        {m.score}%
                      </span>
                    </td>
                    <td className="w-[124px] px-4 py-3">
                      <ActionButton
                        variant={isChosen ? 'success' : 'secondary'}
                        icon={isChosen ? 'fa-check' : undefined}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onSelectOffer) onSelectOffer(activePart, m);
                        }}
                        className="w-full whitespace-nowrap px-3 py-2"
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
        {/* Simplified Match Info card */}
        <div className="min-w-0 flex flex-col justify-between rounded-[20px] border border-[var(--border-default)] bg-[var(--surface-2)] p-4">
          <div>
            <h4 className="text-xs font-bold text-[var(--text-primary)] border-b border-[var(--border-default)] pb-2 mb-4 uppercase tracking-wider flex items-center gap-1.5">
              <i className="fas fa-info-circle text-[var(--accent-primary)]"></i> Детали соответствия
            </h4>

            {selectedMatch ? (
              <div className="space-y-4 text-xs">
                <div>
                  <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase block">Бренд & Артикул</span>
                  <div className="font-bold text-[var(--text-primary)] mt-0.5">{selectedMatch.item.brand}</div>
                  <div className="text-[var(--text-secondary)] mt-0.5">{selectedMatch.item.name}</div>
                  <div className="text-[10px] text-[var(--text-muted)] font-mono mt-1 bg-[var(--surface-3)] px-1.5 py-0.5 rounded inline-block">OEM: {selectedMatch.item.oem_number || 'Н/Д'}</div>
                </div>

                <div>
                  <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase block">Поставщик</span>
                  <div className="font-semibold text-[var(--text-primary)] mt-0.5">{selectedMatch.supplier.name}</div>
                  <div className="text-[11px] text-green-700 flex items-center gap-1 mt-0.5">
                    <i className="fas fa-shield-halved"></i> Рейтинг надежности: {selectedMatch.supplier.reliability_score.toFixed(2)}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase block">Наличие и Срок</span>
                  <div className="font-semibold text-[var(--text-primary)] mt-0.5">На складе: {selectedMatch.item.stock_qty} шт.</div>
                  <div className="text-[11px] text-[var(--text-secondary)] mt-0.5">Срок доставки: {selectedMatch.item.delivery_days} дн.</div>
                </div>

                <div className="border-t border-[var(--border-subtle)] pt-3">
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase">Оценка совпадения</span>
                    <span className="font-bold text-xs text-[var(--accent-primary)]">{selectedMatch.score}%</span>
                  </div>
                  <div className="w-full bg-[var(--surface-4)] rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${
                        selectedMatch.score >= 90 
                          ? 'bg-green-500' 
                          : selectedMatch.score >= 70 
                          ? 'bg-amber-500' 
                          : 'bg-red-500'
                      }`}
                      style={{ width: `${selectedMatch.score}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-xs text-[var(--text-muted)] text-center py-16 flex flex-col items-center justify-center gap-2">
                <i className="fas fa-arrow-pointer text-lg text-[var(--text-muted)]"></i>
                <span>Выберите предложение из таблицы для просмотра деталей соответствия.</span>
              </div>
            )}
          </div>

          {selectedMatch && (
            <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] text-[10px] text-[var(--text-muted)] leading-relaxed">
              <i className="fas fa-circle-info mr-1"></i>
              Оценка рассчитана алгоритмом сопоставления на основе OEM-кода, бренда и категории запчасти.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
