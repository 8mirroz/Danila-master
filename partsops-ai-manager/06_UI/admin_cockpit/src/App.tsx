import React, { useEffect, useState } from 'react';
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
import { EvidenceGatesWidget } from './components/EvidenceGatesWidget';
import { InvoicePreview } from './components/InvoicePreview';
import { LLMCostPanel } from './components/LLMCostPanel';
import { apiFetch, createEventSource } from './lib/api';
import { ChevronStepper } from './components/ChevronStepper';
import { SuppliersPage } from './components/SuppliersPage';
import { CommandPalette } from './components/CommandPalette';
import { PipelineMonitor } from './components/PipelineMonitor';
import { AgentOSPanel } from './components/AgentOSPanel';
import { MultiAgentOrchestraView } from './components/MultiAgentOrchestraView';
import { CrawlerIntakePanel } from './components/CrawlerIntakePanel';
import { ContractControlPanel } from './components/ContractControlPanel';
import { BlockedQueue } from './components/BlockedQueue';
import { TransitionActions } from './components/TransitionActions';
import { notify } from './lib/notify';
import { JobReportView } from './components/JobReportView';
import { HermesChatDrawer } from './components/HermesChatDrawer';
import { getPermissions } from './lib/rbac';
import type { Role } from './lib/rbac';
import { BatchSearchModal } from './components/BatchSearchModal';

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
  const [activeNav, setActiveNav] = useState<string>('dashboard');
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(2);
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const [searchGlobalQuery, setSearchGlobalQuery] = useState('');
  const [currentRole] = useState<Role>('ADMIN');

  const [requests, setRequests] = useState<Request[]>([]);
  const [normalizedParts, setNormalizedParts] = useState<Array<{ name: string; quantity: number }>>([]);
  const [selectedOffers, setSelectedOffers] = useState<Record<string, any>>({});
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [suppliersForPalette, setSuppliersForPalette] = useState<any[]>([]);
  const [lastErpSync, setLastErpSync] = useState<Date | null>(null);
  const [erpSyncText, setErpSyncText] = useState<string>('загрузка...');

  const fetchDataHealth = async () => {
    try {
      const res = await apiFetch('/api/admin/data-health');
      if (res.ok) {
        const data = await res.json();
        const lastSyncStr = data.freshness?.last_erp_sync;
        if (lastSyncStr) {
          setLastErpSync(new Date(lastSyncStr));
        } else {
          setLastErpSync(null);
        }
      }
    } catch (error) {
      console.error('Error fetching data health', error);
    }
  };

  useEffect(() => {
    void fetchDataHealth();
  }, [fetchTrigger]);

  useEffect(() => {
    const updateSyncText = () => {
      if (!lastErpSync) {
        setErpSyncText('нет данных');
        return;
      }
      const now = new Date();
      const diffSeconds = Math.max(0, Math.floor((now.getTime() - lastErpSync.getTime()) / 1000));
      if (diffSeconds < 60) {
        setErpSyncText(`${diffSeconds} сек. назад`);
      } else if (diffSeconds < 3600) {
        const mins = Math.floor(diffSeconds / 60);
        setErpSyncText(`${mins} мин. назад`);
      } else {
        const hours = Math.floor(diffSeconds / 3600);
        setErpSyncText(`${hours} ч. назад`);
      }
    };
    updateSyncText();
    const interval = setInterval(updateSyncText, 5000);
    return () => clearInterval(interval);
  }, [lastErpSync]);


  const fetchSuppliersForPalette = async () => {
    try {
      const res = await apiFetch('/api/suppliers');
      if (res.ok) {
        const data = await res.json();
        setSuppliersForPalette(data);
      }
    } catch (error) {
      console.error('Error fetching suppliers for palette', error);
    }
  };

  useEffect(() => {
    void fetchSuppliersForPalette();
  }, [fetchTrigger]);

  const resolveDropTarget = (req: Request, columnStatuses: string[]) => {
    const currentStatus = req.status;
    const validStates = columnStatuses;
    if (validStates.includes(currentStatus)) return null;
    if (validStates.includes('PART_EXTRACTION') && ['NEW', 'NORMALIZING', 'PARSING', 'VIN_CHECK'].includes(currentStatus)) return 'PART_EXTRACTION';
    if (validStates.includes('MATCHING') && currentStatus !== 'MATCHING') return 'MATCHING';
    if (validStates.includes('READY_FOR_APPROVAL')) return 'READY_FOR_APPROVAL';
    if (validStates.includes('APPROVED') && currentStatus !== 'APPROVED') return 'APPROVED';
    return validStates[0] || null;
  };

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

  useEffect(() => {
    void fetchRequests();
  }, [fetchTrigger]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(true);
      }
      if (e.key === 'Escape') {
        setIsCommandPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID || 'default';
    const es = createEventSource(tenantId);
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'requests_updated' || data.type === 'llm_cost_updated' || data.type === 'metrics_updated' || data.type === 'pipeline_runs_updated') {
          setFetchTrigger((prev) => prev + 1);
          if (data.type === 'pipeline_runs_updated') {
            window.dispatchEvent(new CustomEvent('orchestra-update', { detail: data }));
          }
        }
      } catch (e) {
        console.warn('SSE message parse error:', e);
      }
    };
    es.onerror = (err) => {
      console.warn('SSE connection error:', err);
    };
    return () => {
      es.close();
    };
  }, []);

  useEffect(() => {
    if (selectedReq) {
      try {
        const parsed = JSON.parse(selectedReq.parts_json || '[]');
        setNormalizedParts(parsed);
      } catch {
        setNormalizedParts([]);
      }
      setSelectedOffers({});
      setActiveStep(2);
    }
  }, [selectedReq]);

  const handleSelectRequest = (req: Request) => {
    setSelectedReq(req);
    setActiveNav('matching');
  };

  const handleStateTransition = async (targetState: string, reason: string, reqId?: string) => {
    const idToTransition = reqId || selectedReq?.request_id;
    if (!idToTransition) return;
    try {
      const res = await apiFetch(`/api/requests/${idToTransition}/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_state: targetState, reason, actor_id: 'admin' }),
      });
      if (res.ok) {
        const updated = await res.json();
        notify.transition(selectedReq?.status || 'CURRENT', updated.new_state);
        setFetchTrigger((prev) => prev + 1);
        if (selectedReq && selectedReq.request_id === idToTransition) {
          setSelectedReq((prev) => (prev ? { ...prev, status: updated.new_state } : null));
          if (targetState === 'APPROVED') setActiveStep(5);
        }
      } else {
        const err = await res.json();
        notify.error(`Ошибка смены статуса: ${err.detail}`);
      }
    } catch (error) {
      console.error(error);
      notify.info('Эмуляция локального перехода статуса');
      setRequests((prev) => prev.map((r) => (r.request_id === idToTransition ? { ...r, status: targetState } : r)));
      if (selectedReq && selectedReq.request_id === idToTransition) {
        setSelectedReq((prev) => (prev ? { ...prev, status: targetState } : null));
        if (targetState === 'APPROVED') setActiveStep(5);
      }
    }
  };

  const handleConfirmNormalization = async () => {
    if (!selectedReq) return;
    try {
      const res = await apiFetch(`/api/requests/${selectedReq.request_id}/correction`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_text: selectedReq.customer_name + ' parts order',
          corrected_parts_json: JSON.stringify(normalizedParts),
          correction_reason_tags: ['operator_review'],
        }),
      });
      if (res.ok) notify.success('Нормализация сохранена в Golden Dataset');
    } catch {
      console.warn('Could not save golden correction to backend');
    }
    setSelectedReq((prev) => (prev ? { ...prev, parts_json: JSON.stringify(normalizedParts) } : null));
    setActiveStep(3);
  };

  const navItems = [
    { id: 'dashboard', label: 'Панель управления', icon: 'fa-chart-pie' },
    { id: 'pipeline', label: 'Мультиагентный пайплайн', icon: 'fa-robot' },
    { id: 'orchestra', label: 'Мультиагентный оркестр', icon: 'fa-diagram-project' },
    { id: 'agent_os', label: 'Консоль ИИ-агента', icon: 'fa-terminal' },
    { id: 'kanban', label: 'Канбан-доска', icon: 'fa-table-columns' },
    { id: 'suppliers', label: 'Каталог поставщиков', icon: 'fa-truck-field' },
    { id: 'orders', label: 'Импорт заказов', icon: 'fa-file-arrow-up' },
    { id: 'contract_control', label: 'Договорный контроль', icon: 'fa-file-shield' },
    { id: 'matching', label: 'Матрица подбора', icon: 'fa-arrows-split-up-and-left' },
    { id: 'pricing', label: 'Калькулятор цен', icon: 'fa-calculator' },
    { id: 'audit', label: 'Аудит и логи', icon: 'fa-shield-halved' },
  ];

  const steps = ['Каталог поставщиков', 'Импорт заказов', 'Анализ нормализации', 'Сравнение предложений', 'Согласование', 'Черновик цены'];

  const handleStepClick = (stepIdx: number) => {
    setActiveStep(stepIdx);
    if (stepIdx === 0) setActiveNav('suppliers');
    else if (stepIdx === 1) setActiveNav('orders');
    else if (stepIdx === 2) setActiveNav('matching');
    else if (stepIdx === 3) setActiveNav('matching');
    else if (stepIdx === 4) setActiveNav('matching');
    else if (stepIdx === 5) setActiveNav('pricing');
  };

  const handleNavChange = (navId: string) => {
    setActiveNav(navId);
    if (selectedReq) {
      if (navId === 'suppliers') setActiveStep(0);
      else if (navId === 'orders') setActiveStep(1);
      else if (navId === 'matching') {
        if (activeStep < 2 || activeStep > 4) setActiveStep(3);
      } else if (navId === 'pricing') setActiveStep(5);
    }
  };

  const formattedPartsWithBestMatch = normalizedParts.map((part) => {
    const chosenOffer = selectedOffers[part.name];
    return {
      name: part.name,
      quantity: part.quantity,
      best_match: chosenOffer
        ? {
            name: chosenOffer.item.name,
            price: chosenOffer.item.price,
            price_deviation_from_median: chosenOffer.price_deviation_from_median,
          }
        : undefined,
    };
  });

  return (
      <AppFrame>
        <TopCommandBar
          searchQuery={searchGlobalQuery}
          onSearchChange={setSearchGlobalQuery}
          onResetActive={() => {
            setSelectedReq(null);
            setActiveNav('dashboard');
          }}
          erpSyncTime={erpSyncText}
        />
        <div className="flex-1 flex flex-row overflow-hidden relative">
          <LeftNavRail
            activeTab={activeNav}
            onChangeTab={handleNavChange}
            items={navItems}
            isCollapsed={leftCollapsed}
            onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
          />
          <main className="flex-1 h-full overflow-y-auto bg-[var(--bg-app)]">
            {selectedReq && ['matching', 'pricing'].includes(activeNav) ? (
              <div className="p-4 max-w-6xl mx-auto space-y-4">
                <WorkspaceHeader
                  title={`${selectedReq.customer_name} - План закупки запчастей`}
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
                <ChevronStepper status={selectedReq.status} />
                <StepGate currentStep={activeStep} steps={steps} onStepClick={handleStepClick} />
                <div className="space-y-4">
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
                  {activeStep === 3 && (
                    <SupplierMatrix
                      parts={normalizedParts}
                      selectedOffers={selectedOffers}
                      onSelectOffer={(partName, offer) =>
                        setSelectedOffers((prev) => ({
                          ...prev,
                          [partName]: offer,
                        }))
                      }
                    />
                  )}
                  {activeStep === 4 && (
                    <SectionCard title="Шаг 4: Контроль операционного согласования" icon="fa-key">
                      <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
                        Изучите ценовые аномалии и проверьте целостность цепочки аудита SHA-256. Требуется явное одобрение администратора/специалиста для разблокировки ценового листа перед подготовкой черновика коммерческого предложения.
                      </p>
                      <div className="mb-4">
                        <EvidenceGatesWidget requestId={selectedReq.request_id} refreshTrigger={fetchTrigger} />
                      </div>
                      {Object.keys(selectedOffers).length < normalizedParts.length && (
                        <InlineAlert
                          type="warning"
                          message="Некоторые детали не имеют выбранных предложений поставщиков. Настоятельно рекомендуется сравнить и выбрать варианты для всех позиций перед согласованием."
                        />
                      )}
                      <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-[var(--border-subtle)] justify-end">
                        <TransitionActions
                          status={selectedReq.status}
                          requestId={selectedReq.request_id}
                          onTransition={handleStateTransition}
                          permissions={getPermissions(currentRole)}
                        />
                      </div>
                    </SectionCard>
                  )}
                  {activeStep === 5 && (
                    <div className="space-y-4">
                      <PricingCalculator
                        parts={formattedPartsWithBestMatch}
                        requestId={selectedReq.request_id}
                        isApproved={selectedReq.status === 'APPROVED'}
                        onDraftInvoice={(data) => {
                          notify.invoiceDrafted(data.invoice_number);
                          setFetchTrigger((prev) => prev + 1);
                        }}
                      />
                      <InvoicePreview requestId={selectedReq.request_id} onSent={() => setFetchTrigger((prev) => prev + 1)} />
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-4 max-w-6xl mx-auto space-y-4">
                {activeNav === 'dashboard' && (
                  <>
                    <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-teal-50/50 via-slate-50 to-indigo-50/40 p-6 text-slate-900 shadow-sm border border-slate-200/50">
                      <div className="absolute -right-24 -top-24 h-48 w-48 rounded-full bg-teal-500/5 blur-3xl pointer-events-none" />
                      <div className="absolute -left-24 -bottom-24 h-48 w-48 rounded-full bg-indigo-500/5 blur-3xl pointer-events-none" />
                      <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-6 relative z-10 w-full">
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <span className="text-[9px] text-teal-800 font-extrabold uppercase tracking-widest bg-teal-500/10 border border-teal-500/20 px-2.5 py-0.5 rounded-full backdrop-blur-md">
                              Система активна
                            </span>
                            <span className="h-1.5 w-1.5 rounded-full bg-teal-500 animate-pulse" />
                          </div>
                          <h2 className="text-xl font-extrabold text-slate-900 tracking-tight sm:text-2xl font-sans">
                            Операционная панель PartsOps
                          </h2>
                          <p className="text-xs text-slate-600 max-w-xl leading-relaxed">
                            Интеллектуальное управление закупками на базе ИИ-агентов LangGraph и верификации цепочек поставок.
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 bg-slate-500/5 p-1.5 rounded-2xl border border-slate-200/40 backdrop-blur-md w-full sm:w-auto">
                          <button
                            onClick={() => setActiveNav('orders')}
                            className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 hover:text-slate-900 bg-white hover:bg-slate-50 border border-slate-200 hover:border-slate-300 shadow-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
                            title="Импортировать спецификации деталей"
                          >
                            <i className="fas fa-file-arrow-up text-teal-600" />
                            <span>Импорт заказов</span>
                          </button>
                          <button
                            onClick={() => setActiveNav('suppliers')}
                            className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 hover:text-slate-900 bg-white hover:bg-slate-50 border border-slate-200 hover:border-slate-300 shadow-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
                            title="Открыть базу поставщиков"
                          >
                            <i className="fas fa-truck-field text-indigo-600" />
                            <span>Поставщики</span>
                          </button>
                          <button
                            onClick={() => {
                              setFetchTrigger((prev) => prev + 1);
                              notify.erpSync();
                            }}
                            className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-slate-700 hover:text-slate-900 bg-white hover:bg-slate-50 border border-slate-200 hover:border-slate-300 shadow-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
                            title="Запустить синхронизацию с ERP"
                          >
                            <i className="fas fa-rotate text-amber-500" />
                            <span>Синхронизация</span>
                          </button>
                          <button
                            onClick={() => notify.info('Кэш очищен, сессия обновлена')}
                            className="flex items-center justify-center h-8.5 w-8.5 rounded-xl text-slate-400 hover:text-red-600 bg-white hover:bg-red-50 border border-slate-200 transition-all duration-200"
                            title="Очистить локальный кэш"
                          >
                            <i className="fas fa-trash-can text-[11px]" />
                          </button>
                          <button
                            onClick={() => setIsBatchModalOpen(true)}
                            className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-all duration-200 shadow-[0_4px_14px_rgba(16,185,129,0.3)] hover:scale-[1.02] active:scale-[0.98]"
                            title="Открыть форму пакетного поиска по артикулам OEM"
                          >
                            <i className="fas fa-list-check" />
                            <span>Пакетный поиск OEM</span>
                          </button>
                          <button
                            onClick={() => setActiveNav('orders')}
                            className="flex-1 sm:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-extrabold text-white bg-teal-600 hover:bg-teal-500 border-none transition-all duration-200 shadow-[0_4px_14px_rgba(0,180,157,0.2)] hover:shadow-[0_6px_20px_rgba(0,180,157,0.3)] hover:scale-[1.02] hover:-translate-y-0.5 active:scale-[0.98]"
                          >
                            <i className="fas fa-plus" />
                            <span>Новый запрос</span>
                          </button>
                        </div>
                      </div>
                    </section>


                    <BlockedQueue
                      requests={requests}
                      onSelectRequest={handleSelectRequest}
                      onTransitionRequest={handleStateTransition}
                    />

                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      {overviewMetrics.map((m) => (
                        <MetricTile key={m.label} label={m.label} value={m.value} delta={m.delta} tone={m.tone} />
                      ))}
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                      <SectionCard title="Нагрузка по этапам процесса" icon="fa-network-wired" className="lg:col-span-2">
                        <div className="flex flex-col lg:flex-row items-stretch justify-between gap-3 lg:gap-2 mt-1">
                          {workflowLanes.map((lane, idx) => (
                            <React.Fragment key={lane.title}>
                              <div className="flex-1 bg-[var(--surface-2)] border border-[var(--border-default)] rounded-xl p-3.5 flex flex-col justify-between hover:border-teal-500/30 hover:shadow-sm transition-all duration-300">
                                <div className="flex justify-between items-start gap-2 mb-1.5">
                                  <span className="text-xs font-bold text-[var(--text-primary)] leading-tight">{lane.title}</span>
                                  <span
                                    className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border shrink-0 ${
                                      lane.tone === 'cyan'
                                        ? 'bg-cyan-50 border-cyan-200 text-cyan-700'
                                        : lane.tone === 'violet'
                                          ? 'bg-violet-50 border-violet-200 text-violet-700'
                                          : lane.tone === 'amber'
                                            ? 'bg-amber-50 border-amber-200 text-amber-700'
                                            : 'bg-emerald-50 border-emerald-200 text-emerald-700'
                                    }`}
                                  >
                                    {lane.count}
                                  </span>
                                </div>
                                <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed mt-1">{lane.summary}</p>
                              </div>
                              {idx < workflowLanes.length - 1 && (
                                <div className="hidden lg:flex items-center justify-center text-slate-300 text-sm select-none">
                                  <i className="fas fa-chevron-right" />
                                </div>
                              )}
                            </React.Fragment>
                          ))}
                        </div>
                      </SectionCard>
                      <SectionCard title="Приоритетные инциденты" icon="fa-circle-radiation">
                        <div className="space-y-3 mt-1">
                          {urgentCases.map((c) => {
                            const isAmber = c.tone === 'amber';
                            let cardStyle = '';
                            let icon = '';
                            if (isAmber) {
                              cardStyle = 'border-l-4 border-l-amber-500 bg-amber-50/30 hover:border-amber-300';
                              icon = 'fa-circle-exclamation text-amber-500';
                            } else if (c.tone === 'emerald') {
                              cardStyle = 'border-l-4 border-l-emerald-500 bg-emerald-50/30 hover:border-emerald-300';
                              icon = 'fa-circle-check text-emerald-500';
                            } else {
                              cardStyle = 'border-l-4 border-l-rose-500 bg-rose-50/30 hover:border-rose-300';
                              icon = 'fa-triangle-exclamation text-rose-500';
                            }
                            return (
                              <div
                                key={c.id}
                                className={`border border-y-[var(--border-default)] border-r-[var(--border-default)] rounded-r-xl p-3 flex flex-col gap-1.5 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md cursor-pointer ${cardStyle}`}
                              >
                                <div className="flex justify-between items-center">
                                  <strong className="text-xs font-mono font-extrabold text-[var(--text-primary)]">{c.id}</strong>
                                  <i className={`fas ${icon} text-[11px] animate-pulse`} />
                                </div>
                                <p className="text-[11px] font-bold text-[var(--text-primary)] leading-tight">{c.title}</p>
                                <p className="text-[10px] text-[var(--text-secondary)] leading-relaxed">{c.detail}</p>
                              </div>
                            );
                          })}
                        </div>
                      </SectionCard>
                    </div>
                    <div className="grid grid-cols-1 gap-4">
                      <LLMCostPanel />
                    </div>
                  </>
                )}

                {activeNav === 'kanban' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b border-[var(--border-strong)] pb-3">
                      <div>
                        <h2 className="text-lg font-bold text-[var(--text-primary)]">Интерактивный рабочий процесс</h2>
                        <p className="text-xs text-[var(--text-secondary)]">Перетаскивайте запросы между этапами обработки для автоматического изменения статуса в системе.</p>
                      </div>
                      <ActionButton variant="secondary" icon="fa-rotate" onClick={fetchRequests} title="Обновить доску" />
                    </div>
                    <KanbanBoard
                      requests={requests}
                      onSelectRequest={handleSelectRequest}
                      onTransitionRequest={handleStateTransition}
                      resolveDropTarget={resolveDropTarget}
                    />
                  </div>
                )}

                {activeNav === 'report' && (
                  <JobReportView
                    request={selectedReq || (requests[0] || null)}
                    onBack={() => setActiveNav('dashboard')}
                  />
                )}

                {activeNav === 'pipeline' && (
                  <PipelineMonitor
                    requests={requests}
                    fetchTrigger={fetchTrigger}
                    selectedRequestId={selectedReq?.request_id || null}
                    onSelectRequest={handleSelectRequest}
                  />
                )}


                {activeNav === 'orchestra' && (
                <MultiAgentOrchestraView />
                )}

                {activeNav === 'agent_os' && (
                  <AgentOSPanel />
                )}

                {activeNav === 'suppliers' && (
                  <div className="h-full">
                    <SuppliersPage />
                  </div>
                )}

                {activeNav === 'orders' && (
                  <div className="mx-auto max-w-5xl space-y-4">
                    <CrawlerIntakePanel
                      onCreated={() => {
                        setFetchTrigger((prev) => prev + 1);
                      }}
                    />
                  </div>
                )}

                {activeNav === 'contract_control' && (
                  <div className="mx-auto max-w-6xl space-y-4">
                    <ContractControlPanel requestId={selectedReq?.request_id ?? null} refreshTrigger={fetchTrigger} />
                  </div>
                )}

                {['matching', 'pricing'].includes(activeNav) && (
                  <div className="max-w-md mx-auto py-10">
                    <EmptyState
                      title="Запрос не выбран"
                      description="Пожалуйста, выберите активный запрос из очереди сортировки справа."
                      icon={activeNav === 'matching' ? 'fa-arrows-split-up-and-left' : 'fa-calculator'}
                      actionNode={
                        <button
                          onClick={() => setRightCollapsed(false)}
                          className="mt-4 flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold text-white bg-teal-600 hover:bg-teal-500 border-none transition-all duration-200 shadow-[0_4px_14px_rgba(0,180,157,0.2)] hover:shadow-[0_6px_20px_rgba(0,180,157,0.3)] hover:scale-[1.02] hover:-translate-y-0.5 active:scale-[0.98]"
                        >
                          <i className="fas fa-arrow-right" />
                          <span>Открыть очередь</span>
                        </button>
                      }
                    />
                  </div>
                )}

                {activeNav === 'audit' && selectedReq && (
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

                {activeNav === 'audit' && !selectedReq && (
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
                          <i className="fas fa-history" />
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
        <CommandPalette
          isOpen={isCommandPaletteOpen}
          onClose={() => setIsCommandPaletteOpen(false)}
          onNavigate={(nav) => {
            setActiveNav(nav);
            setIsCommandPaletteOpen(false);
          }}
          requests={requests}
          suppliers={suppliersForPalette}
        />

        <BatchSearchModal
          isOpen={isBatchModalOpen}
          onClose={() => setIsBatchModalOpen(false)}
          onSuccess={(createdReq) => {
            setSelectedReq(createdReq);
            setFetchTrigger((prev) => prev + 1);
            setActiveNav('report');
          }}
        />

        <HermesChatDrawer
          activeScreen={activeNav}
          selectedRequestId={selectedReq?.request_id}
          onNavigate={(screenId, reqId) => {
            setActiveNav(screenId);
            if (reqId) {
              const match = requests.find((r) => r.request_id === reqId);
              if (match) setSelectedReq(match);
            }
          }}
        />
    </AppFrame>
  );
}

export default App;
