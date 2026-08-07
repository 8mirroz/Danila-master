import { getAccessToken, oidcEnabled } from './auth';

/**
 * Prefer same-origin + Vite proxy in local dev (avoids CORS on 5xx).
 * Override with VITE_API_BASE_URL for absolute backends.
 */
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `API request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = oidcEnabled() ? getAccessToken() : import.meta.env.VITE_PARTSOPS_API_TOKEN;
  const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID;

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!oidcEnabled() && tenantId && !headers.has('X-Tenant-ID')) {
    headers.set('X-Tenant-ID', tenantId);
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 20_000);

  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      signal: init.signal ?? controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiError(res.status, data?.detail ?? data ?? res.statusText);
  }
  return data as T;
}

export function buildApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export async function uploadAttachment(
  file: File,
  requestId?: string
): Promise<{ artifact_id: string; stored_path: string; status: string }> {
  const formData = new FormData();
  formData.append('file', file);
  
  const headers = new Headers();
  const token = oidcEnabled() ? getAccessToken() : import.meta.env.VITE_PARTSOPS_API_TOKEN;
  const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID;

  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (!oidcEnabled() && tenantId) headers.set('X-Tenant-ID', tenantId);
  if (requestId) headers.set('Request-Id', requestId);

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 60_000);

  try {
    const res = await fetch(`${API_BASE_URL}/api/attachments/upload`, {
      method: 'POST',
      headers,
      body: formData,
      signal: controller.signal,
    });

    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    
    if (!res.ok) {
      throw new ApiError(res.status, data?.detail ?? data ?? res.statusText);
    }
    
    return data as { artifact_id: string; stored_path: string; status: string };
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function importFromArtifact(
  artifactId: string,
  source?: string,
  customerName?: string,
  priority?: string
): Promise<{ request: any }> {
  const headers = new Headers();
  headers.set('Content-Type', 'application/json');
  const token = oidcEnabled() ? getAccessToken() : import.meta.env.VITE_PARTSOPS_API_TOKEN;
  const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID;

  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (!oidcEnabled() && tenantId) headers.set('X-Tenant-ID', tenantId);

  const res = await fetch(`${API_BASE_URL}/api/requests/import-from-artifact`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      artifact_id: artifactId,
      source: source || 'FILE_UPLOAD',
      customer_name: customerName || 'File Upload Client',
      priority: priority || 'normal',
    }),
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    throw new ApiError(res.status, data?.detail ?? data ?? res.statusText);
  }

  return data as { request: any };
}

export type ContractPositionDraft = {
  part_number: string;
  description?: string;
  quantity: number;
};

export type ContractCreateResponse = {
  request_id: string;
  contract_ref: string;
  positions: number;
  status: string;
};

export type ContractPositionDetail = {
  position_id: string;
  line_no: number;
  part_number: string;
  description?: string | null;
  quantity: number;
  review_status: string;
  selected_evidence_id?: string | null;
  position_uuid: string;
  completeness_status: string;
  blocking_status: string;
  blocking_error_code?: string | null;
  evidence: Array<{
    evidence_id: string;
    source: string;
    price: number;
    source_url: string;
    captured_at: string;
    screenshot_sha256?: string | null;
    screenshot_readability_status?: string;
    screenshot_completeness_status?: string;
  }>;
};

export type ContractCandidates = {
  oem_candidates: Array<{
    candidate_id: string;
    oem_number: string;
    manufacturer?: string | null;
    source: string;
    confidence: number;
    verification_status: string;
  }>;
  analog_candidates: Array<{
    candidate_id: string;
    article: string;
    brand: string;
    source: string;
    compatibility_score: number;
    evidence_score: number;
    manual_review_status: string;
  }>;
};

export type ContractCoverage = {
  has_data: boolean;
  has_check: boolean;
  has_evidence: boolean;
  has_responsible: boolean;
  has_workflow_gate: boolean;
  has_test: boolean;
  export_covered: boolean;
  status: string;
};

export type ContractControlRequirement = {
  requirement_id: string;
  clause: string;
  summary: string;
  type: string;
  object_scope: string;
  criticality: string;
  coverage_status: string;
  implementation_element?: string;
  coverage: ContractCoverage | null;
};

export type ContractControlGap = {
  gap_id: string;
  requirement_id?: string;
  category: string;
  risk: string;
  priority: string;
  status: string;
  description: string;
  closure_criteria: string;
};

export type ContractControlPlane = {
  request_id: string;
  contract_ref: string;
  status: string;
  audits: Array<{
    audit_id: string;
    status: string;
    unresolved_critical_count: number;
    completed_at?: string | null;
  }>;
  requirements: ContractControlRequirement[];
  gaps: ContractControlGap[];
  adrs: Array<{
    adr_id: string;
    requirement_id?: string | null;
    problem: string;
    decision: string;
    affected_components: string;
  }>;
  client_approvals: Array<{
    approval_id: string;
    export_id: string;
    approved_by: string;
    approved_at: string;
  }>;
  purchase_authorizations: Array<{
    authorization_id: string;
    approval_id: string;
    authorized_by: string;
    authorized_at: string;
  }>;
  exceptions: Array<{
    exception_id: string;
    code: string;
    severity: string;
    status: string;
    owner: string;
    retry_count: number;
    max_retries: number;
    resolution?: string | null;
  }>;
  metrics: {
    quality: {
      requirement_coverage_percent: number;
      requirements_covered: number;
      requirements_total: number;
      open_gaps: number;
      blocking_exceptions: number;
      rejected_workflow_transitions: number;
    };
    evidence: {
      positions_total: number;
      total_evidence: number;
      positions_with_all_required_sources: number;
      required_source_coverage_percent: number;
      positions_with_valid_screenshots: number;
      screenshot_coverage_percent: number;
      stale_evidence: number;
    };
    cost: {
      selected_positions: number;
      contract_total: number;
      average_position_total: number;
      currency: string;
    };
    process: {
      workflow_events: number;
      elapsed_minutes?: number | null;
      exports: number;
      client_approvals: number;
      purchase_authorizations: number;
      purchases: number;
      receipt_verifications: number;
      archives: number;
      purchase_locked: boolean;
    };
  };
  purchases: Array<{
    purchase_id: string;
    authorization_id: string;
    supplier_ref: string;
    ordered_by: string;
    ordered_at: string;
    amount_total: number;
    currency: string;
    evidence_ref?: string | null;
    status: string;
    comment?: string | null;
  }>;
  receipt_verifications: Array<{
    receipt_id: string;
    purchase_id: string;
    verified_by: string;
    verified_at: string;
    evidence_ref: string;
    received_quantity: number;
    status: string;
    discrepancy_note?: string | null;
  }>;
  archives: Array<{
    archive_id: string;
    receipt_id: string;
    archived_by: string;
    archived_at: string;
    archive_ref: string;
    registry_hash?: string | null;
    status: string;
    comment?: string | null;
  }>;
  workflow: {
    workflow_id: string;
    current_stage: string;
    current_stage_index: number;
    blocked: boolean;
    blocking_code?: string | null;
    blocking_reason?: string | null;
    stages: string[];
    events: Array<{
      workflow_event_id: string;
      from_stage?: string | null;
      to_stage: string;
      actor_id: string;
      reason: string;
      allowed: boolean;
      violations: string[];
      created_at: string;
    }>;
  };
};

export async function createCrawlerContract(
  positions: ContractPositionDraft[],
): Promise<ContractCreateResponse> {
  return apiJson<ContractCreateResponse>('/api/contracts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contract_ref: '2026.170160',
      positions,
      actor_id: 'operator',
    }),
  });
}

export async function fetchContractControlPlane(requestId: string): Promise<ContractControlPlane> {
  return apiJson<ContractControlPlane>(`/api/contracts/${requestId}/control-plane`);
}

export async function fetchContractPositions(requestId: string): Promise<ContractPositionDetail[]> {
  return apiJson<ContractPositionDetail[]>(`/api/contracts/${requestId}/positions`);
}

export async function fetchContractCandidates(requestId: string, positionId: string): Promise<ContractCandidates> {
  return apiJson<ContractCandidates>(`/api/contracts/${requestId}/positions/${positionId}/candidates`);
}

export async function registerContractOemCandidate(
  requestId: string,
  positionId: string,
  data: {
    oem_number: string;
    manufacturer?: string;
    source: string;
    source_url?: string;
    compatibility_evidence: Array<{ evidence_type: string; source: string; source_url?: string }>;
  },
): Promise<{ candidate_id: string; verification_status: string }> {
  return apiJson<{ candidate_id: string; verification_status: string }>(
    `/api/contracts/${requestId}/positions/${positionId}/oem-candidates`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: 'operator', data }),
    },
  );
}

export async function registerContractAnalogCandidate(
  requestId: string,
  positionId: string,
  data: {
    article: string;
    brand: string;
    source: string;
    oem_candidate_id?: string;
    independent_confirmations: number;
    compatibility_evidence: Array<{ evidence_type: string; source: string; source_url?: string }>;
  },
): Promise<{ candidate_id: string; manual_review_status: string }> {
  return apiJson<{ candidate_id: string; manual_review_status: string }>(
    `/api/contracts/${requestId}/positions/${positionId}/analog-candidates`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actor_id: 'operator', data }),
    },
  );
}

export type PartsOpsEventSource = Pick<EventSource, 'close' | 'onerror' | 'onmessage'>;

class AuthenticatedEventSource implements PartsOpsEventSource {
  onerror: ((this: EventSource, ev: Event) => any) | null = null;
  onmessage: ((this: EventSource, ev: MessageEvent) => any) | null = null;
  private readonly controller = new AbortController();

  constructor(url: string, token: string) {
    void this.consume(url, token);
  }

  close(): void {
    this.controller.abort();
  }

  private async consume(url: string, token: string): Promise<void> {
    try {
      const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: this.controller.signal });
      if (!response.ok || !response.body) throw new Error(`SSE HTTP ${response.status}`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (!this.controller.signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';
        frames.forEach((frame) => {
          const data = frame.split('\n').find((line) => line.startsWith('data:'))?.slice(5).trim();
          if (data) this.onmessage?.call(this as unknown as EventSource, new MessageEvent('message', { data }));
        });
      }
      if (!this.controller.signal.aborted) this.onerror?.call(this as unknown as EventSource, new Event('error'));
    } catch {
      if (!this.controller.signal.aborted) this.onerror?.call(this as unknown as EventSource, new Event('error'));
    }
  }
}

export function createEventSource(tenantId?: string): PartsOpsEventSource {
  const baseUrl = API_BASE_URL;
  const token = getAccessToken();
  if (oidcEnabled() && token) return new AuthenticatedEventSource(`${baseUrl}/api/events/stream`, token);
  const url = `${baseUrl}/api/events/stream${tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''}`;
  return new EventSource(url);
}

export type SupplierAuthStatusMap = Record<string, { site: string; auth_at: string | null; profile_exists: boolean }>;

export async function fetchSuppliersAuthStatus(): Promise<SupplierAuthStatusMap> {
  return apiJson<SupplierAuthStatusMap>('/api/suppliers/auth-status');
}

export async function validateContractData(requestId: string): Promise<any> {
  return apiJson<any>(`/api/contracts/${requestId}/validate`, {
    method: 'POST',
  });
}
