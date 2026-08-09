import React from 'react';
import { Icon } from './Primitives';

type MatchBreakdown = {
  oem_exact: number;
  vehicle_compatibility: number;
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
  breakdown?: MatchBreakdown;
};

interface SmartMatchCardsProps {
  partName: string;
  matches: MatchItem[];
  selectedOffer?: MatchItem | null;
  onSelectOffer: (offer: MatchItem) => void;
}

export const SmartMatchCards: React.FC<SmartMatchCardsProps> = ({
  partName,
  matches,
  selectedOffer,
  onSelectOffer,
}) => {
  // Honesty: never invent offers. Empty API → empty state (no demo Brembo/Bosch/TRW rows).
  const effectiveMatches: MatchItem[] = matches && matches.length > 0 ? matches : [];

  if (effectiveMatches.length === 0) {
    return (
      <div className="space-y-3 mb-6">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold text-ink-primary">
            Рекомендации ИИ для позиции:{' '}
            <span className="text-accent-primary font-semibold">«{partName}»</span>
          </h4>
          <span className="text-[10px] text-ink-muted">Найдено 0 вариантов</span>
        </div>
        <div
          className="rounded-2xl border border-dashed border-line-strong bg-surface-2/60 px-4 py-6 text-center"
          role="status"
          aria-live="polite"
        >
          <p className="text-xs font-semibold text-ink-primary">Нет живых офферов по этой позиции</p>
          <p className="mt-1.5 text-[11px] leading-relaxed text-ink-secondary">
            Matching и краулер ещё не вернули варианты. Запустите подбор поставщиков или загрузите
            прайс — система не подставляет демо-цены.
          </p>
        </div>
      </div>
    );
  }

  const sortedByScore = [...effectiveMatches].sort((a, b) => b.score - a.score);
  const sortedBySpeed = [...effectiveMatches].sort(
    (a, b) => a.item.delivery_days - b.item.delivery_days,
  );
  const sortedByPrice = [...effectiveMatches].sort((a, b) => a.item.price - b.item.price);

  const topChoice = sortedByScore[0];
  const fastestChoice = sortedBySpeed[0];
  const budgetChoice = sortedByPrice[0];

  const cards = [
    {
      badge: '🏆 Топовый выбор ИИ',
      badgeTone: 'bg-emerald-500 text-white',
      borderTone: 'border-emerald-300 hover:border-emerald-500 bg-emerald-50/20',
      data: topChoice,
      desc: 'Максимальный рейтинг совпадения и надежность',
    },
    {
      badge: '⚡ Самый быстрый',
      badgeTone: 'bg-blue-600 text-white',
      borderTone: 'border-blue-300 hover:border-blue-500 bg-blue-50/20',
      data: fastestChoice,
      desc: 'Минимальный срок доставки клиенту',
    },
    {
      badge: '💵 Максимальная экономия',
      badgeTone: 'bg-amber-600 text-white',
      borderTone: 'border-amber-300 hover:border-amber-500 bg-amber-50/20',
      data: budgetChoice,
      desc: 'Лучшая цена для бюджета заказчика',
    },
  ].filter((c, idx, arr) => {
    // Deduplicate when the same offer wins multiple dimensions
    const firstIdx = arr.findIndex((x) => x.data.item.catalog_id === c.data.item.catalog_id);
    return firstIdx === idx;
  });

  return (
    <div className="space-y-3 mb-6">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold text-ink-primary">
          Рекомендации ИИ для позиции:{' '}
          <span className="text-accent-primary font-semibold">«{partName}»</span>
        </h4>
        <span className="text-[10px] text-ink-muted">Найдено {matches.length} вариантов</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {cards.map((c) => {
          const item = c.data.item;
          const supp = c.data.supplier;
          const isSelected = selectedOffer?.item.catalog_id === item.catalog_id;

          return (
            <div
              key={item.catalog_id}
              onClick={() => onSelectOffer(c.data)}
              className={`relative rounded-2xl border p-4 transition-all duration-200 cursor-pointer flex flex-col justify-between ${c.borderTone} ${
                isSelected
                  ? 'ring-2 ring-accent-primary border-accent-primary bg-surface-1 shadow-md'
                  : 'bg-surface-1'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${c.badgeTone}`}>
                    {c.badge}
                  </span>
                  <span className="font-mono text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                    {Math.round(c.data.score * 100)}% совпадение
                  </span>
                </div>

                <div className="font-bold text-sm text-ink-primary truncate mt-1">
                  {item.brand} {item.oem_number}
                </div>
                <div className="text-[11px] text-ink-secondary truncate">{item.name}</div>
                <div className="text-[10px] text-ink-muted mt-1">Поставщик: {supp.name}</div>
              </div>

              <div className="mt-4 pt-3 border-t border-line-subtle flex items-center justify-between">
                <div>
                  <div className="text-base font-extrabold text-ink-primary font-mono">
                    {item.price.toLocaleString('ru-RU')} ₽
                  </div>
                  <div className="text-[10px] text-ink-muted flex items-center gap-1">
                    <Icon name="clock" size={11} />
                    <span>Срок: {item.delivery_days} дн.</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectOffer(c.data);
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    isSelected
                      ? 'bg-emerald-600 text-white'
                      : 'bg-accent-primary text-white hover:bg-accent-strong active:scale-95'
                  }`}
                >
                  {isSelected ? '✓ Выбрано' : 'Выбрать'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SmartMatchCards;
