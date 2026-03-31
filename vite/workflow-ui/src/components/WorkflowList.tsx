import { useEffect, useState } from 'react'
import { workflowApi } from '../api/workflows'
import { useWorkflowStore } from '../store/workflowStore'
import { getTriggerLabel } from '../constants/nodeConfigs'
import type { WorkflowItem } from '../types'

// ═══════════════════════════════════════════════════════════════════
// WorkflowList — Left panel with polished workflow cards
// ═══════════════════════════════════════════════════════════════════

export default function WorkflowList() {
  const {
    workflows, setWorkflows,
    selectedWorkflow, setSelectedWorkflow,
    setBuilderOpen, searchQuery, setSearchQuery,
  } = useWorkflowStore()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadWorkflows()
  }, [])

  const loadWorkflows = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await workflowApi.list()
      setWorkflows(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Yüklenemedi')
    } finally {
      setLoading(false)
    }
  }

  const handleToggle = async (workflow: WorkflowItem, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await workflowApi.toggle(workflow.id)
      setWorkflows(
        workflows.map((w) =>
          w.id === workflow.id ? { ...w, is_active: !w.is_active } : w
        )
      )
    } catch (err) {
      console.error('Toggle failed:', err)
    }
  }

  const handleSelect = (workflow: WorkflowItem) => {
    setSelectedWorkflow(workflow)
    setBuilderOpen(true)
  }

  const handleCreateNew = async () => {
    try {
      const newWorkflow = await workflowApi.create({
        name: 'Yeni İş Akışı',
        trigger_type: 'contact_created',
        is_active: false,
      })
      // Backend may not return counts, set defaults
      const normalized: WorkflowItem = {
        ...newWorkflow,
        conditions_count: newWorkflow.conditions_count ?? 0,
        actions_count: newWorkflow.actions_count ?? 0,
        run_count: newWorkflow.run_count ?? 0,
        last_run_at: newWorkflow.last_run_at ?? null,
      }
      setWorkflows([normalized, ...workflows])
      setSelectedWorkflow(normalized)
      setBuilderOpen(true)
    } catch (err) {
      console.error('Create failed:', err)
    }
  }

  const filteredWorkflows = workflows.filter((w) =>
    w.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // ── Loading skeleton ──
  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ height: 24, background: '#f1f5f9', borderRadius: 6, marginBottom: 12, width: '60%' }} />
          <div style={{ height: 36, background: '#f1f5f9', borderRadius: 8 }} />
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{
            height: 72, background: '#f8fafc', borderRadius: 10,
            marginBottom: 8, animation: 'pulse 1.5s infinite',
          }} />
        ))}
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: '#ffffff',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 16px 12px',
        borderBottom: '1px solid #f3f4f6',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 12,
        }}>
          <div>
            <h2 style={{
              fontSize: 16, fontWeight: 700, color: '#0f172a',
              margin: 0, lineHeight: 1.3,
            }}>
              İş Akışları
            </h2>
            <p style={{
              fontSize: 12, color: '#94a3b8', margin: 0, marginTop: 2,
            }}>
              {workflows.length} iş akışı
            </p>
          </div>
          <button
            onClick={handleCreateNew}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '7px 14px',
              background: '#7c3aed', color: '#ffffff',
              border: 'none', borderRadius: 8,
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(124,58,237,0.25)',
              transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = '#6d28d9' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = '#7c3aed' }}
          >
            <i className="fas fa-plus" style={{ fontSize: 10 }} />
            Yeni
          </button>
        </div>

        {/* Search */}
        <div style={{ position: 'relative' }}>
          <i className="fas fa-search" style={{
            position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            color: '#94a3b8', fontSize: 11,
          }} />
          <input
            type="text"
            placeholder="İş akışı ara..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%', padding: '8px 12px 8px 32px',
              border: '1.5px solid #e5e7eb', borderRadius: 8,
              fontSize: 13, color: '#374151', outline: 'none',
              background: '#f9fafb',
              transition: 'border-color 0.15s',
              boxSizing: 'border-box',
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
            onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
          />
        </div>
      </div>

      {/* Workflow list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 10px' }}>
        {error && (
          <div style={{
            padding: '10px 14px', margin: '6px 0',
            background: '#fef2f2', border: '1px solid #fecaca',
            borderRadius: 8, fontSize: 12, color: '#dc2626',
          }}>
            <i className="fas fa-exclamation-circle" style={{ marginRight: 6 }} />
            {error}
          </div>
        )}

        {filteredWorkflows.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '40px 20px', color: '#94a3b8',
          }}>
            <i className="fas fa-project-diagram" style={{
              fontSize: 36, marginBottom: 12, display: 'block', color: '#e2e8f0',
            }} />
            <p style={{ fontSize: 13, fontWeight: 500, color: '#64748b', margin: '0 0 4px' }}>
              İş akışı bulunamadı
            </p>
            <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
              Yeni bir iş akışı oluşturun
            </p>
          </div>
        ) : (
          filteredWorkflows.map((workflow) => {
            const isSelected = selectedWorkflow?.id === workflow.id
            return (
              <div
                key={workflow.id}
                onClick={() => handleSelect(workflow)}
                style={{
                  padding: '12px 14px',
                  marginBottom: 4,
                  borderRadius: 10,
                  border: `1.5px solid ${isSelected ? '#7c3aed' : 'transparent'}`,
                  background: isSelected ? '#f5f3ff' : 'transparent',
                  cursor: 'pointer',
                  transition: 'all 0.12s ease',
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = '#f8fafc'
                    e.currentTarget.style.borderColor = '#e5e7eb'
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.borderColor = 'transparent'
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                    {/* Status dot */}
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                      background: workflow.is_active ? '#22c55e' : '#d1d5db',
                      boxShadow: workflow.is_active ? '0 0 6px rgba(34,197,94,0.4)' : 'none',
                    }} />

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 13, fontWeight: 600,
                        color: isSelected ? '#4c1d95' : '#0f172a',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {workflow.name}
                      </div>
                      <div style={{
                        fontSize: 11, color: '#94a3b8', marginTop: 2,
                      }}>
                        {getTriggerLabel(workflow.trigger_type)}
                      </div>
                    </div>
                  </div>

                  {/* Toggle */}
                  <button
                    onClick={(e) => handleToggle(workflow, e)}
                    style={{
                      position: 'relative',
                      width: 32, height: 18, borderRadius: 9,
                      border: 'none', cursor: 'pointer', flexShrink: 0,
                      background: workflow.is_active ? '#22c55e' : '#d1d5db',
                      transition: 'background 0.2s',
                      padding: 0,
                    }}
                  >
                    <div style={{
                      position: 'absolute',
                      top: 2, width: 14, height: 14,
                      borderRadius: '50%', background: '#ffffff',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                      transition: 'left 0.2s',
                      left: workflow.is_active ? 16 : 2,
                    }} />
                  </button>
                </div>

                {/* Stats */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  marginTop: 6, marginLeft: 18,
                  fontSize: 11, color: '#94a3b8',
                }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                    <i className="fas fa-play" style={{ fontSize: 8 }} />
                    {workflow.run_count || 0} çalışma
                  </span>
                  {workflow.last_run_at && (
                    <span>
                      Son: {new Date(workflow.last_run_at).toLocaleDateString('tr-TR')}
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
