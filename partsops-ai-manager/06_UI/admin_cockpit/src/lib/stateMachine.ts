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

