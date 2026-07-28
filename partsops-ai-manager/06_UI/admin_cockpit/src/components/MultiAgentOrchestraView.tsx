import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api';
import { SectionCard } from './Primitives';

type NodeStatus = 'idle' | 'active' | 'success' | 'error';

type AgentNode = {
  id: string;
  label: string;
  icon: string;
  color: string;
  description: string;
};

type Edge = {
  from: string;
  to: string;
  label?: string;
};

type PipelineGraph = {
  nodes: AgentNode[];
  edges: Edge[];
};

type PhaseDetail = {
  agent_type: string;
  success: boolean;
  execution_time_ms: number;
  correlation_id: string;
  latency_ms?: number;
  total_tokens?: number;
  cost_usd?: number;
  provider?: string;
  model?: string;
  errors?: string[];
  data?: any;
};

type PipelineRun = {
  request_id: string;
  correlation_id?: string;
  status: string;
  current_stage?: string;
  started_at?: string;
  completed_at?: string;
  total_time_ms?: number;
  phases: Record<string, PhaseDetail>;
};

const GRAPH: PipelineGraph = {
  nodes: [
    { id: 'intake', label: 'Intake Agent', icon: 'fa-inbox', color: '#3b82f6', description: 'Сбор и структурирование заказа' },
    { id: 'processing', label: 'Processing Agent', icon: 'fa-microchip', color: '#a855f7', description: 'Подбор, цены, генерация документов' },
    { id: 'delivery', label: 'Delivery Agent', icon: 'fa-paper-plane', color: '#22c55e', description: 'Клиентская коммуникация' },
    { id: 'reporting', label: 'Reporting Agent', icon: 'fa-chart-line', color: '#f97316', description: 'Отчетность и уведомления' },
  ],
  edges: [
    { from: 'intake', to: 'processing' },
    { from: 'processing', to: 'delivery' },
    { from: 'processing', to: 'reporting', label: 'sync' },
    { from: 'delivery', to: 'reporting' },
    { from: 'reporting', to: 'end' },
  ],
};

const NODE_STATUS_COLORS: Record<NodeStatus, { bg: string; border: string; text: string; pulse: boolean }> = {
  idle: { bg: '#f8fafc', border: '#cbd5e1', text: '#475569', pulse: false },
  active: { bg: '#eff6ff', border: '#3b82f6', text: '#1e40af', pulse: true },
  success: { bg: '#f0fdf4', border: '#22c55e', text: '#15803d', pulse: false },
  error: { bg: '#fef2f2', border: '#ef4444', text: '#991b1b', pulse: false },
};

export function MultiAgentOrchestraView() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [liveMode, setLiveMode] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [vaultSyncStatus, setVaultSyncStatus] = useState<Record<string, { status: 'idle' | 'pending' | 'success' | 'error'; message: string }>>({});

  const triggerVaultSync = async (run: PipelineRun) => {
    if (!run.correlation_id) return;
    
    setVaultSyncStatus((prev) => ({
      ...prev,
      [run.request_id]: { status: 'pending', message: 'Синхронизация...' },
    }));

    try {
      const res = await apiFetch(`/api/admin/observability/vault-sync/${run.correlation_id}`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setVaultSyncStatus((prev) => ({
          ...prev,
          [run.request_id]: { status: 'success', message: `Синхронизировано: ${data.vault_path?.split('/').pop()}` },
        }));
      } else {
        const error = await res.json();
        setVaultSyncStatus((prev) => ({
          ...prev,
          [run.request_id]: { status: 'error', message: error.detail || 'Ошибка синхронизации' },
        }));
      }
    } catch {
      setVaultSyncStatus((prev) => ({
        ...prev,
        [run.request_id]: { status: 'error', message: 'Ошибка сети' },
      }));
    }
  };

  useEffect(() => {
    loadRuns();
    const interval = setInterval(() => {
      if (liveMode) loadRuns();
    }, 8000);
    return () => clearInterval(interval);
  }, [liveMode]);

  useEffect(() => {
    const handler = () => {
      if (liveMode) loadRuns();
    };
    window.addEventListener('orchestra-update', handler);
    return () => window.removeEventListener('orchestra-update', handler);
  }, [liveMode]);

  const loadRuns = async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/admin/observability/pipeline-runs?limit=20');
      if (res.ok) {
        const data = await res.json();
        setRuns(data);
        setLastUpdate(new Date().toISOString());
      } else {
        setRuns([]);
      }
    } catch (e) {
      console.warn('Pipeline graph data unavailable:', e);
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const expandRun = async (run: PipelineRun) => {
    if (expandedRun === run.request_id) {
      setExpandedRun(null);
      return;
    }
    try {
      const res = await apiFetch(`/api/admin/observability/pipeline-runs/${run.correlation_id}`);
      if (res.ok) {
        const data = await res.json();
        setRuns((prev) =>
          prev.map((r) =>
            r.request_id === run.request_id ? { ...r, phases: enrichPhases(r, data.phases || {}) } : r
          )
        );
      }
    } catch (e) {
      console.warn('Detail fetch failed:', e);
    }
    setExpandedRun(run.request_id);
  };

  const getNodeStatus = (run: PipelineRun, nodeId: string): NodeStatus => {
    const phase = Object.values(run.phases).find(
      (p) => p.agent_type?.toLowerCase().includes(nodeId) || p.model?.toLowerCase().includes(nodeId)
    );
    if (!phase) return 'idle';
    if (phase.success) return 'success';
    if (!phase.success && phase.errors && phase.errors.length > 0) return 'error';
    if (phase) return 'active';
    return 'idle';
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Мультиагентный оркестр (Multi-Agent DAG)" icon="fa-diagram-project">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Визуализация состояния мультиагентного конвейера PartsOps. Каждый узел — отдельный LLM-агент (Intake → Processing → Delivery → Reporting).
            Цвет индикатора отражает статус: <span className="text-emerald-700 font-bold">success</span> / <span className="text-blue-700 font-bold">running</span> / <span className="text-rose-700 font-bold">failed</span> /
            <span className="text-slate-500 font-bold"> idle</span>. Клик на запуске раскрывает детали.
          </p>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-[10px] font-medium text-[var(--text-secondary)] cursor-pointer">
              <input
                type="checkbox"
                checked={liveMode}
                onChange={(e) => setLiveMode(e.target.checked)}
                className="w-4 h-4 accent-emerald-600 rounded border-[var(--border-default)]"
              />
              Live (auto-refresh 8s)
            </label>
            {loading && <span className="text-[10px] text-blue-600 animate-pulse">⟳ обновление...</span>}
            {lastUpdate && <span className="text-[9px] text-[var(--text-muted)]">Last: {new Date(lastUpdate).toLocaleTimeString()}</span>}
            <span className="text-[9px] font-mono text-slate-500">|</span>
            <span className="text-[9px] font-mono text-slate-600">Vault: </span>
            <span className="text-[9px] font-mono text-amber-700">bridge-ready</span>
          </div>
        </div>
        <div className="space-y-3">
          {runs.length === 0 && (
            <div className="text-center py-6 text-[var(--text-muted)]">
              <i className="fas fa-robot text-3xl mb-2 opacity-30" />
              <p className="text-xs font-semibold">Активные запуски не обнаружены</p>
            </div>
          )}
          {runs.map((run) => {
            const statuses = GRAPH.nodes.map((n) => ({ node: n, status: getNodeStatus(run, n.id) }));
            const isExpanded = expandedRun === run.request_id;
            return (
              <div key={run.request_id} className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-2)] overflow-hidden">
                <div className="flex items-center justify-between p-3 cursor-pointer" onClick={() => expandRun(run)}>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-[10px] font-mono font-bold text-[var(--text-primary)]">{run.request_id}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold ${
                      run.status === 'completed' ? 'bg-emerald-100 text-emerald-700 border border-emerald-200' :
                      run.status === 'failed' ? 'bg-rose-100 text-rose-700 border border-rose-200' :
                      'bg-blue-100 text-blue-700 border border-blue-200'
                    }`}>{run.status}</span>
                    {run.correlation_id && (
                      <span className="text-[9px] text-[var(--text-muted)] font-mono">cid: {run.correlation_id.slice(0, 8)}...</span>
                    )}
                    {run.total_time_ms && (
                      <span className="text-[9px] font-mono text-[var(--text-secondary)]">{run.total_time_ms}ms</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="text-[9px] px-2 py-1 rounded border border-[var(--border-default)] bg-[var(--surface-1)] text-[var(--text-secondary)] hover:bg-amber-50 hover:text-amber-700 hover:border-amber-200 disabled:opacity-50"
                      onClick={(e) => { e.stopPropagation(); triggerVaultSync(run); }}
                      disabled={!run.correlation_id}
                      title="Sync to Obsidian vault"
                    >
                      ⬇ Vault
                    </button>
                    <i className={`fas fa-chevron-down text-[10px] text-[var(--text-muted)] transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                  </div>
                </div>

                <div className="px-4 pb-2">
                  {/* Vault sync status */}
                  {vaultSyncStatus[run.request_id]?.message && (
                    <div className={`mt-2 text-[9px] font-mono px-2 py-1 rounded border ${
                      vaultSyncStatus[run.request_id].status === 'success' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                      vaultSyncStatus[run.request_id].status === 'error' ? 'bg-rose-50 text-rose-700 border-rose-200' :
                      'bg-blue-50 text-blue-700 border-blue-200'
                    }`}>
                      {vaultSyncStatus[run.request_id].message}
                    </div>
                  )}

                  {/* SVG DAG Visualization */}
                  <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface-1)] p-4 overflow-x-auto">
                    <svg viewBox="0 0 900 220" className="w-full h-auto select-none" style={{ minWidth: 700 }}>
                      {/* Edges */}
                      {GRAPH.edges.map((edge) => {
                        const fromIdx = GRAPH.nodes.findIndex((n) => n.id === edge.from);
                        const toIdx = GRAPH.nodes.findIndex((n) => n.id === edge.to);
                        if (fromIdx === -1 || toIdx === -1) return null;
                        const x1 = 80 + fromIdx * 180;
                        const y1 = 50;
                        const x2 = 80 + toIdx * 180;
                        const y2 = 50;
                        const midY = (y1 + y2) / 2;
                        const fromStatus = statuses[fromIdx]?.status || 'idle';
                        const edgeColor = fromStatus === 'success' ? '#22c55e' : '#cbd5e1';
                        return (
                          <path
                            key={`e-${edge.from}-${edge.to}`}
                            d={`M ${x1} ${y1} Q ${x1} ${midY}, ${(x1 + x2) / 2} ${midY} T ${x2} ${y2}`}
                            fill="none"
                            stroke={edgeColor}
                            strokeWidth="2"
                            markerEnd={`url(#arrowhead-${fromStatus})`}
                          />
                        );
                      })}
                      <defs>
                        {['idle', 'active', 'success', 'error'].map((s) => (
                          <marker key={s} id={`arrowhead-${s}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                            <path d="M 0 0 L 10 5 L 0 10 z" fill={s === 'success' ? '#22c55e' : '#cbd5e1'} />
                          </marker>
                        ))}
                      </defs>

                      {/* Nodes */}
                      {statuses.map(({ node, status }) => {
                        const style = NODE_STATUS_COLORS[status];
                        return (
                          <g key={node.id} onClick={() => setSelectedNode(selectedNode === node.id ? null : node.id)} style={{ cursor: 'pointer' }}>
                            <rect
                              x={80 + GRAPH.nodes.indexOf(node) * 180 - 48}
                              y={8}
                              width={96}
                              height={84}
                              rx={12}
                              fill={style.bg}
                              stroke={style.border}
                              strokeWidth={status === 'active' ? 3 : 2}
                              filter={status === 'active' ? 'url(#glow)' : undefined}
                            />
                            {status === 'active' && (
                              <circle cx={80 + GRAPH.nodes.indexOf(node) * 180} cy={64} r={6} fill="#3b82f6" className="animate-ping" opacity="0.3" />
                            )}
                            <text
                              x={80 + GRAPH.nodes.indexOf(node) * 180}
                              y={34}
                              textAnchor="middle"
                              className="text-[10px] font-bold pointer-events-none"
                              fill={style.text}
                            >
                              {node.label}
                            </text>
                            <text x={80 + GRAPH.nodes.indexOf(node) * 180} y={52} textAnchor="middle" className="text-[9px] pointer-events-none" fill={style.text} opacity="0.9">
                              <tspan x={80 + GRAPH.nodes.indexOf(node) * 180} dy="0">{node.icon}</tspan>
                            </text>
                            {status === 'success' && (
                              <text x={80 + GRAPH.nodes.indexOf(node) * 180} y={68} textAnchor="middle" className="text-[9px] pointer-events-none" fill="#15803d">✓ OK</text>
                            )}
                            {status === 'error' && (
                              <text x={80 + GRAPH.nodes.indexOf(node) * 180} y={68} textAnchor="middle" className="text-[9px] pointer-events-none" fill="#991b1b">⚠ ERR</text>
                            )}
                            {status === 'active' && (
                              <text x={80 + GRAPH.nodes.indexOf(node) * 180} y={68} textAnchor="middle" className="text-[9px] pointer-events-none" fill="#1e40af">⟳ </text>
                            )}
                          </g>
                        );
                      })}
                    </svg>
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="px-4 pb-4 space-y-2 border-t border-[var(--border-subtle)] pt-3 mt-1">
                    <p className="text-[9px] text-[var(--text-muted)] font-mono">
                      Correlation: <strong className="text-[var(--text-secondary)]">{run.correlation_id}</strong>
                    </p>
                    {GRAPH.nodes.map((node) => {
                      const phase = Object.values(run.phases).find(
                        (p) => p.agent_type?.toLowerCase().includes(node.id) || p.model?.toLowerCase().includes(node.id)
                      );
                      return (
                        <div key={`d-${node.id}`} className="flex items-start gap-3 p-2 rounded-lg bg-[var(--surface-1)] border border-[var(--border-default)]">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-[10px] font-mono font-bold text-[var(--text-primary)]">{node.label}</span>
                              <span className={`text-[9px] px-1.5 py-0.5 rounded-full border font-mono ${phase ? (phase.success ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200') : 'bg-slate-50 text-slate-500 border-slate-200'}`}>
                                {phase ? (phase.success ? 'SUCCESS' : 'ERROR') : 'PENDING'}
                              </span>
                              {phase?.provider && <span className="text-[9px] text-[var(--text-muted)]">Provider: <strong>{phase.provider}</strong></span>}
                              {phase?.model && <span className="text-[9px] text-[var(--text-muted)]">Model: <strong className="font-mono">{phase.model.split('/').pop()?.slice(0, 24)}</strong></span>}
                            </div>
                            <div className="mt-1 flex items-center gap-3 text-[9px] text-[var(--text-muted)]">
                              {phase?.latency_ms && <span>Latency: <strong className="text-[var(--text-secondary)]">{phase.latency_ms}ms</strong></span>}
                              {phase?.total_tokens && <span>Tokens: <strong className="text-[var(--text-secondary)]">{phase.total_tokens}</strong></span>}
                              {phase?.cost_usd && <span>Cost: <strong className="text-[var(--text-secondary)]">${phase.cost_usd.toFixed(6)}</strong></span>}
                            </div>
                            {phase?.errors && phase.errors.length > 0 && (
                              <div className="mt-1 text-[9px] text-rose-600 font-mono">⚠ {phase.errors.join('; ')}</div>
                            )}
                          </div>
                        </div>
                      );
                    })}
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

function enrichPhases(run: PipelineRun, traces: any[]): Record<string, PhaseDetail> {
  const result: Record<string, PhaseDetail> = { ...run.phases };
  for (const t of traces) {
    const key = t.provider;
    result[key] = {
      agent_type: t.provider,
      success: t.status === 'success',
      execution_time_ms: t.latency_ms,
      correlation_id: t.correlation_id,
      latency_ms: t.latency_ms,
      total_tokens: t.total_tokens,
      cost_usd: t.cost_usd,
      provider: t.provider,
      model: t.model,
    };
  }
  return result;
}

export default MultiAgentOrchestraView;
