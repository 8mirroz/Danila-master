import React from 'react';
import type { SupplierRecord } from './supplierTypes';
import { Button, Icon } from './Primitives';
import {
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
            className="group relative flex min-h-[248px] cursor-pointer flex-col overflow-hidden rounded-[var(--radius-card)] border border-[var(--border-default)] bg-[var(--surface-1)] p-5 shadow-[var(--shadow-sm)] transition-all duration-[var(--transition-base)] hover:-translate-y-0.5 hover:border-[rgba(37,99,235,0.18)] hover:shadow-[var(--shadow-md)] focus-visible:outline-none"
          >
            <div className="absolute inset-x-0 top-0 h-[3px] bg-[var(--accent-primary)] opacity-80 transition-opacity group-hover:opacity-100" />

            <div className="mb-4 flex items-start justify-between gap-3">
              <span
                className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] ${statusMeta.pillClass}`}
              >
                {statusMeta.label}
              </span>
              <div className="flex items-center gap-2 text-right">
                {renderStars(s.reliability_score)}
                <span className="text-xs font-bold tabular-nums text-[var(--text-muted)]">
                  {(s.reliability_score * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            <div className="mb-3 flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 select-none items-center justify-center rounded-[12px] border border-[var(--border-default)] bg-[var(--surface-2)] text-xs font-bold uppercase text-[var(--text-secondary)] shadow-sm">
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="mb-0.5 line-clamp-2 text-[15px] font-bold leading-tight text-[var(--text-primary)]">
                  {s.name}
                </h3>
                <div className="flex items-center gap-1.5 text-[12px] font-semibold text-[var(--text-muted)]">
                  <Icon name="circle-info" size={10} className="text-[var(--text-muted)]" />
                  <span className="truncate">
                    {s.city || '—'}
                    {s.specialization ? ` · ${s.specialization}` : ''}
                  </span>
                </div>
              </div>
            </div>

            <div className="mb-3 flex flex-wrap gap-2">
              <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-1 text-[10px] font-bold text-[var(--text-secondary)]">
                {s.active_table_count}/{s.table_count} таблиц
              </span>
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${syncMeta.pillClass}`}>
                {syncMeta.label}
              </span>
              <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-1 text-[10px] font-bold tabular-nums text-[var(--text-secondary)]">
                SLA {s.avg_delivery_days} дн.
              </span>
            </div>

            <div className="mb-4 flex flex-wrap gap-1.5">
              {categories.slice(0, 4).map((spec) => (
                <span
                  key={spec}
                  className="rounded-full border border-[var(--border-default)] bg-[var(--surface-2)] px-2.5 py-1 text-[10px] font-semibold text-[var(--text-secondary)]"
                >
                  {spec}
                </span>
              ))}
              {categories.length > 4 && (
                <span className="self-center pl-1 text-[10px] font-bold text-[var(--text-muted)]">
                  +{categories.length - 4}
                </span>
              )}
            </div>

            <div className="mt-auto flex flex-wrap gap-2 border-t border-[var(--border-subtle)] pt-3">
              <Button
                size="sm"
                variant="secondary"
                onClick={(event) => {
                  event.stopPropagation();
                  onOpenTables(s);
                }}
              >
                Таблицы
              </Button>
              <Button
                size="sm"
                variant="secondary"
                icon="pencil"
                onClick={(event) => {
                  event.stopPropagation();
                  onEditSupplier(s);
                }}
              >
                Изменить
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={(event) => {
                  event.stopPropagation();
                  onArchiveSupplier(s);
                }}
              >
                Архив
              </Button>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <div className="min-w-0">
                <div className="ui-eyebrow">Контакт</div>
                <div className="mt-0.5 flex items-center gap-1.5 truncate text-[12px] font-bold text-[var(--text-secondary)]">
                  <span className="truncate">{s.contact_person || '—'}</span>
                  {s.contact_person && (
                    <div className="ml-1 flex shrink-0 items-center gap-1">
                      {s.phone && (
                        <a
                          href={`tel:${s.phone}`}
                          onClick={(e) => e.stopPropagation()}
                          className="p-0.5 text-[var(--text-muted)] transition-colors hover:text-[var(--accent-primary)]"
                          title={`Позвонить: ${s.phone}`}
                          aria-label={`Позвонить ${s.phone}`}
                        >
                          <Icon name="phone" size={12} />
                        </a>
                      )}
                      {s.email && (
                        <a
                          href={`mailto:${s.email}`}
                          onClick={(e) => e.stopPropagation()}
                          className="p-0.5 text-[var(--text-muted)] transition-colors hover:text-[var(--accent-primary)]"
                          title={`Написать: ${s.email}`}
                          aria-label={`Написать ${s.email}`}
                        >
                          <Icon name="envelope" size={12} />
                        </a>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div className="sm:text-right">
                <div className="ui-eyebrow">Надёжность · SLA</div>
                <div className="mt-0.5 text-[12px] font-bold tabular-nums text-[var(--text-secondary)]">
                  {Math.round(s.reliability_score * 100)}% · {s.avg_delivery_days} дн.
                </div>
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
};
