import { useWorkflowStore, type ExecutionLogEntry } from '../store/workflowStore'

// ═══════════════════════════════════════════════════════════════════
// ExecutionOutputPanel — Live output during workflow run
// ═══════════════════════════════════════════════════════════════════

function formatDuration(ms?: number): string {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function LogEntry({ log }: { log: ExecutionLogEntry }) {
  const statusConfig = {
    pending: { bg: '#fef3c7', text: '#92400e', icon: 'fa-clock', label: 'Bekliyor' },
    running: { bg: '#dbeafe', text: '#1e40af', icon: 'fa-spinner fa-spin', label: 'Çalışıyor' },
    success: { bg: '#dcfce7', text: '#166534', icon: 'fa-check-circle', label: 'Başarılı' },
    failed: { bg: '#fef2f2', text: '#991b1b', icon: 'fa-times-circle', label: 'Hata' },
  } as const

  const cfg = statusConfig[log.status]

  return (
    <div style={{
      borderBottom: '1px solid #f3f4f6',
      padding: '12px 16px',
      animation: 'slideInRight 0.2s ease-out',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 24, height: 24, borderRadius: 6,
            background: log.status === 'running' ? '#3b82f6' : log.status === 'success' ? '#22c55e' : log.status === 'failed' ? '#ef4444' : '#f59e0b',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <i className={`fas ${log.status === 'running' ? 'fa-cog fa-spin' : 'fa-arrow-right'}`} style={{ color: '#fff', fontSize: 10 }} />
          </div>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>
            {log.nodeName}
          </span>
        </div>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          padding: '2px 8px', borderRadius: 999,
          fontSize: 10, fontWeight: 600,
          background: cfg.bg, color: cfg.text,
        }}>
          <i className={`fas ${cfg.icon}`} style={{ fontSize: 9 }} />
          {cfg.label}
        </span>
      </div>

      {/* Duration */}
      {log.durationMs !== undefined && (
        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>
          <i className="fas fa-clock" style={{ marginRight: 4 }} />
          {formatDuration(log.durationMs)}
        </div>
      )}

      {/* Output/Error */}
      {log.output && log.status === 'success' && (
        <div style={{
          background: '#0f172a',
          borderRadius: 8,
          padding: '10px 12px',
          fontFamily: 'monospace',
          fontSize: 11,
          color: '#22c55e',
          overflow: 'auto',
          maxHeight: 150,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}>
          {typeof log.output === 'string' ? log.output : JSON.stringify(log.output, null, 2)}
        </div>
      )}

      {log.error && (
        <div style={{
          background: '#fef2f2',
          borderRadius: 8,
          padding: '10px 12px',
          fontSize: 11,
          color: '#dc2626',
          border: '1px solid #fecaca',
        }}>
          <i className="fas fa-exclamation-triangle" style={{ marginRight: 6 }} />
          {log.error}
        </div>
      )}
    </div>
  )
}

export default function ExecutionOutputPanel() {
  const { executionLogs, clearExecutionLogs, isExecuting } = useWorkflowStore()

  if (executionLogs.length === 0) {
    return (
      <div style={{
        width: 300,
        background: '#ffffff',
        borderLeft: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}>
        {/* Header */}
        <div style={{
          padding: '12px 16px',
          borderBottom: '1px solid #f3f4f6',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <i className="fas fa-terminal" style={{ color: '#64748b', fontSize: 13 }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>
              Çıktı
            </span>
          </div>
        </div>

        {/* Empty state */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          padding: 24, color: '#94a3b8', textAlign: 'center',
        }}>
          <i className="fas fa-play-circle" style={{ fontSize: 32, color: '#e2e8f0', marginBottom: 12 }} />
          <p style={{ fontSize: 12, color: '#64748b', margin: '0 0 4px' }}>
            Henüz çıktı yok
          </p>
          <p style={{ fontSize: 11, color: '#94a3b8', margin: 0 }}>
            İş akışını çalıştırdığında burada göreceksin
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      width: 300,
      background: '#ffffff',
      borderLeft: '1px solid #e5e7eb',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      animation: 'slideInRight 0.2s ease-out',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid #f3f4f6',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <i className="fas fa-terminal" style={{ color: isExecuting ? '#3b82f6' : '#64748b', fontSize: 13 }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>
            Çıktı
          </span>
          {isExecuting && (
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: '#3b82f6', animation: 'pulse 1s infinite',
            }} />
          )}
        </div>
        <button
          onClick={clearExecutionLogs}
          style={{
            width: 24, height: 24, borderRadius: 6,
            background: 'transparent', border: 'none',
            color: '#94a3b8', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9'; e.currentTarget.style.color = '#475569' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#94a3b8' }}
          title="Temizle"
        >
          <i className="fas fa-trash-alt" style={{ fontSize: 11 }} />
        </button>
      </div>

      {/* Logs */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {executionLogs.map((log) => (
          <LogEntry key={log.id} log={log} />
        ))}
      </div>
    </div>
  )
}