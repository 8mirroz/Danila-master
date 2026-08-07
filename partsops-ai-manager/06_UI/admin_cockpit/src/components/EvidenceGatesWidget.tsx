import { useEffect, useState, useCallback } from 'react';
import { apiFetch } from '../lib/api';
import { Icon } from './Primitives';


type GateResult = {
  passed: boolean;
  reason: string;
  evidence: any;
  policy_version: string;
};

type GatesResponse = {
  request_id: string;
  gates: {
    PII_SAFE: GateResult;
    EVENT_CHAIN_VALID: GateResult;
    MATCH_CONFIDENCE: GateResult;
    PRICING_POLICY: GateResult;
    OPERATOR_APPROVAL: GateResult;
    DELIVERY_SAFE: GateResult;
    ERP_SYNC_VALID: GateResult;
  };
};

type EvidenceGatesWidgetProps = {
  requestId: string;
  refreshTrigger?: number;
};

export const EvidenceGatesWidget = ({ requestId, refreshTrigger = 0 }: EvidenceGatesWidgetProps) => {
  const [gatesData, setGatesData] = useState<GatesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/requests/${requestId}/gates`);
      if (!res.ok) {
        throw new Error(`Ошибка: ${res.status} ${res.statusText}`);
      }
      const data = await res.json();
      setGatesData(data);
    } catch (e) {
      console.error('Error fetching gates:', e);
      setError(e instanceof Error ? e.message : 'Не удалось загрузить гейты безопасности');
      setGatesData(null);
    } finally {
      setLoading(false);
    }
  }, [requestId]);

  useEffect(() => {
    fetchGates();
    
    // Auto-refresh every 10 seconds for active request evaluation
    const timer = setInterval(() => {
      void fetchGates();
    }, 10000);
    
    return () => clearInterval(timer);
  }, [fetchGates, refreshTrigger]);

  if (loading && !gatesData) {
    return (
      <div className="flex items-center justify-center p-4 border border-line rounded-md bg-surface-1">
        <Icon name="spinner" size={14} className="text-blue-500 mr-2 animate-spin" />
        <span className="text-xs text-ink-secondary">Анализ гейтов безопасности...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 border border-red-200 rounded-md bg-red-50 text-red-700 text-xs flex items-center">
        <Icon name="triangle-exclamation" size={14} className="mr-2" />
        <span>{error}</span>
      </div>
    );
  }

  if (!gatesData) return null;

  const gatesList = [
    { key: 'PII_SAFE', label: 'PII_SAFE (Защита PII)', icon: 'shield-halved' },
    { key: 'EVENT_CHAIN_VALID', label: 'EVENT_CHAIN_VALID (Цепочка аудита)', icon: 'link' },
    { key: 'MATCH_CONFIDENCE', label: 'MATCH_CONFIDENCE (Уверенность матчинга)', icon: 'magnifying-glass' },
    { key: 'PRICING_POLICY', label: 'PRICING_POLICY (Ценовая политика)', icon: 'scale-balanced' },
    { key: 'OPERATOR_APPROVAL', label: 'OPERATOR_APPROVAL (Одобрение оператора)', icon: 'user-check' },
    { key: 'DELIVERY_SAFE', label: 'DELIVERY_SAFE (Безопасность доставки)', icon: 'paper-plane' },
    { key: 'ERP_SYNC_VALID', label: 'ERP_SYNC_VALID (Готовность ERP)', icon: 'arrows-rotate' },
  ];

  return (
    <div className="border border-line rounded-md bg-surface-1 shadow-sm overflow-hidden">
      <div className="bg-surface-2 px-4 py-2 border-b border-line flex justify-between items-center">
        <span className="text-xs font-bold text-ink-primary uppercase tracking-wider flex items-center">
          <Icon name="shield" size={14} className="text-blue-600 mr-1.5" /> Гейты безопасности — Проверки данных
        </span>
        <span className="text-[10px] text-ink-muted">Заявка: {requestId}</span>
      </div>
      <div className="divide-y divide-[var(--border-subtle)] text-xs">
        {gatesList.map(g => {
          const result = gatesData.gates[g.key as keyof typeof gatesData.gates];
          if (!result) return null;
          
          return (
            <div key={g.key} className="flex items-center justify-between p-3 hover:bg-state-hover transition-colors">
              <div className="flex items-center space-x-2.5">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${
                  result.passed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  <Icon name={result.passed ? 'check' : 'xmark'} size={10} />
                </div>
                <div>
                  <span className="font-semibold text-ink-primary flex items-center">
                    <Icon name={g.icon} size={12} className="text-ink-muted mr-1.5" />
                    {g.label}
                  </span>
                  <span className="text-[10px] text-ink-muted block mt-0.5">{result.reason}</span>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                {result.passed ? (
                  <span className="px-2 py-0.5 text-[10px] font-bold text-green-700 bg-green-50 border border-green-200 rounded-full">
                    ПРОЙДЕН
                  </span>
                ) : (
                  <span className="px-2 py-0.5 text-[10px] font-bold text-red-700 bg-red-50 border border-red-200 rounded-full" title={result.reason}>
                    БЛОКИРОВАН
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
