import React from 'react';
import type { SupplierRecord } from './supplierTypes';
import { Icon } from './Primitives';

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
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {suppliers.map((s) => {
        const isSelected = selectedSupplierId === s.supplier_id;
        const activeStatus = s.status === 'active' ? 'Active' : s.status === 'blocked' ? 'Blocked' : 'Pending';
        const displayStatus = s.status === 'active' ? 'Активен' : s.status === 'blocked' ? 'Заблокирован' : 'Ожидает';
        const categories = (s.categories.length ? s.categories : s.specialization.split(','))
          .map((spec) => spec.trim())
          .filter(Boolean);

        const initials = s.name
          .replace(/^(ООО|ИП|АО|ЗАО|ИП|ооо|ип|ао|зао)\s+["«]?/i, '')
          .replace(/["»]/g, '')
          .trim()
          .slice(0, 2);

        return (
          <div
            key={s.supplier_id}
            onClick={() => onSelectSupplier(isSelected ? null : s)}
            className={`group relative flex min-h-[248px] cursor-pointer flex-col overflow-hidden rounded-[24px] border p-5 shadow-sm transition-all duration-300 ${
              isSelected
                ? 'border-[rgba(37,99,235,0.28)] bg-[linear-gradient(180deg,rgba(37,99,235,0.08),rgba(255,255,255,0.94))] ring-2 ring-[rgba(37,99,235,0.18)]'
                : 'border-[var(--border-default)] bg-white/90 hover:-translate-y-0.5 hover:border-[rgba(37,99,235,0.18)] hover:shadow-md'
            }`}
          >
            <div className={`absolute inset-x-0 top-0 h-1.5 ${isSelected ? 'bg-[var(--accent-primary)]' : 'bg-gradient-to-r from-emerald-400 via-sky-400 to-indigo-400 opacity-80'}`} />

            <div>
              <div className="mb-4 flex items-start justify-between gap-3">
                <span
                  className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${
                    activeStatus === 'Active'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : activeStatus === 'Blocked'
                      ? 'bg-rose-50 text-rose-700 border border-rose-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}
                >
                  {displayStatus}
                </span>
                <div className="flex items-center gap-2 text-right">
                  {renderStars(s.reliability_score)}
                  <span className="text-xs font-bold text-slate-500">
                    {(s.reliability_score * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-[var(--surface-2)] border border-[var(--border-default)] flex items-center justify-center font-bold text-xs text-[var(--text-secondary)] shrink-0 shadow-sm select-none uppercase">
                  {initials || 'П'}
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="line-clamp-2 text-[15px] font-black leading-tight text-slate-900 mb-0.5">
                    {s.name}
                  </h3>
                  <div className="flex items-center gap-1.5 text-[12px] font-semibold text-slate-500">
                    <Icon name="circle-info" size={10} className="text-slate-400" />
                    <span className="truncate">{s.city || '—'}</span>
                  </div>
                </div>
              </div>

              <div className="mb-4 flex flex-wrap gap-2">
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">
                  {s.active_table_count}/{s.table_count} таблиц
                </span>
                <span
                  className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${
                    s.last_sync_status === 'synced'
                      ? 'bg-emerald-50 text-emerald-700'
                      : s.last_sync_status === 'stale'
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {s.last_sync_status === 'synced' ? 'Синхронизирован' : s.last_sync_status === 'stale' ? 'Устарел' : 'Сбой'}
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">
                  SLA {s.avg_delivery_days} дн.
                </span>
              </div>

              <div className="mb-4 flex flex-wrap gap-1.5">
                {categories.slice(0, 4).map((spec: string) => (
                  <span
                    key={spec}
                    className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-semibold text-slate-600"
                  >
                    {spec}
                  </span>
                ))}
                {categories.length > 4 && (
                  <span className="self-center pl-1 text-[10px] font-bold text-slate-400">
                    +{categories.length - 4}
                  </span>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    onOpenTables(s);
                  }}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
                >
                  Таблицы
                </button>
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    onEditSupplier(s);
                  }}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
                >
                  Редактировать
                </button>
                <button
                  onClick={(event) => {
                    event.stopPropagation();
                    onArchiveSupplier(s);
                  }}
                  className="rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-[11px] font-bold text-rose-700 transition hover:border-rose-300 hover:text-rose-800"
                >
                  Архив
                </button>
              </div>
            </div>

            <div className="mt-auto border-t border-slate-100 pt-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="min-w-0">
                  <div className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
                    Контакт
                  </div>
                  <div className="flex items-center gap-1.5 truncate text-[12px] font-bold text-slate-700">
                    <span className="truncate">{s.contact_person || '—'}</span>
                    {s.contact_person && (
                      <div className="flex items-center gap-1.5 shrink-0 ml-1">
                        {s.phone && (
                          <a
                            href={`tel:${s.phone}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-slate-400 hover:text-[var(--accent-primary)] transition-colors p-0.5"
                            title={`Позвонить: ${s.phone}`}
                          >
                            <Icon name="phone" size={12} />
                          </a>
                        )}
                        {s.email && (
                          <a
                            href={`mailto:${s.email}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-slate-400 hover:text-[var(--accent-primary)] transition-colors p-0.5"
                            title={`Написать: ${s.email}`}
                          >
                            <Icon name="envelope" size={12} />
                          </a>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div className="sm:text-right">
                  <div className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
                    Надежность / SLA
                  </div>
                  <div className="text-[12px] font-bold text-slate-700">
                    {Math.round(s.reliability_score * 100)}% · {s.avg_delivery_days} дн.
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
