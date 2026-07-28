import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, apiJson } from '../lib/api';
import { SupplierCards } from './SupplierCards';
import { SupplierDetailPage } from './SupplierDetailPage';
import type { SupplierRecord } from './supplierTypes';

type DetailTab = 'overview' | 'profile' | 'tables' | 'analytics' | 'logs' | 'settings';

type SupplierDraft = {
  supplier_id?: string;
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  city: string;
  specialization: string;
  reliability_score: number;
  avg_delivery_days: number;
  status: string;
  rating_manual: number | null;
  account_owner: string;
  payment_terms: string;
  delivery_terms: string;
  currency_default: string;
  notes_internal: string;
  last_sync_status: string;
};

const defaultDraft: SupplierDraft = {
  name: '',
  contact_person: '',
  phone: '',
  email: '',
  city: '',
  specialization: '',
  reliability_score: 0.85,
  avg_delivery_days: 3,
  status: 'active',
  rating_manual: 4.5,
  account_owner: '',
  payment_terms: '',
  delivery_terms: '',
  currency_default: 'RUB',
  notes_internal: '',
  last_sync_status: 'synced',
};

export function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'pending' | 'blocked' | 'archived'>('all');
  const [freshnessFilter, setFreshnessFilter] = useState<'all' | 'synced' | 'stale'>('all');
  const [riskFilter, setRiskFilter] = useState<'all' | 'healthy' | 'attention' | 'high'>('all');
  const [slaFilter, setSlaFilter] = useState<'all' | 'fast' | 'standard' | 'slow'>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');
  const [showEditor, setShowEditor] = useState(false);
  const [draft, setDraft] = useState<SupplierDraft>(defaultDraft);
  const [saving, setSaving] = useState(false);

  const fetchSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (query.trim()) {
        params.set('q', query.trim());
      }
      if (statusFilter !== 'all') {
        params.set('status', statusFilter);
      }
      const path = params.size ? `/api/suppliers?${params.toString()}` : '/api/suppliers';
      const data = await apiJson<SupplierRecord[]>(path);
      setSuppliers(data);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось загрузить поставщиков');
    } finally {
      setLoading(false);
    }
  }, [query, statusFilter]);

  useEffect(() => {
    void fetchSuppliers();
  }, [fetchSuppliers]);

  const filteredSuppliers = useMemo(() => {
    const normalized = query.toLowerCase();
    return suppliers.filter((supplier) => {
      const matchesQuery = !normalized || (
        supplier.name.toLowerCase().includes(normalized) ||
        supplier.city.toLowerCase().includes(normalized) ||
        supplier.specialization.toLowerCase().includes(normalized) ||
        supplier.categories.some((category) => category.toLowerCase().includes(normalized))
      );

      const matchesFreshness =
        freshnessFilter === 'all' ||
        (freshnessFilter === 'stale' ? supplier.last_sync_status === 'stale' : supplier.last_sync_status === 'synced');

      const matchesRisk =
        riskFilter === 'all' ||
        (riskFilter === 'healthy' && supplier.reliability_score >= 0.9) ||
        (riskFilter === 'attention' && supplier.reliability_score >= 0.8 && supplier.reliability_score < 0.9) ||
        (riskFilter === 'high' && supplier.reliability_score < 0.8);

      const matchesSla =
        slaFilter === 'all' ||
        (slaFilter === 'fast' && supplier.avg_delivery_days <= 2) ||
        (slaFilter === 'standard' && supplier.avg_delivery_days >= 3 && supplier.avg_delivery_days <= 5) ||
        (slaFilter === 'slow' && supplier.avg_delivery_days > 5);

      const matchesCategory =
        categoryFilter === 'all' ||
        supplier.categories.some((category) => category.toLowerCase() === categoryFilter.toLowerCase()) ||
        supplier.specialization.toLowerCase().includes(categoryFilter.toLowerCase());

      return matchesQuery && matchesFreshness && matchesRisk && matchesSla && matchesCategory;
    });
  }, [categoryFilter, freshnessFilter, query, riskFilter, slaFilter, suppliers]);

  const categoryOptions = useMemo(() => {
    const values = new Set<string>();
    suppliers.forEach((supplier) => {
      supplier.categories.forEach((category) => values.add(category));
    });
    return Array.from(values).sort((left, right) => left.localeCompare(right));
  }, [suppliers]);

  const counters = useMemo(() => {
    return {
      active: suppliers.filter((supplier) => supplier.status === 'active').length,
      pending: suppliers.filter((supplier) => supplier.status === 'pending').length,
      blocked: suppliers.filter((supplier) => supplier.status === 'blocked').length,
      stale: suppliers.filter((supplier) => supplier.last_sync_status === 'stale').length,
    };
  }, [suppliers]);

  const handleOpenCreate = () => {
    setDraft(defaultDraft);
    setShowEditor(true);
  };

  const handleEditSupplier = (supplier: SupplierRecord) => {
    setSelectedSupplierId(null);
    setDraft({
      supplier_id: supplier.supplier_id,
      name: supplier.name,
      contact_person: supplier.contact_person,
      phone: supplier.phone,
      email: supplier.email,
      city: supplier.city,
      specialization: supplier.specialization,
      reliability_score: supplier.reliability_score,
      avg_delivery_days: supplier.avg_delivery_days,
      status: supplier.status,
      rating_manual: supplier.rating_manual,
      account_owner: supplier.account_owner,
      payment_terms: supplier.payment_terms,
      delivery_terms: supplier.delivery_terms,
      currency_default: supplier.currency_default,
      notes_internal: supplier.notes_internal,
      last_sync_status: supplier.last_sync_status,
    });
    setShowEditor(true);
  };

  const handleOpenDetail = (supplierId: string, initialTab: DetailTab = 'overview') => {
    setDetailTab(initialTab);
    setSelectedSupplierId(supplierId);
  };

  const handleArchiveSupplier = async (supplier: SupplierRecord) => {
    setError(null);
    try {
      await apiJson(`/api/suppliers/${supplier.supplier_id}/archive`, { method: 'POST' });
      if (selectedSupplierId === supplier.supplier_id) {
        setSelectedSupplierId(null);
      }
      await fetchSuppliers();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось архивировать поставщика');
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);
    try {
      const isPatch = Boolean(draft.supplier_id);
      const path = isPatch ? `/api/suppliers/${draft.supplier_id}` : '/api/suppliers';
      const method = isPatch ? 'PATCH' : 'POST';
      await apiJson<SupplierRecord>(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      });
      setShowEditor(false);
      await fetchSuppliers();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : 'Не удалось сохранить поставщика');
    } finally {
      setSaving(false);
    }
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

  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-6 flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-3xl font-black tracking-tight text-slate-900">Поставщики</h2>
            <p className="mt-1 text-sm text-slate-500">
              Живой supplier workspace с карточками, таблицами, аналитикой и журналом изменений.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-1">
              <button
                onClick={() => setViewMode('cards')}
                className={`rounded-xl px-3 py-2 text-sm font-bold transition ${
                  viewMode === 'cards' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Карточки
              </button>
              <button
                onClick={() => setViewMode('table')}
                className={`rounded-xl px-3 py-2 text-sm font-bold transition ${
                  viewMode === 'table' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Table mode
              </button>
            </div>
            <button
              onClick={() => void fetchSuppliers()}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            >
              Обновить
            </button>
            <button
              onClick={handleOpenCreate}
              className="rounded-2xl bg-[var(--accent-primary)] px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:opacity-90"
            >
              Добавить поставщика
            </button>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <CounterCard label="Active" value={counters.active} tone="emerald" />
          <CounterCard label="Pending" value={counters.pending} tone="amber" />
          <CounterCard label="Blocked" value={counters.blocked} tone="rose" />
          <CounterCard label="Stale feeds" value={counters.stale} tone="slate" />
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))]">
          <div className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <label className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Поиск
            </label>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Имя, город, специализация, категория"
              className="w-full border-none bg-transparent text-sm font-medium text-slate-700 outline-none"
            />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 lg:w-64">
            <label className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Статус
            </label>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
              className="w-full border-none bg-transparent text-sm font-medium text-slate-700 outline-none"
            >
              <option value="all">Все</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="blocked">Blocked</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          <FilterSelect
            label="Freshness"
            value={freshnessFilter}
            onChange={(value) => setFreshnessFilter(value as typeof freshnessFilter)}
            options={[
              { value: 'all', label: 'Все' },
              { value: 'synced', label: 'Synced' },
              { value: 'stale', label: 'Stale' },
            ]}
          />
          <FilterSelect
            label="Risk"
            value={riskFilter}
            onChange={(value) => setRiskFilter(value as typeof riskFilter)}
            options={[
              { value: 'all', label: 'Все' },
              { value: 'healthy', label: 'Healthy' },
              { value: 'attention', label: 'Attention' },
              { value: 'high', label: 'High risk' },
            ]}
          />
          <FilterSelect
            label="SLA"
            value={slaFilter}
            onChange={(value) => setSlaFilter(value as typeof slaFilter)}
            options={[
              { value: 'all', label: 'Все' },
              { value: 'fast', label: 'Fast <= 2 дн.' },
              { value: 'standard', label: '3-5 дн.' },
              { value: 'slow', label: '> 5 дн.' },
            ]}
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
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
          {error}
        </div>
      )}

      {showEditor && (
        <div className="mb-6 rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-black text-slate-900">
              {draft.supplier_id ? 'Редактирование поставщика' : 'Новый поставщик'}
            </h3>
            <button
              onClick={() => setShowEditor(false)}
              className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-bold text-slate-600 transition hover:text-slate-900"
            >
              Закрыть
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Field label="Название" value={draft.name} onChange={(value) => setDraft((current) => ({ ...current, name: value }))} />
            <Field label="Контакт" value={draft.contact_person} onChange={(value) => setDraft((current) => ({ ...current, contact_person: value }))} />
            <Field label="Телефон" value={draft.phone} onChange={(value) => setDraft((current) => ({ ...current, phone: value }))} />
            <Field label="Email" value={draft.email} onChange={(value) => setDraft((current) => ({ ...current, email: value }))} />
            <Field label="Город" value={draft.city} onChange={(value) => setDraft((current) => ({ ...current, city: value }))} />
            <Field label="Специализация" value={draft.specialization} onChange={(value) => setDraft((current) => ({ ...current, specialization: value }))} />
            <Field
              label="Надежность"
              type="number"
              value={String(draft.reliability_score)}
              onChange={(value) => setDraft((current) => ({ ...current, reliability_score: Number(value) || 0 }))}
            />
            <Field
              label="SLA (дни)"
              type="number"
              value={String(draft.avg_delivery_days)}
              onChange={(value) => setDraft((current) => ({ ...current, avg_delivery_days: Number(value) || 0 }))}
            />
            <SelectField
              label="Статус"
              value={draft.status}
              onChange={(value) => setDraft((current) => ({ ...current, status: value }))}
              options={[
                { value: 'active', label: 'Active' },
                { value: 'pending', label: 'Pending' },
                { value: 'blocked', label: 'Blocked' },
                { value: 'archived', label: 'Archived' },
              ]}
            />
            <Field
              label="Manual rating"
              type="number"
              value={draft.rating_manual === null ? '' : String(draft.rating_manual)}
              onChange={(value) => setDraft((current) => ({ ...current, rating_manual: value.trim() ? Number(value) : null }))}
            />
            <Field label="Владелец" value={draft.account_owner} onChange={(value) => setDraft((current) => ({ ...current, account_owner: value }))} />
            <Field label="Payment terms" value={draft.payment_terms} onChange={(value) => setDraft((current) => ({ ...current, payment_terms: value }))} />
            <Field label="Delivery terms" value={draft.delivery_terms} onChange={(value) => setDraft((current) => ({ ...current, delivery_terms: value }))} />
            <SelectField
              label="Валюта"
              value={draft.currency_default}
              onChange={(value) => setDraft((current) => ({ ...current, currency_default: value }))}
              options={[
                { value: 'RUB', label: 'RUB' },
                { value: 'USD', label: 'USD' },
                { value: 'EUR', label: 'EUR' },
                { value: 'CNY', label: 'CNY' },
              ]}
            />
            <SelectField
              label="Sync status"
              value={draft.last_sync_status}
              onChange={(value) => setDraft((current) => ({ ...current, last_sync_status: value }))}
              options={[
                { value: 'synced', label: 'Synced' },
                { value: 'stale', label: 'Stale' },
                { value: 'syncing', label: 'Syncing' },
                { value: 'failed', label: 'Failed' },
              ]}
            />
          </div>
          <label className="mt-4 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">
            Внутренняя заметка
          </label>
          <textarea
            value={draft.notes_internal}
            onChange={(event) => setDraft((current) => ({ ...current, notes_internal: event.target.value }))}
            className="mt-2 h-24 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none"
          />
          <div className="mt-4 flex justify-end gap-2">
            <button
              onClick={() => setShowEditor(false)}
              className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-bold text-slate-700 transition hover:text-slate-900"
            >
              Отмена
            </button>
            <button
              onClick={() => void handleSubmit()}
              disabled={saving || !draft.name.trim()}
              className="rounded-2xl bg-[var(--accent-primary)] px-4 py-2 text-sm font-bold text-white shadow-sm transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1">
        {loading ? (
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-[230px] animate-pulse rounded-2xl border border-slate-200 bg-white/70" />
            ))}
          </div>
        ) : filteredSuppliers.length ? (
          viewMode === 'cards' ? (
            <SupplierCards
              suppliers={filteredSuppliers}
              selectedSupplierId={null}
              onSelectSupplier={(supplier) => supplier && handleOpenDetail(supplier.supplier_id)}
              onOpenTables={(supplier) => handleOpenDetail(supplier.supplier_id, 'tables')}
              onEditSupplier={handleEditSupplier}
              onArchiveSupplier={(supplier) => {
                void handleArchiveSupplier(supplier);
              }}
            />
          ) : (
            <SupplierTableMode
              suppliers={filteredSuppliers}
              onOpen={(supplier) => handleOpenDetail(supplier.supplier_id)}
              onOpenTables={(supplier) => handleOpenDetail(supplier.supplier_id, 'tables')}
              onEdit={handleEditSupplier}
              onArchive={(supplier) => {
                void handleArchiveSupplier(supplier);
              }}
            />
          )
        ) : (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white/70 px-6 py-14 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
              <i className="fas fa-truck-field text-lg" />
            </div>
            <h3 className="text-lg font-black text-slate-900">Поставщики не найдены</h3>
            <p className="mt-1 text-sm text-slate-500">Сбросьте фильтр или добавьте нового поставщика.</p>
          </div>
        )}
      </div>
    </div>
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
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
      <label className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</label>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full border-none bg-transparent text-sm font-medium text-slate-700 outline-none"
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
    <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white/90 shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-4 py-3">Поставщик</th>
            <th className="px-4 py-3">Статус</th>
            <th className="px-4 py-3">Категории</th>
            <th className="px-4 py-3">SLA</th>
            <th className="px-4 py-3">Feeds</th>
            <th className="px-4 py-3">Рейтинг</th>
            <th className="px-4 py-3 text-right">Действия</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 bg-white">
          {suppliers.map((supplier) => (
            <tr key={supplier.supplier_id} className="hover:bg-slate-50/80">
              <td className="px-4 py-3">
                <div className="font-black text-slate-900">{supplier.name}</div>
                <div className="text-xs text-slate-500">
                  {supplier.city || '—'} • {supplier.contact_person || 'no contact'}
                </div>
              </td>
              <td className="px-4 py-3">
                <StatusPill status={supplier.status} />
              </td>
              <td className="px-4 py-3 text-slate-600">
                {(supplier.categories.length ? supplier.categories : supplier.specialization.split(','))
                  .slice(0, 2)
                  .map((entry) => entry.trim())
                  .filter(Boolean)
                  .join(', ') || '—'}
              </td>
              <td className="px-4 py-3 font-semibold text-slate-700">{supplier.avg_delivery_days} дн.</td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${
                  supplier.last_sync_status === 'stale'
                    ? 'bg-amber-50 text-amber-700'
                    : 'bg-emerald-50 text-emerald-700'
                }`}>
                  {supplier.active_table_count}/{supplier.table_count} • {supplier.last_sync_status}
                </span>
              </td>
              <td className="px-4 py-3 font-semibold text-slate-700">
                {Math.round(supplier.reliability_score * 100)}%
                {supplier.rating_manual ? ` / ${supplier.rating_manual.toFixed(1)}` : ''}
              </td>
              <td className="px-4 py-3">
                <div className="flex justify-end gap-2">
                  <TableActionButton label="Открыть" onClick={() => onOpen(supplier)} />
                  <TableActionButton label="Таблицы" onClick={() => onOpenTables(supplier)} />
                  <TableActionButton label="Edit" onClick={() => onEdit(supplier)} />
                  <TableActionButton label="Архив" onClick={() => onArchive(supplier)} tone="danger" />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CounterCard({ label, value, tone }: { label: string; value: number; tone: 'emerald' | 'amber' | 'rose' | 'slate' }) {
  const tones = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    rose: 'border-rose-200 bg-rose-50 text-rose-700',
    slate: 'border-slate-200 bg-slate-100 text-slate-700',
  };

  return (
    <div className={`rounded-2xl border px-4 py-3 ${tones[tone]}`}>
      <div className="text-[11px] font-bold uppercase tracking-[0.18em] opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-black">{value}</div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === 'active'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : status === 'blocked'
      ? 'bg-rose-50 text-rose-700 border-rose-200'
      : status === 'archived'
      ? 'bg-slate-100 text-slate-600 border-slate-200'
      : 'bg-amber-50 text-amber-700 border-amber-200';
  return <span className={`rounded-full border px-2 py-1 text-[11px] font-bold uppercase ${tone}`}>{status}</span>;
}

function TableActionButton({
  label,
  onClick,
  tone = 'default',
}: {
  label: string;
  onClick: () => void;
  tone?: 'default' | 'danger';
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl px-2.5 py-1.5 text-[11px] font-bold transition ${
        tone === 'danger'
          ? 'border border-rose-200 bg-rose-50 text-rose-700 hover:border-rose-300'
          : 'border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:text-slate-900'
      }`}
    >
      {label}
    </button>
  );
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'number';
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none"
      />
    </label>
  );
}

function SelectField({
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
    <label className="block">
      <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
