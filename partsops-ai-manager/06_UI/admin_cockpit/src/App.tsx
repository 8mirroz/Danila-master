import { useEffect, useState } from 'react';
import {
  AppFrame,
  TopCommandBar,
  LeftNavRail,
  WorkspaceHeader,
  StepGate,
  SectionCard,
  MetricTile,
  Button,
  ReviewPanel,
  EmptyState,
  InlineAlert,
  Icon,
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
import { useDashboardViewModel } from './lib/useDashboardViewModel';
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

function App() {
  const [selectedReq, setSelectedReq] = useState<Request | null>(null);
  const [activeNav, setActiveNav] = useState<string>('dashboard');
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [navDrawerOpen, setNavDrawerOpen] = useState(false);
  const [queueDrawerOpen, setQueueDrawerOpen] = useState(false);
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

  const dashboardVm = useDashboardViewModel(fetchTrigger);

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
    { id: 'dashboard', label: 'Панель управления', icon: 'search' },
    { id: 'pipeline', label: 'Мультиагентный пайплайн', icon: 'robot' },
    { id: 'orchestra', label: 'Мультиагентный оркестр', icon: 'wave-square' },
    { id: 'agent_os', label: 'Консоль ИИ-агента', icon: 'robot' },
    { id: 'kanban', label: 'Канбан-доска', icon: 'list' },
    { id: 'suppliers', label: 'Каталог поставщиков', icon: 'car' },
    { id: 'orders', label: 'Импорт заказов', icon: 'cloud-arrow-up' },
    { id: 'contract_control', label: 'Договорный контроль', icon: 'user-shield' },
    { id: 'matching', label: 'Матрица подбора', icon: 'rotate' },
    { id: 'pricing', label: 'Калькулятор цен', icon: 'pencil' },
    { id: 'audit', label: 'Аудит и логи', icon: 'circle-info' },
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

  const activeQueueCount =
    dashboardVm.health?.entity_counts?.requests?.active_queue_total ??
    requests.filter((r) => !['CLOSED', 'CANCELLED', 'FAILED', 'EXPIRED', 'CLIENT_REJECTED'].includes(r.status)).length;
  const pendingApprovalsCount = dashboardVm.health?.health_indicators?.approval_pressure?.pending_approvals ?? 0;
  const staleSuppliersCount = dashboardVm.health?.health_indicators?.supplier_feed_freshness?.feed_stale_suppliers ?? 0;
  const isErpFailing = dashboardVm.health?.health_indicators?.erp_health?.currently_failing ?? false;

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
        onOpenNavDrawer={() => setNavDrawerOpen(true)}
        onOpenQueueDrawer={() => setQueueDrawerOpen(true)}
      />
      <div className="flex-1 flex flex-row overflow-hidden relative">
        <LeftNavRail
          activeTab={activeNav}
          onChangeTab={handleNavChange}
          items={navItems}
          isCollapsed={leftCollapsed}
          onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
          drawerOpen={navDrawerOpen}
          onCloseDrawer={() => setNavDrawerOpen(false)}
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
                    icon="square-check"
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
                  <SectionCard title="Шаг 4: Контроль операционного согласования" icon="circle-info">
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
            <div className={activeNav === 'suppliers' ? "h-full" : "p-4 max-w-6xl mx-auto space-y-4"}>
              {activeNav === 'dashboard' && (
                <>
                  {/* Compact Workspace Header (replaces hero) */}
                  <div className="panel-card-tight p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-blue-50 text-blue-700 border border-blue-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
                          Система активна
                        </span>
                        {dashboardVm.health?.tenant_id && (
                          <span className="text-[10px] font-mono text-[var(--text-muted)]">
                            Tenant: {dashboardVm.health.tenant_id}
                          </span>
                        )}
                      </div>
                      <h2 className="text-lg font-bold tracking-tight text-[var(--text-primary)]">
                        Операционный пульт закупок
                      </h2>
                      <p className="text-xs text-[var(--text-secondary)]">
                        Мониторинг очереди, ИИ-агентов LangGraph и интеграции с ERP
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        variant="secondary"
                        icon="search"
                        onClick={() => setIsBatchModalOpen(true)}
                      >
                        Пакетный поиск OEM
                      </Button>
                      <Button
                        variant="secondary"
                        icon="rotate"
                        onClick={() => {
                          setFetchTrigger((prev) => prev + 1);
                          notify.erpSync();
                        }}
                      >
                        Синхронизация
                      </Button>
                      <Button
                        variant="primary"
                        icon="plus"
                        onClick={() => setActiveNav('orders')}
                      >
                        Новый запрос
                      </Button>
                    </div>
                  </div>

                  {/* Real Backend Alerts list */}
                  {dashboardVm.health?.alerts && dashboardVm.health.alerts.length > 0 && (
                    <div className="space-y-2">
                      {dashboardVm.health.alerts.map((alert, idx) => (
                        <InlineAlert
                          key={idx}
                          type={alert.level === 'critical' ? 'danger' : alert.level === 'warning' ? 'warning' : 'info'}
                          message={`${alert.source}: ${alert.message} ${alert.count ? `(${alert.count})` : ''}`}
                        />
                      ))}
                    </div>
                  )}

                  {/* Real KPI Cards with gradient skins */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <MetricTile
                      label="Активная очередь"
                      value={dashboardVm.loading ? '...' : activeQueueCount}
                      delta="запросов в работе"
                      gradient="blue"
                      icon="list"
                    />
                    <MetricTile
                      label="Нагрузка согласования"
                      value={dashboardVm.loading ? '...' : pendingApprovalsCount}
                      delta="ожидают подписи"
                      gradient="violet"
                      icon="circle-info"
                    />
                    <MetricTile
                      label="Устаревшие фиды"
                      value={dashboardVm.loading ? '...' : staleSuppliersCount}
                      delta="поставщиков"
                      gradient="amber"
                      icon="car"
                    />
                    <MetricTile
                      label="Статус ERP"
                      value={dashboardVm.loading ? '...' : isErpFailing ? 'Сбой' : 'ОК'}
                      delta={isErpFailing ? 'требует внимания' : 'синхронизировано'}
                      gradient="teal"
                      icon="rotate"
                    />
                  </div>

                  <BlockedQueue
                    requests={requests}
                    onSelectRequest={handleSelectRequest}
                    onTransitionRequest={handleStateTransition}
                  />

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
                    <Button variant="secondary" icon="rotate" onClick={fetchRequests} title="Обновить доску" />
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
                    icon={activeNav === 'matching' ? 'rotate' : 'pencil'}
                    actionNode={
                      <Button
                        variant="primary"
                        icon="chevron-right"
                        onClick={() => setRightCollapsed(false)}
                      >
                        Открыть очередь
                      </Button>
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
                  <div className="flex items-center justify-center p-8 bg-[var(--surface-1)] border border-[var(--border-default)] rounded-[var(--radius-card)] h-[650px] shadow-[var(--shadow-sm)] select-none">
                    <div className="text-center max-w-sm">
                      <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-4 text-[var(--text-muted)] border border-slate-200 mx-auto">
                        <Icon name="circle-info" size={24} />
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
          drawerOpen={queueDrawerOpen}
          onCloseDrawer={() => setQueueDrawerOpen(false)}
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
