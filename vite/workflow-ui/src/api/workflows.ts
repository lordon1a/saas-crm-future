import type { WorkflowItem, Execution, Stage } from '../types'

function getCsrfToken(): string {
  return document.querySelector('meta[name="csrf-token"]')
    ?.getAttribute('content') || ''
}

const headers = () => ({
  'Content-Type': 'application/json',
  'X-CSRFToken': getCsrfToken()
})

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

  stages: async (): Promise<Stage[]> => {
    try {
      const res = await fetch('/api/v1/pipeline/stages')
      if (!res.ok) return []
      const data = await res.json()
      return data.stages || []
    } catch {
      return []
    }
  }
}
