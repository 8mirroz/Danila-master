const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? `${window.location.protocol}//${window.location.hostname}:8000`;

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
  const token = import.meta.env.VITE_PARTSOPS_API_TOKEN;
  const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID;

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (tenantId && !headers.has('X-Tenant-ID')) {
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
  const token = import.meta.env.VITE_PARTSOPS_API_TOKEN;
  const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID;

  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (tenantId) headers.set('X-Tenant-ID', tenantId);
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
  const token = import.meta.env.VITE_PARTSOPS_API_TOKEN;
  const tenantId = import.meta.env.VITE_PARTSOPS_TENANT_ID;

  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (tenantId) headers.set('X-Tenant-ID', tenantId);

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

export function createEventSource(tenantId?: string): EventSource {
  const baseUrl = API_BASE_URL.replace('/api', '');
  const url = `${baseUrl}/api/events/stream${tenantId ? `?tenant_id=${tenantId}` : ''}`;
  const es = new EventSource(url);
  return es;
}