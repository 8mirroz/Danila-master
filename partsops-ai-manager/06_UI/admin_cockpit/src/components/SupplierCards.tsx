import React from 'react';
import type { SupplierRecord } from './supplierTypes';

interface SupplierCardsProps {
  suppliers: SupplierRecord[];
  selectedSupplierId: string | null;
  onSelectSupplier: (s: SupplierRecord | null) => void;
  onOpenTables: (supplier: SupplierRecord) => void;
  onEditSupplier: (supplier: SupplierRecord) => void;
  onArchiveSupplier: (supplier: SupplierRecord) => void;
}

export const SupplierCards: React.FC<SupplierCardsProps> = ({
  suppliers,
  selectedSupplierId,
  onSelectSupplier,
  onOpenTables,
  onEditSupplier,
  onArchiveSupplier,
}) => {
  const renderStars = (score: number) => {
    const starsCount = Math.round(score * 5);
    return (
      <div className="flex gap-0.5 text-amber-400">
        {[...Array(5)].map((_, i) => (
          <i
            key={i}
            className={`${i < starsCount ? 'fas' : 'far'} fa-star text-[10px]`}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {suppliers.map((s) => {
        const isSelected = selectedSupplierId === s.supplier_id;
        const activeStatus = s.status === 'active' ? 'Active' : s.status === 'blocked' ? 'Blocked' : 'Pending';

        return (
          <div
            key={s.supplier_id}
            onClick={() => onSelectSupplier(isSelected ? null : s)}
            className={`p-5 rounded-2xl cursor-pointer transition-all duration-300 flex flex-col justify-between h-[230px] border shadow-sm ${
              isSelected
                ? 'bg-emerald-50/40 ring-2 ring-[var(--accent-primary)] border-transparent scale-[1.02]'
                : 'bg-white/80 backdrop-blur-md border-[var(--border-default)] hover:shadow-md hover:-translate-y-1 hover:border-[var(--accent-primary)]/40'
            }`}
          >
            <div>
              {/* Header row: Status badge + Rating */}
              <div className="flex items-center justify-between mb-3">
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                    activeStatus === 'Active'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : activeStatus === 'Blocked'
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}
                >
                  {activeStatus}
                </span>
                <div className="flex items-center gap-1.5">
                  {renderStars(s.reliability_score)}
                  <span className="text-[10px] font-bold text-slate-500">
                    {(s.reliability_score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Title & City */}
              <h3 className="font-extrabold text-sm text-slate-800 line-clamp-1 mb-1">
                {s.name}
              </h3>
              <div className="text-[11px] text-slate-400 font-semibold flex items-center mb-3">
                <i className="fas fa-location-dot text-[10px] text-slate-400 mr-1.5" />
                {s.city}
              </div>

              <div className="mb-3 flex flex-wrap gap-1.5">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                  {s.active_table_count}/{s.table_count} таблиц
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    s.last_sync_status === 'synced'
                      ? 'bg-emerald-50 text-emerald-700'
                      : s.last_sync_status === 'stale'
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {s.last_sync_status}
                </span>
              </div>

              {/* Specialization Tags */}
              <div className="flex flex-wrap gap-1.5 mb-4 max-h-[56px] overflow-hidden">
                {(s.categories.length ? s.categories : s.specialization.split(',')).slice(0, 3).map((spec: string) => (
                  <span
                    key={spec}
                    className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded text-[10px] font-semibold"
                  >
                    {spec.trim()}
                  </span>
                ))}
                {(s.categories.length ? s.categories : s.specialization.split(',')).length > 3 && (
                  <span className="text-[10px] text-slate-400 font-bold self-center pl-1">
                    +{(s.categories.length ? s.categories : s.specialization.split(',')).length - 3}
                  </span>
                )}
              </div>

              <div className="mb-4 flex flex-wrap gap-2">
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenTables(s);
                  }}
                  className="rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
                >
                  Таблицы
                </button>
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    onEditSupplier(s);
                  }}
                  className="rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
                >
                  Редактировать
                </button>
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    onArchiveSupplier(s);
                  }}
                  className="rounded-xl border border-rose-200 bg-rose-50 px-2.5 py-1 text-[10px] font-bold text-rose-700 transition hover:border-rose-300 hover:text-rose-800"
                >
                  Архив
                </button>
              </div>
            </div>

            {/* Footer row: Contact person + SLA delivery */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-100 mt-auto">
              <div className="min-w-0">
                <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider">
                  Контакт
                </div>
                <div className="text-[11px] font-bold text-slate-700 truncate max-w-[120px]">
                  {s.contact_person}
                </div>
              </div>
              <div className="text-right">
                <div className="text-[9px] uppercase font-bold text-slate-400 tracking-wider">
                  SLA Доставка
                </div>
                <span
                  className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                    s.avg_delivery_days <= 1
                      ? 'bg-emerald-50 text-emerald-700'
                      : s.avg_delivery_days <= 3
                      ? 'bg-blue-50 text-blue-700'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {s.avg_delivery_days} дн.
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
