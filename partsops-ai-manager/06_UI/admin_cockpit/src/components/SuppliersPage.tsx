import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, apiJson } from '../lib/api';
import { ConfirmModal } from './ConfirmModal';
import {
  Button,
  DataTable,
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
  getSupplierStatusMeta,
  getSyncStatusMeta,
  loadSuppliersPrefs,
  matchesRiskFilter,
  matchesSlaFilter,
  saveSuppliersPrefs,
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
              className="inline-flex rounded-[var(--radius-control)] border border-[var(--border-default)] bg-[var(--surface-2)] p-1"
              role="group"
              aria-label="Режим отображения"
            >
              <button
                type="button"
                onClick={() => setViewMode('cards')}
                className={`rounded-[10px] px-3 py-2 text-xs font-semibold transition-all ${
                  viewMode === 'cards'
                    ? 'border border-[rgba(37,99,235,0.25)] bg-[var(--state-selected)] text-[var(--accent-primary)] shadow-sm'
                    : 'border border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-1)] hover:text-[var(--text-primary)]'
                }`}
              >
                Карточки
              </button>
              <button
                type="button"
                onClick={() => setViewMode('table')}
                className={`rounded-[10px] px-3 py-2 text-xs font-semibold transition-all ${
                  viewMode === 'table'
                    ? 'border border-[rgba(37,99,235,0.25)] bg-[var(--state-selected)] text-[var(--accent-primary)] shadow-sm'
                    : 'border border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-1)] hover:text-[var(--text-primary)]'
                }`}
              >
                Таблица
              </button>
            </div>
            <Button
              variant="secondary"
              icon="arrow-rotate-right"
              onClick={() => void fetchSuppliers()}
              loading={loading}
            >
              Обновить
            </Button>
            <Button variant="primary" icon="plus" onClick={handleOpenCreate}>
              Добавить поставщика
            </Button>
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
                  ? 'bg-slate-900 text-white border-slate-900'
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
      ? 'bg-emerald-500'
      : tone === 'amber'
        ? 'bg-amber-500'
        : tone === 'danger'
          ? 'bg-rose-500'
          : 'bg-slate-400';

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`panel-card-tight min-h-[96px] w-full overflow-hidden p-4 text-left transition-all duration-[var(--transition-base)] hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)] ${
        selected
          ? 'border-[rgba(37,99,235,0.35)] ring-2 ring-[rgba(37,99,235,0.18)]'
          : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          {label}
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${toneDot}`} />
          <Icon name={icon} size={16} className="text-[var(--accent-primary)]" />
        </span>
      </div>
      <strong className="mt-3 block text-[32px] font-bold tracking-[-0.04em] tabular-nums text-[var(--text-primary)]">
        {value}
      </strong>
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
    <DataTable
      columns={[
        { key: 'name', label: 'Поставщик' },
        { key: 'status', label: 'Статус' },
        { key: 'categories', label: 'Категории' },
        { key: 'sla', label: 'SLA', numeric: true },
        { key: 'feeds', label: 'Фиды' },
        { key: 'rating', label: 'Рейтинг', numeric: true },
        { key: 'actions', label: 'Действия' },
      ]}
    >
      {suppliers.map((supplier) => {
        const statusMeta = getSupplierStatusMeta(supplier.status);
        const syncMeta = getSyncStatusMeta(supplier.last_sync_status);
        const categories = (supplier.categories.length
          ? supplier.categories
          : supplier.specialization.split(',')
        )
          .map((entry) => entry.trim())
          .filter(Boolean)
          .slice(0, 2)
          .join(', ');

        return (
          <tr
            key={supplier.supplier_id}
            className="cursor-pointer transition-colors hover:bg-[var(--state-hover)]"
            onClick={() => onOpen(supplier)}
          >
            <td className="px-4 py-3">
              <div className="font-bold text-[var(--text-primary)]">{supplier.name}</div>
              <div className="text-xs text-[var(--text-muted)]">
                {supplier.city || '—'} · {supplier.contact_person || 'нет контакта'}
              </div>
            </td>
            <td className="px-4 py-3">
              <span
                className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] ${statusMeta.pillClass}`}
              >
                {statusMeta.label}
              </span>
            </td>
            <td className="px-4 py-3 text-[var(--text-secondary)]">{categories || '—'}</td>
            <td className="cell-num px-4 py-3 font-semibold tabular-nums text-[var(--text-secondary)]">
              {supplier.avg_delivery_days} дн.
            </td>
            <td className="px-4 py-3">
              <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${syncMeta.pillClass}`}>
                {supplier.active_table_count}/{supplier.table_count} · {syncMeta.shortLabel}
              </span>
            </td>
            <td className="cell-num px-4 py-3 font-semibold tabular-nums text-[var(--text-secondary)]">
              {Math.round(supplier.reliability_score * 100)}%
              {supplier.rating_manual != null ? ` / ${supplier.rating_manual.toFixed(1)}` : ''}
            </td>
            <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
              <div className="flex justify-end gap-1.5">
                <Button size="sm" variant="secondary" onClick={() => onOpen(supplier)}>
                  Открыть
                </Button>
                <Button size="sm" variant="secondary" onClick={() => onOpenTables(supplier)}>
                  Таблицы
                </Button>
                <Button size="sm" variant="secondary" icon="pencil" onClick={() => onEdit(supplier)}>
                  Изменить
                </Button>
                <Button size="sm" variant="danger" onClick={() => onArchive(supplier)}>
                  Архив
                </Button>
              </div>
            </td>
          </tr>
        );
      })}
    </DataTable>
  );
}
