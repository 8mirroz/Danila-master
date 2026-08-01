const OIDC_ISSUER = (import.meta.env.VITE_OIDC_ISSUER ?? '').replace(/\/$/, '');
const OIDC_CLIENT_ID = import.meta.env.VITE_OIDC_CLIENT_ID ?? '';
const OIDC_REDIRECT_URI = import.meta.env.VITE_OIDC_REDIRECT_URI ?? `${window.location.origin}/`;

const ACCESS_TOKEN_KEY = 'partsops.oidc.access_token';
const PKCE_VERIFIER_KEY = 'partsops.oidc.pkce_verifier';
const STATE_KEY = 'partsops.oidc.state';

export type AuthBootstrap =
  | { status: 'ready'; oidc: false }
  | { status: 'authenticated'; oidc: true }
  | { status: 'unauthenticated'; oidc: true; error?: string };

export function oidcEnabled(): boolean {
  return Boolean(OIDC_ISSUER && OIDC_CLIENT_ID);
}

function base64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function randomValue(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return base64Url(new Uint8Array(digest));
}

function tokenIsExpired(token: string): boolean {
  try {
    const [, payload] = token.split('.');
    const json = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    return typeof json.exp === 'number' && json.exp * 1000 <= Date.now() + 30_000;
  } catch {
    return true;
  }
}

export function getAccessToken(): string | undefined {
  if (!oidcEnabled()) return undefined;
  const token = sessionStorage.getItem(ACCESS_TOKEN_KEY) ?? undefined;
  if (token && tokenIsExpired(token)) {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    return undefined;
  }
  return token;
}

export async function beginLogin(): Promise<void> {
  if (!oidcEnabled()) return;
  const verifier = randomValue();
  const state = randomValue();
  sessionStorage.setItem(PKCE_VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);

  const params = new URLSearchParams({
    client_id: OIDC_CLIENT_ID,
    redirect_uri: OIDC_REDIRECT_URI,
    response_type: 'code',
    scope: 'openid profile email',
    code_challenge: await challengeFor(verifier),
    code_challenge_method: 'S256',
    state,
  });
  window.location.assign(`${OIDC_ISSUER}/protocol/openid-connect/auth?${params}`);
}

export function logout(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(PKCE_VERIFIER_KEY);
  sessionStorage.removeItem(STATE_KEY);
}

export async function initializeAuth(): Promise<AuthBootstrap> {
  if (!oidcEnabled()) return { status: 'ready', oidc: false };

  const url = new URL(window.location.href);
  const code = url.searchParams.get('code');
  const returnedState = url.searchParams.get('state');
  const error = url.searchParams.get('error');
  if (error) {
    url.searchParams.delete('error');
    url.searchParams.delete('error_description');
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    return { status: 'unauthenticated', oidc: true, error: 'Вход через OIDC был отменён или отклонён.' };
  }

  if (!code) {
    return getAccessToken()
      ? { status: 'authenticated', oidc: true }
      : { status: 'unauthenticated', oidc: true };
  }

  const expectedState = sessionStorage.getItem(STATE_KEY);
  const verifier = sessionStorage.getItem(PKCE_VERIFIER_KEY);
  if (!expectedState || !verifier || returnedState !== expectedState) {
    logout();
    return { status: 'unauthenticated', oidc: true, error: 'Не удалось проверить состояние OIDC-входа.' };
  }

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: OIDC_CLIENT_ID,
    code,
    redirect_uri: OIDC_REDIRECT_URI,
    code_verifier: verifier,
  });
  try {
    const response = await fetch(`${OIDC_ISSUER}/protocol/openid-connect/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    const payload = await response.json() as { access_token?: string };
    if (!response.ok || !payload.access_token) throw new Error('OIDC token exchange failed');
    sessionStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
    sessionStorage.removeItem(PKCE_VERIFIER_KEY);
    sessionStorage.removeItem(STATE_KEY);
    url.searchParams.delete('code');
    url.searchParams.delete('state');
    url.searchParams.delete('session_state');
    url.searchParams.delete('iss');
    window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    return { status: 'authenticated', oidc: true };
  } catch {
    logout();
    return { status: 'unauthenticated', oidc: true, error: 'Не удалось завершить OIDC-вход. Повторите попытку.' };
  }
}
