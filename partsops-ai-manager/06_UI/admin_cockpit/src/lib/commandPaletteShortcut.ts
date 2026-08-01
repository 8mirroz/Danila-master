type ShortcutState = {
  installed: boolean;
  pending: boolean;
  open: (() => void) | null;
};

declare global {
  interface Window {
    __partsopsCommandPaletteShortcut?: ShortcutState;
  }
}

function shortcutState(): ShortcutState {
  const existing = window.__partsopsCommandPaletteShortcut;
  if (existing) return existing;
  const state: ShortcutState = { installed: false, pending: false, open: null };
  window.__partsopsCommandPaletteShortcut = state;
  return state;
}

function installShortcutListener(state: ShortcutState): void {
  if (!state.installed) {
    state.installed = true;
    window.addEventListener('keydown', (event) => {
      const key = event.key.toLowerCase();
      const keyboardShortcut = key === 'k' && (event.metaKey || event.ctrlKey);
      const programmaticActivation = key === 'k' && event.target === window;
      if (!keyboardShortcut && !programmaticActivation) return;
      event.preventDefault();
      if (state.open) state.open();
      else state.pending = true;
    });
  }
}

// This executes while the module graph loads, before React begins the AuthGate
// bootstrap. A shortcut pressed during a slow SSO/App mount is therefore held.
const bootstrappedState = shortcutState();
installShortcutListener(bootstrappedState);

/** Register the current App instance; HMR/SSO remounts replace only this callback. */
export function subscribeCommandPaletteShortcut(open: () => void): () => void {
  const state = bootstrappedState;
  state.open = open;
  if (state.pending) {
    state.pending = false;
    open();
  }
  return () => {
    if (state.open === open) state.open = null;
  };
}
