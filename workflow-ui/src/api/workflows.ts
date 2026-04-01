import type { WorkflowItem, Execution, Stage, CanvasData, WorkflowVersion, WorkflowUsage, WorkflowTemplate } from '../types'

function getCsrfToken(): string {
  return document.querySelector('meta[name="csrf-token"]')
    ?.getAttribute('content') || ''
}

const headers = () => ({
  'Content-Type': 'application/json',
  'X-CSRFToken': getCsrfToken()
})

// Graph execution result
export interface GraphExecutionResult {
  workflow_id: number
  execution_id?: number
  status: 'success' | 'failed' | 'pending' | 'running' | 'completed'
  started_at: string
  completed_at?: string
  node_results: Array<{
    node_id: string
    node_type: string
    subtype: string
    status: 'success' | 'failed' | 'skipped' | 'pending' | 'running'
    started_at: string
    completed_at?: string
    duration_ms: number
    output?: Record<string, unknown>
    error?: string
    retries: number
  }>
  error?: string
  duration_ms: number
}

// Dry run result
export interface DryRunResult {
  workflow_id: number
  workflow_name: string
  execution_plan: {
    total_nodes: number
    total_edges: number
    trigger_nodes: string[]
    condition_nodes: string[]
    action_nodes: string[]
    execution_order: string[]
  }
  node_details: Array<{
    id: string
    type: string
    subtype: string
    label: string
  }>
}

export const workflowApi = {
  list: async (): Promise<WorkflowItem[]> => {
    const res = await fetch('/api/v1/workflows')
    if (!res.ok) throw new Error('İş akışları yüklenemedi')
    const data = await res.json()
    return data.workflows
  },

  get: async (id: number): Promise<WorkflowItem> => {
    const res = await fetch(`/api/v1/workflows/${id}`)
    if (!res.ok) throw new Error('İş akışı bulunamadı')
    return res.json()
  },

  create: async (data: Partial<WorkflowItem>): Promise<WorkflowItem> => {
    const res = await fetch('/api/v1/workflows', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(data)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Oluşturma başarısız' }))
      throw new Error(err.error || 'Oluşturma başarısız')
    }
    return res.json()
  },

  update: async (id: number, data: Partial<WorkflowItem>): Promise<void> => {
    const res = await fetch(`/api/v1/workflows/${id}`, {
      method: 'PUT',
      headers: headers(),
      body: JSON.stringify(data)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Güncelleme başarısız' }))
      throw new Error(err.error || 'Güncelleme başarısız')
    }
  },

  delete: async (id: number): Promise<void> => {
    const res = await fetch(`/api/v1/workflows/${id}`, {
      method: 'DELETE',
      headers: headers()
    })
    if (!res.ok) throw new Error('Silme başarısız')
  },

  toggle: async (id: number): Promise<void> => {
    const res = await fetch(`/api/v1/workflows/${id}/toggle`, {
      method: 'PATCH',
      headers: headers()
    })
    if (!res.ok) throw new Error('Durum değiştirme başarısız')
  },

  executions: async (id: number): Promise<Execution[]> => {
    const res = await fetch(`/api/v1/workflows/${id}/executions`)
    if (!res.ok) throw new Error('Geçmiş yüklenemedi')
    const data = await res.json()
    return data.executions || []
  },

  test: async (id: number): Promise<unknown> => {
    const res = await fetch(`/api/v1/workflows/${id}/test`, {
      method: 'POST',
      headers: headers()
    })
    if (!res.ok) throw new Error('Test başarısız')
    return res.json()
  },

  httpTest: async (config: {
    url: string
    method: string
    auth_type: string
    header_key: string
    header_value: string
    body: string
    timeout: number
  }): Promise<{
    success: boolean
    status?: number
    data?: unknown
    error?: string
    duration_ms?: number
  }> => {
    const res = await fetch('/api/v1/workflows/http-test', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(config)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'HTTP test başarısız' }))
      throw new Error(err.error || 'HTTP test başarısız')
    }
    return res.json()
  },

  templates: async (): Promise<WorkflowTemplate[]> => {
    const res = await fetch('/api/v1/workflows/templates')
    if (!res.ok) return []
    const data = await res.json()
    return data.templates || []
  },

  useTemplate: async (templateId: string): Promise<WorkflowItem> => {
    const res = await fetch(`/api/v1/workflows/templates/${templateId}/use`, {
      method: 'POST',
      headers: headers()
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Şablon kullanılamadı' }))
      throw new Error(err.error || 'Şablon kullanılamadı')
    }
    return res.json()
  },

  stages: async (): Promise<Stage[]> => {
    try {
      const res = await fetch('/api/v1/pipeline/stages')
      if (!res.ok) return []
      const data = await res.json()
      return data.stages || []
    } catch {
      return []
    }
  },

  // ═══════════════════════════════════════════════════════════════════
  // GRAPH EXECUTION (n8n-style)
  // ═══════════════════════════════════════════════════════════════════

  /**
   * Execute a workflow using the n8n-style graph runner.
   * Takes canvas_data (nodes + edges) and executes as a directed graph.
   */
  executeGraph: async (
    workflowId: number,
    params: {
      entity_type: string
      entity_id: number
      context?: Record<string, unknown>
      canvas_data?: CanvasData
    }
  ): Promise<GraphExecutionResult> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/execute`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(params)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Execution failed' }))
      throw new Error(err.error || 'Execution failed')
    }
    return res.json()
  },

  /**
   * Dry-run a workflow without executing actions.
   * Returns the execution plan (which nodes would execute and in what order).
   */
  dryRunGraph: async (
    workflowId: number,
    params: {
      entity_type: string
      entity_id: number
      context?: Record<string, unknown>
      canvas_data?: CanvasData
    }
  ): Promise<DryRunResult> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/execute/dry-run`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(params)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Dry run failed' }))
      throw new Error(err.error || 'Dry run failed')
    }
    return res.json()
  },

  // ═══════════════════════════════════════════════════════════════════
  // VERSIONING
  // ═══════════════════════════════════════════════════════════════════

  publish: async (workflowId: number): Promise<{ success: boolean; version: WorkflowVersion }> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/publish`, {
      method: 'POST',
      headers: headers()
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Publish failed' }))
      throw new Error(err.error || 'Publish failed')
    }
    return res.json()
  },

  versions: async (workflowId: number): Promise<WorkflowVersion[]> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/versions`)
    if (!res.ok) throw new Error('Versions load failed')
    const data = await res.json()
    return data.versions || []
  },

  revert: async (workflowId: number, versionId: number): Promise<{ success: boolean; message: string }> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/revert/${versionId}`, {
      method: 'POST',
      headers: headers()
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Revert failed' }))
      throw new Error(err.error || 'Revert failed')
    }
    return res.json()
  },

  // ═══════════════════════════════════════════════════════════════════
  // TEST RUN (real graph execution with dry-run)
  // ═══════════════════════════════════════════════════════════════════

  testRun: async (
    workflowId: number,
    params: { entity_type?: string; entity_id?: number; canvas_data?: CanvasData }
  ): Promise<GraphExecutionResult> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/test-run`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(params)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Test run failed' }))
      throw new Error(err.error || 'Test run failed')
    }
    const data = await res.json()
    return data.test_result
  },

  /**
   * Get execution status (for polling)
   */
  execute: async (executionId: number): Promise<GraphExecutionResult> => {
    const res = await fetch(`/api/v1/workflows/executions/${executionId}`, {
      method: 'GET',
      headers: headers()
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Execution status fetch failed' }))
      throw new Error(err.error || 'Execution status fetch failed')
    }
    return res.json()
  },

  // ═══════════════════════════════════════════════════════════════════
  // USAGE / CREDITS
  // ═══════════════════════════════════════════════════════════════════

  usage: async (): Promise<WorkflowUsage> => {
    const res = await fetch('/api/v1/workflows/usage')
    if (!res.ok) throw new Error('Usage load failed')
    return res.json()
  },

  usageHistory: async (): Promise<WorkflowUsage[]> => {
    const res = await fetch('/api/v1/workflows/usage/history')
    if (!res.ok) throw new Error('Usage history load failed')
    const data = await res.json()
    return data.history || []
  },

  // ═══════════════════════════════════════════════════════════════════
  // MANUAL TRIGGER
  // ═══════════════════════════════════════════════════════════════════

  runManual: async (workflowId: number, entityType?: string, entityId?: number): Promise<GraphExecutionResult> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/run-manual`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ entity_type: entityType || 'contact', entity_id: entityId || null }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Manual run failed' }))
      throw new Error(err.error || 'Manual run failed')
    }
    return res.json()
  },

  // ═══════════════════════════════════════════════════════════════════
  // VARIABLES SCHEMA
  // ═══════════════════════════════════════════════════════════════════

  variablesSchema: async (workflowId: number): Promise<{ groups: Array<{ group: string; vars: Array<{ path: string; label: string; type: string }> }> }> => {
    const res = await fetch(`/api/v1/workflows/${workflowId}/variables-schema`, {
      headers: headers(),
    })
    if (!res.ok) throw new Error('Variables schema load failed')
    return res.json()
  },

  // ═══════════════════════════════════════════════════════════════════
  // SSE EXECUTION STREAM
  // ═══════════════════════════════════════════════════════════════════

  streamExecution: (executionId: number, onUpdate: (data: GraphExecutionResult & { execution_id: number; error?: string }) => void): () => void => {
    const evtSource = new EventSource(`/api/v1/workflows/executions/${executionId}/stream`, { withCredentials: true })
    evtSource.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data)
        onUpdate(parsed)
        if (parsed.status === 'completed' || parsed.status === 'failed' || parsed.error) {
          evtSource.close()
        }
      } catch {
        // ignore parse errors
      }
    }
    evtSource.onerror = () => { evtSource.close() }
    return () => evtSource.close()
  },
}
