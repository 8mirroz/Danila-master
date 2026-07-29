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

