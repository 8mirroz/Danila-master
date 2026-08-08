export const WORKFLOW_STEPS = ['Нормализация', 'Сравнение', 'Согласование и цена', 'Аудит'];

export const REQUEST_STATUS_LABELS: Record<string, string> = {
  NEW: 'Новый',
  NORMALIZING: 'Нормализация',
  PARSING: 'Разбор',
  VIN_CHECK: 'VIN Чек',
  PART_EXTRACTION: 'Разбор',
  MATCHING: 'Поиск',
  SUPPLIER_SEARCH: 'Поиск',
  OFFER_RANKING: 'Подбор',
  PRICING_REVIEW: 'Прайсинг',
  READY_FOR_APPROVAL: 'Согласование',
  APPROVED: 'Одобрено',
  ERP_SYNCING: '1С Sync',
  ERP_SYNC_FAILED: 'Ошибка 1С',
  INVOICE_DRAFTED: 'Счет',
  SENT_TO_CLIENT: 'Отправлено',
  PAID: 'Оплачено',
  PURCHASE_ORDERED: 'Заказано',
  FULFILLED: 'Исполнено',
  CLOSED: 'Закрыто',
  MANUAL_REVIEW: 'Контроль',
  NEEDS_CLARIFICATION: 'Уточнение',
  NEEDS_MANUAL_PARSE: 'Коррекция',
  FAILED: 'Ошибка',
  CANCELLED: 'Отмена',
  REWORK: 'Доработка',
  CLIENT_REJECTED: 'Отклонено',
  EXPIRED: 'Истекло',
  SUPPLIER_ISSUE: 'Сбой поставок',
  RETURN_CASE: 'Возврат',
  FINANCE_REVIEW: 'Фин. проверка',
  VALIDATED: 'Проверено',
};

const DONE_STATUSES = new Set([
  'INVOICE_DRAFTED',
  'SENT_TO_CLIENT',
  'PAID',
  'PURCHASE_ORDERED',
  'FULFILLED',
  'CLOSED',
]);

const BLOCKED_STATUSES = new Set([
  'NEEDS_CLARIFICATION',
  'MANUAL_REVIEW',
  'FAILED',
  'ERP_SYNC_FAILED',
  'SUPPLIER_ISSUE',
  'NEEDS_MANUAL_PARSE',
  'FINANCE_REVIEW',
  'REWORK',
  'CLIENT_REJECTED',
  'EXPIRED',
  'RETURN_CASE',
  'CANCELLED',
]);

const APPROVAL_STATUSES = new Set(['PRICING_REVIEW', 'READY_FOR_APPROVAL', 'FINANCE_REVIEW']);
const MATCHING_STATUSES = new Set(['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING']);
const INVOICE_READY_STATUSES = new Set(['APPROVED', 'ERP_SYNCING', 'ERP_SYNC_FAILED']);

export const getStatusLabel = (status: string) => REQUEST_STATUS_LABELS[status.toUpperCase()] ?? status;

export const getStatusBadgeClasses = (status: string) => {
  const normalized = status.toUpperCase();

  if (DONE_STATUSES.has(normalized) || normalized === 'APPROVED' || normalized === 'VALIDATED') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  }

  if (BLOCKED_STATUSES.has(normalized)) {
    return 'bg-rose-50 text-rose-700 border-rose-200';
  }

  if (APPROVAL_STATUSES.has(normalized) || normalized === 'PART_EXTRACTION' || normalized === 'VIN_CHECK') {
    return 'bg-amber-50 text-amber-800 border-amber-200';
  }

  return 'bg-cyan-50 text-cyan-700 border-cyan-200';
};

export const isActiveRequestStatus = (status: string) => {
  const normalized = status.toUpperCase();
  return !DONE_STATUSES.has(normalized) && normalized !== 'CANCELLED' && normalized !== 'CLOSED';
};

export const isBlockedRequestStatus = (status: string) => BLOCKED_STATUSES.has(status.toUpperCase());
export const isApprovalPendingStatus = (status: string) => APPROVAL_STATUSES.has(status.toUpperCase());
export const isMatchingStatus = (status: string) => MATCHING_STATUSES.has(status.toUpperCase());
export const isInvoiceReadyStatus = (status: string) => INVOICE_READY_STATUSES.has(status.toUpperCase());

export type TrafficLightColor = 'green' | 'yellow' | 'red';

export const getTrafficLight = (status: string): TrafficLightColor => {
  const norm = (status || '').toUpperCase();
  if (BLOCKED_STATUSES.has(norm) || norm === 'FAILED' || norm === 'ERP_SYNC_FAILED' || norm === 'CANCELLED' || norm === 'EXPIRED') {
    return 'red';
  }
  if (APPROVAL_STATUSES.has(norm) || norm === 'NEEDS_CLARIFICATION' || norm === 'NEEDS_MANUAL_PARSE' || norm === 'REWORK') {
    return 'yellow';
  }
  return 'green';
};

export const getTrafficLightLabel = (status: string): string => {
  const light = getTrafficLight(status);
  if (light === 'red') return 'Сбой / Блокировка';
  if (light === 'yellow') return 'Требует внимания';
  return 'В норме';
};

export const getWorkflowStepIndex = (status: string) => {
  const normalized = status.toUpperCase();

  if (DONE_STATUSES.has(normalized) || normalized === 'ERP_SYNC_FAILED') {
    return 3;
  }

  if (APPROVAL_STATUSES.has(normalized) || normalized === 'APPROVED' || normalized === 'ERP_SYNCING') {
    return 2;
  }

  if (MATCHING_STATUSES.has(normalized) || normalized === 'MANUAL_REVIEW' || normalized === 'SUPPLIER_ISSUE') {
    return 1;
  }

  return 0;
};

export const getNextActionLabel = (status: string) => {
  const normalized = status.toUpperCase();

  if (normalized === 'NEW' || normalized === 'NORMALIZING' || normalized === 'PARSING' || normalized === 'VIN_CHECK' || normalized === 'PART_EXTRACTION') {
    return 'Проверить извлечение деталей';
  }

  if (MATCHING_STATUSES.has(normalized)) {
    return 'Выбрать оффер и зафиксировать решение';
  }

  if (APPROVAL_STATUSES.has(normalized)) {
    return 'Подтвердить цену или отправить на доработку';
  }

  if (normalized === 'APPROVED' || normalized === 'ERP_SYNCING' || normalized === 'ERP_SYNC_FAILED') {
    return 'Выпустить черновик счета и проверить ERP';
  }

  if (DONE_STATUSES.has(normalized)) {
    return 'Проверить аудит и завершение цикла';
  }

  if (normalized === 'MANUAL_REVIEW') {
    return 'Снять кейс с ручной проверки';
  }

  if (normalized === 'NEEDS_CLARIFICATION' || normalized === 'NEEDS_MANUAL_PARSE') {
    return 'Запросить уточнение или повторный разбор';
  }

  if (normalized === 'FAILED' || normalized === 'SUPPLIER_ISSUE' || normalized === 'FINANCE_REVIEW' || normalized === 'REWORK') {
    return 'Разобрать блокер и выбрать безопасный переход';
  }

  return 'Оценить состояние кейса';
};

export const getStatusGroup = (status: string) => {
  const normalized = status.toUpperCase();

  if (normalized === 'NEW' || normalized === 'NORMALIZING' || normalized === 'PARSING' || normalized === 'VIN_CHECK' || normalized === 'PART_EXTRACTION') {
    return 'intake';
  }

  if (MATCHING_STATUSES.has(normalized)) {
    return 'matching';
  }

  if (APPROVAL_STATUSES.has(normalized)) {
    return 'approval';
  }

  if (isInvoiceReadyStatus(normalized)) {
    return 'invoice';
  }

  if (isBlockedRequestStatus(normalized)) {
    return 'blocked';
  }

  if (DONE_STATUSES.has(normalized)) {
    return 'done';
  }

  return 'active';
};

export const getPriorityLabel = (priority?: string) => {
  const normalized = (priority || 'normal').toUpperCase();

  if (normalized === 'URGENT' || normalized === 'HIGH' || normalized === 'ВЫСОКИЙ') return 'Срочно';
  if (normalized === 'VIP') return 'VIP';
  if (normalized === 'LOW') return 'Низкий';
  return 'Обычный';
};

export const getPriorityClasses = (priority?: string) => {
  const normalized = (priority || 'normal').toUpperCase();

  if (normalized === 'URGENT' || normalized === 'HIGH' || normalized === 'ВЫСОКИЙ') {
    return 'bg-red-50 text-red-700 border-red-200';
  }

  if (normalized === 'VIP') {
    return 'bg-violet-50 text-violet-700 border-violet-200';
  }

  if (normalized === 'LOW') {
    return 'bg-surface-3 text-ink-secondary border-line';
  }

  return 'bg-blue-50 text-blue-700 border-blue-200';
};
