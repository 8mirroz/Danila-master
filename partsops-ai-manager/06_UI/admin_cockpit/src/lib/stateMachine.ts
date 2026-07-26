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
  APPROVED: ['ERP_SYNCING', 'REWORK'],
  ERP_SYNCING: ['INVOICE_DRAFTED', 'ERP_SYNC_FAILED'],
  INVOICE_DRAFTED: ['SENT_TO_CLIENT', 'REWORK'],
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

export type TransitionVariant = 'primary' | 'warning' | 'danger' | 'secondary';

export const TRANSITION_META: Record<string, { label: string; variant: TransitionVariant; icon: string }> = {
  APPROVED:           { label: 'Согласовать',        variant: 'primary',   icon: 'fa-circle-check' },
  CANCELLED:          { label: 'Отменить',            variant: 'danger',    icon: 'fa-trash-can' },
  REWORK:             { label: 'На доработку',        variant: 'warning',   icon: 'fa-rotate-left' },
  MANUAL_REVIEW:      { label: 'Ручная проверка',     variant: 'warning',   icon: 'fa-magnifying-glass' },
  ERP_SYNCING:        { label: 'Выгрузить в ERP',     variant: 'primary',   icon: 'fa-rotate' },
  INVOICE_DRAFTED:    { label: 'Создать счёт',        variant: 'primary',   icon: 'fa-file-invoice' },
  SENT_TO_CLIENT:     { label: 'Отправить клиенту',   variant: 'primary',   icon: 'fa-paper-plane' },
  FINANCE_REVIEW:     { label: 'Фин. проверка',       variant: 'warning',   icon: 'fa-shield-halved' },
  NEEDS_CLARIFICATION:{ label: 'Запросить уточнение', variant: 'secondary', icon: 'fa-comment-dots' },
  NORMALIZING:        { label: 'Нормализовать',      variant: 'primary',   icon: 'fa-wand-magic-sparkles' },
  PARSING:            { label: 'Разобрать',           variant: 'primary',   icon: 'fa-file-code' },
  VIN_CHECK:          { label: 'Проверить VIN',       variant: 'primary',   icon: 'fa-car' },
  PART_EXTRACTION:    { label: 'Извлечь детали',      variant: 'primary',   icon: 'fa-gears' },
  MATCHING:           { label: 'Запустить подбор',     variant: 'primary',   icon: 'fa-arrows-split-up-and-left' },
  SUPPLIER_SEARCH:    { label: 'Поиск поставщиков',   variant: 'primary',   icon: 'fa-truck-field' },
  OFFER_RANKING:      { label: 'Ранжировать офферы',  variant: 'primary',   icon: 'fa-list-check' },
  PRICING_REVIEW:     { label: 'Расчёт цен',          variant: 'primary',   icon: 'fa-calculator' },
  READY_FOR_APPROVAL: { label: 'Готово к согласованию', variant: 'primary', icon: 'fa-clipboard-check' },
  PAID:               { label: 'Оплачено',            variant: 'primary',   icon: 'fa-money-bill-wave' },
  PURCHASE_ORDERED:   { label: 'Заказ поставщику',    variant: 'primary',   icon: 'fa-cart-shopping' },
  FULFILLED:          { label: 'Выполнено',           variant: 'primary',   icon: 'fa-box-check' },
  CLOSED:             { label: 'Закрыть',             variant: 'secondary', icon: 'fa-lock' },
};

export const getAllowedNext = (status: string): string[] => ALLOWED_TRANSITIONS[status] ?? [];
export const isTerminal = (status: string): boolean => getAllowedNext(status).length === 0;
export const isBlocked = (status: string): boolean =>
  ['FAILED', 'ERP_SYNC_FAILED', 'SUPPLIER_ISSUE', 'NEEDS_CLARIFICATION',
   'NEEDS_MANUAL_PARSE', 'CLIENT_REJECTED', 'EXPIRED'].includes(status);

