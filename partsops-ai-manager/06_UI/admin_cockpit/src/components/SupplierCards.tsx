import React from 'react';
import type { SupplierRecord } from './supplierTypes';
import { Button, Icon } from './Primitives';
import {
  getScraperBrandMeta,
  getSupplierStatusMeta,
  getSyncStatusMeta,
  supplierInitials,
} from './supplierConfig';

interface SupplierCardsProps {
  suppliers: SupplierRecord[];
  onSelectSupplier: (s: SupplierRecord) => void;
  onOpenTables: (supplier: SupplierRecord) => void;
  onEditSupplier: (supplier: SupplierRecord) => void;
  onArchiveSupplier: (supplier: SupplierRecord) => void;
}

export const SupplierCards: React.FC<SupplierCardsProps> = ({
  suppliers,
  onSelectSupplier,
  onOpenTables,
  onEditSupplier,
  onArchiveSupplier,
}) => {
  const renderStars = (score: number) => {
    const starsCount = Math.round(score * 5);
    return (
      <div className="flex gap-0.5 text-amber-400" aria-hidden="true">
        {[...Array(5)].map((_, i) => (
          <span
            key={i}
            className={`text-[10px] leading-none ${i < starsCount ? 'opacity-100' : 'opacity-25'}`}
          >
            ★
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {suppliers.map((s) => {
        const statusMeta = getSupplierStatusMeta(s.status);
        const syncMeta = getSyncStatusMeta(s.last_sync_status);
        const brandMeta = getScraperBrandMeta(s.supplier_id, s.name);
        const scraperConfigured = Boolean(s.scraper_source);
        const categories = (s.categories.length ? s.categories : s.specialization.split(','))
          .map((spec) => spec.trim())
          .filter(Boolean);
        const initials = supplierInitials(s.name) || 'П';

        return (
          <article
            key={s.supplier_id}
            role="button"
            tabIndex={0}
            onClick={() => onSelectSupplier(s)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onSelectSupplier(s);
              }
            }}
            className="group relative flex min-h-[260px] cursor-pointer flex-col overflow-hidden rounded-2xl border border-line bg-surface-1 p-5 shadow-ds-sm transition-all duration-200 hover:-translate-y-1 hover:border-blue-500/40 hover:shadow-md focus-visible:outline-none"
          >
            {/* Top accent line */}
            <div
              className="absolute inset-x-0 top-0 h-[3px] opacity-80 transition-opacity group-hover:opacity-100"
              style={{ backgroundColor: brandMeta.accentColor }}
            />

            {/* Top row badges & rating */}
            <div className="mb-3.5 flex items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusMeta.pillClass}`}
                >
                  {statusMeta.label}
                </span>

                {scraperConfigured && (
                  <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700">
                    Scraper настроен
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1.5 text-right">
                {renderStars(s.reliability_score)}
                <span className="text-xs font-bold tabular-nums text-ink-primary">
                  {Math.round(s.reliability_score * 100)}%
                </span>
              </div>
            </div>

            {/* Main info row */}
            <div className="mb-3.5 flex items-start gap-3">
              <div
                className={`flex h-11 w-11 shrink-0 select-none items-center justify-center rounded-xl text-sm ${brandMeta.avatarBg} shadow-ds-sm`}
              >
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="mb-0.5 line-clamp-1 text-base font-bold leading-tight text-ink-primary group-hover:text-blue-600 transition-colors">
                  {s.name}
                </h3>
                <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                  <Icon name="location-dot" size={11} className="shrink-0 text-ink-muted" />
                  <span className="truncate">
                    {s.city || '—'}
                    {s.specialization ? ` · ${s.specialization}` : ''}
                  </span>
                </div>
              </div>
            </div>

            {/* Badges strip */}
            <div className="mb-3 flex flex-wrap gap-1.5">
              <span className="rounded-lg bg-surface-2 px-2.5 py-1 text-[11px] font-bold text-ink-secondary">
                {s.active_table_count}/{s.table_count} таблиц
              </span>
              <span className={`rounded-lg px-2.5 py-1 text-[11px] font-bold ${syncMeta.pillClass}`}>
                {syncMeta.label}
              </span>
              <span className="rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 px-2.5 py-1 text-[11px] font-bold tabular-nums">
                ⚡ SLA {s.avg_delivery_days} дн.
              </span>
            </div>

            {/* Categories */}
            <div className="mb-4 flex flex-wrap gap-1.5">
              {categories.slice(0, 3).map((spec) => (
                <span
                  key={spec}
                  className="rounded-md border border-line bg-surface-2 px-2 py-0.5 text-[10px] font-semibold text-ink-secondary"
                >
                  {spec}
                </span>
              ))}
              {categories.length > 3 && (
                <span className="self-center pl-1 text-[10px] font-bold text-ink-muted">
                  +{categories.length - 3}
                </span>
              )}
            </div>

            {/* Contacts & Notes */}
            <div className="mt-auto border-t border-line-subtle pt-3 pb-2 text-xs">
              <div className="flex items-center justify-between gap-2 text-ink-muted">
                <span className="truncate font-medium">
                  {s.contact_person || 'Отдел продаж'}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  {s.phone && (
                    <a
                      href={`tel:${s.phone}`}
                      onClick={(e) => e.stopPropagation()}
                      className="p-1 rounded-md hover:bg-surface-2 text-ink-muted hover:text-blue-600 transition"
                      title={`Позвонить: ${s.phone}`}
                    >
                      <Icon name="phone" size={12} />
                    </a>
                  )}
                  {s.email && (
                    <a
                      href={`mailto:${s.email}`}
                      onClick={(e) => e.stopPropagation()}
                      className="p-1 rounded-md hover:bg-surface-2 text-ink-muted hover:text-blue-600 transition"
                      title={`Написать: ${s.email}`}
                    >
                      <Icon name="envelope" size={12} />
                    </a>
                  )}
                </div>
              </div>
            </div>

            {/* Actions bar */}
            <div
              className="flex items-center justify-between gap-2 border-t border-line-subtle pt-3"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => onOpenTables(s)}
                >
                  Таблицы
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  icon="pencil"
                  onClick={() => onEditSupplier(s)}
                >
                  Изменить
                </Button>
              </div>

              <Button
                size="sm"
                variant="danger"
                onClick={() => onArchiveSupplier(s)}
              >
                Архив
              </Button>
            </div>
          </article>
        );
      })}
    </div>
  );
};
