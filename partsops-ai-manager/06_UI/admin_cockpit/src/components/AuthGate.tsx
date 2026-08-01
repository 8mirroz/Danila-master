import { useEffect, useState } from 'react';
import App from '../App';
import { beginLogin, initializeAuth, type AuthBootstrap } from '../lib/auth';

export function AuthGate() {
  const [auth, setAuth] = useState<AuthBootstrap | null>(null);

  useEffect(() => {
    let active = true;
    void initializeAuth().then((nextAuth) => {
      if (active) setAuth(nextAuth);
    });
    return () => { active = false; };
  }, []);

  if (!auth) return <main className="auth-gate">Проверяем защищённую сессию…</main>;
  if (auth.status === 'unauthenticated') {
    return (
      <main className="auth-gate">
        <section>
          <p className="auth-gate__eyebrow">PARTSOPS QUOTEOPS</p>
          <h1>Войдите в рабочее пространство</h1>
          <p>{auth.error ?? 'Для доступа требуется корпоративная учётная запись.'}</p>
          <button type="button" onClick={() => void beginLogin()}>Войти через SSO</button>
        </section>
      </main>
    );
  }
  return <App />;
}
