export type TransitionVariant = 'primary' | 'warning' | 'danger' | 'secondary';

export const TRANSITION_META: Record<string, { label: string; variant: TransitionVariant; icon: string }> = {
  APPROVED:           { label: 'Согласовать',        variant: 'primary',   icon: 'circle-check' },
  CANCELLED:          { label: 'Отменить',            variant: 'danger',    icon: 'trash-can' },
  REWORK:             { label: 'На доработку',        variant: 'warning',   icon: 'rotate-left' },
  MANUAL_REVIEW:      { label: 'Ручная проверка',     variant: 'warning',   icon: 'magnifying-glass' },
  ERP_SYNCING:        { label: 'Выгрузить в ERP',     variant: 'primary',   icon: 'rotate' },
  INVOICE_DRAFTED:    { label: 'Создать счёт',        variant: 'primary',   icon: 'file-invoice' },
  SENT_TO_CLIENT:     { label: 'Отправить клиенту',   variant: 'primary',   icon: 'paper-plane' },
  FINANCE_REVIEW:     { label: 'Фин. проверка',       variant: 'warning',   icon: 'shield-halved' },
  NEEDS_CLARIFICATION:{ label: 'Запросить уточнение', variant: 'secondary', icon: 'comment-dots' },
  NORMALIZING:        { label: 'Нормализовать',      variant: 'primary',   icon: 'wand-magic-sparkles' },
  PARSING:            { label: 'Разобрать',           variant: 'primary',   icon: 'file-code' },
  VIN_CHECK:          { label: 'Проверить VIN',       variant: 'primary',   icon: 'car' },
  PART_EXTRACTION:    { label: 'Извлечь детали',      variant: 'primary',   icon: 'gears' },
  MATCHING:           { label: 'Запустить подбор',     variant: 'primary',   icon: 'arrows-split-up-and-left' },
  SUPPLIER_SEARCH:    { label: 'Поиск поставщиков',   variant: 'primary',   icon: 'truck-field' },
  OFFER_RANKING:      { label: 'Ранжировать офферы',  variant: 'primary',   icon: 'list-check' },
  PRICING_REVIEW:     { label: 'Расчёт цен',          variant: 'primary',   icon: 'calculator' },
  READY_FOR_APPROVAL: { label: 'Готово к согласованию', variant: 'primary', icon: 'clipboard-check' },
  PAID:               { label: 'Оплачено',            variant: 'primary',   icon: 'money-bill-wave' },
  PURCHASE_ORDERED:   { label: 'Заказ поставщику',    variant: 'primary',   icon: 'cart-shopping' },
  FULFILLED:          { label: 'Выполнено',           variant: 'primary',   icon: 'box-check' },
  CLOSED:             { label: 'Закрыть',             variant: 'secondary', icon: 'lock' },
};

/**
 * Mirrors backend models.ALLOWED_TRANSITIONS (single-hop).
 * Used by Kanban valid-drop matrix — must stay in sync with models.py.
 */
export const ALLOWED_TRANSITIONS: Record<string, string[]> = {
  NEW: ['NORMALIZING', 'CANCELLED'],
  NORMALIZING: ['PARSING', 'NEEDS_MANUAL_PARSE', 'FAILED'],
  PARSING: ['VIN_CHECK', 'NEEDS_CLARIFICATION', 'FAILED'],
  VIN_CHECK: ['PART_EXTRACTION', 'NEEDS_CLARIFICATION', 'MANUAL_REVIEW'],
  PART_EXTRACTION: ['MATCHING', 'NEEDS_CLARIFICATION', 'MANUAL_REVIEW'],
  MATCHING: ['SUPPLIER_SEARCH', 'MANUAL_REVIEW', 'NEEDS_CLARIFICATION'],
  SUPPLIER_SEARCH: ['OFFER_RANKING', 'MANUAL_REVIEW', 'FAILED'],
  OFFER_RANKING: ['PRICING_REVIEW', 'MANUAL_REVIEW'],
  PRICING_REVIEW: ['READY_FOR_APPROVAL', 'FINANCE_REVIEW', 'MANUAL_REVIEW'],
  READY_FOR_APPROVAL: ['APPROVED', 'CLIENT_REJECTED', 'REWORK'],
  APPROVED: ['INVOICE_DRAFTED', 'REWORK'],
  INVOICE_DRAFTED: ['ERP_SYNCING', 'REWORK'],
  ERP_SYNCING: ['ERP_SYNCED', 'ERP_SYNC_FAILED'],
  ERP_SYNCED: ['SENT_TO_CLIENT', 'REWORK'],
  SENT_TO_CLIENT: ['PAID', 'CLIENT_REJECTED', 'EXPIRED'],
  PAID: ['PURCHASE_ORDERED', 'FULFILLED'],
  PURCHASE_ORDERED: ['FULFILLED', 'SUPPLIER_ISSUE'],
  FULFILLED: ['CLOSED', 'RETURN_CASE'],
  CLOSED: [],
  MANUAL_REVIEW: ['MATCHING', 'SUPPLIER_SEARCH', 'APPROVED', 'CANCELLED', 'REWORK'],
  NEEDS_CLARIFICATION: ['PARSING', 'CANCELLED'],
  FAILED: ['NORMALIZING', 'CANCELLED'],
  REWORK: ['MATCHING', 'SUPPLIER_SEARCH', 'MANUAL_REVIEW'],
  ERP_SYNC_FAILED: ['ERP_SYNCING', 'MANUAL_REVIEW'],
  RETURN_CASE: ['CLOSED'],
  SUPPLIER_ISSUE: ['PURCHASE_ORDERED', 'MANUAL_REVIEW'],
  NEEDS_MANUAL_PARSE: ['PARSING', 'CANCELLED'],
  FINANCE_REVIEW: ['READY_FOR_APPROVAL', 'REWORK', 'CANCELLED'],
  CLIENT_REJECTED: ['CANCELLED', 'REWORK'],
  EXPIRED: ['CANCELLED'],
};

export function getAllowedNext(status: string): string[] {
  return ALLOWED_TRANSITIONS[(status || '').toUpperCase()] ?? [];
}

/**
 * Pick a legal single-hop target for dropping a card into a column.
 * Prefers preferredTarget when allowed; otherwise first column status that is allowed.
 */
export function resolveColumnDropTarget(
  currentStatus: string,
  columnStatuses: string[],
  preferredTarget?: string,
): string | null {
  const allowed = new Set(getAllowedNext(currentStatus));
  if (!allowed.size) return null;

  const preferred = preferredTarget?.toUpperCase();
  if (preferred && allowed.has(preferred) && columnStatuses.includes(preferred)) {
    return preferred;
  }

  for (const status of columnStatuses) {
    if (allowed.has(status)) return status;
  }
  return null;
}

export function canDropOnColumn(
  currentStatus: string,
  columnStatuses: string[],
  preferredTarget?: string,
): boolean {
  return resolveColumnDropTarget(currentStatus, columnStatuses, preferredTarget) !== null;
}

