import { useState, useMemo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { NODE_CONFIGS, TYPE_COLORS } from '../constants/nodeConfigs'
import { useWorkflowStore } from '../store/workflowStore'
import type { WorkflowNodeData, NodeType } from '../types'

// ═══════════════════════════════════════════════════════════════════
// Execution state colors (n8n-style)
// ═══════════════════════════════════════════════════════════════════
const EXECUTION_COLORS = {
  pending: { border: '#6366f1', glow: 'rgba(99, 102, 241, 0.3)', icon: '#6366f1' },
  running: { border: '#f59e0b', glow: 'rgba(245, 158, 11, 0.4)', icon: '#f59e0b' },
  success: { border: '#22c55e', glow: 'rgba(34, 197, 94, 0.3)', icon: '#22c55e' },
  failed: { border: '#ef4444', glow: 'rgba(239, 68, 68, 0.4)', icon: '#ef4444' },
  skipped: { border: '#94a3b8', glow: 'rgba(148, 163, 184, 0.3)', icon: '#94a3b8' },
} as const

// ═══════════════════════════════════════════════════════════════════
// WorkflowNode — n8n / Twenty CRM quality node card
// ═══════════════════════════════════════════════════════════════════

export default function WorkflowNode({ id, data, selected }: NodeProps) {
  const [hovered, setHovered] = useState(false)
  const d = data as WorkflowNodeData
  const nodeType: NodeType = d.nodeType ?? 'action'
  const config = NODE_CONFIGS[d.subtype]
  const colors = TYPE_COLORS[nodeType]

  // Get execution state from store
  const executionState = useWorkflowStore((s) => s.executionState)
  const setSelectedNode = useWorkflowStore((s) => s.setSelectedNode)

  // Get execution status for this node
  const nodeExecution = executionState.nodeResults[id]
  const executionStatus = nodeExecution?.status || 'pending'
  const isRunning = executionState.currentNodeId === id

  // Execution color overrides
  const execColor = EXECUTION_COLORS[executionStatus] || EXECUTION_COLORS.pending

  const displayLabel = d.label || config?.title || d.subtype.replace(/_/g, ' ')
  const typeLabel = config?.label || (nodeType === 'trigger' ? 'Tetikleyici' : nodeType === 'condition' ? 'Koşul' : 'Aksiyon')

  // Build a config summary string
  const configSummary = useMemo(() => {
    if (!d.config || !config?.fields) return null
    const parts: string[] = []
    for (const field of config.fields) {
      const val = d.config[field.key]
      if (val !== undefined && val !== '') {
        if (field.type === 'select') {
          const opt = field.options?.find(o => o.value === String(val))
          parts.push(opt?.label || String(val))
        } else {
          parts.push(String(val))
        }
      }
    }
    return parts.length > 0 ? parts.join(' · ') : null
  }, [d.config, config?.fields])

  // Branching nodes get TRUE (bottom) + FALSE (right) handles
  const isBranchNode = d.subtype === 'if_else' || d.subtype === 'if' || d.subtype === 'check_field' || d.subtype === 'check_score'

  const showAdd = !d.hasNextStep && !isBranchNode && (nodeType === 'trigger' || hovered || selected)

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedNode(id, d)
  }

  const handleAddClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    // Dispatch event for canvas to handle
    window.dispatchEvent(new CustomEvent('wf:request-add-node', { detail: { parentId: id } }))
  }

  // ── Empty trigger placeholder ──
  if (d.isEmpty) {
    return (
      <div
        style={{ position: 'relative' }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <Handle type="target" position={Position.Top} 
          style={{ 
            width: 12, height: 12, background: '#e5e7eb', border: '2px solid #fff',
            top: -6, opacity: hovered ? 1 : 0.5, transition: 'opacity 0.15s'
          }} 
        />
        
        <div
          onClick={handleClick}
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: '#ffffff',
            borderRadius: 10,
            border: `1.5px solid ${selected ? '#7c3aed' : '#e5e7eb'}`,
            borderLeft: `3px solid ${colors.bg}`,
            padding: '14px 16px',
            minWidth: 220, maxWidth: 280,
            cursor: 'pointer',
            boxShadow: selected
              ? '0 0 0 2px rgba(124,58,237,0.15), 0 2px 8px rgba(0,0,0,0.06)'
              : '0 2px 8px rgba(0,0,0,0.06)',
            transition: 'all 0.15s ease',
          }}
        >
          <div style={{
            width: 36, height: 36, borderRadius: 8, flexShrink: 0,
            border: '2px dashed #cbd5e1', background: '#f8fafc',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <i className="fas fa-bolt" style={{ color: '#94a3b8', fontSize: 14 }} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.6px', color: colors.text, marginBottom: 2,
            }}>Tetikleyici</div>
            <div style={{
              fontSize: 13, fontWeight: 500, color: '#64748b',
            }}>Tetikleyici ekleyin</div>
          </div>
        </div>

        {/* Add button below */}
        {renderAddButton(showAdd, handleAddClick)}
        <Handle type="source" position={Position.Bottom} 
          style={{ 
            width: 12, height: 12, background: '#e5e7eb', border: '2px solid #fff',
            bottom: -6, opacity: hovered ? 1 : 0.5, transition: 'opacity 0.15s'
          }} 
        />
      </div>
    )
  }

  // ── Normal node card ──
  // Determine border color based on execution state
  const borderColor = executionStatus !== 'pending' && executionStatus !== undefined
    ? execColor.border
    : selected ? '#7c3aed' : hovered ? '#cbd5e1' : '#e5e7eb'

  const boxShadow = executionStatus !== 'pending' && executionStatus !== undefined
    ? `0 0 0 2px ${execColor.glow}, 0 4px 12px rgba(0,0,0,0.08)`
    : selected
      ? '0 0 0 2px rgba(124,58,237,0.15), 0 4px 12px rgba(0,0,0,0.08)'
      : hovered
        ? '0 4px 16px rgba(0,0,0,0.1)'
        : '0 2px 8px rgba(0,0,0,0.06)'

  return (
    <div
      style={{ position: 'relative' }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <Handle type="target" position={Position.Top} 
        style={{ 
          width: 12, height: 12, background: execColor.border, border: '2px solid #fff',
          top: -6, opacity: hovered ? 1 : 0.5, transition: 'opacity 0.15s'
        }} 
      />

      <div
        onClick={handleClick}
        style={{
          background: '#ffffff',
          borderRadius: 10,
          border: `1.5px solid ${borderColor}`,
          borderLeft: `3px solid ${executionStatus !== 'pending' ? execColor.border : colors.bg}`,
          minWidth: 220, maxWidth: 280,
          cursor: 'pointer',
          boxShadow,
          transition: 'all 0.15s ease',
          overflow: 'hidden',
        }}
      >
        {/* Branch node badge */}
        {isBranchNode && (
          <div style={{
            position: 'absolute', top: -9, right: 10,
            fontSize: 9, fontWeight: 700, letterSpacing: '0.5px',
            background: '#fef3c7', color: '#92400e',
            border: '1px solid #fcd34d', borderRadius: 4,
            padding: '1px 5px', pointerEvents: 'none',
          }}>IF / ELSE</div>
        )}
        {/* Header with subtle gradient tint */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 14px',
          background: colors.gradient,
          borderBottom: `1px solid ${colors.light}`,
        }}>
          {/* Icon box */}
          <div style={{
            width: 32, height: 32, borderRadius: 7, flexShrink: 0,
            background: config?.iconBg || colors.bg,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 2px 4px ${colors.bg}30`,
          }}>
            {/* Show spinner for running, check for success, X for failed */}
            {isRunning ? (
              <i className="fas fa-spinner fa-spin" style={{ color: config?.iconColor || '#ffffff', fontSize: 14 }} />
            ) : executionStatus === 'success' ? (
              <i className="fas fa-check" style={{ color: '#22c55e', fontSize: 14 }} />
            ) : executionStatus === 'failed' ? (
              <i className="fas fa-times" style={{ color: '#ef4444', fontSize: 14 }} />
            ) : executionStatus === 'skipped' ? (
              <i className="fas fa-forward" style={{ color: '#94a3b8', fontSize: 14 }} />
            ) : (
              <i className={`fas ${config?.faIcon || 'fa-bolt'}`} style={{ color: config?.iconColor || '#ffffff', fontSize: 14 }} />
            )}
          </div>

          {/* Labels */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: '0.6px', color: colors.text, marginBottom: 1,
              lineHeight: 1.2,
            }}>
              {typeLabel}
            </div>
            <div style={{
              fontSize: 13, fontWeight: 600, color: '#0f172a',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              lineHeight: 1.3,
            }}>
              {displayLabel}
            </div>
          </div>
        </div>

        {/* Config summary body */}
        {configSummary && (
          <div style={{
            padding: '8px 14px',
            background: '#ffffff',
          }}>
            <div style={{
              fontSize: 11, color: '#6b7280', lineHeight: 1.4,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {configSummary}
            </div>
          </div>
        )}

        {/* Hover action button: reset for trigger, delete for others */}
        {(hovered || selected) && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              window.dispatchEvent(new CustomEvent('wf:request-delete-node', { detail: { nodeId: id } }))
            }}
            style={{
              position: 'absolute', top: 6, right: 6,
              width: 22, height: 22, borderRadius: '50%',
              background: '#fff', border: '1.5px solid #e5e7eb',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', fontSize: 10, color: '#9ca3af',
              boxShadow: '0 1px 3px rgba(0,0,0,0.08)', zIndex: 20,
              transition: 'all 0.1s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = nodeType === 'trigger' ? '#eff6ff' : '#fef2f2'
              e.currentTarget.style.borderColor = nodeType === 'trigger' ? '#93c5fd' : '#fca5a5'
              e.currentTarget.style.color = nodeType === 'trigger' ? '#3b82f6' : '#ef4444'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#fff'
              e.currentTarget.style.borderColor = '#e5e7eb'
              e.currentTarget.style.color = '#9ca3af'
            }}
            title={nodeType === 'trigger' ? 'Tetikleyiciyi Değiştir' : 'Sil'}
          >
            <i className={`fas ${nodeType === 'trigger' ? 'fa-exchange-alt' : 'fa-times'}`} />
          </button>
        )}
      </div>

      {/* Add button below */}
      {renderAddButton(showAdd, handleAddClick)}

      {/* TRUE path — bottom */}
      <Handle
        id="true"
        type="source"
        position={Position.Bottom}
        style={{ 
          width: 12, height: 12,
          background: isBranchNode ? '#22c55e' : '#e5e7eb',
          border: '2px solid #fff',
          bottom: -6, opacity: hovered ? 1 : 0.5, transition: 'opacity 0.15s'
        }}
      />
      {isBranchNode && (
        <div style={{
          position: 'absolute', bottom: -22, left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 9, fontWeight: 700, color: '#16a34a',
          letterSpacing: '0.4px', pointerEvents: 'none',
        }}>TRUE</div>
      )}

      {/* FALSE path — right (only for branch nodes) */}
      {isBranchNode && (
        <>
          <Handle
            id="false"
            type="source"
            position={Position.Right}
            style={{ 
              width: 12, height: 12,
              background: '#ef4444',
              border: '2px solid #fff',
              right: -6, opacity: hovered ? 1 : 0.5, transition: 'opacity 0.15s'
            }}
          />
          <div style={{
            position: 'absolute', top: '50%', right: -30,
            transform: 'translateY(-50%)',
            fontSize: 9, fontWeight: 700, color: '#dc2626',
            letterSpacing: '0.4px', pointerEvents: 'none',
          }}>FALSE</div>
        </>
      )}
    </div>
  )
}

// ── Shared "+" button with dashed connector ──
function renderAddButton(visible: boolean, onClick: (e: React.MouseEvent) => void) {
  return (
    <div style={{
      position: 'absolute', bottom: 0, left: '50%',
      transform: 'translateX(-50%) translateY(100%)',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      opacity: visible ? 1 : 0, transition: 'opacity 0.15s ease',
      pointerEvents: visible ? 'auto' : 'none',
      zIndex: 10,
    }}>
      {/* Dashed line */}
      <svg width="2" height="32" viewBox="0 0 2 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M1 0V32" stroke="#cbd5e1" strokeWidth="2" strokeDasharray="4 3" />
      </svg>
      {/* Add button */}
      <button
        onClick={onClick}
        title="Adım ekle"
        style={{
          width: 24, height: 24, borderRadius: '50%',
          border: '1.5px solid #d1d5db', background: '#ffffff',
          color: '#6b7280', display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', fontSize: 14, lineHeight: 1, padding: 0,
          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
          transition: 'all 0.15s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = '#7c3aed'
          e.currentTarget.style.color = '#7c3aed'
          e.currentTarget.style.boxShadow = '0 2px 6px rgba(124,58,237,0.25)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = '#d1d5db'
          e.currentTarget.style.color = '#6b7280'
          e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)'
        }}
      >
        +
      </button>
    </div>
  )
}
