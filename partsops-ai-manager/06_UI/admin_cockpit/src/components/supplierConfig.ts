/** Single source of truth for supplier catalog labels, filters, and prefs. */

export type SupplierStatusKey = 'active' | 'pending' | 'blocked' | 'archived';
export type SyncStatusKey = 'synced' | 'stale' | 'syncing' | 'failed';
export type RiskFilterKey = 'all' | 'healthy' | 'attention' | 'high';
export type SlaFilterKey = 'all' | 'fast' | 'standard' | 'slow';
export type FreshnessFilterKey = 'all' | 'synced' | 'stale';
export type StatusFilterKey = 'all' | SupplierStatusKey;
export type ViewMode = 'cards' | 'table';
export type SortKey = 'name' | 'reliability' | 'sla' | 'activity';

export type ToneKey = 'emerald' | 'amber' | 'rose' | 'slate' | 'sky';

export type StatusMeta = {
  label: string;
  shortLabel: string;
  tone: ToneKey;
  pillClass: string;
};

export const SUPPLIER_STATUSES: Record<SupplierStatusKey, StatusMeta> = {
  active: {
    label: 'Активен',
    shortLabel: 'Активные',
    tone: 'emerald',
    pillClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  },
  pending: {
    label: 'Ожидает',
    shortLabel: 'Ожидают',
    tone: 'amber',
    pillClass: 'bg-amber-50 text-amber-700 border-amber-200',
  },
  blocked: {
    label: 'Заблокирован',
    shortLabel: 'Заблокированы',
    tone: 'rose',
    pillClass: 'bg-rose-50 text-rose-700 border-rose-200',
  },
  archived: {
    label: 'Архив',
    shortLabel: 'Архив',
    tone: 'slate',
    pillClass: 'bg-surface-3 text-ink-secondary border-line',
  },
};

export const SYNC_STATUSES: Record<SyncStatusKey, StatusMeta> = {
  synced: {
    label: 'Синхронизирован',
    shortLabel: 'Синхр.',
    tone: 'emerald',
    pillClass: 'bg-emerald-50 text-emerald-700',
  },
  stale: {
    label: 'Устарел',
    shortLabel: 'Устаревшие',
    tone: 'amber',
    pillClass: 'bg-amber-50 text-amber-700',
  },
  syncing: {
    label: 'Синхронизация',
    shortLabel: 'Синхр…',
    tone: 'sky',
    pillClass: 'bg-sky-50 text-sky-700',
  },
  failed: {
    label: 'Сбой',
    shortLabel: 'Сбой',
    tone: 'rose',
    pillClass: 'bg-rose-50 text-rose-700',
  },
};

export const RISK_FILTERS: Record<
  RiskFilterKey,
  { label: string; min?: number; max?: number }
> = {
  all: { label: 'Все' },
  healthy: { label: 'Низкий риск', min: 0.9 },
  attention: { label: 'Внимание', min: 0.8, max: 0.9 },
  high: { label: 'Высокий риск', max: 0.8 },
};

export const SLA_FILTERS: Record<
  SlaFilterKey,
  { label: string; minDays?: number; maxDays?: number }
> = {
  all: { label: 'Все' },
  fast: { label: '≤ 2 дн.', maxDays: 2 },
  standard: { label: '3–5 дн.', minDays: 3, maxDays: 5 },
  slow: { label: '> 5 дн.', minDays: 6 },
};

export const FRESHNESS_FILTERS: Record<FreshnessFilterKey, { label: string }> = {
  all: { label: 'Все' },
  synced: { label: 'Актуальные' },
  stale: { label: 'Устаревшие' },
};

export const STATUS_FILTER_OPTIONS: Array<{ value: StatusFilterKey; label: string }> = [
  { value: 'all', label: 'Все' },
  { value: 'active', label: SUPPLIER_STATUSES.active.label },
  { value: 'pending', label: SUPPLIER_STATUSES.pending.label },
  { value: 'blocked', label: SUPPLIER_STATUSES.blocked.label },
  { value: 'archived', label: SUPPLIER_STATUSES.archived.label },
];

export const RISK_FILTER_OPTIONS: Array<{ value: RiskFilterKey; label: string }> = (
  Object.entries(RISK_FILTERS) as Array<[RiskFilterKey, { label: string }]>
).map(([value, meta]) => ({ value, label: meta.label }));

export const SLA_FILTER_OPTIONS: Array<{ value: SlaFilterKey; label: string }> = (
  Object.entries(SLA_FILTERS) as Array<[SlaFilterKey, { label: string }]>
).map(([value, meta]) => ({ value, label: meta.label }));

export const FRESHNESS_FILTER_OPTIONS: Array<{ value: FreshnessFilterKey; label: string }> = (
  Object.entries(FRESHNESS_FILTERS) as Array<[FreshnessFilterKey, { label: string }]>
).map(([value, meta]) => ({ value, label: meta.label }));

export const CURRENCY_OPTIONS = ['RUB', 'USD', 'EUR', 'CNY'] as const;

export type TableStatusKey = 'active' | 'draft' | 'stale' | 'archived';

export const TABLE_STATUSES: Record<TableStatusKey, { label: string }> = {
  active: { label: 'Активна' },
  draft: { label: 'Черновик' },
  stale: { label: 'Устарела' },
  archived: { label: 'Архив' },
};

export const TABLE_STATUS_OPTIONS: Array<{ value: TableStatusKey; label: string }> = (
  Object.entries(TABLE_STATUSES) as Array<[TableStatusKey, { label: string }]>
).map(([value, meta]) => ({ value, label: meta.label }));

export function getTableStatusLabel(status: string): string {
  const key = status as TableStatusKey;
  return TABLE_STATUSES[key]?.label ?? status ?? '—';
}

export const SORT_OPTIONS: Array<{ value: SortKey; label: string }> = [
  { value: 'name', label: 'Имя' },
  { value: 'reliability', label: 'Надёжность' },
  { value: 'sla', label: 'SLA' },
  { value: 'activity', label: 'Активность' },
];

export const LOCAL_PREFS_KEY = 'partsops.suppliers.prefs.v1';

export type SuppliersPrefs = {
  viewMode: ViewMode;
};

export function getSupplierStatusMeta(status: string): StatusMeta {
  const key = status as SupplierStatusKey;
  return SUPPLIER_STATUSES[key] ?? {
    label: status || '—',
    shortLabel: status || '—',
    tone: 'slate',
    pillClass: 'bg-surface-3 text-ink-secondary border-line',
  };
}

export function getSyncStatusMeta(status: string): StatusMeta {
  const key = status as SyncStatusKey;
  return SYNC_STATUSES[key] ?? {
    label: status || '—',
    shortLabel: status || '—',
    tone: 'slate',
    pillClass: 'bg-surface-3 text-ink-secondary',
  };
}

export function matchesRiskFilter(score: number, filter: RiskFilterKey): boolean {
  if (filter === 'all') return true;
  if (filter === 'healthy') return score >= 0.9;
  if (filter === 'attention') return score >= 0.8 && score < 0.9;
  if (filter === 'high') return score < 0.8;
  return true;
}

export function matchesSlaFilter(days: number, filter: SlaFilterKey): boolean {
  if (filter === 'all') return true;
  if (filter === 'fast') return days <= 2;
  if (filter === 'standard') return days >= 3 && days <= 5;
  if (filter === 'slow') return days > 5;
  return true;
}

export function loadSuppliersPrefs(): SuppliersPrefs {
  try {
    const raw = localStorage.getItem(LOCAL_PREFS_KEY);
    if (!raw) return { viewMode: 'cards' };
    const parsed = JSON.parse(raw) as Partial<SuppliersPrefs>;
    return {
      viewMode: parsed.viewMode === 'table' ? 'table' : 'cards',
    };
  } catch {
    return { viewMode: 'cards' };
  }
}

export function saveSuppliersPrefs(prefs: SuppliersPrefs): void {
  try {
    localStorage.setItem(LOCAL_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    // ignore quota / private mode
  }
}

export function supplierInitials(name: string): string {
  return name
    .replace(/^(ООО|ИП|АО|ЗАО|ооо|ип|ао|зао)\s+["«]?/i, '')
    .replace(/["»]/g, '')
    .trim()
    .slice(0, 2)
    .toUpperCase();
}

export function getScraperBrandMeta(supplierId: string, name: string) {
  const idLower = (supplierId || '').toLowerCase();
  const nameLower = (name || '').toLowerCase();

  if (idLower.includes('exist') || nameLower.includes('exist')) {
    return {
      brandName: 'Exist.ru',
      badgeClass: 'bg-blue-600 text-white shadow-ds-sm',
      avatarBg: 'bg-gradient-to-br from-blue-600 to-indigo-700 text-white font-black',
      borderClass: 'border-blue-500/30',
      accentColor: '#2563eb',
      searchUrl: 'https://exist.ru/Price/Search?article={oem}',
      isConfiguredScraper: true,
    };
  }
  if (idLower.includes('autodoc') || nameLower.includes('autodoc')) {
    return {
      brandName: 'Autodoc.ru',
      badgeClass: 'bg-rose-600 text-white shadow-ds-sm',
      avatarBg: 'bg-gradient-to-br from-rose-600 to-red-700 text-white font-black',
      borderClass: 'border-rose-500/30',
      accentColor: '#e11d48',
      searchUrl: 'https://www.autodoc.ru/search?query={oem}',
      isConfiguredScraper: true,
    };
  }
  if (idLower.includes('rossko') || nameLower.includes('rossko')) {
    return {
      brandName: 'Rossko.ru',
      badgeClass: 'bg-amber-600 text-white shadow-ds-sm',
      avatarBg: 'bg-gradient-to-br from-amber-500 to-orange-600 text-white font-black',
      borderClass: 'border-amber-500/30',
      accentColor: '#d97706',
      searchUrl: 'https://rossko.ru/search?query={oem}',
      isConfiguredScraper: true,
    };
  }
  return {
    brandName: null,
    badgeClass: 'bg-ink-secondary text-white',
    avatarBg: 'bg-surface-2 text-ink-secondary font-bold',
    borderClass: 'border-line',
    accentColor: '#64748b',
    searchUrl: null,
    isConfiguredScraper: false,
  };
}
