import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// ═══════════════════════════════════════════════════════════════════
// Main entry — Mounts the full React workflow app
// No more window.WorkflowReact bridge — React is self-contained
// ═══════════════════════════════════════════════════════════════════

const rootEl = document.getElementById('workflow-react-root')
if (rootEl) {
  createRoot(rootEl).render(
    <StrictMode>
      <App />
    </StrictMode>
  )

  // Expose minimal API for template to detect mount status
  ;(window as unknown as Record<string, unknown>).WorkflowReact = { ready: true }
}
