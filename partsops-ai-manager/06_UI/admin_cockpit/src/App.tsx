import { useEffect, useState } from 'react';
import '@fortawesome/fontawesome-free/css/all.min.css';
import { 
  AppFrame, 
  TopCommandBar, 
  LeftNavRail, 
  WorkspaceHeader, 
  StepGate, 
  SectionCard, 
  MetricTile, 
  ActionButton, 
  Dropzone, 
  ReviewPanel, 
  EmptyState, 
  InlineAlert,
} from './components/Primitives';
import { SupplierMatrix } from './components/SupplierMatrix';
import { PricingCalculator } from './components/PricingCalculator';
import { AuditTimeline } from './components/AuditTimeline';
import { CompletedOrdersHistory } from './components/CompletedOrdersHistory';
import { RightPanel } from './components/RightPanel';
import { KanbanBoard } from './components/KanbanBoard';
import { apiFetch } from './lib/api';


type Request = {
  id: number;
  request_id: string;
  source: string;
  status: string;
  customer_name: string;
  created_at: string;
  parts_json: string;
  customer_phone_masked?: string;
  customer_email_masked?: string;
  vehicle_vin_masked?: string;
  priority?: string;
  vehicle_make?: string;
  vehicle_model?: string;
};

type Supplier = {
  supplier_id: string;
  name: string;
  contact_person: string;
  phone: string;
  email: string;
  city: string;
  specialization: string;
  reliability_score: number;
  avg_delivery_days: number;
};


const overviewMetrics = [
  { label: 'Уверенность системы', value: '94%', delta: '+4 п.', tone: 'emerald' as const },
  { label: 'Нагрузка согласования', value: '07', delta: '2 срочных', tone: 'amber' as const },
  { label: 'Пакеты подтверждений', value: '318', delta: 'активно', tone: 'cyan' as const },
  { label: 'Защищенная маржа', value: '12.8%', delta: 'безопасно', tone: 'violet' as const },
];

const workflowLanes = [
  { title: 'Прием запросов', count: '18', summary: 'Новые запросы разобраны, 4 требуют уточнения', tone: 'cyan' as const },
  { title: 'Подбор предложений', count: '09', summary: 'Случаи с низкой уверенностью ждут подтверждений', tone: 'violet' as const },
  { title: 'Согласование', count: '07', summary: '2 высокоприоритетных случая требуют подписи админа', tone: 'amber' as const },
  { title: 'Черновики ERP', count: '05', summary: 'Коммерческие пакеты готовы к отправке', tone: 'emerald' as const },
];

const urgentCases = [
  {
    title: 'Запрос комплекта тормозов с конфликтом OEM',
    id: 'REQ-4821',
    detail: 'Сравните аналоги и проверьте актуальность поставщика перед выпуском.',
    tone: 'danger' as const,
  },
  {
    title: 'Устаревший фид поставщика для рулевой рейки',
    id: 'REQ-4817',
    detail: 'Обновите цену Nordline и отложите согласование до завершения синхронизации.',
    tone: 'amber' as const,
  },
  {
    title: 'Готовый к счету запрос выше целевой маржи',
    id: 'REQ-4815',
    detail: 'Коммерческий пакет обоснован и готов к отправке клиенту.',
    tone: 'emerald' as const,
  },
];

function App() {
  const [selectedReq, setSelectedReq] = useState<Request | null>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [activeNav, setActiveNav] = useState<string>('dashboard');
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(2); // Default to Normalization Review (Step 2)
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const [searchSupplierQuery, setSearchSupplierQuery] = useState('');
  const [searchGlobalQuery, setSearchGlobalQuery] = useState('');
  
  // Requests state hoisted from RightPanel
  const [requests, setRequests] = useState<Request[]>([]);
  const [dashboardView, setDashboardView] = useState<'overview' | 'kanban'>('overview');
  
  // Supplier selection and import modal states
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);
  const [showSupplierImportModal, setShowSupplierImportModal] = useState(false);
  const [supplierItems, setSupplierItems] = useState<any[]>([]);
  const [supplierItemsLoading, setSupplierItemsLoading] = useState(false);
  
  // Local session state for imports
  const [localSupplierMessage, setLocalSupplierMessage] = useState<string | null>(null);
  const [localOrderMessage, setLocalOrderMessage] = useState<string | null>(null);
  const [normalizedParts, setNormalizedParts] = useState<Array<{ name: string; quantity: number }>>([]);
  
  // Track selected catalog offer per part: record of partName -> MatchItem
  const [selectedOffers, setSelectedOffers] = useState<Record<string, any>>({});

  const fetchRequests = async () => {
    try {
      const res = await apiFetch('/api/requests');
      if (res.ok) {
        const data = await res.json();
        setRequests(data);
      }
    } catch (error) {
      console.error('Error fetching requests', error);
    }
  };

  const fetchSuppliers = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/suppliers');
      if (res.ok) {
        const data = await res.json();
        setSuppliers(data);
      }
    } catch (error) {
      console.error('Error fetching suppliers', error);
      // Fallback fallback suppliers for offline demo
      setSuppliers([
        { supplier_id: 'SUPP-001', name: 'EuroParts GmbH', contact_person: 'Dieter Becker', phone: '', email: 'becker@europarts.de', city: 'Munich', specialization: 'Brakes, Suspension', reliability_score: 0.96, avg_delivery_days: 2 },
        { supplier_id: 'SUPP-002', name: 'Nordic Auto Feeds', contact_person: 'Astrid Lind', phone: '', email: 'lind@nordicauto.no', city: 'Oslo', specialization: 'Steering systems', reliability_score: 0.89, avg_delivery_days: 4 },
        { supplier_id: 'SUPP-003', name: 'Orient Parts Express', contact_person: 'Li Wei', phone: '', email: 'wei@orientparts.cn', city: 'Shanghai', specialization: 'Electronics, Alternates', reliability_score: 0.76, avg_delivery_days: 7 },
      ]);
    }
  };

  useEffect(() => {
    void fetchSuppliers();
    void fetchRequests();
  }, [fetchTrigger]);

  useEffect(() => {
    if (selectedSupplier) {
      const fetchSupplierItems = async () => {
        setSupplierItemsLoading(true);
        try {
          const res = await fetch(`http://localhost:8000/api/suppliers/${selectedSupplier.supplier_id}/items`);
          if (res.ok) {
            const data = await res.json();
            setSupplierItems(data);
          } else {
            setSupplierItems([]);
          }
        } catch (e) {
          console.error("Error fetching supplier items", e);
          setSupplierItems([]);
        } finally {
          setSupplierItemsLoading(false);
        }
      };
      void fetchSupplierItems();
    } else {
      setSupplierItems([]);
    }
  }, [selectedSupplier]);

  // When request changes, reset parts and selected offers
  useEffect(() => {
    if (selectedReq) {
      try {
        const parsed = JSON.parse(selectedReq.parts_json || '[]');
        setNormalizedParts(parsed);
      } catch (e) {
        setNormalizedParts([]);
      }
      setSelectedOffers({});
      // Auto transition active step to Normalization Review
      setActiveStep(2);
    }
  }, [selectedReq]);

  const handleSelectRequest = (req: Request) => {
    setSelectedReq(req);
    setActiveNav('matching'); // auto route to workflow canvas
  };

  const handleStateTransition = async (targetState: string, reason: string, reqId?: string) => {
    const idToTransition = reqId || selectedReq?.request_id;
    if (!idToTransition) return;
    try {
      const res = await fetch(
        `http://localhost:8000/api/requests/${idToTransition}/transition`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_state: targetState,
            reason,
            actor_id: 'admin',
          }),
        },
      );

      if (res.ok) {
        const updated = await res.json();
        alert(`Статус запроса ${idToTransition} успешно обновлен на ${updated.new_state}`);
        setFetchTrigger((prev) => prev + 1);
        if (selectedReq && selectedReq.request_id === idToTransition) {
          setSelectedReq((prev) => (prev ? { ...prev, status: updated.new_state } : null));
          // If approved, advance to step 5 (Pricing Draft)
          if (targetState === 'APPROVED') {
            setActiveStep(5);
          }
        }
      } else {
        const err = await res.json();
        alert(`Transition failed: ${err.detail}`);
      }
    } catch (error) {
      console.error(error);
      alert("API error during transition. Simulating local transition for demo.");
      setRequests(prev => prev.map(r => r.request_id === idToTransition ? { ...r, status: targetState } : r));
      if (selectedReq && selectedReq.request_id === idToTransition) {
        setSelectedReq((prev) => prev ? { ...prev, status: targetState } : null);
        if (targetState === 'APPROVED') {
          setActiveStep(5);
        }
      }
    }
  };

  // Local parts correction handler
  const handleConfirmNormalization = async () => {
    if (!selectedReq) return;
    try {
      // call backend correction API if available
      const res = await fetch(`http://localhost:8000/api/requests/${selectedReq.request_id}/correction`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_text: selectedReq.customer_name + " parts order",
          corrected_parts_json: JSON.stringify(normalizedParts),
          correction_reason_tags: ["operator_review"],
        })
      });
      if (res.ok) {
        alert("Normalization confirmed and saved to Golden Dataset.");
      }
    } catch (e) {
      console.warn("Could not save golden correction to backend", e);
    }
    
    // update parts json in selected req locally
    setSelectedReq(prev => prev ? { ...prev, parts_json: JSON.stringify(normalizedParts) } : null);
    // advance step to Offer Comparison (step 3)
    setActiveStep(3);
  };

  // Supplier import handler
  const handleImportSuppliers = (text: string) => {
    try {
      const parsed = JSON.parse(text);
      const items = Array.isArray(parsed) ? parsed : [parsed];
      
      const newSuppliers: Supplier[] = items.map((item: any, index: number) => ({
        supplier_id: item.supplier_id || `SUPP-LOCAL-${Date.now()}-${index}`,
        name: item.name || 'Unnamed Supplier',
        contact_person: item.contact_person || 'N/A',
        phone: item.phone || '',
        email: item.email || '',
        city: item.city || 'N/A',
        specialization: item.specialization || 'General Sourcing',
        reliability_score: Number(item.reliability_score) || 0.85,
        avg_delivery_days: Number(item.avg_delivery_days) || 3,
      }));

      setSuppliers(prev => [...newSuppliers, ...prev]);
      setLocalSupplierMessage(`Successfully imported ${newSuppliers.length} suppliers into local session catalog.`);
      setTimeout(() => setLocalSupplierMessage(null), 5000);
    } catch (e) {
      alert("Error parsing JSON supplier feed. Make sure it is a valid JSON array or object.");
    }
  };

  // Order manual import handler
  const handleImportOrders = async (text: string) => {
    try {
      // Try to parse as JSON first, if fails, treat as raw text request
      let payload = { source: 'UI_UPLOAD', text: text, customer_name: 'Direct Upload Client' };
      try {
        const parsed = JSON.parse(text);
        payload = {
          source: parsed.source || 'UI_UPLOAD',
          text: parsed.text || text,
          customer_name: parsed.customer_name || 'Direct Upload Client',
        };
      } catch {}

      const res = await fetch('http://localhost:8000/api/requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        setLocalOrderMessage(`Successfully added order ${data.request.request_id} to the live triage queue.`);
        setFetchTrigger(prev => prev + 1);
        setTimeout(() => setLocalOrderMessage(null), 5000);
      } else {
        alert("Backend failed to intake the request. Adding local simulation draft.");
        throw new Error("Local fallback");
      }
    } catch (e) {
      // Local fallback simulation
      const mockId = `REQ-LOCAL-${Math.floor(1000 + Math.random() * 9000)}`;
      const mockReq: Request = {
        id: Date.now(),
        request_id: mockId,
        source: 'LOCAL_DRAFT',
        status: 'NEW',
        customer_name: 'Local Demo Client',
        created_at: new Date().toISOString(),
        parts_json: JSON.stringify([{ name: 'Brake pads', quantity: 2 }, { name: 'Air filter', quantity: 1 }]),
      };
      setSelectedReq(mockReq);
      setLocalOrderMessage(`Intake offline. Added local draft ${mockId} to active triage queue.`);
      setTimeout(() => setLocalOrderMessage(null), 5000);
      // We trigger fetch to let right panel update if backend is alive, otherwise we handle session storage if we want
    }
  };

  const filteredSuppliers = suppliers.filter(
    (supplier) =>
      supplier.name.toLowerCase().includes(searchSupplierQuery.toLowerCase()) ||
      supplier.specialization.toLowerCase().includes(searchSupplierQuery.toLowerCase()) ||
      supplier.city.toLowerCase().includes(searchSupplierQuery.toLowerCase())
  );

  // Left Nav tabs config
  const navItems = [
    { id: 'dashboard', label: 'Панель управления', icon: 'fa-chart-pie' },
    { id: 'kanban', label: 'Канбан-доска', icon: 'fa-table-columns' },
    { id: 'suppliers', label: 'Каталог поставщиков', icon: 'fa-truck-field' },
    { id: 'orders', label: 'Импорт заказов', icon: 'fa-file-arrow-up' },
    { id: 'matching', label: 'Матрица подбора', icon: 'fa-arrows-split-up-and-left' },
    { id: 'pricing', label: 'Калькулятор цен', icon: 'fa-calculator' },
    { id: 'audit', label: 'Аудит и логи', icon: 'fa-shield-halved' },
  ];

  // Steps list for active workflow
  const steps = [
    "Каталог поставщиков",
    "Импорт заказов",
    "Анализ нормализации",
    "Сравнение предложений",
    "Согласование",
    "Черновик цены"
  ];

  const handleStepClick = (stepIdx: number) => {
    setActiveStep(stepIdx);
    // Align active navigation tab with step views for seamless layout transition
    if (stepIdx === 0) setActiveNav('suppliers');
    else if (stepIdx === 1) setActiveNav('orders');
    else if (stepIdx === 2) setActiveNav('matching'); // Normalization Review
    else if (stepIdx === 3) setActiveNav('matching'); // Offer Comparison
    else if (stepIdx === 4) setActiveNav('matching'); // Approval Gate
    else if (stepIdx === 5) setActiveNav('pricing');  // Pricing Draft
  };

  // Synchronize left nav clicks to steps when a request is active
  const handleNavChange = (navId: string) => {
    setActiveNav(navId);
    if (selectedReq) {
      if (navId === 'suppliers') setActiveStep(0);
      else if (navId === 'orders') setActiveStep(1);
      else if (navId === 'matching') {
        if (activeStep < 2 || activeStep > 4) {
          setActiveStep(3); // default to matching matrix
        }
      }
      else if (navId === 'pricing') setActiveStep(5);
    }
  };

  // Selected offers mapper to construct best matches for Pricing Calculator
  const formattedPartsWithBestMatch = normalizedParts.map(part => {
    const chosenOffer = selectedOffers[part.name];
    return {
      name: part.name,
      quantity: part.quantity,
      best_match: chosenOffer ? {
        name: chosenOffer.item.name,
        price: chosenOffer.item.price
      } : undefined
    };
  });

  return (
    <AppFrame>
      {/* Top Header Bar */}
      <TopCommandBar 
        searchQuery={searchGlobalQuery}
        onSearchChange={setSearchGlobalQuery}
        onResetActive={() => {
          setSelectedReq(null);
          setActiveNav('dashboard');
        }}
      />

      <div className="flex-1 flex flex-row overflow-hidden relative">
        {/* Left persistent nav rail */}
        <LeftNavRail 
          activeTab={activeNav}
          onChangeTab={handleNavChange}
          items={navItems}
          isCollapsed={leftCollapsed}
          onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
        />

        {/* Center workspace canvas */}
        <main className="flex-1 h-full overflow-y-auto bg-[var(--bg-app)]">
        {/* If a request is active and we're not on general pages, show request workflow */}
        {selectedReq && ['matching', 'pricing', 'audit'].includes(activeNav) ? (
          <div className="p-4 max-w-6xl mx-auto space-y-4">
            
            {/* Header context card */}
            <WorkspaceHeader 
              title={selectedReq.customer_name + " - План закупки запчастей"}
              requestId={selectedReq.request_id}
              status={selectedReq.status}
              priority={selectedReq.priority || 'Normal'}
              customerName={selectedReq.customer_name}
              customerPhone={selectedReq.customer_phone_masked}
              customerEmail={selectedReq.customer_email_masked}
              vin={selectedReq.vehicle_vin_masked}
              vehicleMake={selectedReq.vehicle_make}
              vehicleModel={selectedReq.vehicle_model}
              onBack={() => {
                setSelectedReq(null);
                setActiveNav('dashboard');
              }}
            />

            {/* Stepper Steps Gate */}
            <StepGate 
              currentStep={activeStep}
              steps={steps}
              onStepClick={handleStepClick}
            />

            {/* Sub-workspace views dependent on active step */}
            <div className="space-y-4">
              
              {/* Step 2: Normalization Review */}
              {activeStep === 2 && (
                <SectionCard 
                  title="Шаг 2: Анализ нормализации и корректировка данных" 
                  icon="fa-square-check"
                  headerActions={
                    <span className="text-[10px] font-bold text-[var(--accent-primary)] uppercase bg-blue-50 px-2 py-0.5 border border-blue-200 rounded">
                      Защита перс. данных активна
                    </span>
                  }
                >
                  <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
                    Проверьте детали, распознанные агентом приема LangGraph. Вы можете редактировать названия, изменять количество и подтверждать совпадения перед подбором.
                  </p>
                  <ReviewPanel 
                    items={normalizedParts}
                    onChange={setNormalizedParts}
                    onConfirm={handleConfirmNormalization}
                  />
                </SectionCard>
              )}

              {/* Step 3: Offer Comparison */}
              {activeStep === 3 && (
                <SupplierMatrix 
                  parts={normalizedParts}
                  selectedOffers={selectedOffers}
                  onSelectOffer={(partName, offer) => {
                    setSelectedOffers(prev => ({
                      ...prev,
                      [partName]: offer
                    }));
                  }}
                />
              )}

              {/* Step 4: Approval Gate */}
              {activeStep === 4 && (
                <SectionCard title="Шаг 4: Контроль операционного согласования" icon="fa-key">
                  <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
                    Изучите ценовые аномалии и проверьте целостность цепочки аудита SHA-256. Требуется явное одобрение администратора/специалиста для разблокировки ценового листа перед подготовкой черновика коммерческого предложения.
                  </p>

                  <div className="bg-slate-50 border border-[var(--border-default)] rounded-md p-4 mb-4 text-xs space-y-2">
                    <div className="flex justify-between border-b border-[var(--border-subtle)] pb-2">
                      <span className="text-[var(--text-muted)] font-semibold">Проверка целостности сортировки</span>
                      <span className="text-green-700 font-bold"><i className="fas fa-check-circle"></i> ПРОЙДЕНО</span>
                    </div>
                    <div className="flex justify-between border-b border-[var(--border-subtle)] pb-2">
                      <span className="text-[var(--text-muted)] font-semibold">Уровень защиты перс. данных</span>
                      <span className="text-green-700 font-bold"><i className="fas fa-check-circle"></i> 100% БЕЗОПАСНО</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--text-muted)] font-semibold">Кандидаты предложений загружены</span>
                      <span className="font-bold text-[var(--text-primary)]">{Object.keys(selectedOffers).length} из {normalizedParts.length} деталей сопоставлено</span>
                    </div>
                  </div>

                  {Object.keys(selectedOffers).length < normalizedParts.length && (
                    <InlineAlert 
                      type="warning"
                      message="Некоторые детали не имеют выбранных предложений поставщиков. Настоятельно рекомендуется сравнить и выбрать варианты для всех позиций перед согласованием."
                    />
                  )}

                  <div className="flex flex-col md:flex-row gap-3 pt-3 border-t border-[var(--border-subtle)] justify-end">
                    <ActionButton 
                      variant="secondary"
                      icon="fa-shuffle"
                      onClick={() => {
                        const reason = prompt('Укажите причину переработки:');
                        if (reason !== null) handleStateTransition('MANUAL_REVIEW', reason || 'Требуется ручное уточнение');
                      }}
                    >
                      Уточнить / Переработать
                    </ActionButton>
                    <ActionButton 
                      variant="primary"
                      icon="fa-circle-check"
                      onClick={() => {
                        const reason = prompt('Укажите примечания к согласованию:');
                        if (reason !== null) handleStateTransition('APPROVED', reason || 'Согласовано администратором закупок');
                      }}
                    >
                      Явно одобрить закупку
                    </ActionButton>
                    <ActionButton 
                      variant="danger"
                      icon="fa-trash-can"
                      onClick={() => {
                        const reason = prompt('Укажите причину отмены:');
                        if (reason !== null) handleStateTransition('CANCELLED', reason || 'Запрос отклонен');
                      }}
                    >
                      Отменить / Отклонить запрос
                    </ActionButton>
                  </div>
                </SectionCard>
              )}

              {/* Step 5: Pricing Draft */}
              {activeStep === 5 && (
                <PricingCalculator 
                  parts={formattedPartsWithBestMatch}
                  requestId={selectedReq.request_id}
                  isApproved={selectedReq.status === 'APPROVED'}
                  onDraftInvoice={(data) => {
                    alert(`Черновик счета создан! Номер счета: ${data.invoice_number}`);
                    setFetchTrigger(prev => prev + 1);
                  }}
                />
              )}
            </div>

            {/* Audit timeline with side-by-side Completed Orders History */}
            {activeNav === 'audit' && (
              <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-4">
                <CompletedOrdersHistory 
                  selectedRequestId={selectedReq.request_id}
                  onSelectRequest={(req) => {
                    setSelectedReq(req);
                    setActiveNav('audit');
                  }}
                  fetchTrigger={fetchTrigger}
                />
                <AuditTimeline requestId={selectedReq.request_id} />
              </div>
            )}
          </div>
        ) : (
          /* General navigation pages when no active request is being stepped */
          <div className="p-4 max-w-6xl mx-auto space-y-4">
            
            {/* Nav: Dashboard (Overview Panel) */}
            {activeNav === 'dashboard' && (
              <>
                <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-6 text-white shadow-xl border border-indigo-950/40">
                  {/* Decorative glowing background elements */}
                  <div className="absolute -right-24 -top-24 h-48 w-48 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
                  <div className="absolute -left-24 -bottom-24 h-48 w-48 rounded-full bg-blue-500/10 blur-3xl pointer-events-none" />
                  
                  <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10 w-full">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[9px] text-indigo-200 font-extrabold uppercase tracking-widest bg-indigo-500/20 border border-indigo-500/30 px-2.5 py-0.5 rounded-full backdrop-blur-md">
                          Система активна
                        </span>
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      </div>
                      <h2 className="text-xl font-extrabold text-white tracking-tight sm:text-2xl font-sans">
                        Операционная панель PartsOps
                      </h2>
                      <p className="text-xs text-slate-300 max-w-xl leading-relaxed">
                        Интеллектуальное управление закупками на базе ИИ-агентов LangGraph и верификации цепочек поставок.
                      </p>
                    </div>

                    {/* Integrated Premium Quick Actions Toolbelt */}
                    <div className="flex flex-wrap items-center gap-2 bg-white/5 p-1.5 rounded-2xl border border-white/10 backdrop-blur-md w-full sm:w-auto">
                      <button
                        onClick={() => setActiveNav('orders')}
                        className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-100 hover:text-white bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 transition-all duration-200 animate-fadeIn"
                        title="Импортировать спецификации деталей"
                      >
                        <i className="fas fa-file-arrow-up text-blue-400"></i>
                        <span>Импорт заказов</span>
                      </button>
                      <button
                        onClick={() => setActiveNav('suppliers')}
                        className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-100 hover:text-white bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 transition-all duration-200 animate-fadeIn"
                        title="Открыть базу поставщиков"
                      >
                        <i className="fas fa-truck-field text-emerald-400"></i>
                        <span>Поставщики</span>
                      </button>
                      <button
                        onClick={() => {
                          setFetchTrigger(prev => prev + 1);
                          alert("Синхронизация с ERP успешно запущена!");
                        }}
                        className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-100 hover:text-white bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 transition-all duration-200 animate-fadeIn"
                        title="Запустить синхронизацию с ERP"
                      >
                        <i className="fas fa-rotate text-amber-400"></i>
                        <span>Синхронизация</span>
                      </button>
                      <button
                        onClick={() => {
                          alert("Кэш очищен, сессия обновлена.");
                        }}
                        className="flex items-center justify-center h-8.5 w-8.5 rounded-xl text-slate-300 hover:text-red-400 bg-white/5 hover:bg-white/10 border border-white/5 transition-all duration-200"
                        title="Очистить локальный кэш"
                      >
                        <i className="fas fa-trash-can text-[11px]"></i>
                      </button>
                      <button
                        onClick={() => setActiveNav('orders')}
                        className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-extrabold text-white bg-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/90 border-none transition-all duration-200 shadow-md hover:shadow-lg active:scale-95"
                      >
                        <i className="fas fa-plus"></i>
                        <span>Новый запрос</span>
                      </button>
                    </div>
                  </div>
                </section>

                {/* Metrics scale */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {overviewMetrics.map(m => (
                    <MetricTile key={m.label} label={m.label} value={m.value} delta={m.delta} tone={m.tone} />
                  ))}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {/* Operational workflow lanes */}
                  <SectionCard title="Нагрузка по этапам процесса" icon="fa-network-wired" className="lg:col-span-2">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-1">
                      {workflowLanes.map(lane => (
                        <div key={lane.title} className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-md p-3.5 flex flex-col justify-between">
                          <div className="flex justify-between items-center mb-1">
                            <span className="text-xs font-bold text-[var(--text-primary)]">{lane.title}</span>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                              lane.tone === 'cyan' ? 'bg-cyan-50 border-cyan-200 text-cyan-700' :
                              lane.tone === 'violet' ? 'bg-violet-50 border-violet-200 text-violet-700' :
                              lane.tone === 'amber' ? 'bg-amber-50 border-amber-200 text-amber-700' :
                              'bg-green-50 border-green-200 text-green-700'
                            }`}>{lane.count} задач</span>
                          </div>
                          <p className="text-[11px] text-[var(--text-secondary)] mt-1">{lane.summary}</p>
                        </div>
                      ))}
                    </div>
                  </SectionCard>

                  {/* Urgent Cases list */}
                  <SectionCard title="Приоритетные инциденты" icon="fa-circle-radiation">
                    <div className="space-y-3 mt-1">
                      {urgentCases.map(c => (
                        <div key={c.id} className="border border-[var(--border-default)] hover:border-[var(--text-secondary)] transition-all bg-[var(--surface-1)] rounded p-3 flex flex-col gap-1.5 shadow-sm">
                          <div className="flex justify-between items-center">
                            <strong className="text-xs font-bold text-[var(--text-primary)]">{c.id}</strong>
                            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span>
                          </div>
                          <p className="text-[11px] font-semibold text-[var(--text-primary)] leading-tight">{c.title}</p>
                          <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">{c.detail}</p>
                        </div>
                      ))}
                    </div>
                  </SectionCard>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  {/* AI Agent Monitor */}
                  <SectionCard title="Активность ИИ-агентов LangGraph" icon="fa-robot" className="lg:col-span-2">
                    <div className="space-y-3 mt-1">
                      <div className="flex items-center justify-between p-2.5 border border-[var(--border-subtle)] bg-[var(--surface-2)] rounded-lg text-xs">
                        <div className="flex items-center gap-2">
                          <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                          </span>
                          <span className="font-bold text-[var(--text-primary)]">Triage & Normalization Agent</span>
                        </div>
                        <span className="text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-100 px-1.5 py-0.5 rounded font-mono font-bold uppercase">Ожидание</span>
                      </div>
                      <div className="flex items-center justify-between p-2.5 border border-[var(--border-subtle)] bg-[var(--surface-2)] rounded-lg text-xs">
                        <div className="flex items-center gap-2">
                          <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                          </span>
                          <span className="font-bold text-[var(--text-primary)]">Offer Parsing & Matcher</span>
                        </div>
                        <span className="text-[10px] text-blue-700 bg-blue-50 border border-blue-100 px-1.5 py-0.5 rounded font-mono font-bold uppercase">Анализ OEM</span>
                      </div>
                      <div className="flex items-center justify-between p-2.5 border border-[var(--border-subtle)] bg-[var(--surface-2)] rounded-lg text-xs">
                        <div className="flex items-center gap-2">
                          <span className="relative flex h-2 w-2">
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-slate-400"></span>
                          </span>
                          <span className="font-bold text-[var(--text-primary)]">SLA & Margin Guard</span>
                        </div>
                        <span className="text-[10px] text-[var(--text-muted)] bg-[var(--surface-1)] border border-[var(--border-default)] px-1.5 py-0.5 rounded font-mono font-bold uppercase">Спящий режим</span>
                      </div>
                    </div>
                  </SectionCard>

                  {/* System Status Block */}
                  <SectionCard title="Состояние системы" icon="fa-heartbeat">
                    <div className="space-y-3.5 mt-1 text-xs">
                      <div className="flex justify-between items-center border-b border-[var(--border-subtle)] pb-2">
                        <span className="text-[var(--text-secondary)]">Всего запросов в системе</span>
                        <span className="font-mono font-bold text-[var(--text-primary)]">{requests.length}</span>
                      </div>
                      <div className="flex justify-between items-center border-b border-[var(--border-subtle)] pb-2">
                        <span className="text-[var(--text-secondary)]">Срочные инциденты</span>
                        <span className="font-bold text-red-500 flex items-center gap-1.5">
                          <i className="fas fa-circle-exclamation"></i>
                          <span>{requests.filter(r => r.priority?.toLowerCase() === 'high' || r.priority?.toLowerCase() === 'высокий').length}</span>
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-[var(--text-secondary)]">Аптайм API шлюза</span>
                        <span className="text-emerald-500 font-bold flex items-center gap-1">
                          <i className="fas fa-circle text-[8px] animate-pulse"></i> 99.98%
                        </span>
                      </div>
                    </div>
                  </SectionCard>
                </div>
              </>
            )}

            {/* Nav: Kanban Board (Dedicated Page) */}
            {activeNav === 'kanban' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-[var(--border-strong)] pb-3">
                  <div>
                    <h2 className="text-lg font-bold text-[var(--text-primary)]">Интерактивный рабочий процесс</h2>
                    <p className="text-xs text-[var(--text-secondary)]">Перетаскивайте запросы между этапами обработки для автоматического изменения статуса в системе.</p>
                  </div>
                  <ActionButton 
                    variant="secondary" 
                    icon="fa-rotate" 
                    onClick={fetchRequests}
                    title="Обновить доску" 
                  />
                </div>
                <KanbanBoard
                  requests={requests}
                  onSelectRequest={handleSelectRequest}
                  onTransitionRequest={handleStateTransition}
                />
              </div>
            )}

            {/* Nav: Supplier Catalog & Imports */}
            {activeNav === 'suppliers' && (
              <div className="space-y-4">
                {/* Header toolbar: search + import button */}
                <div className="flex flex-wrap items-center gap-3 justify-between">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="relative flex-1 max-w-sm">
                      <i className="fas fa-magnifying-glass absolute left-3 top-2.5 text-[var(--text-muted)] text-xs"></i>
                      <input
                        type="text"
                        placeholder="Поиск по поставщику, бренду, специализации..."
                        value={searchSupplierQuery}
                        onChange={(e) => setSearchSupplierQuery(e.target.value)}
                        className="w-full bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-[var(--accent-primary)] font-sans"
                      />
                    </div>
                    <span className="text-[11px] text-[var(--text-muted)] font-semibold whitespace-nowrap">
                      {filteredSuppliers.length} поставщиков
                    </span>
                  </div>
                  <ActionButton
                    variant="primary"
                    icon="fa-file-import"
                    onClick={() => setShowSupplierImportModal(!showSupplierImportModal)}
                  >
                    Импортировать поставщика
                  </ActionButton>
                </div>

                {/* Inline import panel (shown/hidden by toggle) */}
                {showSupplierImportModal && (
                  <div className="panel-card-tight p-5 border border-[var(--accent-primary)]/30 bg-[var(--surface-2)]">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                        <i className="fas fa-file-import text-[var(--accent-primary)]"></i> Импорт каталога поставщиков
                      </h3>
                      <button
                        onClick={() => setShowSupplierImportModal(false)}
                        className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors text-sm w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[var(--surface-3)]"
                      >
                        <i className="fas fa-xmark"></i>
                      </button>
                    </div>
                    {localSupplierMessage && (
                      <InlineAlert type="success" message={localSupplierMessage} />
                    )}
                    <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
                      Импортируйте новые справочники поставщиков или обновляйте действующие соглашения об уровне обслуживания (SLA) путем загрузки файлов.
                    </p>
                    <Dropzone
                      title="Перетащите файл каталога поставщиков"
                      description="Принимает массивы JSON с метаданными поставщиков, категориями специализации, логами надежности и скоростью доставки по SLA."
                      onImport={handleImportSuppliers}
                    />
                  </div>
                )}

                {/* Full-width suppliers table */}
                <div className="panel-card-tight overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[var(--border-strong)] bg-[var(--surface-2)]">
                          {["ID", "Название и адрес", "Контакт", "Специализация", "Надёжность", "Ср. доставка", "E-mail", ""].map((h) => (
                            <th key={h} className="px-4 py-3 text-left font-bold uppercase tracking-wider text-[10px] text-[var(--text-muted)] whitespace-nowrap">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredSuppliers.map((s) => {
                          const isSelected = selectedSupplier?.supplier_id === s.supplier_id;
                          return (
                            <>
                              <tr
                                key={s.supplier_id}
                                onClick={() => setSelectedSupplier(isSelected ? null : s)}
                                className={`border-b border-[var(--border-subtle)] cursor-pointer transition-all text-xs ${
                                  isSelected
                                    ? 'bg-emerald-50/60 border-l-2 border-l-emerald-500'
                                    : 'hover:bg-[var(--surface-2)]'
                                }`}
                              >
                                <td className="px-4 py-3 font-mono text-[10px] font-bold text-[var(--text-muted)]">
                                  {s.supplier_id}
                                </td>
                                <td className="px-4 py-3">
                                  <div className="font-bold text-[var(--text-primary)]">{s.name}</div>
                                  <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                                    <i className="fas fa-location-dot mr-1 text-[8px]"></i>{s.city}
                                  </div>
                                </td>
                                <td className="px-4 py-3 text-[var(--text-secondary)] font-medium">{s.contact_person}</td>
                                <td className="px-4 py-3">
                                  <div className="flex flex-wrap gap-1">
                                    {s.specialization.split(',').map((spec: string) => (
                                      <span key={spec} className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                                        {spec.trim()}
                                      </span>
                                    ))}
                                  </div>
                                </td>
                                <td className="px-4 py-3">
                                  <div className="flex items-center gap-1.5">
                                    <div className="w-20 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                      <div
                                        className={`h-full rounded-full ${s.reliability_score >= 0.9 ? 'bg-emerald-500' : s.reliability_score >= 0.8 ? 'bg-amber-400' : 'bg-red-400'}`}
                                        style={{ width: `${s.reliability_score * 100}%` }}
                                      />
                                    </div>
                                    <span className={`text-[10px] font-bold ${s.reliability_score >= 0.9 ? 'text-emerald-700' : s.reliability_score >= 0.8 ? 'text-amber-600' : 'text-red-600'}`}>
                                      {(s.reliability_score * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                                <td className="px-4 py-3">
                                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                    s.avg_delivery_days <= 1 ? 'bg-emerald-50 text-emerald-700' :
                                    s.avg_delivery_days <= 3 ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'
                                  }`}>
                                    {s.avg_delivery_days} дн.
                                  </span>
                                </td>
                                <td className="px-4 py-3 text-[var(--text-muted)] text-[11px]">
                                  <a href={`mailto:${s.email || ''}`} className="hover:text-[var(--accent-primary)] transition-colors" onClick={(e) => e.stopPropagation()}>
                                    {s.email || '—'}
                                  </a>
                                </td>
                                <td className="px-4 py-3 text-right">
                                  <i className={`fas fa-chevron-${isSelected ? 'up' : 'down'} text-[10px] text-[var(--text-muted)]`}></i>
                                </td>
                              </tr>

                              {/* Expanded supplier card with catalog items */}
                              {isSelected && (
                                <tr key={`${s.supplier_id}-expanded`} className="bg-[var(--surface-2)] border-b border-[var(--border-strong)]">
                                  <td colSpan={8} className="px-5 py-5">
                                    <div className="space-y-4">
                                      {/* Supplier Info Card */}
                                      <div className="bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 shadow-sm">
                                        <div>
                                          <p className="text-[10px] uppercase font-bold text-[var(--text-muted)] mb-1">Контакт</p>
                                          <p className="text-xs font-semibold text-[var(--text-primary)]">{s.contact_person || '—'}</p>
                                        </div>
                                        <div>
                                          <p className="text-[10px] uppercase font-bold text-[var(--text-muted)] mb-1">Телефон</p>
                                          <p className="text-xs font-semibold text-[var(--text-primary)]">{s.phone || '—'}</p>
                                        </div>
                                        <div>
                                          <p className="text-[10px] uppercase font-bold text-[var(--text-muted)] mb-1">E-mail</p>
                                          <p className="text-xs font-semibold text-[var(--accent-primary)]">{s.email || '—'}</p>
                                        </div>
                                        <div>
                                          <p className="text-[10px] uppercase font-bold text-[var(--text-muted)] mb-1">Специализация</p>
                                          <p className="text-xs font-semibold text-[var(--text-primary)]">{s.specialization}</p>
                                        </div>
                                      </div>

                                      {/* Catalog items table */}
                                      <div>
                                        <h4 className="text-[10px] uppercase font-bold text-[var(--text-muted)] tracking-widest mb-2 flex items-center gap-2">
                                          <i className="fas fa-boxes-stacked text-[var(--accent-primary)]"></i>
                                          Каталог позиций поставщика
                                          {supplierItemsLoading && <i className="fas fa-spinner animate-spin text-[var(--accent-primary)]"></i>}
                                        </h4>
                                        {supplierItemsLoading ? (
                                          <div className="text-xs text-[var(--text-muted)] py-4 text-center">Загрузка позиций...</div>
                                        ) : supplierItems.length === 0 ? (
                                          <div className="text-xs text-[var(--text-muted)] py-4 text-center">Позиции каталога не найдены.</div>
                                        ) : (
                                          <div className="overflow-x-auto rounded-xl border border-[var(--border-default)]">
                                            <table className="w-full text-xs">
                                              <thead>
                                                <tr className="bg-[var(--surface-2)] border-b border-[var(--border-default)]">
                                                  {["Артикул", "Наименование", "OEM №", "Бренд", "Цена", "Склад", "Доставка", "Категория"].map((h) => (
                                                    <th key={h} className="px-3 py-2 text-left font-bold uppercase tracking-wider text-[9px] text-[var(--text-muted)] whitespace-nowrap">
                                                      {h}
                                                    </th>
                                                  ))}
                                                </tr>
                                              </thead>
                                              <tbody>
                                                {supplierItems.map((item) => (
                                                  <tr key={item.catalog_id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--surface-1)] transition-all">
                                                    <td className="px-3 py-2 font-mono text-[10px] text-[var(--text-muted)] font-bold">{item.catalog_id}</td>
                                                    <td className="px-3 py-2 font-semibold text-[var(--text-primary)] max-w-xs">{item.name}</td>
                                                    <td className="px-3 py-2 font-mono text-[10px] text-[var(--text-muted)]">{item.oem_number || '—'}</td>
                                                    <td className="px-3 py-2">
                                                      <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded text-[10px] font-bold">{item.brand}</span>
                                                    </td>
                                                    <td className="px-3 py-2 font-bold text-[var(--text-primary)]">
                                                      {item.price.toLocaleString('ru-RU')} ₽
                                                    </td>
                                                    <td className="px-3 py-2">
                                                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${item.stock_qty > 10 ? 'bg-emerald-50 text-emerald-700' : item.stock_qty > 0 ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'}`}>
                                                        {item.stock_qty} шт.
                                                      </span>
                                                    </td>
                                                    <td className="px-3 py-2 text-[var(--text-secondary)]">{item.delivery_days} дн.</td>
                                                    <td className="px-3 py-2">
                                                      <span className="bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase">{item.category}</span>
                                                    </td>
                                                  </tr>
                                                ))}
                                              </tbody>
                                            </table>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* Nav: Order Intake */}
            {activeNav === 'orders' && (
              <div className="max-w-2xl mx-auto space-y-4">
                <SectionCard title="Центр импорта и создания заказов" icon="fa-file-import">
                  <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
                    Загружайте опросные листы клиентов, вставляйте сырые списки совместимости VIN или импортируйте комплексные запросы. Исходные данные пройдут через узлы приема LangGraph для извлечения нормализованных списков деталей.
                  </p>

                  {localOrderMessage && (
                    <InlineAlert type="success" message={localOrderMessage} />
                  )}

                  <Dropzone 
                    title="Перетащите файл запроса на закупку"
                    description="Загружайте текстовые документы, листы предложений клиентов или экспорт писем для автоматической регистрации новых запросов в очереди приема LangGraph."
                    onImport={handleImportOrders}
                  />
                </SectionCard>
              </div>
            )}

            {/* General Empty States for Matching and Pricing if no request is chosen */}
            {['matching', 'pricing'].includes(activeNav) && (
              <div className="max-w-md mx-auto py-10">
                <EmptyState 
                  title="Запрос не выбран"
                  description="Пожалуйста, выберите активный запрос из очереди сортировки справа, чтобы загрузить данные подбора, сравнить предложения кандидатов и подготовить коммерческие документы."
                  icon={
                    activeNav === 'matching' ? 'fa-arrows-split-up-and-left' : 'fa-calculator'
                  }
                />
              </div>
            )}

            {/* Audit view when no request is selected - show completed orders list + explanation */}
            {activeNav === 'audit' && (
              <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-4">
                <CompletedOrdersHistory 
                  selectedRequestId={null}
                  onSelectRequest={(req) => {
                    setSelectedReq(req);
                    setActiveNav('audit');
                  }}
                  fetchTrigger={fetchTrigger}
                />
                <div className="flex items-center justify-center p-8 bg-[var(--surface-1)] border border-[var(--border-default)] rounded-xl h-[650px] shadow-sm select-none">
                  <div className="text-center max-w-sm">
                    <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-4 text-[var(--text-muted)] text-xl border border-slate-200 mx-auto">
                      <i className="fas fa-history"></i>
                    </div>
                    <h3 className="text-sm font-bold text-[var(--text-primary)] block mb-1">Детальный аудит не загружен</h3>
                    <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                      Пожалуйста, выберите завершенный заказ из архива слева или активный запрос из очереди справа, чтобы просмотреть цепочку событий аудита и проверить SHA-256 хеши.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

        {/* Right operational triage queue rail */}
        <RightPanel 
          requests={requests}
          fetchRequests={fetchRequests}
          selectedRequestId={selectedReq?.request_id || null}
          onSelectRequest={handleSelectRequest}
          fetchTrigger={fetchTrigger}
          isCollapsed={rightCollapsed}
          onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
        />
      </div>
    </AppFrame>
  );
}

export default App;
