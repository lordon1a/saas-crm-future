import { useEffect, useRef } from 'react'
import { useWorkflowStore } from '../store/workflowStore'
import { NODE_CONFIGS, TYPE_COLORS } from '../constants/nodeConfigs'
import type { WorkflowNodeData, NodeType } from '../types'

// ═══════════════════════════════════════════════════════════════════
// NodePropertiesPanel — Right sidebar for node configuration
// Slides in when a node is selected
// ═══════════════════════════════════════════════════════════════════

interface Props {
  onUpdateNode: (nodeId: string, patch: Record<string, unknown>) => void
}

export default function NodePropertiesPanel({ onUpdateNode }: Props) {
  const { selectedNodeId, selectedNodeData, setSelectedNode, stages } = useWorkflowStore()
  const panelRef = useRef<HTMLDivElement>(null)

  const d = selectedNodeData as WorkflowNodeData | null
  const config = d ? NODE_CONFIGS[d.subtype] : null
  const nodeType: NodeType = d?.nodeType ?? 'action'
  const colors = TYPE_COLORS[nodeType]

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedNode(null)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [setSelectedNode])

  if (!selectedNodeId || !d || !config) return null

  const currentConfig = (d.config || {}) as Record<string, string | number | boolean>

  const handleFieldChange = (key: string, value: string | number) => {
    const newConfig = { ...currentConfig, [key]: value }
    onUpdateNode(selectedNodeId, { config: newConfig })
  }

  return (
    <div
      ref={panelRef}
      style={{
        width: 300,
        background: '#ffffff',
        borderLeft: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        flexShrink: 0,
        animation: 'slideInRight 0.2s ease-out',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid #f3f4f6',
        background: colors.gradient,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        {/* Icon */}
        <div style={{
          width: 32, height: 32, borderRadius: 7,
          background: config.iconBg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 2px 4px ${colors.bg}30`,
          flexShrink: 0,
        }}>
          <i className={`fas ${config.faIcon}`} style={{ color: '#fff', fontSize: 14 }} />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.6px', color: colors.text, marginBottom: 1,
          }}>
            {config.label}
          </div>
          <div style={{
            fontSize: 14, fontWeight: 600, color: '#0f172a',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {config.title}
          </div>
        </div>

        {/* Close button */}
        <button
          onClick={() => setSelectedNode(null)}
          style={{
            width: 28, height: 28, borderRadius: 6,
            background: 'transparent', border: 'none',
            color: '#94a3b8', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#f1f5f9'
            e.currentTarget.style.color = '#475569'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.color = '#94a3b8'
          }}
          title="Kapat"
        >
          <i className="fas fa-times" style={{ fontSize: 12 }} />
        </button>
      </div>

      {/* Fields */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '16px',
      }}>
        {config.fields.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '24px 16px',
            color: '#94a3b8', fontSize: 13,
          }}>
            <i className="fas fa-check-circle" style={{ fontSize: 24, marginBottom: 8, display: 'block' }} />
            Bu adım için yapılandırma gerekmez.
          </div>
        ) : (
          config.fields.map((field) => {
            const value = currentConfig[field.key] ?? field.default ?? ''

            return (
              <div key={field.key} style={{ marginBottom: 16 }}>
                <label style={{
                  display: 'block', fontSize: 11, fontWeight: 600,
                  color: '#475569', marginBottom: 5,
                  textTransform: 'uppercase', letterSpacing: '0.3px',
                }}>
                  {field.label}
                </label>

                {field.type === 'textarea' ? (
                  <textarea
                    value={String(value)}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    placeholder={field.placeholder || ''}
                    rows={3}
                    style={{
                      width: '100%', padding: '8px 12px',
                      border: '1.5px solid #e5e7eb', borderRadius: 8,
                      fontSize: 13, color: '#374151', background: '#fafafa',
                      outline: 'none', resize: 'vertical',
                      fontFamily: 'inherit', lineHeight: 1.5,
                      transition: 'border-color 0.15s',
                      boxSizing: 'border-box',
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed'; e.currentTarget.style.background = '#fff' }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb'; e.currentTarget.style.background = '#fafafa' }}
                  />
                ) : field.type === 'select' ? (
                  <select
                    value={String(value)}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    style={{
                      width: '100%', padding: '8px 32px 8px 12px',
                      border: '1.5px solid #e5e7eb', borderRadius: 8,
                      fontSize: 13, color: '#374151', background: '#fafafa',
                      outline: 'none', cursor: 'pointer',
                      appearance: 'none',
                      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m6 8 4 4 4-4'/%3E%3C/svg%3E")`,
                      backgroundPosition: 'right 8px center',
                      backgroundRepeat: 'no-repeat',
                      backgroundSize: '16px',
                      transition: 'border-color 0.15s',
                      boxSizing: 'border-box',
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
                  >
                    <option value="">Seçin...</option>
                    {field.options?.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                ) : field.type === 'stage_select' ? (
                  <select
                    value={String(value)}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    style={{
                      width: '100%', padding: '8px 32px 8px 12px',
                      border: '1.5px solid #e5e7eb', borderRadius: 8,
                      fontSize: 13, color: '#374151', background: '#fafafa',
                      outline: 'none', cursor: 'pointer',
                      appearance: 'none',
                      backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m6 8 4 4 4-4'/%3E%3C/svg%3E")`,
                      backgroundPosition: 'right 8px center',
                      backgroundRepeat: 'no-repeat',
                      backgroundSize: '16px',
                      transition: 'border-color 0.15s',
                      boxSizing: 'border-box',
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
                  >
                    <option value="">Aşama Seçin...</option>
                    {stages.map((stage) => (
                      <option key={stage.id} value={stage.id}>{stage.name}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={field.type === 'number' ? 'number' : 'text'}
                    value={String(value)}
                    onChange={(e) => handleFieldChange(
                      field.key,
                      field.type === 'number' ? Number(e.target.value) : e.target.value
                    )}
                    placeholder={field.placeholder || ''}
                    style={{
                      width: '100%', padding: '8px 12px',
                      border: '1.5px solid #e5e7eb', borderRadius: 8,
                      fontSize: 13, color: '#374151', background: '#fafafa',
                      outline: 'none',
                      transition: 'border-color 0.15s',
                      boxSizing: 'border-box',
                    }}
                    onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed'; e.currentTarget.style.background = '#fff' }}
                    onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb'; e.currentTarget.style.background = '#fafafa' }}
                  />
                )}
              </div>
            )
          })
        )}

        {/* Variable hint */}
        {config.fields.length > 0 && (
          <div style={{
            marginTop: 8, padding: '10px 12px',
            background: '#f8fafc', borderRadius: 8,
            border: '1px solid #f1f5f9',
          }}>
            <div style={{
              fontSize: 10, fontWeight: 600, color: '#94a3b8',
              textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 4,
            }}>
              Değişkenler
            </div>
            <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.5 }}>
              <code style={{
                background: '#e0e7ff', color: '#4338ca', padding: '1px 5px',
                borderRadius: 3, fontSize: 10, fontFamily: 'monospace',
              }}>{'{{contact.first_name}}'}</code>
              {' '}gibi değişkenler kullanabilirsiniz.
            </div>
          </div>
        )}
      </div>

      {/* Node ID footer */}
      <div style={{
        padding: '8px 16px',
        borderTop: '1px solid #f3f4f6',
        background: '#fafafa',
      }}>
        <div style={{
          fontSize: 10, color: '#94a3b8',
          fontFamily: 'monospace',
        }}>
          ID: {selectedNodeId}
        </div>
      </div>
    </div>
  )
}
