import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import {
  SectionCard,
  ActionButton,
  InlineAlert,
} from './Primitives';

interface PipelinePhase {
  name: string;
  agent_type: string;
  success: boolean;
  data?: any;
  errors?: string[];
  execution_time_ms?: number;
  correlation_id?: string;
}

interface PipelineRequest {
  request_id: string;
  status: string;
  source: string;
  customer_name: string;
  vehicle_make?: string;
  vehicle_model?: string;
  vehicle_year?: number;
  parts_json?: string;
  pipeline_phases?: Record<string, PipelinePhase>;
  correlation_id?: string;
  total_time_ms?: number;
  created_at?: string;
  updated_at?: string;
  priority?: string;
}

interface PipelineMonitorProps {
  requests: PipelineRequest[];
  fetchTrigger: number;
  selectedRequestId?: string | null;
  onSelectRequest?: (req: any) => void;
}

const AGENT_LABELS: Record<string, { label: string; icon: string; desc: string }> = {
  intake: { label: 'Прием', icon: 'fa-file-import', desc: 'Сбор и структурирование данных' },
  processing: { label: 'Подбор', icon: 'fa-brain', desc: 'Подбор аналогов и расчет цен' },
  delivery: { label: 'Доставка', icon: 'fa-truck-fast', desc: 'Отправка документов клиенту' },
  reporting: { label: 'Отчет', icon: 'fa-chart-pie', desc: 'Уведомления и аналитика' },
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'В ожидании',
  running: 'Выполняется',
  completed: 'Готово',
  failed: 'Ошибка',
  awaiting_approval: 'Согласование',
  in_progress: 'В процессе',
};

const BADGE_COLORS: Record<string, string> = {
  pending: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700',
  running: 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400 border-amber-200 dark:border-amber-900 animate-pulse',
  completed: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900',
  failed: 'bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-400 border-rose-200 dark:border-rose-900',
  awaiting_approval: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900',
  in_progress: 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400 border-blue-200 dark:border-blue-900',
};

const PHASE_STATUS_STYLES: Record<string, { border: string; bg: string; text: string }> = {
  completed: {
    border: 'border-emerald-500 dark:border-emerald-400',
    bg: 'bg-emerald-50 dark:bg-emerald-950/20',
    text: 'text-emerald-600 dark:text-emerald-400',
  },
  failed: {
    border: 'border-rose-500 dark:border-rose-400',
    bg: 'bg-rose-50 dark:bg-rose-950/20',
    text: 'text-rose-600 dark:text-rose-400',
  },
  running: {
    border: 'border-amber-500 dark:border-amber-400 animate-pulse',
    bg: 'bg-amber-50 dark:bg-amber-950/20',
    text: 'text-amber-600 dark:text-amber-400',
  },
  awaiting_approval: {
    border: 'border-indigo-500 dark:border-indigo-400',
    bg: 'bg-indigo-50 dark:bg-indigo-950/20',
    text: 'text-indigo-600 dark:text-indigo-400',
  },
  pending: {
    border: 'border-slate-200 dark:border-slate-800',
    bg: 'bg-slate-50 dark:bg-slate-900/50',
    text: 'text-slate-400 dark:text-slate-600',
  },
};

export function PipelineMonitor({ requests, fetchTrigger, selectedRequestId, onSelectRequest }: PipelineMonitorProps) {
  const [pipelineDetails, setPipelineDetails] = useState<Record<string, any>>({});
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});
  const [expandedRequests, setExpandedRequests] = useState<Record<string, boolean>>({});

  // Fetch pipeline status for each request
  useEffect(() => {
    const fetchPipelineStatus = async (request: PipelineRequest) => {
      if (!request.request_id) return;
      
      setLoadingDetails(prev => ({ ...prev, [request.request_id!]: true }));
      try {
        const res = await apiFetch(`/api/pipeline/status/${request.request_id}`);
        if (res.ok) {
          const data = await res.json();
          setPipelineDetails(prev => ({ ...prev, [request.request_id!]: data }));
        }
      } catch (err) {
        console.error(`Failed to fetch pipeline status for ${request.request_id}`, err);
      } finally {
        setLoadingDetails(prev => ({ ...prev, [request.request_id!]: false }));
      }
    };

    requests.forEach(fetchPipelineStatus);
  }, [requests, fetchTrigger]);

  const getPhaseStatus = (request: PipelineRequest, phaseName: string): 'pending' | 'running' | 'completed' | 'failed' | 'awaiting_approval' => {
    const phases = request.pipeline_phases || pipelineDetails[request.request_id]?.phases || {};
    const phase = phases[phaseName];
    
    if (!phase) return 'pending';
    
    if (phase.success) return 'completed';
    if (phase.errors && phase.errors.length > 0) {
      const errorText = phase.errors.join(' ');
      if (errorText.includes('READY_FOR_APPROVAL') || errorText.includes('approval')) {
        return 'awaiting_approval';
      }
      return 'failed';
    }
    
    if (request.status === 'READY_FOR_APPROVAL' && phaseName === 'processing') {
      return 'awaiting_approval';
    }
    
    return 'pending';
  };

  const getRequestOverallStatus = (request: PipelineRequest): string => {
    const phases = ['intake', 'processing', 'delivery', 'reporting'];
    const phaseStatuses = phases.map(p => getPhaseStatus(request, p));
    
    if (phaseStatuses.includes('failed')) return 'failed';
    if (phaseStatuses.includes('running')) return 'running';
    if (phaseStatuses.includes('awaiting_approval')) return 'awaiting_approval';
    if (phaseStatuses.every(s => s === 'completed')) return 'completed';
    if (phaseStatuses.some(s => s === 'completed' || s === 'running' || s === 'awaiting_approval')) return 'in_progress';
    return 'pending';
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}мс`;
    return `${(ms / 1000).toFixed(1)}с`;
  };

  const handleCardClick = (request: PipelineRequest) => {
    onSelectRequest?.(request);
  };

  const toggleExpand = (e: React.MouseEvent, requestId: string) => {
    e.stopPropagation();
    setExpandedRequests(prev => ({
      ...prev,
      [requestId]: !prev[requestId]
    }));
  };

  return (
    <div className="space-y-4">
      <SectionCard title="Мультиагентный пайплайн" icon="fa-robot" className="w-full">
        <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
          Визуализация статусов работы ИИ-агентов. Кликните на карточку для выбора заказа в системе, либо нажмите стрелку справа для развертывания подробностей.
        </p>

        {requests.length === 0 && (
          <div className="text-center py-6 text-[var(--text-secondary)]">
            <i className="fas fa-robot text-2xl mb-2 opacity-30" />
            <p>Нет активных запросов в пайплайне</p>
          </div>
        )}

        <div className="space-y-2">
          {requests.map((request) => {
            const phases = ['intake', 'processing', 'delivery', 'reporting'];
            const overallStatus = getRequestOverallStatus(request);
            const detail = pipelineDetails[request.request_id];
            const isLoading = loadingDetails[request.request_id] && !detail;
            const isSelected = selectedRequestId === request.request_id;
            const isExpanded = expandedRequests[request.request_id] || false;

            // Parse parts JSON safely
            let parts: any[] = [];
            try {
              parts = request.parts_json ? JSON.parse(request.parts_json) : [];
            } catch (e) {
              // ignore
            }

            return (
              <div
                key={request.request_id}
                onClick={() => handleCardClick(request)}
                className={`bg-[var(--surface-2)] border rounded-xl p-3 hover:shadow-md transition-all duration-200 cursor-pointer ${
                  isSelected 
                    ? 'border-teal-500 dark:border-teal-400 ring-1 ring-teal-500/20 shadow-sm' 
                    : 'border-[var(--border-default)] hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                {/* Header */}
                <div className="flex items-center justify-between gap-3 mb-2">
                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <span className="font-mono font-bold text-xs text-[var(--text-primary)]">{request.request_id}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${BADGE_COLORS[overallStatus]}`}>
                      {STATUS_LABELS[overallStatus]?.toUpperCase() || overallStatus.toUpperCase()}
                    </span>
                    <span className="text-[9px] text-[var(--text-secondary)] bg-[var(--surface-3)] px-1.5 py-0.5 rounded font-medium">
                      {request.source.toUpperCase()}
                    </span>
                    {request.priority === 'urgent' && (
                      <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-rose-100 dark:bg-rose-950/30 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-900">
                        СРОЧНО
                      </span>
                    )}
                    {request.priority === 'vip' && (
                      <span className="px-1.5 py-0.5 rounded text-[8px] font-bold bg-violet-100 dark:bg-violet-950/30 text-violet-700 dark:text-violet-400 border border-violet-200 dark:border-violet-900">
                        VIP
                      </span>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-1">
                    {isLoading && (
                      <div className="w-3.5 h-3.5 border border-teal-500 border-t-transparent rounded-full animate-spin mr-1" />
                    )}
                    <button
                      onClick={(e) => toggleExpand(e, request.request_id)}
                      className="text-[var(--text-secondary)] hover:text-teal-500 p-1 rounded-lg hover:bg-[var(--surface-3)] transition-colors duration-150"
                      aria-label="Подробнее"
                    >
                      <i className={`fas ${isExpanded ? 'fa-chevron-up' : 'fa-chevron-down'} text-xs`} />
                    </button>
                  </div>
                </div>

                {/* Subheader */}
                <div className="text-xs text-[var(--text-secondary)] mb-3 flex items-center gap-1.5 flex-wrap">
                  <span className="font-semibold text-[var(--text-primary)]">{request.customer_name}</span>
                  {request.vehicle_make && (
                    <>
                      <span className="text-slate-300 dark:text-slate-700">•</span>
                      <span>{request.vehicle_make} {request.vehicle_model || ''} {request.vehicle_year ? `(${request.vehicle_year})` : ''}</span>
                    </>
                  )}
                </div>

                {/* Pipeline phases visualization */}
                <div className="relative py-2">
                  {/* Connector line */}
                  <div className="absolute left-[12.5%] right-[12.5%] top-[24px] h-[2px] bg-slate-100 dark:bg-slate-800" />
                  
                  <div className="flex justify-between relative z-10">
                    {phases.map((phaseName) => {
                      const agentInfo = AGENT_LABELS[phaseName];
                      const phaseStatus = getPhaseStatus(request, phaseName);
                      const styles = PHASE_STATUS_STYLES[phaseStatus];
                      const phaseData = (request.pipeline_phases || detail?.phases || {})[phaseName];
                      
                      return (
                        <div key={phaseName} className="flex flex-col items-center flex-1 group">
                          {/* Phase Circle */}
                          <div className="relative">
                            <div className={`w-8 h-8 rounded-full border-2 ${styles.border} ${styles.bg} ${styles.text} flex items-center justify-center transition-all duration-200`}>
                              <i className={`fas ${agentInfo.icon} text-xs`} />
                              
                              {/* Corner status indicator badge */}
                              {phaseStatus === 'completed' && (
                                <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[7px] border border-white dark:border-slate-900">
                                  <i className="fas fa-check" />
                                </span>
                              )}
                              {phaseStatus === 'failed' && (
                                <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-rose-500 text-white flex items-center justify-center text-[7px] border border-white dark:border-slate-900">
                                  <i className="fas fa-times" />
                                </span>
                              )}
                              {phaseStatus === 'awaiting_approval' && (
                                <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-indigo-500 text-white flex items-center justify-center text-[7px] border border-white dark:border-slate-900">
                                  <i className="fas fa-clock" />
                                </span>
                              )}
                            </div>
                            
                            {/* Hover tooltip */}
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2.5 py-1.5 bg-slate-900/95 dark:bg-slate-950 text-white rounded-lg text-[9px] shadow-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none z-20 border border-slate-700/30">
                              <p className="font-semibold text-slate-200">{agentInfo.desc}</p>
                              <p className="text-slate-400 mt-0.5">
                                Статус: <span className="font-medium text-slate-300">{STATUS_LABELS[phaseStatus]}</span>
                                {phaseData?.execution_time_ms ? ` • ${formatDuration(phaseData.execution_time_ms)}` : ''}
                              </p>
                            </div>
                          </div>
                          
                          {/* Phase Label */}
                          <div className="mt-1.5 text-center">
                            <span className="text-[10px] font-semibold text-[var(--text-secondary)]">{agentInfo.label}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Collapsible Details */}
                {isExpanded && (
                  <div className="mt-4 pt-3 border-t border-[var(--border-default)] space-y-3" onClick={(e) => e.stopPropagation()}>
                    {/* Parts list */}
                    {parts.length > 0 && (
                      <div>
                        <h4 className="text-[10px] uppercase font-bold text-slate-400 mb-1.5 tracking-wider">Список запчастей</h4>
                        <div className="bg-[var(--surface-3)] rounded-lg overflow-hidden border border-[var(--border-default)]">
                          <table className="min-w-full text-[11px]">
                            <thead>
                              <tr className="border-b border-[var(--border-default)] bg-slate-50 dark:bg-slate-900/30">
                                <th className="py-1 px-2 text-left font-semibold text-[var(--text-secondary)]">Название</th>
                                <th className="py-1 px-2 text-left font-semibold text-[var(--text-secondary)]">Артикул</th>
                                <th className="py-1 px-2 text-center font-semibold text-[var(--text-secondary)]">Кол-во</th>
                              </tr>
                            </thead>
                            <tbody>
                              {parts.map((p: any, idx: number) => (
                                <tr key={idx} className="border-b border-[var(--border-default)] last:border-0 hover:bg-slate-100/30 dark:hover:bg-slate-800/10">
                                  <td className="py-1 px-2 font-medium text-[var(--text-primary)]">{p.part_name || p.name || 'Неизвестно'}</td>
                                  <td className="py-1 px-2 font-mono text-[var(--text-secondary)]">{p.part_number || p.oem || '—'}</td>
                                  <td className="py-1 px-2 text-center text-[var(--text-secondary)]">{p.quantity || p.qty || 1} шт.</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Metadata and Times */}
                    <div className="grid grid-cols-2 gap-2 text-[10px] bg-[var(--surface-3)] p-2 rounded-lg border border-[var(--border-default)] font-mono text-[var(--text-secondary)]">
                      <div>
                        <span className="text-[var(--text-muted)]">Время запуска:</span>{' '}
                        <span>{request.created_at ? new Date(request.created_at).toLocaleString('ru-RU') : '—'}</span>
                      </div>
                      {detail?.total_time_ms ? (
                        <div>
                          <span className="text-[var(--text-muted)]">Длительность:</span>{' '}
                          <span className="text-[var(--text-primary)] font-bold">{formatDuration(detail.total_time_ms)}</span>
                        </div>
                      ) : null}
                      {request.correlation_id && (
                        <div className="col-span-2 break-all">
                          <span className="text-[var(--text-muted)]">Correlation ID:</span>{' '}
                          <span>{request.correlation_id}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Error details if any phase failed */}
                {phases.some(p => getPhaseStatus(request, p) === 'failed') && (
                  <div className="mt-3 p-2 bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200/50 dark:border-rose-950/50 rounded-lg text-[10px] text-rose-700 dark:text-rose-400">
                    <strong>Ошибки выполнения пайплайна:</strong>
                    {phases.map(p => {
                      const phaseData = (request.pipeline_phases || detail?.phases || {})[p];
                      if (phaseData?.errors && phaseData.errors.length > 0) {
                        return <div key={p} className="ml-2 mt-0.5 font-mono">• {AGENT_LABELS[p]?.label || p}: {phaseData.errors.join('; ')}</div>;
                      }
                      return null;
                    })}
                  </div>
                )}

                {/* Approval action if awaiting approval */}
                {overallStatus === 'awaiting_approval' && (
                  <div className="mt-3 p-2.5 bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/50 dark:border-amber-900/50 rounded-lg">
                    <InlineAlert
                      type="warning"
                      message="Запрос ожидает ручного согласования менеджером. Откройте согласование для принятия решения."
                    />
                    <ActionButton
                      variant="primary"
                      icon="fa-circle-check"
                      className="mt-2 text-xs py-1 px-3"
                      onClick={(e) => {
                        e.stopPropagation();
                        window.dispatchEvent(new CustomEvent('navigate-to-matching', { detail: { requestId: request.request_id } }));
                      }}
                    >
                      Открыть согласование
                    </ActionButton>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </SectionCard>
    </div>
  );
}

export default PipelineMonitor;
