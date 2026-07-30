import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, apiJson } from '../lib/api';
import { ConfirmModal } from './ConfirmModal';
import {
  Button,
  EmptyState,
  ErrorState,
  Icon,
  SearchField,
  Skeleton,
} from './Primitives';
import { SupplierCards } from './SupplierCards';
import { SupplierDetailPage } from './SupplierDetailPage';
import { SupplierEditorModal } from './SupplierEditorModal';
import {
  FRESHNESS_FILTER_OPTIONS,
  RISK_FILTER_OPTIONS,
  SLA_FILTER_OPTIONS,
  SORT_OPTIONS,
  STATUS_FILTER_OPTIONS,
  type FreshnessFilterKey,
  type RiskFilterKey,
  type SlaFilterKey,
  type SortKey,
  type StatusFilterKey,
  type ViewMode,
  getScraperBrandMeta,
  getSupplierStatusMeta,
  getSyncStatusMeta,
  loadSuppliersPrefs,
  matchesRiskFilter,
  matchesSlaFilter,
  saveSuppliersPrefs,
  supplierInitials,
} from './supplierConfig';
import type { SupplierRecord } from './supplierTypes';

type DetailTab = 'overview' | 'profile' | 'tables' | 'analytics' | 'logs' | 'settings';

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function SuppliersPage() {
  const initialPrefs = loadSuppliersPrefs();
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, 300);
  const [statusFilter, setStatusFilter] = useState<StatusFilterKey>('all');
  const [freshnessFilter, setFreshnessFilter] = useState<FreshnessFilterKey>('all');
  const [riskFilter, setRiskFilter] = useState<RiskFilterKey>('all');
  const [slaFilter, setSlaFilter] = useState<SlaFilterKey>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<ViewMode>(initialPrefs.viewMode);
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [showEditor, setShowEditor] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState<SupplierRecord | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<SupplierRecord | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);

  const fetchSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (debouncedQuery.trim()) {
        params.set('q', debouncedQuery.trim());
      }
      if (statusFilter !== 'all') {
        params.set('status', statusFilter);
      }
      const path = params.size ? `/api/suppliers?${params.toString()}` : '/api/suppliers';
      const data = await apiJson<SupplierRecord[]>(path);
      setSuppliers(data);
      setLastUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось загрузить поставщиков');
      setSuppliers([]);
    } finally {
      setLoading(false);
    }
  }, [debouncedQuery, statusFilter]);

  useEffect(() => {
    void fetchSuppliers();
  }, [fetchSuppliers]);

  useEffect(() => {
    saveSuppliersPrefs({ viewMode });
  }, [viewMode]);

  const categoryOptions = useMemo(() => {
    const values = new Set<string>();
    suppliers.forEach((supplier) => {
      supplier.categories.forEach((category) => values.add(category));
    });
    return Array.from(values).sort((left, right) => left.localeCompare(right, 'ru'));
  }, [suppliers]);

  const filteredSuppliers = useMemo(() => {
    const list = suppliers.filter((supplier) => {
      const matchesFreshness =
        freshnessFilter === 'all' ||
        (freshnessFilter === 'stale'
          ? supplier.last_sync_status === 'stale'
          : supplier.last_sync_status === 'synced');

      const matchesRisk = matchesRiskFilter(supplier.reliability_score, riskFilter);
      const matchesSla = matchesSlaFilter(supplier.avg_delivery_days, slaFilter);

      const matchesCategory =
        categoryFilter === 'all' ||
        supplier.categories.some((category) => category.toLowerCase() === categoryFilter.toLowerCase()) ||
        supplier.specialization.toLowerCase().includes(categoryFilter.toLowerCase());

      return matchesFreshness && matchesRisk && matchesSla && matchesCategory;
    });

    const sorted = [...list];
    sorted.sort((a, b) => {
      if (sortKey === 'reliability') return b.reliability_score - a.reliability_score;
      if (sortKey === 'sla') return a.avg_delivery_days - b.avg_delivery_days;
      if (sortKey === 'activity') {
        const aTime = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0;
        const bTime = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0;
        return bTime - aTime;
      }
      return a.name.localeCompare(b.name, 'ru');
    });
    return sorted;
  }, [categoryFilter, freshnessFilter, riskFilter, slaFilter, sortKey, suppliers]);

  const counters = useMemo(
    () => ({
      active: suppliers.filter((s) => s.status === 'active').length,
      pending: suppliers.filter((s) => s.status === 'pending').length,
      blocked: suppliers.filter((s) => s.status === 'blocked').length,
      stale: suppliers.filter((s) => s.last_sync_status === 'stale').length,
    }),
    [suppliers],
  );

  const hasActiveFilters =
    statusFilter !== 'all' ||
    freshnessFilter !== 'all' ||
    riskFilter !== 'all' ||
    slaFilter !== 'all' ||
    categoryFilter !== 'all' ||
    query.trim().length > 0;

  const activeFilterChips = useMemo(() => {
    const chips: Array<{ id: string; label: string; onClear: () => void }> = [];
    if (query.trim()) {
      chips.push({ id: 'q', label: `Поиск: ${query.trim()}`, onClear: () => setQuery('') });
    }
    if (statusFilter !== 'all') {
      chips.push({
        id: 'status',
        label: `Статус: ${getSupplierStatusMeta(statusFilter).label}`,
        onClear: () => setStatusFilter('all'),
      });
    }
    if (freshnessFilter !== 'all') {
      chips.push({
        id: 'fresh',
        label: `Свежесть: ${FRESHNESS_FILTER_OPTIONS.find((o) => o.value === freshnessFilter)?.label}`,
        onClear: () => setFreshnessFilter('all'),
      });
    }
    if (riskFilter !== 'all') {
      chips.push({
        id: 'risk',
        label: `Риск: ${RISK_FILTER_OPTIONS.find((o) => o.value === riskFilter)?.label}`,
        onClear: () => setRiskFilter('all'),
      });
    }
    if (slaFilter !== 'all') {
      chips.push({
        id: 'sla',
        label: `SLA: ${SLA_FILTER_OPTIONS.find((o) => o.value === slaFilter)?.label}`,
        onClear: () => setSlaFilter('all'),
      });
    }
    if (categoryFilter !== 'all') {
      chips.push({
        id: 'cat',
        label: `Категория: ${categoryFilter}`,
        onClear: () => setCategoryFilter('all'),
      });
    }
    return chips;
  }, [categoryFilter, freshnessFilter, query, riskFilter, slaFilter, statusFilter]);

  const clearAllFilters = () => {
    setQuery('');
    setStatusFilter('all');
    setFreshnessFilter('all');
    setRiskFilter('all');
    setSlaFilter('all');
    setCategoryFilter('all');
  };

  const handleOpenCreate = () => {
    setEditingSupplier(null);
    setShowEditor(true);
  };

  const handleEditSupplier = (supplier: SupplierRecord) => {
    setSelectedSupplierId(null);
    setEditingSupplier(supplier);
    setShowEditor(true);
  };

  const handleOpenDetail = (supplierId: string, initialTab: DetailTab = 'overview') => {
    setDetailTab(initialTab);
    setSelectedSupplierId(supplierId);
  };

  const handleArchiveConfirm = async () => {
    if (!archiveTarget) return;
    const target = archiveTarget;
    setArchiveTarget(null);
    setError(null);
    try {
      await apiJson(`/api/suppliers/${target.supplier_id}/archive`, { method: 'POST' });
      if (selectedSupplierId === target.supplier_id) {
        setSelectedSupplierId(null);
      }
      await fetchSuppliers();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось архивировать поставщика');
    }
  };

  const handleKpiClick = (kind: 'active' | 'pending' | 'blocked' | 'stale') => {
    if (kind === 'stale') {
      setStatusFilter('all');
      setFreshnessFilter((prev) => (prev === 'stale' ? 'all' : 'stale'));
      return;
    }
    setFreshnessFilter('all');
    setStatusFilter((prev) => (prev === kind ? 'all' : kind));
  };

  if (selectedSupplierId) {
    return (
      <SupplierDetailPage
        supplierId={selectedSupplierId}
        onBack={() => setSelectedSupplierId(null)}
        initialTab={detailTab}
        onRefresh={() => {
          void fetchSuppliers();
        }}
        onEditSupplier={handleEditSupplier}
      />
    );
  }

  const updatedLabel = lastUpdatedAt
    ? lastUpdatedAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <header className="panel-card shrink-0 p-5 md:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <p className="ui-eyebrow mb-1">Каталог</p>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] md:text-[28px]">
              Поставщики
            </h1>
            <p className="mt-1 text-sm text-[var(--text-muted)]">
              Каталог, фиды, рейтинги и журнал изменений
              {updatedLabel ? (
                <span className="ml-2 tabular-nums text-[var(--text-muted)]">· обновлено {updatedLabel}</span>
              ) : null}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div
              className="inline-flex rounded-xl border border-[var(--border-default)] bg-[var(--surface-2)] p-1 shadow-xs"
              role="group"
              aria-label="Режим отображения"
            >
              <button
                type="button"
                onClick={() => setViewMode('cards')}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                  viewMode === 'cards'
                    ? 'bg-[var(--surface-1)] text-[var(--accent-primary)] shadow-xs'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Icon name="grid-2" size={13} />
                <span>Карточки</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('table')}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                  viewMode === 'table'
                    ? 'bg-[var(--surface-1)] text-[var(--accent-primary)] shadow-xs'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Icon name="table" size={13} />
                <span>Таблица</span>
              </button>
            </div>

            <button
              type="button"
              onClick={() => void fetchSuppliers()}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border border-[var(--border-default)] bg-[var(--surface-1)] text-[var(--text-primary)] hover:bg-[var(--surface-2)] transition shadow-xs disabled:opacity-50"
            >
              <Icon name="arrow-rotate-right" size={13} className={loading ? 'animate-spin' : ''} />
              <span>Обновить</span>
            </button>

            <button
              type="button"
              onClick={handleOpenCreate}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-xs hover:shadow-md transition-all active:scale-[0.98]"
            >
              <Icon name="plus" size={13} />
              <span>Добавить поставщика</span>
            </button>
          </div>
        </div>
      </header>

      {/* KPI */}
      <div className="grid shrink-0 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiButton
          label="Активные"
          value={counters.active}
          tone="emerald"
          icon="circle-check"
          selected={statusFilter === 'active'}
          onClick={() => handleKpiClick('active')}
        />
        <KpiButton
          label="Ожидают"
          value={counters.pending}
          tone="amber"
          icon="bell"
          selected={statusFilter === 'pending'}
          onClick={() => handleKpiClick('pending')}
        />
        <KpiButton
          label="Заблокированы"
          value={counters.blocked}
          tone="danger"
          icon="warning"
          selected={statusFilter === 'blocked'}
          onClick={() => handleKpiClick('blocked')}
        />
        <KpiButton
          label="Устаревшие фиды"
          value={counters.stale}
          tone="neutral"
          icon="cloud-arrow-up"
          selected={freshnessFilter === 'stale'}
          onClick={() => handleKpiClick('stale')}
        />
      </div>

      {/* Filters Tray */}
      <section className="panel-card-tight shrink-0 p-3.5 transition-all duration-300">
        {/* Compact Tray Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-1 items-center gap-3 min-w-[280px]">
            <SearchField
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Поиск по имени, городу, категории..."
              className="flex-1"
            />
            {activeFilterChips.length > 0 && !isFiltersOpen && (
              <div className="hidden md:flex items-center gap-1.5 overflow-x-auto py-1">
                {activeFilterChips.map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    onClick={chip.onClear}
                    className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700 transition hover:bg-blue-100"
                  >
                    {chip.label}
                    <Icon name="x-mark" size={10} />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold tabular-nums text-[var(--text-muted)] whitespace-nowrap hidden sm:inline">
              Показано {filteredSuppliers.length} из {suppliers.length}
            </span>

            <button
              type="button"
              onClick={() => setIsFiltersOpen(!isFiltersOpen)}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-xs border ${
                isFiltersOpen || activeFilterChips.length > 0
                  ? 'bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]'
                  : 'bg-[var(--surface-2)] text-[var(--text-primary)] border-[var(--border-default)] hover:bg-[var(--surface-1)]'
              }`}
            >
              <Icon name="sliders" size={13} />
              <span>Фильтры</span>
              {activeFilterChips.length > 0 && (
                <span className="w-4 h-4 rounded-full bg-blue-500 text-white text-[10px] flex items-center justify-center font-bold">
                  {activeFilterChips.length}
                </span>
              )}
              <Icon name={isFiltersOpen ? 'chevron-up' : 'chevron-down'} size={12} className="ml-0.5" />
            </button>
          </div>
        </div>

        {/* Collapsible Tray Panel */}
        {isFiltersOpen && (
          <div className="mt-4 pt-4 border-t border-[var(--border-subtle)] space-y-3 animate-fadeIn">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
              <FilterSelect
                label="Статус"
                value={statusFilter}
                onChange={(value) => setStatusFilter(value as StatusFilterKey)}
                options={STATUS_FILTER_OPTIONS}
              />
              <FilterSelect
                label="Свежесть"
                value={freshnessFilter}
                onChange={(value) => setFreshnessFilter(value as FreshnessFilterKey)}
                options={FRESHNESS_FILTER_OPTIONS}
              />
              <FilterSelect
                label="Риск"
                value={riskFilter}
                onChange={(value) => setRiskFilter(value as RiskFilterKey)}
                options={RISK_FILTER_OPTIONS}
              />
              <FilterSelect
                label="SLA"
                value={slaFilter}
                onChange={(value) => setSlaFilter(value as SlaFilterKey)}
                options={SLA_FILTER_OPTIONS}
              />
              <FilterSelect
                label="Категория"
                value={categoryFilter}
                onChange={setCategoryFilter}
                options={[
                  { value: 'all', label: 'Все' },
                  ...categoryOptions.map((category) => ({ value: category, label: category })),
                ]}
              />
              <FilterSelect
                label="Сортировка"
                value={sortKey}
                onChange={(value) => setSortKey(value as SortKey)}
                options={SORT_OPTIONS}
              />
            </div>

            {activeFilterChips.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[var(--border-subtle)]">
                {activeFilterChips.map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    onClick={chip.onClear}
                    className="inline-flex items-center gap-1.5 rounded-full border border-[rgba(37,99,235,0.2)] bg-[var(--state-selected)] px-2.5 py-1 text-[11px] font-semibold text-[var(--accent-primary)] transition hover:bg-[var(--state-active)]"
                  >
                    {chip.label}
                    <Icon name="x-mark" size={10} />
                  </button>
                ))}
                <button
                  type="button"
                  onClick={clearAllFilters}
                  className="text-[11px] font-bold text-[var(--text-muted)] transition hover:text-[var(--text-primary)]"
                >
                  Сбросить все
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      {/* Content */}
      <div className="space-y-4 pb-6">
        {error && !loading ? (
          <ErrorState title="Не удалось загрузить поставщиков" message={error} onRetry={() => void fetchSuppliers()} />
        ) : loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="panel-card-tight flex min-h-[230px] flex-col gap-3 p-5"
              >
                <div className="flex justify-between">
                  <Skeleton className="h-6 w-20 rounded-full" />
                  <Skeleton className="h-4 w-16" />
                </div>
                <div className="flex gap-3">
                  <Skeleton className="h-10 w-10 rounded-[12px]" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
                <Skeleton className="h-6 w-full" />
                <Skeleton className="mt-auto h-8 w-full" />
              </div>
            ))}
          </div>
        ) : filteredSuppliers.length ? (
          viewMode === 'cards' ? (
            <SupplierCards
              suppliers={filteredSuppliers}
              onSelectSupplier={(supplier) => handleOpenDetail(supplier.supplier_id)}
              onOpenTables={(supplier) => handleOpenDetail(supplier.supplier_id, 'tables')}
              onEditSupplier={handleEditSupplier}
              onArchiveSupplier={setArchiveTarget}
            />
          ) : (
            <SupplierTableMode
              suppliers={filteredSuppliers}
              onOpen={(supplier) => handleOpenDetail(supplier.supplier_id)}
              onOpenTables={(supplier) => handleOpenDetail(supplier.supplier_id, 'tables')}
              onEdit={handleEditSupplier}
              onArchive={setArchiveTarget}
            />
          )
        ) : (
          <EmptyState
            title={suppliers.length === 0 ? 'Поставщики пока не добавлены' : 'Поставщики не найдены'}
            description={
              suppliers.length === 0
                ? 'Создайте первого поставщика, чтобы вести каталог, фиды и SLA.'
                : 'Сбросьте фильтры или измените поисковый запрос.'
            }
            icon="folder-open"
            actionNode={
              <div className="flex flex-wrap items-center justify-center gap-2">
                {hasActiveFilters && suppliers.length > 0 && (
                  <Button variant="secondary" onClick={clearAllFilters}>
                    Сбросить фильтры
                  </Button>
                )}
                <Button variant="primary" icon="plus" onClick={handleOpenCreate}>
                  {suppliers.length === 0 ? 'Добавить первого' : 'Добавить поставщика'}
                </Button>
              </div>
            }
          />
        )}
      </div>

      <SupplierEditorModal
        open={showEditor}
        onClose={() => {
          setShowEditor(false);
          setEditingSupplier(null);
        }}
        supplier={editingSupplier}
        onSaved={() => {
          void fetchSuppliers();
        }}
      />

      <ConfirmModal
        isOpen={Boolean(archiveTarget)}
        title={archiveTarget ? `Архивировать «${archiveTarget.name}»?` : 'Архивировать поставщика?'}
        description="Карточка скроется из активного каталога. Данные и таблицы сохранятся."
        variant="danger"
        confirmLabel="Архивировать"
        cancelLabel="Отмена"
        onConfirm={() => {
          void handleArchiveConfirm();
        }}
        onCancel={() => setArchiveTarget(null)}
      />
    </div>
  );
}

function KpiButton({
  label,
  value,
  tone,
  icon,
  selected,
  onClick,
}: {
  label: string;
  value: number;
  tone: 'emerald' | 'amber' | 'danger' | 'neutral';
  icon: string;
  selected: boolean;
  onClick: () => void;
}) {
  const toneDot =
    tone === 'emerald'
      ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]'
      : tone === 'amber'
        ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]'
        : tone === 'danger'
          ? 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'
          : 'bg-slate-400';

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`group relative overflow-hidden rounded-2xl border p-3.5 md:p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${
        selected
          ? 'border-blue-500/40 bg-blue-50/20 ring-2 ring-blue-500/20 dark:bg-blue-950/20'
          : 'border-[var(--border-default)] bg-[var(--surface-1)] hover:border-slate-300 dark:hover:border-slate-700'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
          {label}
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${toneDot}`} />
          <Icon name={icon} size={15} className="text-[var(--accent-primary)] opacity-80 group-hover:opacity-100 transition-opacity" />
        </span>
      </div>
      <div className="mt-2 flex items-baseline justify-between">
        <strong className="text-2xl md:text-3xl font-extrabold tracking-tight tabular-nums text-[var(--text-primary)]">
          {value}
        </strong>
        {selected && (
          <span className="text-[10px] font-bold text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/40 px-2 py-0.5 rounded-full">
            Фильтр вкл.
          </span>
        )}
      </div>
    </button>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div>
      <label className="ui-eyebrow mb-1.5 block">{label}</label>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-[var(--radius-control)] border border-[var(--border-default)] bg-[var(--surface-1)] px-3 py-2.5 text-xs font-semibold text-[var(--text-primary)] outline-none transition-all focus:border-[var(--accent-primary)]"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function SupplierTableMode({
  suppliers,
  onOpen,
  onOpenTables,
  onEdit,
  onArchive,
}: {
  suppliers: SupplierRecord[];
  onOpen: (supplier: SupplierRecord) => void;
  onOpenTables: (supplier: SupplierRecord) => void;
  onEdit: (supplier: SupplierRecord) => void;
  onArchive: (supplier: SupplierRecord) => void;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-[var(--border-default)] bg-[var(--surface-1)] shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-[var(--border-default)] bg-[var(--surface-2)]/60 text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              <th scope="col" className="px-4 py-3 min-w-[220px]">Поставщик</th>
              <th scope="col" className="px-3 py-3 min-w-[130px]">Статус & Скрапер</th>
              <th scope="col" className="px-3 py-3 min-w-[160px]">Специализация</th>
              <th scope="col" className="px-3 py-3 min-w-[90px] text-center">SLA</th>
              <th scope="col" className="px-3 py-3 min-w-[130px]">Фиды & Таблицы</th>
              <th scope="col" className="px-3 py-3 min-w-[110px] text-right">Надёжность</th>
              <th scope="col" className="px-4 py-3 min-w-[150px] text-right">Действия</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)]">
            {suppliers.map((supplier) => {
              const statusMeta = getSupplierStatusMeta(supplier.status);
              const syncMeta = getSyncStatusMeta(supplier.last_sync_status);
              const brandMeta = getScraperBrandMeta(supplier.supplier_id, supplier.name);
              const scraperConfigured = Boolean(supplier.scraper_source);
              const categories = (supplier.categories.length
                ? supplier.categories
                : supplier.specialization.split(',')
              )
                .map((entry) => entry.trim())
                .filter(Boolean);
              const initials = supplierInitials(supplier.name) || 'П';

              return (
                <tr
                  key={supplier.supplier_id}
                  className="group cursor-pointer transition-colors hover:bg-blue-50/30 dark:hover:bg-blue-950/20"
                  onClick={() => onOpen(supplier)}
                >
                  {/* Поставщик */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex h-9 w-9 shrink-0 select-none items-center justify-center rounded-xl text-xs font-black ${brandMeta.avatarBg} shadow-xs`}
                      >
                        {initials}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-sm text-[var(--text-primary)] group-hover:text-blue-600 transition-colors truncate max-w-[200px]" title={supplier.name}>
                          {supplier.name}
                        </div>
                        <div className="text-[11px] text-[var(--text-muted)] truncate max-w-[200px]">
                          {supplier.city || '—'} · {supplier.contact_person || 'нет контакта'}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Статус & Скрапер */}
                  <td className="px-3 py-3 whitespace-nowrap">
                    <div className="flex flex-col gap-1 items-start">
                      <span
                        className={`inline-flex rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusMeta.pillClass}`}
                      >
                        {statusMeta.label}
                      </span>
                      {scraperConfigured && (
                        <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[9px] font-bold text-blue-700">
                          Scraper настроен
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Специализация & Категории */}
                  <td className="px-3 py-3">
                    <div className="flex flex-wrap gap-1 max-w-[180px]">
                      {categories.slice(0, 2).map((cat) => (
                        <span
                          key={cat}
                          className="rounded-md border border-[var(--border-default)] bg-[var(--surface-2)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)] truncate max-w-[110px]"
                        >
                          {cat}
                        </span>
                      ))}
                      {categories.length > 2 && (
                        <span className="text-[10px] font-bold text-[var(--text-muted)] self-center">
                          +{categories.length - 2}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* SLA */}
                  <td className="px-3 py-3 text-center whitespace-nowrap">
                    <span className="inline-flex items-center gap-1 rounded-md bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 px-2 py-0.5 text-[11px] font-bold tabular-nums text-blue-700 dark:text-blue-300">
                      ⚡ {supplier.avg_delivery_days} дн.
                    </span>
                  </td>

                  {/* Фиды */}
                  <td className="px-3 py-3 whitespace-nowrap">
                    <span className={`inline-flex rounded-lg px-2.5 py-1 text-[11px] font-bold ${syncMeta.pillClass}`}>
                      {supplier.active_table_count}/{supplier.table_count} · {syncMeta.shortLabel}
                    </span>
                  </td>

                  {/* Рейтинг */}
                  <td className="px-3 py-3 text-right whitespace-nowrap">
                    <div className="font-extrabold text-sm tabular-nums text-[var(--text-primary)]">
                      {Math.round(supplier.reliability_score * 100)}%
                    </div>
                    {supplier.rating_manual != null && (
                      <div className="text-[10px] font-semibold text-amber-500">
                        ★ {supplier.rating_manual.toFixed(1)} / 5.0
                      </div>
                    )}
                  </td>

                  {/* Действия */}
                  <td className="px-4 py-3 text-right whitespace-nowrap" onClick={(event) => event.stopPropagation()}>
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => onOpen(supplier)}
                      >
                        Открыть
                      </Button>
                      <button
                        type="button"
                        onClick={() => onOpenTables(supplier)}
                        className="inline-flex items-center justify-center p-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--surface-1)] hover:bg-[var(--surface-2)] text-[var(--text-secondary)] transition hover:text-blue-600"
                        title="Таблицы прайсов"
                        aria-label="Таблицы прайсов"
                      >
                        <Icon name="table" size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => onEdit(supplier)}
                        className="inline-flex items-center justify-center p-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--surface-1)] hover:bg-[var(--surface-2)] text-[var(--text-secondary)] transition hover:text-blue-600"
                        title="Изменить"
                        aria-label="Изменить"
                      >
                        <Icon name="pencil" size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => onArchive(supplier)}
                        className="inline-flex items-center justify-center p-1.5 rounded-lg border border-rose-200 dark:border-rose-900 bg-rose-50/60 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 hover:bg-rose-100 transition"
                        title="В архив"
                        aria-label="В архив"
                      >
                        <Icon name="trash" size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
