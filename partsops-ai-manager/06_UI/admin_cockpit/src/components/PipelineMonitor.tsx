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
}

const AGENT_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  intake: { label: 'Intake Agent', icon: 'fa-inbox', color: 'bg-blue-500' },
  processing: { label: 'Processing Agent', icon: 'fa-cogs', color: 'bg-purple-500' },
  delivery: { label: 'Delivery Agent', icon: 'fa-paper-plane', color: 'bg-green-500' },
  reporting: { label: 'Reporting Agent', icon: 'fa-chart-line', color: 'bg-orange-500' },
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-500',
  running: 'bg-yellow-500 animate-pulse',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  awaiting_approval: 'bg-amber-500',
};

export function PipelineMonitor({ requests, fetchTrigger }: PipelineMonitorProps) {
  const [pipelineDetails, setPipelineDetails] = useState<Record<string, any>>({});
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});

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
      // Check if it's an approval wait
      const errorText = phase.errors.join(' ');
      if (errorText.includes('READY_FOR_APPROVAL') || errorText.includes('approval')) {
        return 'awaiting_approval';
      }
      return 'failed';
    }
    
    // Check if this phase is currently running
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
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className="space-y-4">
      <SectionCard title="Мультиагентный пайплайн" icon="fa-robot" className="w-full">
        <p className="text-xs text-[var(--text-secondary)] mb-4 leading-relaxed">
          Визуализация статусов четырех агентов: Intake (прием заказов) → Processing (подбор и цены) → Delivery (отправка клиенту) → Reporting (уведомления).
          Нажмите на запрос для деталей.
        </p>

        {requests.length === 0 && (
          <div className="text-center py-8 text-[var(--text-secondary)]">
            <i className="fas fa-robot text-3xl mb-2 opacity-30" />
            <p>Нет активных запросов в пайплайне</p>
          </div>
        )}

        <div className="space-y-3">
          {requests.map((request) => {
            const phases = ['intake', 'processing', 'delivery', 'reporting'];
            const phaseStatuses = phases.map(p => getPhaseStatus(request, p));
            const overallStatus = getRequestOverallStatus(request);
            const detail = pipelineDetails[request.request_id];
            const isLoading = loadingDetails[request.request_id] && !detail;

            return (
              <div
                key={request.request_id}
                className="bg-[var(--surface-2)] border border-[var(--border-default)] rounded-xl p-4 hover:border-teal-500/30 hover:shadow-sm transition-all duration-300 cursor-pointer"
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono font-bold text-xs text-[var(--text-primary)]">{request.request_id}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold ${STATUS_COLORS[overallStatus]} text-white`}>
                        {overallStatus.toUpperCase()}
                      </span>
                      <span className="text-[10px] text-[var(--text-muted)] bg-[var(--surface-3)] px-2 py-0.5 rounded">
                        {request.source}
                      </span>
                      {request.priority === 'urgent' && (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-rose-100 text-rose-700 border border-rose-200">
                          URGENT
                        </span>
                      )}
                      {request.priority === 'vip' && (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-violet-100 text-violet-700 border border-violet-200">
                          VIP
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-sm text-[var(--text-secondary)]">
                      {request.customer_name} • {request.vehicle_make || ''} {request.vehicle_model || ''} {request.vehicle_year ? `(${request.vehicle_year})` : ''}
                    </div>
                    {detail?.phases && (
                      <div className="mt-1 text-[10px] text-[var(--text-muted)] font-mono">
                        Total: {formatDuration(detail.total_time_ms || 0)} | Correlation: {detail.correlation_id?.slice(0, 8)}...
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {isLoading && (
                      <div className="w-5 h-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
                    )}
                    <ActionButton
                      variant="secondary"
                      icon="fa-chevron-down"
                      className="text-[var(--text-secondary)] hover:text-teal-500 p-1"
                    />
                  </div>
                </div>

                {/* Pipeline phases visualization */}
                <div className="relative">
                  {/* Connector line */}
                  <div className="absolute left-8 right-8 top-6 h-0.5 bg-[var(--border-default)]" />
                  
                  <div className="flex items-start justify-between relative z-10">
                    {phases.map((phaseName, index) => {
                      const agentInfo = AGENT_LABELS[phaseName];
                      const phaseStatus = getPhaseStatus(request, phaseName);
                      const phaseData = (request.pipeline_phases || detail?.phases || {})[phaseName];
                      
                      return (
                        <div key={phaseName} className="flex flex-col items-center flex-1">
                          {/* Phase circle */}
                          <div className="relative">
                            <div className={`w-4 h-4 rounded-full border-2 ${STATUS_COLORS[phaseStatus]} flex items-center justify-center`}>
                              {phaseStatus === 'completed' && (
                                <i className="fas fa-check text-[8px] text-white" />
                              )}
                              {phaseStatus === 'failed' && (
                                <i className="fas fa-times text-[8px] text-white" />
                              )}
                              {phaseStatus === 'running' && (
                                <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
                              )}
                              {phaseStatus === 'awaiting_approval' && (
                                <i className="fas fa-clock text-[8px] text-white" />
                              )}
                            </div>
                            {/* Tooltip / hover info */}
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[var(--surface-3)] border border-[var(--border-default)] rounded text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                              {agentInfo.label}
                              {phaseData?.execution_time_ms && ` • ${formatDuration(phaseData.execution_time_ms)}`}
                              {phaseData?.errors && phaseData.errors.length > 0 && (
                                <span className="text-red-400 ml-1">⚠ {phaseData.errors[0].slice(0, 30)}...</span>
                              )}
                            </div>
                          </div>
                          
                          {/* Phase label */}
                          <div className="mt-1 text-center">
                            <span className="text-[9px] font-medium text-[var(--text-primary)]">{agentInfo.label}</span>
                            <div className="flex items-center justify-center gap-1 mt-0.5">
                              <i className={`fas ${agentInfo.icon} text-[8px] ${agentInfo.color} text-white`} />
                            </div>
                          </div>
                          
                          {/* Connector between phases */}
                          {index < phases.length - 1 && (
                            <div className="w-full h-0.5 bg-[var(--border-default)] mt-2 relative">
                              <div className={`absolute top-0 h-full w-1/2 left-1/2 ${phaseStatuses[index] === 'completed' ? 'bg-green-500' : 'bg-[var(--border-default)]'}`} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Error details if any phase failed */}
                {phases.some(p => getPhaseStatus(request, p) === 'failed') && (
                  <div className="mt-3 p-2 bg-rose-50/50 border border-rose-200 rounded-lg text-[10px] text-rose-700">
                    <strong>Ошибки:</strong>
                    {phases.map(p => {
                      const phaseData = (request.pipeline_phases || detail?.phases || {})[p];
                      if (phaseData?.errors && phaseData.errors.length > 0) {
                        return <div key={p} className="ml-2">• {p}: {phaseData.errors.join('; ')}</div>;
                      }
                      return null;
                    })}
                  </div>
                )}

                {/* Approval action if awaiting approval */}
                {overallStatus === 'awaiting_approval' && (
                  <div className="mt-3 p-3 bg-amber-50/50 border border-amber-200 rounded-lg">
                    <InlineAlert
                      type="warning"
                      message="Запрос ожидает ручного согласования менеджером. Нажмите для перехода к согласованию."
                    />
                    <ActionButton
                              variant="primary"
                              icon="fa-circle-check"
                              className="mt-2"
                              onClick={() => window.dispatchEvent(new CustomEvent('navigate-to-matching', { detail: { requestId: request.request_id } }))}
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