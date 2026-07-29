import { useEffect, useState, useRef } from 'react';
import {
  AppFrame,
  TopCommandBar,
  LeftNavRail,
  WorkspaceHeader,
  SectionCard,
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
import { BatchSearchModal } from './components/BatchSearchModal';
import { getWorkflowStepIndex } from './lib/workflow';

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
  erp_quotation_ref?: string | null;
  erp_invoice_ref?: string | null;
  allowed_targets?: string[];
  allowed_actions?: Array<{ id: string; kind: string; target_state?: string }>;
  recommended_action?: { id: string; kind: string; target_state?: string } | null;
  is_blocked?: boolean;
  version?: string | null;
};

type Workspace = {
  request: { request_id: string; status: string; parts: Array<{ name: string; quantity: number }> };
  candidates: { selected_offers: Record<string, any> };
  principal_permissions: { can_create_invoice: boolean; can_sync_erp: boolean };
  allowed_actions: Array<{ id: string; kind: string; target_state?: string }>;
  updated_at?: string | null;
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
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  const [requests, setRequests] = useState<Request[]>([]);
  const [normalizedParts, setNormalizedParts] = useState<Array<{ name: string; quantity: number }>>([]);
  const [selectedOffers, setSelectedOffers] = useState<Record<string, any>>({});
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [orderIntakeKey, setOrderIntakeKey] = useState(0);
  const [isErpSyncing, setIsErpSyncing] = useState(false);
  const [suppliersForPalette, setSuppliersForPalette] = useState<any[]>([]);

  const handleOpenNewOrder = () => {
    setOrderIntakeKey((prev) => prev + 1);
    setActiveNav('orders');
  };
  const [lastErpSync, setLastErpSync] = useState<Date | null>(null);
  const [erpSyncText, setErpSyncText] = useState<string>('загрузка...');

  const dashboardVm = useDashboardViewModel(fetchTrigger);

  useEffect(() => {
    void apiFetch('/api/session')
      .then(async (res) => {
        if (!res.ok) throw new Error(`Session HTTP ${res.status}`);
        return res.json();
      })
      .catch((error) => {
        console.error('Session identity unavailable', error);
        setWorkspaceError('Не удалось подтвердить роль пользователя. Действия заблокированы до восстановления соединения.');
      });
  }, []);

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

  const getRequestWorkspaceStep = (status: string) => {
    const normalizedStatus = status.toUpperCase();
    if (['APPROVED', 'ERP_SYNCING', 'ERP_SYNC_FAILED', 'INVOICE_DRAFTED', 'SENT_TO_CLIENT', 'PAID', 'PURCHASE_ORDERED', 'FULFILLED', 'CLOSED'].includes(normalizedStatus)) {
      return 5;
    }
    const workflowIndex = getWorkflowStepIndex(normalizedStatus);
    return workflowIndex >= 2 ? 4 : workflowIndex === 1 ? 3 : 2;
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

  const pendingGRef = useRef(false);
  const pendingGTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const isTypingTarget = (el: EventTarget | null) => {
      if (!(el instanceof HTMLElement)) return false;
      const tag = el.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
      if (el.isContentEditable) return true;
      return false;
    };

    const gNavMap: Record<string, string> = {
      d: 'dashboard',
      k: 'kanban',
      s: 'suppliers',
      o: 'orders',
      m: 'matching',
      p: 'pricing',
      a: 'audit',
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(true);
        return;
      }
      if (e.key === 'Escape') {
        setIsCommandPaletteOpen(false);
        return;
      }

      // Do not steal keys while typing in fields
      if (isTypingTarget(e.target)) return;

      // ⌘/Ctrl+N → new request (orders)
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        setActiveNav('orders');
        return;
      }

      // ⌘/Ctrl+R → soft refresh (no full page reload)
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'r') {
        e.preventDefault();
        setFetchTrigger((prev) => prev + 1);
        return;
      }

      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const key = e.key.toLowerCase();

      // G then letter navigation (short-lived pending G, ~800ms)
      if (key === 'g' && !e.repeat) {
        pendingGRef.current = true;
        if (pendingGTimerRef.current != null) {
          window.clearTimeout(pendingGTimerRef.current);
        }
        pendingGTimerRef.current = window.setTimeout(() => {
          pendingGRef.current = false;
          pendingGTimerRef.current = null;
        }, 800);
        return;
      }

      if (pendingGRef.current && gNavMap[key]) {
        e.preventDefault();
        pendingGRef.current = false;
        if (pendingGTimerRef.current != null) {
          window.clearTimeout(pendingGTimerRef.current);
          pendingGTimerRef.current = null;
        }
        setActiveNav(gNavMap[key]);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      if (pendingGTimerRef.current != null) {
        window.clearTimeout(pendingGTimerRef.current);
      }
    };
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
      setWorkspace(null);
      setWorkspaceError(null);
      setSelectedOffers({});
      void apiFetch(`/api/requests/${selectedReq.request_id}/workspace`)
        .then(async (res) => {
          if (!res.ok) throw new Error(`Workspace HTTP ${res.status}`);
          return res.json() as Promise<Workspace>;
        })
        .then((data) => {
          setWorkspace(data);
          setNormalizedParts(data.request.parts ?? []);
          setSelectedOffers(data.candidates.selected_offers ?? {});
          setSelectedReq((previous) => previous && previous.status !== data.request.status
            ? { ...previous, status: data.request.status }
            : previous);
          setActiveStep(getRequestWorkspaceStep(data.request.status));
        })
        .catch((error: unknown) => {
          setNormalizedParts([]);
          setWorkspaceError(error instanceof Error ? error.message : 'Не удалось загрузить подтверждённое состояние заявки');
        });
    }
  }, [selectedReq]);

  const handleSelectRequest = (req: Request) => {
    setSelectedReq(req);
    setActiveNav('matching');
    setActiveStep(getRequestWorkspaceStep(req.status));
  };

  const handleStateTransition = async (targetState: string, reason: string, reqId?: string, version?: string | null) => {
    const idToTransition = reqId || selectedReq?.request_id;
    if (!idToTransition) return;
    try {
      const res = await apiFetch(`/api/requests/${idToTransition}/transition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(version ? { 'X-Request-Version': version } : {}) },
        body: JSON.stringify({ target_state: targetState, reason }),
      });
      if (res.ok) {
        const updated = await res.json();
        const updatedStatus = updated.workspace?.request?.status ?? updated.transition?.new_state;
        if (!updatedStatus) throw new Error('Backend не вернул каноническое состояние заявки');
        notify.transition(selectedReq?.status || 'CURRENT', updatedStatus);
        setFetchTrigger((prev) => prev + 1);
        if (selectedReq && selectedReq.request_id === idToTransition) {
          setSelectedReq((prev) => (prev ? { ...prev, status: updatedStatus } : null));
          if (updated.workspace) setWorkspace(updated.workspace);
          if (targetState === 'APPROVED') setActiveStep(5);
        }
      } else {
        const err = await res.json().catch(() => null);
        const detail = typeof err?.detail === 'string' ? err.detail : err?.detail?.reason || `HTTP ${res.status}`;
        const transitionError = new Error(`Ошибка смены статуса: ${detail}`);
        notify.error(transitionError.message);
        throw transitionError;
      }
    } catch (error) {
      console.error(error);
      const transitionError = error instanceof Error ? error : new Error('Backend недоступен: переход не выполнен');
      notify.error(transitionError.message);
      throw transitionError;
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

  const requestPartsCount = normalizedParts.length;
  const selectedOffersCount = Object.keys(selectedOffers).filter((key) => selectedOffers[key] != null).length;
  const allOffersSelected = requestPartsCount > 0 && selectedOffersCount === requestPartsCount;
  const canOpenWorkspaceStep = (index: number) => {
    if (index <= 2) return true;
    if (index === 3) return requestPartsCount > 0;
    if (index === 4) return allOffersSelected;
    if (index >= 5) return selectedReq?.status === 'APPROVED' || activeStep >= 5;
    return false;
  };

  const openWorkspaceStep = (index: number) => {
    if (!canOpenWorkspaceStep(index)) return;
    if (index === 2 || index === 3 || index === 4 || index >= 5) {
      setActiveStep(index === 2 ? 2 : index === 3 ? 3 : index === 4 ? 4 : 5);
    }
  };

  const navItems = [
    { id: 'dashboard', label: 'Панель управления', icon: 'search', group: 'main' as const },
    { id: 'kanban', label: 'Канбан-доска', icon: 'list', group: 'main' as const },
    { id: 'suppliers', label: 'Каталог поставщиков', icon: 'car', group: 'main' as const },
    { id: 'orders', label: 'Загрузка заказа', icon: 'cloud-arrow-up', group: 'main' as const },
    { id: 'matching', label: 'Матрица подбора', icon: 'rotate', group: 'main' as const },
    { id: 'pricing', label: 'Калькулятор цен', icon: 'pencil', group: 'main' as const },
    { id: 'pipeline', label: 'Мультиагентный пайплайн', icon: 'robot', group: 'admin' as const },
    { id: 'orchestra', label: 'Мультиагентный оркестр', icon: 'wave-square', group: 'admin' as const },
    { id: 'agent_os', label: 'Консоль ИИ-агента', icon: 'robot', group: 'admin' as const },
    { id: 'audit', label: 'Аудит и логи', icon: 'circle-info', group: 'admin' as const },
    { id: 'hermes', label: 'AI агент', icon: 'robot', group: 'bottom' as const },
  ];

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

  const activeQueueCount =
    dashboardVm.health?.entity_counts?.requests?.active_queue_total ??
    requests.filter((r) => !['CLOSED', 'CANCELLED', 'FAILED', 'EXPIRED', 'CLIENT_REJECTED'].includes(r.status)).length;
  const pendingApprovalsCount = dashboardVm.health?.health_indicators?.approval_pressure?.pending_approvals ?? 0;
  const staleSuppliersCount = dashboardVm.health?.health_indicators?.supplier_feed_freshness?.feed_stale_suppliers ?? 0;
  const hasErpHealth = dashboardVm.health?.health_indicators?.erp_health != null;
  const isErpFailing = Boolean(dashboardVm.health?.health_indicators?.erp_health?.currently_failing);

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
              <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl shadow-sm text-xs font-semibold border border-indigo-900/40">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span>Режим контекста заявки: <strong className="font-mono text-blue-300">{selectedReq.request_id}</strong> ({selectedReq.customer_name || 'Без имени'})</span>
                </div>
                <button
                  onClick={() => setSelectedReq(null)}
                  className="px-3 py-1 bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl text-[11px] font-bold text-white transition-all active:scale-95 flex items-center gap-1.5"
                  title="Перейти в автономный глобальный инструмент подбора/расчета без привязки к заявке"
                >
                  <Icon name="rotate" size={12} /> 🔓 Открепить заявку (Автономный режим)
                </button>
              </div>
              <WorkspaceHeader
                title={selectedReq.customer_name ? `${selectedReq.customer_name} - План закупки запчастей` : `${selectedReq.request_id} - План закупки запчастей`}
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
              <ChevronStepper
                status={selectedReq.status}
                activeIndex={activeStep === 2 ? 2 : activeStep === 3 ? 3 : activeStep === 4 ? 5 : 6}
                canOpenStep={canOpenWorkspaceStep}
                onStepClick={openWorkspaceStep}
              />
              {workspaceError && <InlineAlert type="danger" message={`${workspaceError} Повторите открытие заявки после восстановления соединения.`} />}
              {!workspace && !workspaceError && <InlineAlert type="info" message="Загружаем подтверждённое состояние заявки и разрешённые действия…" />}
              <div className="flex items-center justify-between gap-3 rounded-2xl border border-blue-100 bg-blue-50/55 px-4 py-3 text-xs">
                <div className="min-w-0">
                  <p className="font-bold text-slate-900">{activeStep === 2 ? 'Проверьте распознанные позиции' : activeStep === 3 ? 'Выберите лучший оффер для каждой позиции' : activeStep === 4 ? 'Проверьте доказательства и согласуйте цену' : 'Подготовьте и отправьте счёт'}</p>
                  <p className="mt-0.5 text-slate-600">Шаг нельзя пропустить, пока не выполнено обязательное условие текущего этапа.</p>
                </div>
                <span className="hidden shrink-0 rounded-full border border-blue-200 bg-white px-2.5 py-1 font-mono text-[10px] font-bold text-blue-700 sm:inline-flex">{activeStep === 2 ? `${requestPartsCount} поз.` : activeStep === 3 ? `${selectedOffersCount}/${requestPartsCount} выбрано` : selectedReq.status}</span>
              </div>
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
                  <>
                    <SupplierMatrix
                      parts={normalizedParts}
                      selectedOffers={selectedOffers}
                      requestId={selectedReq.request_id}
                      onSelectOffer={(partName, offer) => {
                        void apiFetch(`/api/requests/${selectedReq.request_id}/actions/select_offer`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json', ...(workspace?.updated_at ? { 'X-Request-Version': workspace.updated_at } : {}) },
                          body: JSON.stringify({ part_name: partName, offer }),
                        })
                          .then(async (res) => {
                            if (!res.ok) {
                              const detail = await res.json().catch(() => null);
                              throw new Error(typeof detail?.detail === 'string' ? detail.detail : `HTTP ${res.status}`);
                            }
                            return res.json();
                          })
                          .then((data: Workspace) => {
                            setWorkspace(data);
                            setSelectedOffers(data.candidates?.selected_offers ?? {});
                            notify.success(`Оффер для «${partName}» сохранён`);
                          })
                          .catch((error) => {
                            notify.error(error instanceof Error ? error.message : 'Не удалось сохранить оффер');
                          });
                      }}
                    />
                    <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                      <Button variant="secondary" icon="arrow-left" onClick={() => setActiveStep(2)}>Назад к проверке</Button>
                      <Button variant="primary" icon="arrow-right" disabled={!allOffersSelected} onClick={() => setActiveStep(4)} title={!allOffersSelected ? 'Выберите оффер для каждой позиции' : undefined}>
                        К согласованию <span className="ml-1 font-mono text-[10px] opacity-80">{selectedOffersCount}/{requestPartsCount}</span>
                      </Button>
                    </div>
                  </>
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
                      <Button variant="secondary" icon="arrow-left" onClick={() => setActiveStep(3)}>Назад к подбору</Button>
                      <TransitionActions
                        status={selectedReq.status}
                        requestId={selectedReq.request_id}
                        onTransition={handleStateTransition}
                        allowedTargets={(workspace?.allowed_actions ?? [])
                          .filter((action) => action.kind === 'transition')
                          .flatMap((action) => action.target_state ? [action.target_state] : [])}
                      />
                    </div>
                  </SectionCard>
                )}
                {activeStep === 5 && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-start">
                      <Button variant="secondary" icon="arrow-left" onClick={() => setActiveStep(4)}>Назад к согласованию</Button>
                    </div>
                    <PricingCalculator
                      requestId={selectedReq.request_id}
                      version={workspace?.updated_at}
                      isApproved={selectedReq.status === 'APPROVED'}
                      canCreateInvoice={Boolean(workspace?.principal_permissions.can_create_invoice)}
                      canSyncErp={Boolean((workspace?.allowed_actions ?? []).some((action) => action.id === 'sync_to_erp'))}
                      erpQuotationRef={selectedReq.erp_quotation_ref}
                      onDraftInvoice={(data) => {
                        const invoice = data.invoice ?? data;
                        const invoiceRef = invoice.invoice_ref ?? invoice.invoice_number;
                        if (!invoiceRef || !data.request?.status) {
                          notify.error('Backend не вернул канонический invoice workspace');
                          return;
                        }
                        notify.invoiceDrafted(invoiceRef);
                        setWorkspace(data as Workspace);
                        setSelectedReq((prev) => prev
                          ? { ...prev, status: data.request.status, erp_invoice_ref: invoiceRef }
                          : prev);
                        setFetchTrigger((prev) => prev + 1);
                      }}
                    />
                    <InvoicePreview requestId={selectedReq.request_id} onSent={() => setFetchTrigger((prev) => prev + 1)} />
                  </div>
                )}
              </div>
            </div>
          ) : activeNav === 'hermes' ? (
            <div className="hermes-workspace-shell p-4 lg:p-6">
              <div className="mx-auto h-full max-w-7xl">
                <HermesChatDrawer
                  activeScreen={activeNav}
                  selectedRequestId={selectedReq?.request_id}
                  open
                  embedded
                  onOpenChange={(open) => { if (!open) setActiveNav('dashboard'); }}
                  onNavigate={(screenId, reqId) => {
                    setActiveNav(screenId);
                    if (reqId) {
                      const match = requests.find((r) => r.request_id === reqId);
                      if (match) setSelectedReq(match);
                    }
                  }}
                />
              </div>
            </div>
          ) : (
            <div className={activeNav === 'suppliers' ? "h-full" : "p-4 max-w-6xl mx-auto space-y-4"}>
              {activeNav === 'dashboard' && (
                <>
                  {/* Premium Hero Banner inspired by reference design */}
                  <div className="rounded-3xl border border-slate-700/40 bg-gradient-to-r from-[#0F172A] via-[#1E293B] to-[#0F172A] p-6 text-white shadow-lg space-y-5">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                            {dashboardVm.loading ? 'Проверка системы' : dashboardVm.health?.status === 'healthy' ? 'Данные подтверждены' : 'Статус недоступен'}
                          </span>
                          {dashboardVm.health?.tenant_id && (
                            <span className="text-[10px] font-mono text-slate-400">
                              Tenant: {dashboardVm.health.tenant_id}
                            </span>
                          )}
                        </div>
                        <h2 className="text-xl font-black tracking-tight text-white">
                          Рабочая очередь PartsOps
                        </h2>
                        <p className="text-xs text-slate-300 font-medium">
                          Мониторинг единой очереди запросов, ИИ-агентов LangGraph и синхронизации с ERP
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-2.5">
                        <button
                          onClick={() => setIsBatchModalOpen(true)}
                          className="rounded-2xl border border-white/20 bg-white/10 hover:bg-white/20 px-4 py-2.5 text-xs font-bold text-white transition-all duration-200 backdrop-blur-md shadow-xs flex items-center gap-2 active:scale-95"
                          title="Быстрый пакетный поиск по списку артикулов OEM"
                        >
                          <Icon name="search" size={14} className="text-blue-300" />
                          Быстрый поиск по артикулу
                        </button>
                        <button
                          onClick={() => {
                            setIsErpSyncing(true);
                            setFetchTrigger((prev) => prev + 1);
                            void notify.erpSync();
                            setTimeout(() => setIsErpSyncing(false), 800);
                          }}
                          className="rounded-2xl border border-white/20 bg-white/10 hover:bg-white/20 px-4 py-2.5 text-xs font-bold text-white transition-all duration-200 backdrop-blur-md shadow-xs flex items-center gap-2 active:scale-95"
                          title="Обновить статус ERP (синхронизация состояния)"
                        >
                          <Icon name="rotate" size={14} className={`text-slate-300 ${isErpSyncing ? 'animate-spin text-blue-400' : ''}`} />
                          Статус ERP
                        </button>
                        <button
                          onClick={handleOpenNewOrder}
                          className="rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 px-5 py-2.5 text-xs font-black text-white transition-all duration-200 shadow-md hover:shadow-blue-500/25 flex items-center gap-2 active:scale-95"
                          title="Создать и настроить новый кастомный запрос"
                        >
                          <Icon name="plus" size={14} className="text-white" />
                          Новый запрос (Кастом)
                        </button>
                      </div>
                    </div>

                    {/* Integrated Glassmorphism KPI Grid */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
                      <div className="rounded-2xl bg-white/10 border border-white/15 p-4 backdrop-blur-md">
                        <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-300 mb-1">
                          Активная очередь
                        </div>
                        <div className="text-2xl font-black text-white">
                          {dashboardVm.loading ? '...' : activeQueueCount}
                        </div>
                        <div className="text-[10px] text-blue-200 mt-1 font-semibold">
                          запросов в обработке
                        </div>
                      </div>

                      <div className="rounded-2xl bg-white/10 border border-white/15 p-4 backdrop-blur-md">
                        <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-300 mb-1">
                          Нагрузка согласования
                        </div>
                        <div className="text-2xl font-black text-white">
                          {dashboardVm.loading ? '...' : pendingApprovalsCount}
                        </div>
                        <div className="text-[10px] text-violet-200 mt-1 font-semibold">
                          ожидают подписи
                        </div>
                      </div>

                      <div className="rounded-2xl bg-white/10 border border-white/15 p-4 backdrop-blur-md">
                        <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-300 mb-1">
                          Устаревшие фиды
                        </div>
                        <div className="text-2xl font-black text-white">
                          {dashboardVm.loading ? '...' : staleSuppliersCount}
                        </div>
                        <div className="text-[10px] text-amber-200 mt-1 font-semibold">
                          поставщиков
                        </div>
                      </div>

                      <div className="rounded-2xl bg-white/10 border border-white/15 p-4 backdrop-blur-md">
                        <div className="text-[10px] font-extrabold uppercase tracking-wider text-slate-300 mb-1">
                          Статус ERP
                        </div>
                        <div className="text-2xl font-black text-white">
                          {dashboardVm.loading ? '...' : !hasErpHealth ? 'н/д' : isErpFailing ? 'Сбой' : 'OK'}
                        </div>
                        <div className="text-[10px] text-emerald-200 mt-1 font-semibold">
                          {dashboardVm.loading
                            ? 'загрузка'
                            : !hasErpHealth
                              ? 'нет данных'
                              : isErpFailing
                                ? 'требует внимания'
                                : 'в норме'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Real Backend Alerts list */}
                  {dashboardVm.error && <InlineAlert type="danger" message={`${dashboardVm.error}. Повторите обновление очереди.`} />}
                  {dashboardVm.partialErrors.length > 0 && !dashboardVm.error && (
                    <InlineAlert type="warning" message={`Частично недоступны: ${dashboardVm.partialErrors.join(', ')}. Показаны только подтверждённые данные.`} />
                  )}
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
                  <BlockedQueue
                    requests={requests}
                    onSelectRequest={handleSelectRequest}
                    onTransitionRequest={(requestId, targetState, reason, version) =>
                      handleStateTransition(targetState, reason, requestId, version)
                    }
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
                    onRunsChanged={() => {
                      setFetchTrigger((previous) => previous + 1);
                    }}
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
                    key={orderIntakeKey}
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

              {activeNav === 'matching' && !selectedReq && (
                <EmptyState
                  title="Выберите заявку для подбора"
                  description="Матрица офферов доступна только в подтверждённом workspace заявки."
                  icon="fa-list-check"
                />
              )}

              {activeNav === 'pricing' && !selectedReq && (
                <EmptyState
                  title="Выберите согласованную заявку"
                  description="Pricing и ERP-команды доступны только из подтверждённого lifecycle workspace."
                  icon="fa-calculator"
                />
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

    </AppFrame>
  );
}

export default App;
