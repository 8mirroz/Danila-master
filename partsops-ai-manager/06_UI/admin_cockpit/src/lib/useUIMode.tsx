import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

// ─────────────────────────────────────────────
// UI Mode: Autopilot (simplified) vs Expert (full)
// ─────────────────────────────────────────────

export type UIMode = 'autopilot' | 'expert';

const STORAGE_KEY = 'partsops-ui-mode';

interface UIModeContextValue {
  mode: UIMode;
  setMode: (mode: UIMode) => void;
  toggle: () => void;
  isAutopilot: boolean;
  isExpert: boolean;
}

const UIModeContext = createContext<UIModeContextValue>({
  mode: 'autopilot',
  setMode: () => {},
  toggle: () => {},
  isAutopilot: true,
  isExpert: false,
});

function readStoredMode(): UIMode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'expert' || stored === 'autopilot') return stored;
  } catch {
    // localStorage unavailable
  }
  return 'autopilot';
}

export function UIModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeRaw] = useState<UIMode>(readStoredMode);

  const setMode = useCallback((next: UIMode) => {
    setModeRaw(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const toggle = useCallback(() => {
    setMode(mode === 'autopilot' ? 'expert' : 'autopilot');
  }, [mode, setMode]);

  // Sync data-ui-mode attribute on <body> for CSS overrides
  useEffect(() => {
    document.body.setAttribute('data-ui-mode', mode);
    return () => {
      document.body.removeAttribute('data-ui-mode');
    };
  }, [mode]);

  return (
    <UIModeContext.Provider
      value={{
        mode,
        setMode,
        toggle,
        isAutopilot: mode === 'autopilot',
        isExpert: mode === 'expert',
      }}
    >
      {children}
    </UIModeContext.Provider>
  );
}

export function useUIMode(): UIModeContextValue {
  return useContext(UIModeContext);
}
