import React from 'react';
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
} from 'lucide-react';
import './styles.css';

type MetricProps = {
  title: string;
  value: string;
  caption: string;
  tone?: 'ok' | 'warn' | 'danger';
};

function MetricCard({ title, value, caption, tone = 'ok' }: MetricProps) {
  return (
    <div className={`metric metric-${tone}`}>
      <div className="metric-title">{title}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-caption">{caption}</div>
    </div>
  );
}

function TopControlBar() {
  return (
    <header className="topbar">
      <div className="topbar-copy">
        <div className="badges">
          <span className="badge">AGENT OS</span>
          <span className="badge green">Поток активен</span>
          <span className="badge">PROD</span>
        </div>
        <h1>Операторская консоль AI-движка</h1>
        <p>
          Контроль модели, бюджета, очередей, approval, tool calls и debug в одном
          рабочем контуре.
        </p>
      </div>
      <div className="metrics">
        <MetricCard title="SESSION SPEND" value="$2.02" caption="из бюджета $10.00" />
        <MetricCard title="RPM POLICY" value="20" caption="запросов в минуту" />
        <MetricCard title="QUEUE HEALTH" value="31" caption="событие в окне" />
        <MetricCard title="ERROR RATE" value="1.2%" caption="последний час" tone="warn" />
      </div>
    </header>
  );
}

type Supplier = {
  id: string;
  name: string;
  status: string;
  response: string;
  freshness: string;
  score: string;
  badge: string;
  note: string;
  action: string;
  tone?: 'ok' | 'warn' | 'danger';
};

type RailStat = {
  label: string;
  value: string;
  note: string;
};

type ModuleCard = {
  id: string;
  title: string;
  description: string;
  badge: string;
  tone?: 'dark' | 'light';
};

const suppliers: Supplier[] = [
  {
    id: 'alfa',
    name: 'АвтоЛиния',
    status: 'online',
    response: '7m avg',
    freshness: '2m ago',
    score: '98',
    badge: 'Preferred',
    note: 'Высокая конверсия, стабильный SLA',
    action: 'Open catalog',
    tone: 'ok',
  },
  {
    id: 'orbit',
    name: 'Orbit Parts',
    status: 'active',
    response: '12m avg',
    freshness: '15m ago',
    score: '91',
    badge: 'Active',
    note: 'Хорошая скорость, проверенный поставщик',
    action: 'Compare offers',
    tone: 'ok',
  },
  {
    id: 'nova',
    name: 'Nova Trade',
    status: 'stale',
    response: '29m avg',
    freshness: '2h ago',
    score: '76',
    badge: 'Stale',
    note: 'Цена устарела, нужен refresh',
    action: 'Refresh price',
    tone: 'warn',
  },
  {
    id: 'delta',
    name: 'Delta Supply',
    status: 'risky',
    response: '18m avg',
    freshness: '47m ago',
    score: '62',
    badge: 'Risky',
    note: 'Слабая история, только с review',
    action: 'Review risk',
    tone: 'danger',
  },
];

const railStats: RailStat[] = [
  { label: 'Queue', value: '2', note: 'live tasks ready' },
  { label: 'SLA', value: '3', note: 'pressure windows' },
  { label: 'Risk', value: '1', note: 'manual review' },
];

const navigationModules: ModuleCard[] = [
  {
    id: 'operations',
    title: 'Операции',
    description: 'Сводка контура и фокус смены',
    badge: '1 срочных',
    tone: 'light',
  },
  {
    id: 'suppliers',
    title: 'Поставщики',
    description: 'SLA, надежность и watchlist',
    badge: '2 top',
    tone: 'dark',
  },
  {
    id: 'approvals',
    title: 'Approval lane',
    description: 'Проверка рисков и эскалаций',
    badge: '4 задач',
    tone: 'dark',
  },
];

type SupplierSidebarProps = {
  selectedSupplierId: string;
  onSelectSupplier: (supplierId: string) => void;
};

function SupplierSidebar({ selectedSupplierId, onSelectSupplier }: SupplierSidebarProps) {
  const focusedSupplier = suppliers.find((supplier) => supplier.id === selectedSupplierId) ?? suppliers[0];

  return (
    <aside className="left rail rail-dark">
      <div className="railShell railShellDark">
        <div className="railHeader">
          <div>
            <span className="railEyebrow">Navigation Tray</span>
            <h3>Левое меню</h3>
          </div>
          <button className="iconPill iconPillDark" type="button" aria-label="Adjust navigation">
            <SlidersHorizontal size={15} />
          </button>
        </div>

        <p className="railLead">Команды, модули и live supplier watchlist.</p>

        <div className="railStats">
          {railStats.map((stat) => (
            <div className="railStat" key={stat.label}>
              <span>{stat.label}</span>
              <b>{stat.value}</b>
              <small>{stat.note}</small>
            </div>
          ))}
        </div>

        <section className="railSection">
          <div className="railSectionHead">
            <span className="sectionLabel sectionLabelDark">Workspace</span>
            <button className="railGhostButton" type="button">
              Обновить
            </button>
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
            <span className="sectionLabel sectionLabelDark">Supplier watchlist</span>
            <span className="railMeta">3 live</span>
          </div>
          <div className="railList">
            {suppliers.map((supplier) => (
              <button
                className={`railRow ${supplier.id === selectedSupplierId ? 'railRowActive' : ''}`}
                key={supplier.id}
                type="button"
                onClick={() => onSelectSupplier(supplier.id)}
                aria-pressed={supplier.id === selectedSupplierId}
              >
                <div className="railRowTop">
                  <div>
                    <strong>{supplier.name}</strong>
                    <span>{supplier.note}</span>
                  </div>
                  <span className={`statusPill ${supplier.tone ?? 'ok'}`}>{supplier.badge}</span>
                </div>
                <div className="railRowMeta">
                  <span>
                    <Clock3 size={12} />
                    {supplier.response}
                  </span>
                  <span>
                    <Sparkles size={12} />
                    {supplier.freshness}
                  </span>
                  <span>
                    <ShieldCheck size={12} />
                    {supplier.score}%
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
    </aside>
  );
}

function LiveEventLog() {
  const events = [
    ['06:36:43', 'ERP', 'Синхронизация очереди задач с ERP завершена штатно.', 'ok'],
    ['17:12:46', 'ЯДРО', 'Выгрузка audit log в SHA-256 storage.', 'info'],
    ['17:12:56', 'ПАРСЕР', 'Сканирование новой входящей спецификации.', 'info'],
    ['17:13:02', 'MATCH', 'Найдено 7 офферов, 2 требуют review.', 'warn'],
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

type Request = {
  id: string;
  title: string;
  summary: string;
  status: string;
  priority: string;
  age: string;
  sla: string;
  action: string;
  tone?: 'ok' | 'warn' | 'danger';
};

const requests: Request[] = [
  {
    id: 'REQ-0042',
    title: 'BMW X5 brake pads',
    summary: 'OEM + safe alternative review',
    status: 'Approval',
    priority: 'High',
    age: '12m',
    sla: '36m left',
    action: 'Review approval',
    tone: 'warn',
  },
  {
    id: 'REQ-0045',
    title: 'Toyota Camry filter set',
    summary: 'Price compare, ready to close',
    status: 'Ready',
    priority: 'Medium',
    age: '24m',
    sla: '58m left',
    action: 'Open request',
    tone: 'ok',
  },
  {
    id: 'REQ-0047',
    title: 'VW Golf sensor',
    summary: 'Waiting for confirmation',
    status: 'Waiting',
    priority: 'High',
    age: '41m',
    sla: '08m left',
    action: 'Ping client',
    tone: 'danger',
  },
  {
    id: 'REQ-0048',
    title: 'Mercedes belt kit',
    summary: 'Fresh request, routing in progress',
    status: 'New',
    priority: 'Low',
    age: '3m',
    sla: '90m left',
    action: 'Assign supplier',
    tone: 'ok',
  },
];

type RequestSidebarProps = {
  selectedRequestId: string;
  onSelectRequest: (requestId: string) => void;
};

function RequestSidebar({ selectedRequestId, onSelectRequest }: RequestSidebarProps) {
  const focusedRequest = requests.find((request) => request.id === selectedRequestId) ?? requests[0];

  return (
    <aside className="right rail rail-light">
      <div className="railShell railShellLight">
        <div className="railTopbar">
          <div>
            <span className="railEyebrow">Control Dashboard</span>
            <h3>Dashboard</h3>
          </div>
          <div className="railTopActions">
            <button className="iconPill" type="button" aria-label="Notifications">
              <Bell size={15} />
            </button>
            <button className="profilePill" type="button" aria-label="Profile menu">
              DM
            </button>
          </div>
        </div>

        <div className="railSearch">
          <Search size={15} />
          <input aria-label="Search control rail" placeholder="Search transactions, customers, subscriptions" />
          <ChevronDown size={15} />
        </div>

        <div className="railMetrics">
          <div className="railMetric railMetricSoft">
            <span>Current MRR</span>
            <b>$12.4k</b>
            <small>baseline for this workspace</small>
          </div>
          <div className="railMetric">
            <span>Active customers</span>
            <b>16,601</b>
            <small>steady growth this week</small>
          </div>
          <div className="railMetric railMetricDark">
            <span>Queue depth</span>
            <b>33%</b>
            <small>live load on the approval lane</small>
          </div>
        </div>

        <section className="railFocusCard">
          <div className="railSectionHead">
            <span className="sectionLabel">Focused request</span>
            <span className={`statusPill ${focusedRequest.tone ?? 'ok'}`}>{focusedRequest.status}</span>
          </div>
          <div className="focusTitle focusTitleRail">
            <LayoutDashboard size={18} />
            {focusedRequest.id}
          </div>
          <p>{focusedRequest.summary}</p>
          <div className="focusGrid focusGridRail">
            <div>
              <span>Priority</span>
              <b>{focusedRequest.priority}</b>
            </div>
            <div>
              <span>Age</span>
              <b>{focusedRequest.age}</b>
            </div>
            <div>
              <span>SLA</span>
              <b>{focusedRequest.sla}</b>
            </div>
          </div>
          <div className="queueActions">
            <button className="primaryRow" type="button">
              {focusedRequest.action}
              <ArrowRight size={16} />
            </button>
            <button className="secondaryRow" type="button">
              <CheckCircle2 size={16} />
              Approve recommended
            </button>
          </div>
        </section>

        <section className="railSection">
          <div className="railSectionHead">
            <span className="sectionLabel">Request queue</span>
            <button className="railGhostButton" type="button">
              This week
            </button>
          </div>
          <div className="railList railListLight">
            {requests.map((request) => (
              <button
                className={`queueCard ${request.id === selectedRequestId ? 'queueCardActive' : ''}`}
                key={request.id}
                type="button"
                onClick={() => onSelectRequest(request.id)}
                aria-pressed={request.id === selectedRequestId}
              >
                <div className="railRowTop">
                  <div>
                    <strong>{request.id}</strong>
                    <span>{request.title}</span>
                  </div>
                  <span className={`statusPill ${request.tone ?? 'ok'}`}>{request.status}</span>
                </div>
                <div className="railRowMeta">
                  <span>
                    <ShieldAlert size={12} />
                    {request.priority}
                  </span>
                  <span>
                    <Clock3 size={12} />
                    {request.age}
                  </span>
                  <span>
                    <Sparkles size={12} />
                    {request.sla}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
    </aside>
  );
}

type WorkspaceSummaryProps = {
  supplier: Supplier;
  request: Request;
};

function WorkspaceSummary({ supplier, request }: WorkspaceSummaryProps) {
  return (
    <section className="summaryStrip">
      <div className="summaryItem">
        <span className="summaryLabel">Selected supplier</span>
        <div className="summaryValue">
          <Truck size={16} />
          {supplier.name}
        </div>
        <p>
          {supplier.badge} · {supplier.response} · {supplier.freshness}
        </p>
      </div>
      <div className="summaryConnector" aria-hidden="true">
        <ArrowRight size={18} />
      </div>
      <div className="summaryItem">
        <span className="summaryLabel">Selected request</span>
        <div className="summaryValue">
          <Package size={16} />
          {request.id}
        </div>
        <p>
          {request.status} · {request.priority} · {request.sla}
        </p>
      </div>
    </section>
  );
}

type BottomDebugLayerProps = {
  supplier: Supplier;
  request: Request;
};

function BottomDebugLayer({ supplier, request }: BottomDebugLayerProps) {
  return (
    <footer className="bottom panel">
      <div className="bottomCopy">
        <b>Evidence Timeline</b>
        <span>
          {request.id} routed through {supplier.name} → parse → match → approval
        </span>
      </div>
      <div className="tabs">
        <button type="button">Evidence</button>
        <button type="button">Trace</button>
        <button type="button">Raw JSON</button>
        <button type="button">Errors</button>
        <button type="button">Replay</button>
        <button type="button">Rollback</button>
      </div>
    </footer>
  );
}

function App() {
  const [selectedSupplierId, setSelectedSupplierId] = React.useState(suppliers[0].id);
  const [selectedRequestId, setSelectedRequestId] = React.useState(requests[0].id);

  const selectedSupplier = suppliers.find((supplier) => supplier.id === selectedSupplierId) ?? suppliers[0];
  const selectedRequest = requests.find((request) => request.id === selectedRequestId) ?? requests[0];

  return (
    <main>
      <TopControlBar />
      <div className="workspace">
        <SupplierSidebar selectedSupplierId={selectedSupplierId} onSelectSupplier={setSelectedSupplierId} />
        <div className="centerStack">
          <WorkspaceSummary supplier={selectedSupplier} request={selectedRequest} />
          <LiveEventLog />
        </div>
        <RequestSidebar selectedRequestId={selectedRequestId} onSelectRequest={setSelectedRequestId} />
      </div>
      <BottomDebugLayer supplier={selectedSupplier} request={selectedRequest} />
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
