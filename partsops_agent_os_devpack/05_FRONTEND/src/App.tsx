import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  ChevronDown,
  LayoutDashboard,
  Bell,
  Package,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  SlidersHorizontal,
  Truck,
  Search,
  Plus,
  Star,
  MapPin,
  Phone,
  Mail,
  X,
  FileText,
  AlertTriangle,
  Inbox,
  Bot,
  UserCheck,
  Shuffle,
  Calculator,
  FilePenLine,
  Receipt,
  CircleCheck,
  ChevronRight,
} from 'lucide-react';
import './styles.css';

/* ─────────────────────────────────────────────
   TYPES
───────────────────────────────────────────── */
type Tone = 'ok' | 'warn' | 'danger';

type Supplier = {
  id: string;
  name: string;
  city: string;
  status: 'active' | 'stale' | 'risky';
  response: string;
  freshness: string;
  score: number;
  badge: string;
  note: string;
  action: string;
  contact: string;
  phone: string;
  email: string;
  categories: string[];
  slaDelivery: string;
  tone?: Tone;
};

type Request = {
  id: string;
  title: string;
  summary: string;
  status: string;
  workflowStatus: string;
  priority: string;
  age: string;
  sla: string;
  action: string;
  customer: string;
  vehicle: string;
  parts: string[];
  tone?: Tone;
};

/* ─────────────────────────────────────────────
   DATA
───────────────────────────────────────────── */
const suppliers: Supplier[] = [
  {
    id: 'alfa',
    name: 'АвтоЛиния',
    city: 'Москва',
    status: 'active',
    response: 'ср. 7 мин',
    freshness: '2 мин назад',
    score: 0.98,
    badge: 'Приоритетный',
    note: 'Высокая конверсия, стабильный SLA',
    action: 'Открыть каталог',
    contact: 'Алексей Смирнов',
    phone: '+7 495 000-11-22',
    email: 'alex@avtolinia.ru',
    categories: ['Тормозная система', 'Подвеска', 'OEM'],
    slaDelivery: '1 день',
    tone: 'ok',
  },
  {
    id: 'orbit',
    name: 'Orbit Parts',
    city: 'Санкт-Петербург',
    status: 'active',
    response: 'ср. 12 мин',
    freshness: '15 мин назад',
    score: 0.91,
    badge: 'Активен',
    note: 'Хорошая скорость, проверенный поставщик',
    action: 'Сравнить офферы',
    contact: 'Мария Кузнецова',
    phone: '+7 812 000-33-44',
    email: 'maria@orbitparts.ru',
    categories: ['Двигатель', 'Трансмиссия'],
    slaDelivery: '2 дня',
    tone: 'ok',
  },
  {
    id: 'nova',
    name: 'Nova Trade',
    city: 'Екатеринбург',
    status: 'stale',
    response: 'ср. 29 мин',
    freshness: '2 ч назад',
    score: 0.76,
    badge: 'Устарел',
    note: 'Цена устарела, нужен refresh',
    action: 'Обновить цену',
    contact: 'Игорь Попов',
    phone: '+7 343 000-55-66',
    email: 'igor@novatrade.ru',
    categories: ['Фильтры', 'Расходники'],
    slaDelivery: '3 дня',
    tone: 'warn',
  },
  {
    id: 'delta',
    name: 'Delta Supply',
    city: 'Казань',
    status: 'risky',
    response: 'ср. 18 мин',
    freshness: '47 мин назад',
    score: 0.62,
    badge: 'Рискованный',
    note: 'Слабая история, только с проверкой',
    action: 'Проверить риск',
    contact: 'Сергей Андреев',
    phone: '+7 843 000-77-88',
    email: 'sergey@deltasupply.ru',
    categories: ['Электрика', 'Сенсоры'],
    slaDelivery: '5 дней',
    tone: 'danger',
  },
];

const requests: Request[] = [
  {
    id: 'REQ-0042',
    title: 'BMW X5 тормозные колодки',
    summary: 'OEM + проверка безопасной альтернативы',
    status: 'Согласование',
    workflowStatus: 'READY_FOR_APPROVAL',
    priority: 'Высокий',
    age: '12 мин',
    sla: '36 мин осталось',
    action: 'Проверить согласование',
    customer: 'Иван Петров',
    vehicle: 'BMW X5 2020, VIN: WB***4321',
    parts: ['Колодки тормозные передние — 2 компл.', 'Датчик износа колодок — 2 шт.'],
    tone: 'warn',
  },
  {
    id: 'REQ-0045',
    title: 'Toyota Camry комплект фильтров',
    summary: 'Сравнение цен, готово к закрытию',
    status: 'Готово',
    workflowStatus: 'APPROVED',
    priority: 'Средний',
    age: '24 мин',
    sla: '58 мин осталось',
    action: 'Открыть запрос',
    customer: 'Олег Сидоров',
    vehicle: 'Toyota Camry 2019',
    parts: ['Фильтр воздушный — 1 шт.', 'Фильтр масляный — 1 шт.', 'Фильтр салонный — 1 шт.'],
    tone: 'ok',
  },
  {
    id: 'REQ-0047',
    title: 'VW Golf датчик',
    summary: 'Ожидание подтверждения клиента',
    status: 'Ожидание',
    workflowStatus: 'MATCHING',
    priority: 'Высокий',
    age: '41 мин',
    sla: '08 мин осталось',
    action: 'Написать клиенту',
    customer: 'Наталья Иванова',
    vehicle: 'VW Golf 2018',
    parts: ['Датчик кислорода — 1 шт.'],
    tone: 'danger',
  },
  {
    id: 'REQ-0048',
    title: 'Mercedes комплект ремней',
    summary: 'Новый запрос, маршрутизация в процессе',
    status: 'Новый',
    workflowStatus: 'NEW',
    priority: 'Низкий',
    age: '3 мин',
    sla: '90 мин осталось',
    action: 'Назначить поставщика',
    customer: 'Дмитрий Козлов',
    vehicle: 'Mercedes C-Class 2021',
    parts: ['Ремень ГРМ — 1 шт.', 'Ремень генератора — 1 шт.', 'Натяжной ролик — 2 шт.'],
    tone: 'ok',
  },
];

const railStats = [
  { label: 'Очередь', value: '2', note: 'активных задачи' },
  { label: 'SLA', value: '3', note: 'окна давления' },
  { label: 'Риск', value: '1', note: 'ручная проверка' },
];

const navigationModules = [
  { id: 'operations', title: 'Операции', description: 'Сводка контура и фокус смены', badge: '1 срочных', tone: 'light' as const },
  { id: 'suppliers', title: 'Поставщики', description: 'SLA, надежность и список наблюдения', badge: '2 top', tone: 'dark' as const },
  { id: 'approvals', title: 'Согласования', description: 'Проверка рисков и эскалаций', badge: '4 задач', tone: 'dark' as const },
];

const WORKFLOW_STAGES = [
  { id: 'NEW', label: 'Входящая', icon: Inbox },
  { id: 'AI_PARSE', label: 'ИИ Разбор', icon: Bot },
  { id: 'VERIFICATION', label: 'Проверка', icon: UserCheck },
  { id: 'MATCHING', label: 'Матчинг', icon: Shuffle },
  { id: 'PRICING', label: 'Прайсинг', icon: Calculator },
  { id: 'APPROVAL', label: 'Согласование', icon: FilePenLine },
  { id: 'INVOICE', label: 'Счёт', icon: Receipt },
  { id: 'FULFILLED', label: 'Исполнено', icon: CircleCheck },
];

function getStageIndex(workflowStatus: string): number {
  const s = workflowStatus.toUpperCase();
  if (['NEW', 'NORMALIZING', 'PARSING'].includes(s)) return 0;
  if (['VIN_CHECK', 'PART_EXTRACTION'].includes(s)) return 1;
  if (['NEEDS_MANUAL_PARSE', 'VALIDATED', 'MANUAL_REVIEW'].includes(s)) return 2;
  if (['MATCHING', 'SUPPLIER_SEARCH', 'OFFER_RANKING'].includes(s)) return 3;
  if (['PRICING_REVIEW', 'REWORK', 'FINANCE_REVIEW'].includes(s)) return 4;
  if (['READY_FOR_APPROVAL', 'APPROVED'].includes(s)) return 5;
  if (['ERP_SYNCING', 'INVOICE_DRAFTED'].includes(s)) return 6;
  if (['SENT_TO_CLIENT', 'PAID', 'FULFILLED', 'CLOSED'].includes(s)) return 7;
  return 0;
}

/* ─────────────────────────────────────────────
   CHEVRON STEPPER
───────────────────────────────────────────── */
function ChevronStepper({ workflowStatus }: { workflowStatus: string }) {
  const currentIndex = getStageIndex(workflowStatus);
  return (
    <div className="chevron-stepper">
      {WORKFLOW_STAGES.map((stage, idx) => {
        const Icon = stage.icon;
        const isCompleted = idx < currentIndex;
        const isCurrent = idx === currentIndex;
        const cls = isCompleted ? 'chevron-step completed' : isCurrent ? 'chevron-step current' : 'chevron-step';
        return (
          <div key={stage.id} className={cls} style={{ zIndex: WORKFLOW_STAGES.length - idx }}>
            {idx !== WORKFLOW_STAGES.length - 1 && <div className="chevron-arrow" />}
            <div className="chevron-step-inner">
              {isCompleted
                ? <CheckCircle2 size={12} className="chevron-icon-done" />
                : <Icon size={12} />
              }
              <span>{stage.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ─────────────────────────────────────────────
   METRIC CARD
───────────────────────────────────────────── */
function MetricCard({ title, value, caption, tone = 'ok' }: { title: string; value: string; caption: string; tone?: Tone | 'ok' }) {
  return (
    <div className={`metric metric-${tone}`}>
      <div className="metric-title">{title}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-caption">{caption}</div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   TOP BAR
───────────────────────────────────────────── */
function TopControlBar() {
  return (
    <header className="topbar">
      <div className="topbar-copy">
        <div className="badges">
          <span className="badge">АГЕНТ ОС</span>
          <span className="badge green">Поток активен</span>
          <span className="badge">ПРОД</span>
        </div>
        <h1>Операторская консоль AI-движка</h1>
        <p>Контроль модели, бюджета, очередей, согласований, вызовов инструментов и отладки в одном рабочем контуре.</p>
      </div>
      <div className="metrics">
        <MetricCard title="РАСХОД СЕССИИ" value="$2.02" caption="из бюджета $10.00" />
        <MetricCard title="ЛИМИТ RPM" value="20" caption="запросов в минуту" />
        <MetricCard title="ЗДОРОВЬЕ ОЧЕРЕДИ" value="31" caption="событие в окне" />
        <MetricCard title="ДОЛЯ ОШИБОК" value="1.2%" caption="последний час" tone="warn" />
      </div>
    </header>
  );
}

/* ─────────────────────────────────────────────
   SUPPLIER CARD (детальная карточка)
───────────────────────────────────────────── */
function SupplierCard({ supplier, onClose }: { supplier: Supplier; onClose: () => void }) {
  const stars = Math.round(supplier.score * 5);
  const statusColor = supplier.tone === 'ok' ? 'pill-ok' : supplier.tone === 'warn' ? 'pill-warn' : 'pill-danger';

  return (
    <div className="detail-card">
      <div className="detail-card-header">
        <div>
          <span className="eyebrow">Карточка поставщика</span>
          <h3 className="detail-card-title">{supplier.name}</h3>
        </div>
        <button className="icon-close" onClick={onClose} aria-label="Закрыть"><X size={16} /></button>
      </div>

      <div className="detail-card-meta">
        <span className={`statusPill ${statusColor}`}>{supplier.badge}</span>
        <span className="detail-meta-item"><MapPin size={12} />{supplier.city}</span>
        <span className="detail-meta-item">
          {[...Array(5)].map((_, i) => (
            <Star key={i} size={11} fill={i < stars ? '#f59e0b' : 'none'} stroke={i < stars ? '#f59e0b' : '#cbd5e1'} />
          ))}
          <b>{Math.round(supplier.score * 100)}%</b>
        </span>
      </div>

      <p className="detail-card-note">{supplier.note}</p>

      <div className="detail-grid">
        <div className="detail-grid-item">
          <span>Время ответа</span>
          <b><Clock3 size={12} /> {supplier.response}</b>
        </div>
        <div className="detail-grid-item">
          <span>Актуальность</span>
          <b><Sparkles size={12} /> {supplier.freshness}</b>
        </div>
        <div className="detail-grid-item">
          <span>SLA доставка</span>
          <b><Truck size={12} /> {supplier.slaDelivery}</b>
        </div>
        <div className="detail-grid-item">
          <span>Надёжность</span>
          <b><ShieldCheck size={12} /> {Math.round(supplier.score * 100)}%</b>
        </div>
      </div>

      <div className="detail-tags">
        {supplier.categories.map(c => <span key={c} className="tag">{c}</span>)}
      </div>

      <div className="detail-contacts">
        <div className="detail-contact-row"><Phone size={12} /><span>{supplier.phone}</span></div>
        <div className="detail-contact-row"><Mail size={12} /><span>{supplier.email}</span></div>
        <div className="detail-contact-row"><FileText size={12} /><span>Контакт: {supplier.contact}</span></div>
      </div>

      <div className="detail-actions">
        <button className="primaryRow">{supplier.action}<ArrowRight size={14} /></button>
        <button className="secondaryRow">Редактировать</button>
        <button className="dangerRow">В архив</button>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   ADD SUPPLIER MODAL
───────────────────────────────────────────── */
function AddSupplierModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="detail-card-header">
          <div>
            <span className="eyebrow">Новый поставщик</span>
            <h3 className="detail-card-title">Добавить поставщика</h3>
          </div>
          <button className="icon-close" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="modal-form">
          <label>Название компании<input placeholder="ООО «Авто Детали»" /></label>
          <label>Город<input placeholder="Москва" /></label>
          <label>Контактное лицо<input placeholder="Иван Иванов" /></label>
          <label>Телефон<input placeholder="+7 495 000-00-00" /></label>
          <label>Email<input placeholder="contact@supplier.ru" /></label>
          <label>Специализация<input placeholder="Тормозная система, Подвеска..." /></label>
          <label>SLA доставки (дней)<input type="number" placeholder="2" /></label>
        </div>
        <div className="detail-actions">
          <button className="primaryRow">Добавить поставщика<ArrowRight size={14} /></button>
          <button className="secondaryRow" onClick={onClose}>Отмена</button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   REQUEST DETAIL CARD
───────────────────────────────────────────── */
function RequestDetailCard({ request, onClose }: { request: Request; onClose: () => void }) {
  return (
    <div className="detail-card">
      <div className="detail-card-header">
        <div>
          <span className="eyebrow">Карточка заявки</span>
          <h3 className="detail-card-title">{request.id}</h3>
        </div>
        <button className="icon-close" onClick={onClose} aria-label="Закрыть"><X size={16} /></button>
      </div>

      <ChevronStepper workflowStatus={request.workflowStatus} />

      <div className="detail-card-meta">
        <span className={`statusPill ${request.tone === 'ok' ? 'pill-ok' : request.tone === 'warn' ? 'pill-warn' : 'pill-danger'}`}>{request.status}</span>
        <span className="detail-meta-item"><AlertTriangle size={12} />{request.priority}</span>
        <span className="detail-meta-item"><Clock3 size={12} />{request.age}</span>
      </div>

      <p className="detail-card-note">{request.summary}</p>

      <div className="detail-grid">
        <div className="detail-grid-item">
          <span>Клиент</span>
          <b>{request.customer}</b>
        </div>
        <div className="detail-grid-item">
          <span>Автомобиль</span>
          <b>{request.vehicle}</b>
        </div>
        <div className="detail-grid-item">
          <span>SLA</span>
          <b>{request.sla}</b>
        </div>
        <div className="detail-grid-item">
          <span>Приоритет</span>
          <b>{request.priority}</b>
        </div>
      </div>

      <div className="detail-section-label">Запчасти</div>
      <div className="detail-parts">
        {request.parts.map(p => (
          <div key={p} className="detail-part-row">
            <Package size={12} />
            <span>{p}</span>
          </div>
        ))}
      </div>

      <div className="detail-actions">
        <button className="primaryRow">{request.action}<ArrowRight size={14} /></button>
        <button className="secondaryRow"><CheckCircle2 size={14} />Одобрить рекомендацию</button>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   SUPPLIER SIDEBAR (левая панель)
───────────────────────────────────────────── */
function SupplierSidebar({
  selectedSupplierId,
  onSelectSupplier,
  onOpenCard,
  onAddSupplier,
}: {
  selectedSupplierId: string;
  onSelectSupplier: (id: string) => void;
  onOpenCard: (s: Supplier) => void;
  onAddSupplier: () => void;
}) {
  return (
    <aside className="left rail rail-dark">
      <div className="railShell railShellDark">
        <div className="railHeader">
          <div>
            <span className="railEyebrow">Навигация</span>
            <h3>Левое меню</h3>
          </div>
          <button className="iconPill iconPillDark" type="button"><SlidersHorizontal size={15} /></button>
        </div>

        <p className="railLead">Команды, модули и список наблюдения поставщиков.</p>

        <div className="railStats">
          {railStats.map(stat => (
            <div className="railStat" key={stat.label}>
              <span>{stat.label}</span>
              <b>{stat.value}</b>
              <small>{stat.note}</small>
            </div>
          ))}
        </div>

        <section className="railSection">
          <div className="railSectionHead">
            <span className="sectionLabel sectionLabelDark">Рабочее пространство</span>
            <button className="railGhostButton" type="button">Обновить</button>
          </div>
          <div className="moduleList">
            {navigationModules.map((module, index) => (
              <article
                className={`moduleCard ${index === 0 ? 'moduleCardActive' : ''} ${module.tone === 'dark' ? 'moduleCardDark' : 'moduleCardLight'}`}
                key={module.id}
              >
                <div className="moduleCardTop">
                  <div>
                    <h4>{module.title}</h4>
                    <span>{module.description}</span>
                  </div>
                  <span className="moduleBadge">{module.badge}</span>
                </div>
                <div className="moduleCardBar" aria-hidden="true" />
              </article>
            ))}
          </div>
        </section>

        <section className="railSection">
          <div className="railSectionHead">
            <span className="sectionLabel sectionLabelDark">Список наблюдения</span>
            <button className="railGhostButton add-btn" type="button" onClick={onAddSupplier}>
              <Plus size={12} />Добавить
            </button>
          </div>
          <div className="railList">
            {suppliers.map(supplier => (
              <button
                className={`railRow ${supplier.id === selectedSupplierId ? 'railRowActive' : ''}`}
                key={supplier.id}
                type="button"
                onClick={() => onSelectSupplier(supplier.id)}
              >
                <div className="railRowTop">
                  <div>
                    <strong>{supplier.name}</strong>
                    <span>{supplier.note}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                    <span className={`statusPill ${supplier.tone ?? 'ok'}`}>{supplier.badge}</span>
                    <button
                      className="chevron-open-btn"
                      type="button"
                      onClick={e => { e.stopPropagation(); onOpenCard(supplier); }}
                      title="Открыть карточку"
                    >
                      <ChevronRight size={12} />
                    </button>
                  </div>
                </div>
                <div className="railRowMeta">
                  <span><Clock3 size={12} />{supplier.response}</span>
                  <span><Sparkles size={12} />{supplier.freshness}</span>
                  <span><ShieldCheck size={12} />{Math.round(supplier.score * 100)}%</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
    </aside>
  );
}

/* ─────────────────────────────────────────────
   LIVE EVENT LOG
───────────────────────────────────────────── */
function LiveEventLog() {
  const events = [
    ['06:36:43', 'ERP', 'Синхронизация очереди задач с ERP завершена штатно.', 'ok'],
    ['17:12:46', 'ЯДРО', 'Выгрузка audit log в SHA-256 хранилище.', 'info'],
    ['17:12:56', 'ПАРСЕР', 'Сканирование новой входящей спецификации.', 'info'],
    ['17:13:02', 'МАТЧИНГ', 'Найдено 7 офферов, 2 требуют проверки.', 'warn'],
  ];
  return (
    <section className="center panel">
      <div className="sectionHead">
        <div>
          <span className="eyebrow">Живой лог событий</span>
          <h2>Сигналы, исключения и маршрут работы</h2>
        </div>
        <input placeholder="Фильтр событий..." />
      </div>
      <div className="events">
        {events.map(([time, src, msg, tone]) => (
          <div className="event" key={time + msg}>
            <span>{time}</span>
            <b className={tone}>{src}</b>
            <p>{msg}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────
   REQUEST SIDEBAR (правая панель)
───────────────────────────────────────────── */
function RequestSidebar({
  selectedRequestId,
  onSelectRequest,
  onOpenCard,
}: {
  selectedRequestId: string;
  onSelectRequest: (id: string) => void;
  onOpenCard: (r: Request) => void;
}) {
  const focusedRequest = requests.find(r => r.id === selectedRequestId) ?? requests[0];

  return (
    <aside className="right rail rail-light">
      <div className="railShell railShellLight">
        <div className="railTopbar">
          <div>
            <span className="railEyebrow">Панель управления</span>
            <h3>Дашборд</h3>
          </div>
          <div className="railTopActions">
            <button className="iconPill" type="button"><Bell size={15} /></button>
            <button className="profilePill" type="button">ДМ</button>
          </div>
        </div>

        <div className="railSearch">
          <Search size={15} />
          <input placeholder="Поиск транзакций, клиентов, подписок" />
          <ChevronDown size={15} />
        </div>

        <div className="railMetrics">
          <div className="railMetric railMetricSoft">
            <span>Текущий MRR</span>
            <b>$12.4k</b>
            <small>базовый показатель рабочего пространства</small>
          </div>
          <div className="railMetric">
            <span>Активные клиенты</span>
            <b>16 601</b>
            <small>стабильный рост на этой неделе</small>
          </div>
          <div className="railMetric railMetricDark">
            <span>Глубина очереди</span>
            <b>33%</b>
            <small>живая нагрузка на полосу согласований</small>
          </div>
        </div>

        {/* Текущий запрос */}
        <section className="railFocusCard">
          <div className="railSectionHead">
            <span className="sectionLabel">Текущий запрос</span>
            <span className={`statusPill ${focusedRequest.tone ?? 'ok'}`}>{focusedRequest.status}</span>
          </div>

          {/* ChevronStepper внутри карточки */}
          <div className="focus-stepper-wrap">
            <ChevronStepper workflowStatus={focusedRequest.workflowStatus} />
          </div>

          <div className="focusTitle focusTitleRail">
            <LayoutDashboard size={18} />
            {focusedRequest.id}
          </div>
          <p>{focusedRequest.summary}</p>
          <div className="focusGrid focusGridRail">
            <div><span>Приоритет</span><b>{focusedRequest.priority}</b></div>
            <div><span>Возраст</span><b>{focusedRequest.age}</b></div>
            <div><span>SLA</span><b>{focusedRequest.sla}</b></div>
          </div>
          <div className="queueActions">
            <button className="primaryRow" type="button">
              {focusedRequest.action}<ArrowRight size={16} />
            </button>
            <button className="secondaryRow" type="button">
              <CheckCircle2 size={16} />Одобрить рекомендацию
            </button>
          </div>
        </section>

        {/* Очередь запросов */}
        <section className="railSection">
          <div className="railSectionHead">
            <span className="sectionLabel">Очередь запросов</span>
            <button className="railGhostButton" type="button">Эта неделя</button>
          </div>
          <div className="railList railListLight">
            {requests.map(request => (
              <button
                className={`queueCard ${request.id === selectedRequestId ? 'queueCardActive' : ''}`}
                key={request.id}
                type="button"
                onClick={() => onSelectRequest(request.id)}
              >
                <div className="railRowTop">
                  <div>
                    <strong>{request.id}</strong>
                    <span>{request.title}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                    <span className={`statusPill ${request.tone ?? 'ok'}`}>{request.status}</span>
                    <button
                      className="chevron-open-btn"
                      type="button"
                      onClick={e => { e.stopPropagation(); onOpenCard(request); }}
                      title="Открыть карточку"
                    >
                      <ChevronRight size={12} />
                    </button>
                  </div>
                </div>
                <div className="railRowMeta">
                  <span><ShieldAlert size={12} />{request.priority}</span>
                  <span><Clock3 size={12} />{request.age}</span>
                  <span><Sparkles size={12} />{request.sla}</span>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
    </aside>
  );
}

/* ─────────────────────────────────────────────
   WORKSPACE SUMMARY STRIP
───────────────────────────────────────────── */
function WorkspaceSummary({ supplier, request }: { supplier: Supplier; request: Request }) {
  return (
    <section className="summaryStrip">
      <div className="summaryItem">
        <span className="summaryLabel">Выбранный поставщик</span>
        <div className="summaryValue"><Truck size={16} />{supplier.name}</div>
        <p>{supplier.badge} · {supplier.response} · {supplier.freshness}</p>
      </div>
      <div className="summaryConnector" aria-hidden="true"><ArrowRight size={18} /></div>
      <div className="summaryItem">
        <span className="summaryLabel">Выбранный запрос</span>
        <div className="summaryValue"><Package size={16} />{request.id}</div>
        <p>{request.status} · {request.priority} · {request.sla}</p>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────
   BOTTOM DEBUG LAYER
───────────────────────────────────────────── */
function BottomDebugLayer({ supplier, request }: { supplier: Supplier; request: Request }) {
  return (
    <footer className="bottom panel">
      <div className="bottomCopy">
        <b>Хронология доказательств</b>
        <span>{request.id} маршрутизирован через {supplier.name} → парсинг → матчинг → согласование</span>
      </div>
      <div className="tabs">
        <button type="button">Доказательства</button>
        <button type="button">Трассировка</button>
        <button type="button">Raw JSON</button>
        <button type="button">Ошибки</button>
        <button type="button">Воспроизведение</button>
        <button type="button">Откат</button>
      </div>
    </footer>
  );
}

/* ─────────────────────────────────────────────
   APP ROOT
───────────────────────────────────────────── */
function App() {
  const [selectedSupplierId, setSelectedSupplierId] = useState(suppliers[0].id);
  const [selectedRequestId, setSelectedRequestId] = useState(requests[0].id);
  const [openSupplierCard, setOpenSupplierCard] = useState<Supplier | null>(null);
  const [openRequestCard, setOpenRequestCard] = useState<Request | null>(null);
  const [showAddSupplier, setShowAddSupplier] = useState(false);

  const selectedSupplier = suppliers.find(s => s.id === selectedSupplierId) ?? suppliers[0];
  const selectedRequest = requests.find(r => r.id === selectedRequestId) ?? requests[0];

  return (
    <main>
      <TopControlBar />
      <div className="workspace">
        <SupplierSidebar
          selectedSupplierId={selectedSupplierId}
          onSelectSupplier={setSelectedSupplierId}
          onOpenCard={setOpenSupplierCard}
          onAddSupplier={() => setShowAddSupplier(true)}
        />
        <div className="centerStack">
          <WorkspaceSummary supplier={selectedSupplier} request={selectedRequest} />
          {/* Шевронный степпер выбранного запроса в центральной зоне */}
          <div className="center-stepper-wrap">
            <div className="center-stepper-label">
              <span className="eyebrow">Этап обработки</span>
              <b>{selectedRequest.id} — {selectedRequest.title}</b>
            </div>
            <ChevronStepper workflowStatus={selectedRequest.workflowStatus} />
          </div>
          <LiveEventLog />
        </div>
        <RequestSidebar
          selectedRequestId={selectedRequestId}
          onSelectRequest={setSelectedRequestId}
          onOpenCard={setOpenRequestCard}
        />
      </div>
      <BottomDebugLayer supplier={selectedSupplier} request={selectedRequest} />

      {/* Детальная карточка поставщика */}
      {openSupplierCard && (
        <div className="slide-panel-overlay" onClick={() => setOpenSupplierCard(null)}>
          <div className="slide-panel" onClick={e => e.stopPropagation()}>
            <SupplierCard supplier={openSupplierCard} onClose={() => setOpenSupplierCard(null)} />
          </div>
        </div>
      )}

      {/* Детальная карточка заявки */}
      {openRequestCard && (
        <div className="slide-panel-overlay" onClick={() => setOpenRequestCard(null)}>
          <div className="slide-panel" onClick={e => e.stopPropagation()}>
            <RequestDetailCard request={openRequestCard} onClose={() => setOpenRequestCard(null)} />
          </div>
        </div>
      )}

      {/* Модальное окно добавления поставщика */}
      {showAddSupplier && <AddSupplierModal onClose={() => setShowAddSupplier(false)} />}
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
