import { useEffect, useRef } from 'react'
import { useWorkflowStore } from '../store/workflowStore'
import { NODE_CONFIGS, TYPE_COLORS } from '../constants/nodeConfigs'
import type { WorkflowNodeData, NodeType } from '../types'
import VariablesDropdown from './VariablesDropdown'

// ═══════════════════════════════════════════════════════════════════
// IF/ELSE Condition Editor
// ═══════════════════════════════════════════════════════════════════

interface IfCondition {
  field: string
  operator: string
  value: string
}

const OPERATORS = [
  { value: 'equals', label: 'Eşittir (=)' },
  { value: 'not_equals', label: 'Eşit Değil (≠)' },
  { value: 'greater_than', label: 'Büyüktür (>)' },
  { value: 'less_than', label: 'Küçüktür (<)' },
  { value: 'contains', label: 'İçerir' },
  { value: 'not_contains', label: 'İçermez' },
  { value: 'is_empty', label: 'Boş' },
  { value: 'is_not_empty', label: 'Boş Değil' },
]

const inputBase: React.CSSProperties = {
  width: '100%', padding: '7px 10px',
  border: '1.5px solid #e5e7eb', borderRadius: 7,
  fontSize: 12, color: '#374151', background: '#fafafa',
  outline: 'none', boxSizing: 'border-box',
}

function IfElseEditor({ conditions, logic, onChange }: {
  conditions: IfCondition[]
  logic: string
  onChange: (conditions: IfCondition[], logic: string) => void
}) {
  const addCondition = () =>
    onChange([...conditions, { field: '', operator: 'equals', value: '' }], logic)

  const removeCondition = (i: number) => {
    const next = conditions.filter((_, idx) => idx !== i)
    onChange(next.length ? next : [{ field: '', operator: 'equals', value: '' }], logic)
  }

  const updateCondition = (i: number, patch: Partial<IfCondition>) => {
    onChange(conditions.map((c, idx) => idx === i ? { ...c, ...patch } : c), logic)
  }

  return (
    <div>
      {/* Logic toggle */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {(['AND', 'OR'] as const).map((l) => (
          <button key={l} onClick={() => onChange(conditions, l)}
            style={{
              flex: 1, padding: '5px 0', borderRadius: 6, border: 'none',
              fontWeight: 700, fontSize: 11, cursor: 'pointer',
              background: logic === l ? '#f59e0b' : '#f1f5f9',
              color: logic === l ? '#fff' : '#64748b',
              transition: 'all 0.15s',
            }}
          >{l === 'AND' ? 'Tümü (AND)' : 'Herhangi biri (OR)'}</button>
        ))}
      </div>

      {/* Condition rows */}
      {conditions.map((cond, i) => (
        <div key={i} style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 10, marginBottom: 8 }}>
          {conditions.length > 1 && i > 0 && (
            <div style={{ fontSize: 10, fontWeight: 700, color: '#f59e0b', marginBottom: 6 }}>{logic}</div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <input
              style={inputBase}
              placeholder="Alan: deal.amount, contact.email..."
              value={cond.field}
              onChange={(e) => updateCondition(i, { field: e.target.value })}
            />
            <select
              style={{ ...inputBase, appearance: 'none' as const }}
              value={cond.operator}
              onChange={(e) => updateCondition(i, { operator: e.target.value })}
            >
              {OPERATORS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            {!['is_empty', 'is_not_empty'].includes(cond.operator) && (
              <input
                style={inputBase}
                placeholder="Değer: 1000, vip, true..."
                value={cond.value}
                onChange={(e) => updateCondition(i, { value: e.target.value })}
              />
            )}
          </div>
          {conditions.length > 1 && (
            <button
              onClick={() => removeCondition(i)}
              style={{
                marginTop: 6, background: 'none', border: 'none', color: '#94a3b8',
                cursor: 'pointer', fontSize: 11, padding: 0,
              }}
            ><i className="fas fa-trash" style={{ marginRight: 4 }} />Sil</button>
          )}
        </div>
      ))}

      <button
        onClick={addCondition}
        style={{
          width: '100%', padding: '7px 0', borderRadius: 7,
          border: '1.5px dashed #d1d5db', background: 'none',
          color: '#6b7280', fontSize: 12, cursor: 'pointer',
          fontWeight: 500, transition: 'all 0.15s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#f59e0b'; e.currentTarget.style.color = '#f59e0b' }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#d1d5db'; e.currentTarget.style.color = '#6b7280' }}
      >
        <i className="fas fa-plus" style={{ marginRight: 6 }} />
        Koşul Ekle
      </button>

      {/* Branch legend */}
      <div style={{
        marginTop: 12, padding: '8px 10px', borderRadius: 7,
        background: '#fffbeb', border: '1px solid #fcd34d',
        fontSize: 11, color: '#92400e', lineHeight: 1.5,
      }}>
        <i className="fas fa-info-circle" style={{ marginRight: 5 }} />
        Koşul geçerliyse <span style={{ color: '#16a34a', fontWeight: 700 }}>TRUE (↓ alt)</span>, geçersizse{' '}
        <span style={{ color: '#dc2626', fontWeight: 700 }}>FALSE (→ sağ)</span> yolundan devam eder.
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// NodePropertiesPanel — Right sidebar for node configuration
// Slides in when a node is selected
// ═══════════════════════════════════════════════════════════════════

interface Props {
  onUpdateNode: (nodeId: string, patch: Record<string, unknown>) => void
}

export default function NodePropertiesPanel({ onUpdateNode }: Props) {
  const { selectedNodeId, selectedNodeData, setSelectedNode, stages, selectedWorkflow } = useWorkflowStore()
  const workflowId = selectedWorkflow?.id ?? null
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

  // IF/ELSE condition parsing
  const isIfElseNode = d.subtype === 'if_else' || d.subtype === 'if'
  let parsedConditions: IfCondition[] = []
  try {
    const raw = currentConfig.conditions
    parsedConditions = raw ? JSON.parse(String(raw)) : []
  } catch { parsedConditions = [] }
  if (parsedConditions.length === 0) parsedConditions = [{ field: '', operator: 'equals', value: '' }]
  const parsedLogic = String(currentConfig.logic || 'AND')

  const handleIfElseChange = (conditions: IfCondition[], logic: string) => {
    onUpdateNode(selectedNodeId, {
      config: {
        ...currentConfig,
        conditions: JSON.stringify(conditions),
        logic,
      }
    })
  }

  // Webhook URL
  const isWebhookTrigger = d.subtype === 'webhook_trigger'
  const webhookUrl = isWebhookTrigger
    ? `${window.location.origin}/webhooks/workflow/${selectedNodeId}`
    : null

  // Schedule: hide cron_expression unless custom_cron
  const isSchedule = d.subtype === 'schedule'
  const showCronExpr = isSchedule && currentConfig.interval_type === 'custom_cron'

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
        {/* IF/ELSE: multi-condition editor */}
        {isIfElseNode ? (
          <>
            <div style={{ marginBottom: 12, fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Koşullar</div>
            <IfElseEditor
              conditions={parsedConditions}
              logic={parsedLogic}
              onChange={handleIfElseChange}
            />
          </>
        ) : config.fields.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '24px 16px',
            color: '#94a3b8', fontSize: 13,
          }}>
            <i className="fas fa-check-circle" style={{ fontSize: 24, marginBottom: 8, display: 'block' }} />
            Bu adım için yapılandırma gerekmez.
          </div>
        ) : (
          <>
          {/* Webhook URL (readonly) */}
          {isWebhookTrigger && webhookUrl && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.3px' }}>
                Webhook URL
              </label>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '8px 10px', background: '#f0fdf4',
                border: '1.5px solid #86efac', borderRadius: 8,
              }}>
                <code style={{ flex: 1, fontSize: 10, color: '#15803d', wordBreak: 'break-all', fontFamily: 'monospace' }}>{webhookUrl}</code>
                <button
                  onClick={() => { navigator.clipboard.writeText(webhookUrl) }}
                  style={{ background: 'none', border: 'none', color: '#16a34a', cursor: 'pointer', fontSize: 13, flexShrink: 0 }}
                  title="Kopyala"
                ><i className="fas fa-copy" /></button>
              </div>
            </div>
          )}
          {config.fields.map((field) => {
            // Hide cron_expression unless custom_cron is selected
            if (field.key === 'cron_expression' && isSchedule && !showCronExpr) return null
            const fieldValue = currentConfig[field.key] ?? field.default ?? ''
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
                    value={String(fieldValue)}
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
                    value={String(fieldValue)}
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
                    value={String(fieldValue)}
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
                  <>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {String(fieldValue).includes('{{') ? (
                          <div style={{ position: 'relative' }}>
                            <div style={{
                              width: '100%', padding: '8px 12px',
                              border: '1.5px solid #7c3aed', borderRadius: 8,
                              fontSize: 13, color: '#7c3aed', background: '#f3e8ff',
                              fontFamily: 'monospace',
                              minHeight: 36, cursor: 'pointer',
                            }}>
                              {String(fieldValue)}
                            </div>
                            <div style={{
                              position: 'absolute', right: 8, top: 8,
                              fontSize: 10, color: '#7c3aed', fontWeight: 600,
                            }}>
                              <i className="fas fa-flask" style={{ marginRight: 4 }} />
                              EXPRESSION
                            </div>
                          </div>
                        ) : (
                          <input
                            type={field.type === 'number' ? 'number' : 'text'}
                            value={String(fieldValue)}
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
                      {field.type === 'text' && (
                        <VariablesDropdown
                          workflowId={workflowId}
                          onSelect={(expr) => handleFieldChange(field.key, String(fieldValue) + expr)}
                        />
                      )}
                    </div>
                  </>
                )}
              </div>
            )
          })}

          {/* Variable hint */}
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
          </>
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
