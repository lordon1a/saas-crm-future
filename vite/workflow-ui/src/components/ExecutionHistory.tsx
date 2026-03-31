import { useEffect, useState } from 'react'
import { useWorkflowStore } from '../store/workflowStore'
import { workflowApi } from '../api/workflows'
import type { Execution } from '../types'

// ═══════════════════════════════════════════════════════════════════
// ExecutionHistory — Polished execution log
// ═══════════════════════════════════════════════════════════════════

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return 'Az önce'
  if (minutes < 60) return `${minutes}dk önce`
  if (hours < 24) return `${hours}sa önce`
  if (days < 7) return `${days}g önce`
  return date.toLocaleDateString('tr-TR')
}

const STATUS_CONFIG = {
  completed: { bg: '#dcfce7', text: '#166534', label: 'Tamamlandı', icon: 'fa-check-circle' },
  failed:    { bg: '#fef2f2', text: '#991b1b', label: 'Başarısız', icon: 'fa-times-circle' },
  pending:   { bg: '#fef3c7', text: '#92400e', label: 'Bekliyor', icon: 'fa-clock' },
  running:   { bg: '#dbeafe', text: '#1e40af', label: 'Çalışıyor', icon: 'fa-spinner fa-spin' },
} as const

function StatusBadge({ status }: { status: Execution['status'] }) {
  const cfg = STATUS_CONFIG[status]
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 999,
      fontSize: 11, fontWeight: 600,
      background: cfg.bg, color: cfg.text,
    }}>
      <i className={`fas ${cfg.icon}`} style={{ fontSize: 9 }} />
      {cfg.label}
    </span>
  )
}

export default function ExecutionHistory() {
  const { selectedWorkflow, executions, setExecutions } = useWorkflowStore()
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (selectedWorkflow) loadExecutions()
  }, [selectedWorkflow])

  const loadExecutions = async () => {
    if (!selectedWorkflow) return
    try {
      setLoading(true)
      const data = await workflowApi.executions(selectedWorkflow.id)
      setExecutions(data)
    } catch (err) {
      console.error('Failed to load executions:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!selectedWorkflow) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        height: '100%', color: '#94a3b8',
      }}>
        <p style={{ fontSize: 13 }}>Bir iş akışı seçin</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ padding: 20, width: '100%' }}>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} style={{
            height: 60, background: '#f8fafc', borderRadius: 10,
            marginBottom: 8, animation: 'pulse 1.5s infinite',
          }} />
        ))}
      </div>
    )
  }

  if (executions.length === 0) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        height: '100%', color: '#94a3b8', width: '100%',
      }}>
        <i className="fas fa-history" style={{ fontSize: 40, color: '#e2e8f0', marginBottom: 12 }} />
        <p style={{ fontSize: 14, fontWeight: 500, color: '#64748b', margin: '0 0 4px' }}>
          Henüz çalışma geçmişi yok
        </p>
        <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
          İş akışı çalıştığında burada göreceksiniz
        </p>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', width: '100%' }}>
      {/* Table header */}
      <div style={{
        display: 'grid', gridTemplateColumns: '100px 1fr 120px 100px',
        padding: '10px 20px', borderBottom: '1px solid #f3f4f6',
        background: '#fafafa',
        fontSize: 10, fontWeight: 700, color: '#94a3b8',
        textTransform: 'uppercase', letterSpacing: '0.5px',
        position: 'sticky', top: 0, zIndex: 1,
      }}>
        <span>Durum</span>
        <span>Varlık</span>
        <span>Tetikleyici</span>
        <span>Zaman</span>
      </div>

      {/* Rows */}
      {executions.map((execution) => (
        <div
          key={execution.id}
          style={{
            display: 'grid', gridTemplateColumns: '100px 1fr 120px 100px',
            padding: '12px 20px',
            borderBottom: '1px solid #f8fafc',
            transition: 'background 0.1s',
            cursor: 'default',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#f8fafc' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
        >
          <div>
            <StatusBadge status={execution.status} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#0f172a' }}>
              {execution.entity_name || `${execution.entity_type} #${execution.entity_id}`}
            </div>
            {execution.error_message && (
              <div style={{
                marginTop: 4, padding: '4px 8px',
                background: '#fef2f2', borderRadius: 4,
                fontSize: 11, color: '#dc2626', lineHeight: 1.4,
              }}>
                {execution.error_message}
              </div>
            )}
          </div>
          <div style={{ fontSize: 12, color: '#64748b' }}>
            {(execution.triggered_by || execution.trigger_type || '').replace(/_/g, ' ')}
          </div>
          <div style={{ fontSize: 12, color: '#94a3b8' }}>
            {formatTimeAgo(execution.started_at)}
          </div>
        </div>
      ))}
    </div>
  )
}
