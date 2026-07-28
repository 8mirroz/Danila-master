import { useState, useEffect, useCallback } from 'react';
import { apiJson } from './api';

export interface DataHealthResponse {
  status: string;
  generated_at: string;
  tenant_id: string;
  entity_counts: {
    requests: {
      total: number;
      by_status: Record<string, number>;
      active_queue_total: number;
    };
    suppliers: {
      total: number;
      active: number;
      inactive: number;
    };
    invoices: {
      total: number;
      by_status: Record<string, number>;
    };
    approval_tickets: {
      total: number;
      pending: number;
      approved: number;
      rejected: number;
    };
    erp_sync_logs: {
      total: number;
      success: number;
      failed: number;
    };
    events: number;
    llm_usage_logs: number;
  };
  freshness: {
    last_request_at?: string;
    last_event_at?: string;
    last_erp_sync_at?: string;
    seconds_since_last_request?: number;
    seconds_since_last_event?: number;
    seconds_since_last_erp_sync?: number;
  };
  health_indicators: {
    queue_staleness: {
      stuck_over_24h: number;
      stuck_over_72h: number;
      oldest_active_request_hours: number;
    };
    approval_pressure: {
      pending_approvals: number;
    };
    erp_health: {
      currently_failing: boolean;
    };
    agent_health: {
      llm_error_rate_last_hour: number;
      llm_errors_last_hour: number;
      llm_requests_last_hour: number;
    };
    supplier_feed_freshness: {
      feed_stale_suppliers: number;
      suppliers_without_feed: number;
    };
  };
  alerts: Array<{
    level: 'info' | 'warning' | 'critical';
    source: string;
    message: string;
    count?: number;
  }>;
}

export interface LlmCostResponse {
  count: number;
  total_cost_usd: number;
  by_provider: Record<string, number>;
  by_model: Record<string, number>;
}

export interface PipelineRun {
  run_id: string;
  request_id: string;
  status: string;
  current_stage: string;
  started_at: string;
  completed_at?: string;
}

export interface DashboardViewModel {
  health: DataHealthResponse | null;
  llmCosts: LlmCostResponse | null;
  pipelineRuns: PipelineRun[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useDashboardViewModel(fetchTrigger: number = 0): DashboardViewModel {
  const [health, setHealth] = useState<DataHealthResponse | null>(null);
  const [llmCosts, setLlmCosts] = useState<LlmCostResponse | null>(null);
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, costsData, runsData] = await Promise.allSettled([
        apiJson<DataHealthResponse>('/api/admin/data-health'),
        apiJson<LlmCostResponse>('/api/admin/observability/llm-costs'),
        apiJson<PipelineRun[]>('/api/admin/observability/pipeline-runs'),
      ]);

      if (healthData.status === 'fulfilled') {
        setHealth(healthData.value);
      } else {
        console.error('Failed to fetch data health:', healthData.reason);
      }

      if (costsData.status === 'fulfilled') {
        setLlmCosts(costsData.value);
      } else {
        console.error('Failed to fetch LLM costs:', costsData.reason);
      }

      if (runsData.status === 'fulfilled') {
        setPipelineRuns(Array.isArray(runsData.value) ? runsData.value : []);
      } else {
        setPipelineRuns([]);
      }
    } catch (err: any) {
      setError(err?.message || 'Ошибка загрузки дашборда');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData, fetchTrigger]);

  return {
    health,
    llmCosts,
    pipelineRuns,
    loading,
    error,
    refetch: fetchData,
  };
}
