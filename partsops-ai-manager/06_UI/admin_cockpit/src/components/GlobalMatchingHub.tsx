import React, { useState, useMemo } from 'react';
import { SectionCard, Icon } from './Primitives';
import { type RequestItem } from '../lib/types';
import { apiFetch } from '../lib/api';

type GlobalMatchingHubProps = {
  requests: RequestItem[];
  onSelectRequest: (req: RequestItem) => void;
  onSimulatePrice?: (price: number) => void;
};

type MatchBreakdown = {
  // Legacy fields
  oem_exact?: number;
  brand_article?: number;
  normalized_name?: number;
  vehicle_compatibility?: number;
  side_position?: number;
  quantity_pack?: number;
  language_synonym?: number;
  historical_acceptance?: number;
  supplier_data_quality?: number;

  // Real backend fields
  oem_score?: number;
  brand_score?: number;
  text_score?: number;
  vehicle_score?: number;
  position_score?: number;
  supplier_score?: number;
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

export const GlobalMatchingHub: React.FC<GlobalMatchingHubProps> = ({
  requests,
  onSelectRequest,
  onSimulatePrice,
}) => {
  const [searchOem, setSearchOem] = useState('');
  const [selectedReqId, setSelectedReqId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<MatchItem[]>([]);
  const [hoveredScoreIdx, setHoveredScoreIdx] = useState<number | null>(null);

  const [searchHistory, setSearchHistory] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('partsops_search_history');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const addToHistory = (q: string) => {
    const trimmed = q.trim();
    if (!trimmed || trimmed.length < 2) return;
    setSearchHistory((prev) => {
      const filtered = prev.filter((item) => item.toLowerCase() !== trimmed.toLowerCase());
      const next = [trimmed, ...filtered].slice(0, 6);
      localStorage.setItem('partsops_search_history', JSON.stringify(next));
      return next;
    });
  };

  const clearHistory = () => {
    setSearchHistory([]);
    localStorage.removeItem('partsops_search_history');
  };

  const performSearch = async (query: string) => {
    const q = query.trim();
    if (!q) {
      setSearchResults([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      addToHistory(q);
      const res = await apiFetch(`/api/catalog/search?q=${encodeURIComponent(q)}`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(Array.isArray(data.matches) ? data.matches : []);
      } else {
        setSearchResults([]);
        const detail = await res.json().catch(() => null);
        setError(typeof detail?.detail === 'string' ? detail.detail : `Ошибка ${res.status}`);
      }
    } catch (e) {
      setSearchResults([]);
      setError(e instanceof Error ? e.message : 'Не удалось выполнить поиск');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      void performSearch(searchOem);
    }
  };

  const activeRequests = useMemo(() => {
    return requests.filter((r) => !['CLOSED', 'CANCELLED', 'FAILED'].includes(r.status));
  }, [requests]);

  const handleSelectReqChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setSelectedReqId(id);
    if (id) {
      const match = requests.find((r) => r.request_id === id);
      if (match) onSelectRequest(match);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Banner Header */}
      <div className="rounded-3xl border border-slate-700/50 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 p-6 text-white shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-blue-500/20 text-blue-300 border border-blue-500/30">
                <Icon name="rotate" size={12} /> Автономный режим поиска
              </span>
              <span className="text-[10px] text-slate-400 font-mono">Global OEM Cross-Matching Engine v2.4</span>
            </div>
            <h2 className="text-xl font-black tracking-tight">
              Матрица подбора аналогов и кросс-кодов
            </h2>
            <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">
              Мгновенный подбор кросс-номеров, сравнение цен поставщиков и оценка рисков качества. Вы можете искать детали напрямую по артикулу OEM или выбрать запрос из рабочей очереди.
            </p>
          </div>

          {/* Quick Request Selector */}
          <div className="flex items-center gap-3 bg-white/10 p-3 rounded-2xl border border-white/15 backdrop-blur-md">
            <div className="text-right shrink-0 hidden sm:block">
              <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-300">Контекст заявки</div>
              <div className="text-xs font-bold text-white">Открыть в степпере</div>
            </div>
            <select
              value={selectedReqId}
              onChange={handleSelectReqChange}
              className="bg-slate-800 text-white text-xs font-semibold rounded-xl border border-slate-600 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
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

      {/* Control Filters & Search Bar */}
      <SectionCard title="Поисковый фильтр артикулов и аналогов" icon="search">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="relative flex-1 min-w-[260px]">
            <input
              type="text"
              value={searchOem}
              onChange={(e) => setSearchOem(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Введите артикул OEM (напр. 34116852253), бренд (BOSCH) или номер кросса..."
              className="w-full pl-10 pr-24 py-2.5 bg-white border border-slate-300 rounded-xl text-xs font-semibold text-slate-800 placeholder-slate-400 focus:outline-none focus:border-[#0F172A] focus:ring-1 focus:ring-[#0F172A] transition-all shadow-sm"
            />
            <div className="absolute left-3 top-3 text-[var(--text-muted)]">
              <Icon name="search" size={14} />
            </div>
            <div className="absolute right-2 top-1.5 flex items-center gap-1">
              <button
                onClick={() => performSearch(searchOem)}
                className="px-3 py-1 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-lg text-[10px] font-bold shadow-xs transition"
              >
                Найти
              </button>
            </div>
            {searchOem && (
              <button
                onClick={() => {
                  setSearchOem('');
                  setSearchResults([]);
                }}
                className="absolute right-16 top-2.5 text-xs text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            )}
          </div>

          {/* Quick OEM Chip Buttons */}
          <div className="flex items-center gap-1.5 overflow-x-auto py-1 max-w-full">
            <span className="text-[10px] font-bold text-slate-400 uppercase mr-1 whitespace-nowrap">
              {searchHistory.length > 0 ? 'История:' : 'Быстрый выбор:'}
            </span>
            {(searchHistory.length > 0 ? searchHistory : ['34116852253', '04465-33470', '13717582310']).map((chip) => (
              <button
                key={chip}
                onClick={() => {
                  setSearchOem(chip);
                  void performSearch(chip);
                }}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-mono font-bold transition-all border whitespace-nowrap ${
                  searchOem === chip
                    ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-blue-50 hover:text-blue-700'
                }`}
              >
                {chip}
              </button>
            ))}
            {searchHistory.length > 0 && (
              <button
                onClick={clearHistory}
                className="px-2 py-1 text-[10px] text-slate-400 hover:text-rose-600 font-bold transition-colors ml-2 whitespace-nowrap"
                title="Очистить историю поиска"
              >
                Очистить ✕
              </button>
            )}
          </div>
        </div>
      </SectionCard>

      {/* Results Table */}
      <SectionCard
        title={`Результаты поиска кроссов (${searchResults.length} поз.)`}
        icon="list"
        headerActions={
          <span className="text-[10px] font-mono font-bold text-slate-500 bg-slate-100 px-2 py-1 rounded border border-slate-200">
            Прямое сопоставление база данных + API
          </span>
        }
      >
        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-slate-500">
            <Icon name="spinner" size={32} className="animate-spin mb-4 text-blue-600" />
            <p className="text-xs font-bold text-slate-700">Ищем аналоги и предложения поставщиков...</p>
          </div>
        ) : error ? (
          <div className="py-12 flex flex-col items-center justify-center text-rose-500">
            <Icon name="warning" size={32} className="mb-4 text-rose-500" />
            <p className="text-xs font-bold text-slate-700">Ошибка поиска</p>
            <p className="text-[11px] text-slate-500 mt-1">{error}</p>
          </div>
        ) : searchResults.length === 0 ? (
          !searchOem ? (
            <div className="py-12 px-6 max-w-2xl mx-auto text-center space-y-6">
              <div className="w-16 h-16 rounded-3xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mx-auto text-indigo-600">
                <Icon name="search" size={28} />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-800">Добро пожаловать в хаб подбора аналогов</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto leading-relaxed">
                  Введите OEM артикул детали, бренд или название в поисковую строку выше для быстрого поиска по каталогам поставщиков и симуляции цен.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
                <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl space-y-1">
                  <div className="flex items-center gap-2 text-indigo-600 font-bold text-xs">
                    <Icon name="rotate" size={12} />
                    <span>Умный кросс-метчинг</span>
                  </div>
                  <p className="text-[10px] text-slate-500 leading-normal">
                    6-компонентная формула подбора анализирует синонимы, совместимость моделей и расположение.
                  </p>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl space-y-1">
                  <div className="flex items-center gap-2 text-indigo-600 font-bold text-xs">
                    <Icon name="pencil" size={12} />
                    <span>Симуляция цен в 1 клик</span>
                  </div>
                  <p className="text-[10px] text-slate-500 leading-normal">
                    Переносите цены найденных аналогов напрямую в калькулятор прибыли и логистических затрат.
                  </p>
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={() => {
                    const demoOem = '34116852253';
                    setSearchOem(demoOem);
                    void performSearch(demoOem);
                  }}
                  className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-sm transition-all"
                >
                  Попробовать демо-поиск (34116852253)
                </button>
              </div>
            </div>
          ) : (
            <div className="py-10 text-center">
              <Icon name="circle-info" size={32} className="mx-auto text-slate-400 mb-2" />
              <p className="text-xs font-bold text-slate-700">
                По запросу «{searchOem}» аналоги не найдены
              </p>
              <p className="text-[11px] text-slate-500 mt-1">Попробуйте ввести только цифровую часть артикула OEM или выберите другой фильтр.</p>
            </div>
          )
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                  <th className="py-3 px-3">Артикул</th>
                  <th className="py-3 px-3">Наименование / Бренд</th>
                  <th className="py-3 px-3">Категория</th>
                  <th className="py-3 px-3">Поставщик</th>
                  <th className="py-3 px-3 text-right">Цена (₽)</th>
                  <th className="py-3 px-3 text-center">AI Оценка</th>
                  <th className="py-3 px-3 text-center">Срок (дн)</th>
                  <th className="py-3 px-3 text-center">Наличие</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {searchResults.map((match, idx) => {
                  const item = match.item;
                  return (
                    <tr key={`${item.catalog_id}-${idx}`} className="hover:bg-blue-50/40 transition-colors">
                      <td className="py-3 px-3 font-mono font-bold text-slate-900">
                        {item.oem_number}
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-bold text-slate-900 text-[11px] truncate max-w-[150px]" title={item.name}>{item.name}</div>
                        <div className="text-[10px] text-slate-500 font-semibold">{item.brand}</div>
                      </td>
                      <td className="py-3 px-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wide border ${
                          item.category === 'OES' ? 'bg-indigo-50 text-indigo-700 border-indigo-200' :
                          item.category === 'PREMIUM' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                          'bg-slate-100 text-slate-600 border-slate-300'
                        }`}>
                          {item.category}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-[11px] font-bold text-slate-700">{match.supplier?.name || 'Н/Д'}</span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <div className="font-mono font-black text-slate-900">
                          {item.price.toLocaleString()} ₽
                        </div>
                        {onSimulatePrice && (
                          <button
                            onClick={() => onSimulatePrice(item.price)}
                            className="text-[9px] text-indigo-600 hover:text-indigo-800 hover:underline font-bold block ml-auto mt-0.5 whitespace-nowrap"
                            title="Перенести цену в симулятор"
                          >
                            В симулятор →
                          </button>
                        )}
                      </td>
                      <td
                        className="py-3 px-3 text-center relative"
                        onMouseEnter={() => setHoveredScoreIdx(idx)}
                        onMouseLeave={() => setHoveredScoreIdx(null)}
                      >
                        <span className={`text-[10px] font-bold px-2 py-1 rounded border cursor-help ${
                          match.score >= 80 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                          match.score >= 50 ? 'bg-amber-50 text-amber-700 border-amber-200' :
                          'bg-rose-50 text-rose-700 border-rose-200'
                        }`}>
                          {Math.round(match.score)}%
                        </span>

                        {hoveredScoreIdx === idx && match.breakdown && (
                          <div className="absolute z-30 bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 bg-slate-900 text-white text-[11px] rounded-xl p-3 shadow-xl border border-slate-700 space-y-1.5 text-left">
                            <div className="font-bold border-b border-slate-700 pb-1 text-xs text-blue-300">Детализация AI оценки</div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">OEM совпадение (30%):</span>
                              <span className="font-mono font-bold">{(match.breakdown.oem_score ?? match.breakdown.oem_exact ?? 0)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">Совпадение бренда (20%):</span>
                              <span className="font-mono font-bold">{(match.breakdown.brand_score ?? match.breakdown.brand_article ?? 0)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">Текст / Синонимы (20%):</span>
                              <span className="font-mono font-bold">{(match.breakdown.text_score ?? match.breakdown.normalized_name ?? 0)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">Совместимость авто (15%):</span>
                              <span className="font-mono font-bold">{(match.breakdown.vehicle_score ?? match.breakdown.vehicle_compatibility ?? 0)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">Расположение / Сторона (10%):</span>
                              <span className="font-mono font-bold">{(match.breakdown.position_score ?? match.breakdown.side_position ?? 0)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-slate-400">Надёжность поставщика (5%):</span>
                              <span className="font-mono font-bold">{(match.breakdown.supplier_score ?? match.breakdown.supplier_data_quality ?? 0)}%</span>
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className="text-[11px] font-bold text-slate-700">{item.delivery_days}</span>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className="text-[11px] font-bold text-slate-700">{item.stock_qty} шт.</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
};
