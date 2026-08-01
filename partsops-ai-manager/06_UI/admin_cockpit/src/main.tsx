import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import { AuthGate } from './components/AuthGate';
import '@fontsource-variable/plus-jakarta-sans';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthGate />
    <Toaster
      position="bottom-right"
      toastOptions={{
        duration: 4000,
        style: {
          background: 'var(--surface-1, #ffffff)',
          color: 'var(--text-primary, #0f172a)',
          border: '1px solid var(--border-default, #cbd5e1)',
          borderRadius: '12px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
          fontSize: '13px',
          fontWeight: '600',
        },
      }}
    />
  </React.StrictMode>,
)
