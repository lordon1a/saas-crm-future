import { useEffect, useState, useCallback } from 'react'
import { workflowApi } from '../api/workflows'
import { useWorkflowStore } from '../store/workflowStore'
import { getTriggerLabel } from '../constants/nodeConfigs'
import type { WorkflowItem, WorkflowTemplate } from '../types'

// ═══════════════════════════════════════════════════════════════════
// Category config
// ═══════════════════════════════════════════════════════════════════

const CATEGORIES = [
  { id: 'all', label: 'Tümü', icon: 'fa-th-large' },
  { id: 'contact', label: 'Kişi', icon: 'fa-user' },
  { id: 'deal', label: 'Anlaşma', icon: 'fa-briefcase' },
  { id: 'task', label: 'Görev', icon: 'fa-check-circle' },
  { id: 'advanced', label: 'Gelişmiş', icon: 'fa-robot' },
] as const

type CategoryId = typeof CATEGORIES[number]['id']

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  contact: { bg: '#ede9fe', text: '#6d28d9' },
  deal: { bg: '#dbeafe', text: '#1d4ed8' },
  task: { bg: '#dcfce7', text: '#15803d' },
  advanced: { bg: '#fce7f3', text: '#be185d' },
}

// ═══════════════════════════════════════════════════════════════════
// TemplateModal — full overlay template picker
// ═══════════════════════════════════════════════════════════════════

interface TemplateModalProps {
  templates: WorkflowTemplate[]
  loading: boolean
  onUse: (tpl: WorkflowTemplate) => void
  onClose: () => void
}

function TemplateModal({ templates, loading, onUse, onClose }: TemplateModalProps) {
  const [category, setCategory] = useState<CategoryId>('all')
  const [search, setSearch] = useState('')

  const filtered = templates.filter((t) => {
    const matchCat = category === 'all' || t.category === category
    const matchSearch = t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase())
    return matchCat && matchSearch
  })

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(15,23,42,0.55)', backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#ffffff', borderRadius: 16,
          border: '1px solid #e5e7eb',
          boxShadow: '0 24px 80px rgba(0,0,0,0.18)',
          width: '100%', maxWidth: 740, maxHeight: '88vh',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #f3f4f6' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                Şablon Seç
              </h2>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                Hazır bir şablondan başlayarak hızlıca iş akışı oluşturun
              </p>
            </div>
            <button
              onClick={onClose}
              style={{
                width: 32, height: 32, borderRadius: 8, border: 'none',
                background: '#f1f5f9', color: '#64748b', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
              }}
            >
              <i className="fas fa-times" />
            </button>
          </div>
          {/* Search */}
          <div style={{ position: 'relative', marginBottom: 12 }}>
            <i className="fas fa-search" style={{
              position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)',
              color: '#94a3b8', fontSize: 12,
            }} />
            <input
              type="text"
              placeholder="Şablon ara..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
              style={{
                width: '100%', padding: '9px 12px 9px 34px', boxSizing: 'border-box',
                border: '1.5px solid #e5e7eb', borderRadius: 9, fontSize: 13,
                outline: 'none', background: '#f9fafb', color: '#0f172a',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
              onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
            />
          </div>
          {/* Category tabs */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                onClick={() => setCategory(c.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '5px 12px', borderRadius: 20,
                  border: `1.5px solid ${category === c.id ? '#7c3aed' : '#e5e7eb'}`,
                  background: category === c.id ? '#f5f3ff' : 'transparent',
                  color: category === c.id ? '#7c3aed' : '#64748b',
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.12s',
                }}
              >
                <i className={`fas ${c.icon}`} style={{ fontSize: 10 }} />
                {c.label}
              </button>
            ))}
          </div>
        </div>

        {/* Template grid */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          {loading ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {[1,2,3,4].map((i) => (
                <div key={i} style={{ height: 110, background: '#f8fafc', borderRadius: 10 }} />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
              <i className="fas fa-search" style={{ fontSize: 28, marginBottom: 10, display: 'block', color: '#e2e8f0' }} />
              <p style={{ fontSize: 13, margin: 0 }}>Şablon bulunamadı</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {filtered.map((tpl) => {
                const catColor = CATEGORY_COLORS[tpl.category] || { bg: '#f3f4f6', text: '#374151' }
                return (
                  <div
                    key={tpl.id}
                    style={{
                      padding: '14px 16px', borderRadius: 12,
                      border: '1.5px solid #e5e7eb', background: '#fafafa',
                      cursor: 'pointer', transition: 'all 0.14s',
                      display: 'flex', flexDirection: 'column', gap: 8,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = '#7c3aed'
                      e.currentTarget.style.background = '#faf5ff'
                      e.currentTarget.style.boxShadow = '0 4px 16px rgba(124,58,237,0.1)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = '#e5e7eb'
                      e.currentTarget.style.background = '#fafafa'
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                    onClick={() => onUse(tpl)}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 22, lineHeight: 1 }}>{tpl.icon}</span>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', lineHeight: 1.3 }}>
                            {tpl.name}
                          </div>
                          <span style={{
                            display: 'inline-block', marginTop: 3,
                            fontSize: 10, fontWeight: 600, padding: '2px 7px',
                            borderRadius: 99, background: catColor.bg, color: catColor.text,
                          }}>
                            {CATEGORIES.find(c => c.id === tpl.category)?.label}
                          </span>
                        </div>
                      </div>
                    </div>
                    <p style={{ fontSize: 11.5, color: '#64748b', margin: 0, lineHeight: 1.5 }}>
                      {tpl.description}
                    </p>
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      marginTop: 'auto',
                    }}>
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        <i className="fas fa-bolt" style={{ marginRight: 3 }} />
                        {getTriggerLabel(tpl.trigger)}
                      </span>
                      <span style={{
                        fontSize: 11, fontWeight: 700, color: '#7c3aed',
                        display: 'flex', alignItems: 'center', gap: 4,
                      }}>
                        Kullan <i className="fas fa-arrow-right" style={{ fontSize: 9 }} />
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// WorkflowList — Left panel with polished workflow cards + templates
// ═══════════════════════════════════════════════════════════════════

export default function WorkflowList() {
  const {
    workflows, setWorkflows,
    selectedWorkflow, setSelectedWorkflow,
    setBuilderOpen, searchQuery, setSearchQuery,
  } = useWorkflowStore()

  const [tab, setTab] = useState<'workflows' | 'templates'>('workflows')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [templateCategory, setTemplateCategory] = useState<CategoryId>('all')
  const [templateSearch, setTemplateSearch] = useState('')
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [usingTemplate, setUsingTemplate] = useState<string | null>(null)

  useEffect(() => {
    loadWorkflows()
  }, [])

  useEffect(() => {
    if (tab === 'templates' && templates.length === 0) {
      loadTemplates()
    }
  }, [tab])

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

  const loadTemplates = async () => {
    try {
      setTemplatesLoading(true)
      const data = await workflowApi.templates()
      setTemplates(data)
    } catch {
      // silently fail
    } finally {
      setTemplatesLoading(false)
    }
  }

  const handleToggle = async (workflow: WorkflowItem, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await workflowApi.toggle(workflow.id)
      setWorkflows(workflows.map((w) =>
        w.id === workflow.id ? { ...w, is_active: !w.is_active } : w
      ))
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
        is_active: true,
      })
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

  const handleUseTemplate = useCallback(async (tpl: WorkflowTemplate) => {
    if (usingTemplate) return
    setUsingTemplate(tpl.id)
    setShowTemplateModal(false)
    try {
      // Ensure templates are loaded if called from modal before tab was open
      const result = await workflowApi.useTemplate(tpl.id)
      const normalized: WorkflowItem = {
        ...result,
        conditions_count: result.conditions_count ?? 0,
        actions_count: result.actions_count ?? (tpl.actions.length),
        run_count: result.run_count ?? 0,
        last_run_at: result.last_run_at ?? null,
      }
      setWorkflows([normalized, ...workflows])
      setSelectedWorkflow(normalized)
      setBuilderOpen(true)
      setTab('workflows')
    } catch (err) {
      console.error('Template use failed:', err)
    } finally {
      setUsingTemplate(null)
    }
  }, [usingTemplate, workflows, setWorkflows, setSelectedWorkflow, setBuilderOpen])

  const filteredWorkflows = workflows.filter((w) =>
    w.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredTemplates = templates.filter((t) => {
    const matchCat = templateCategory === 'all' || t.category === templateCategory
    const matchSearch = t.name.toLowerCase().includes(templateSearch.toLowerCase()) ||
      t.description.toLowerCase().includes(templateSearch.toLowerCase())
    return matchCat && matchSearch
  })

  // ── Loading skeleton ──
  if (loading) {
    return (
      <div style={{ padding: 16 }}>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{
            height: 72, background: '#f8fafc', borderRadius: 10,
            marginBottom: 8,
          }} />
        ))}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#ffffff' }}>

      {/* ── Header ── */}
      <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid #f3f4f6' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: 0 }}>İş Akışları</h2>
          <div style={{ display: 'flex', gap: 6 }}>
            {/* From template button */}
            <button
              onClick={() => {
                if (templates.length === 0) loadTemplates()
                setShowTemplateModal(true)
              }}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '6px 10px',
                background: '#f5f3ff', color: '#7c3aed',
                border: '1.5px solid #ddd6fe', borderRadius: 7,
                fontSize: 11.5, fontWeight: 600, cursor: 'pointer',
                transition: 'all 0.12s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = '#ede9fe' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = '#f5f3ff' }}
            >
              <i className="fas fa-magic" style={{ fontSize: 10 }} />
              Şablondan
            </button>
            {/* New blank workflow button */}
            <button
              onClick={handleCreateNew}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '6px 12px',
                background: '#7c3aed', color: '#ffffff',
                border: 'none', borderRadius: 7,
                fontSize: 11.5, fontWeight: 600, cursor: 'pointer',
                boxShadow: '0 2px 4px rgba(124,58,237,0.25)',
                transition: 'all 0.12s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = '#6d28d9' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = '#7c3aed' }}
            >
              <i className="fas fa-plus" style={{ fontSize: 10 }} />
              Yeni
            </button>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div style={{ display: 'flex', gap: 0, borderRadius: 8, background: '#f1f5f9', padding: 3 }}>
          {([['workflows', 'İş Akışlarım', `${workflows.length}`], ['templates', 'Şablonlar', `${templates.length || ''}`]] as const).map(([id, label, count]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              style={{
                flex: 1, padding: '6px 0', borderRadius: 6,
                border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
                background: tab === id ? '#ffffff' : 'transparent',
                color: tab === id ? '#7c3aed' : '#64748b',
                boxShadow: tab === id ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.12s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              }}
            >
              {label}
              {count && (
                <span style={{
                  fontSize: 10, fontWeight: 700,
                  background: tab === id ? '#ede9fe' : '#e2e8f0',
                  color: tab === id ? '#7c3aed' : '#94a3b8',
                  borderRadius: 99, padding: '1px 6px',
                }}>
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ── */}
      {tab === 'workflows' ? (
        /* ── My workflows ── */
        <>
          <div style={{ padding: '8px 12px 4px' }}>
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
                  width: '100%', padding: '7px 10px 7px 30px', boxSizing: 'border-box',
                  border: '1.5px solid #e5e7eb', borderRadius: 8,
                  fontSize: 12, color: '#374151', outline: 'none', background: '#f9fafb',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
                onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
              />
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '4px 10px 10px' }}>
            {error && (
              <div style={{ padding: '10px 14px', margin: '6px 0', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, fontSize: 12, color: '#dc2626' }}>
                <i className="fas fa-exclamation-circle" style={{ marginRight: 6 }} />{error}
              </div>
            )}

            {filteredWorkflows.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 16px', color: '#94a3b8' }}>
                <i className="fas fa-project-diagram" style={{ fontSize: 32, marginBottom: 10, display: 'block', color: '#e2e8f0' }} />
                <p style={{ fontSize: 13, fontWeight: 500, color: '#64748b', margin: '0 0 4px' }}>İş akışı bulunamadı</p>
                <p style={{ fontSize: 11, color: '#94a3b8', margin: '0 0 14px' }}>Şablondan başlayarak hızlıca oluşturun</p>
                <button
                  onClick={() => { if (templates.length === 0) loadTemplates(); setShowTemplateModal(true) }}
                  style={{
                    padding: '7px 14px', background: '#7c3aed', color: '#fff',
                    border: 'none', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  <i className="fas fa-magic" style={{ marginRight: 5 }} />Şablondan Başla
                </button>
              </div>
            ) : (
              filteredWorkflows.map((workflow) => {
                const isSelected = selectedWorkflow?.id === workflow.id
                return (
                  <div
                    key={workflow.id}
                    onClick={() => handleSelect(workflow)}
                    style={{
                      padding: '11px 13px', marginBottom: 4, borderRadius: 10,
                      border: `1.5px solid ${isSelected ? '#7c3aed' : 'transparent'}`,
                      background: isSelected ? '#f5f3ff' : 'transparent',
                      cursor: 'pointer', transition: 'all 0.12s ease',
                    }}
                    onMouseEnter={(e) => { if (!isSelected) { e.currentTarget.style.background = '#f8fafc'; e.currentTarget.style.borderColor = '#e5e7eb' } }}
                    onMouseLeave={(e) => { if (!isSelected) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent' } }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flex: 1, minWidth: 0 }}>
                        <div style={{
                          width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                          background: workflow.is_active ? '#22c55e' : '#d1d5db',
                          boxShadow: workflow.is_active ? '0 0 6px rgba(34,197,94,0.4)' : 'none',
                        }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: isSelected ? '#4c1d95' : '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {workflow.name}
                          </div>
                          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                            {getTriggerLabel(workflow.trigger_type)}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={(e) => handleToggle(workflow, e)}
                        style={{
                          position: 'relative', width: 32, height: 18, borderRadius: 9,
                          border: 'none', cursor: 'pointer', flexShrink: 0,
                          background: workflow.is_active ? '#22c55e' : '#d1d5db',
                          transition: 'background 0.2s', padding: 0,
                        }}
                      >
                        <div style={{
                          position: 'absolute', top: 2, width: 14, height: 14,
                          borderRadius: '50%', background: '#ffffff',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                          transition: 'left 0.2s', left: workflow.is_active ? 16 : 2,
                        }} />
                      </button>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 5, marginLeft: 17, fontSize: 11, color: '#94a3b8' }}>
                      <span><i className="fas fa-play" style={{ fontSize: 8, marginRight: 3 }} />{workflow.run_count || 0} çalışma</span>
                      {workflow.last_run_at && <span>Son: {new Date(workflow.last_run_at).toLocaleDateString('tr-TR')}</span>}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </>
      ) : (
        /* ── Templates tab ── */
        <>
          {/* Template search */}
          <div style={{ padding: '8px 12px 6px' }}>
            <div style={{ position: 'relative' }}>
              <i className="fas fa-search" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', fontSize: 11 }} />
              <input
                type="text"
                placeholder="Şablon ara..."
                value={templateSearch}
                onChange={(e) => setTemplateSearch(e.target.value)}
                style={{
                  width: '100%', padding: '7px 10px 7px 30px', boxSizing: 'border-box',
                  border: '1.5px solid #e5e7eb', borderRadius: 8,
                  fontSize: 12, color: '#374151', outline: 'none', background: '#f9fafb',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
                onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
              />
            </div>
          </div>

          {/* Category filter */}
          <div style={{ padding: '0 10px 6px', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                onClick={() => setTemplateCategory(c.id)}
                style={{
                  padding: '4px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600,
                  border: `1.5px solid ${templateCategory === c.id ? '#7c3aed' : '#e5e7eb'}`,
                  background: templateCategory === c.id ? '#f5f3ff' : 'transparent',
                  color: templateCategory === c.id ? '#7c3aed' : '#64748b',
                  cursor: 'pointer', transition: 'all 0.1s',
                }}
              >
                {c.label}
              </button>
            ))}
          </div>

          {/* Template list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '2px 10px 10px' }}>
            {templatesLoading ? (
              [1,2,3,4].map((i) => (
                <div key={i} style={{ height: 88, background: '#f8fafc', borderRadius: 10, marginBottom: 8 }} />
              ))
            ) : filteredTemplates.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 16px', color: '#94a3b8' }}>
                <i className="fas fa-search" style={{ fontSize: 28, marginBottom: 10, display: 'block', color: '#e2e8f0' }} />
                <p style={{ fontSize: 13, margin: 0 }}>Şablon bulunamadı</p>
              </div>
            ) : (
              filteredTemplates.map((tpl) => {
                const catColor = CATEGORY_COLORS[tpl.category] || { bg: '#f3f4f6', text: '#374151' }
                const isUsing = usingTemplate === tpl.id
                return (
                  <div
                    key={tpl.id}
                    style={{
                      padding: '12px 13px', marginBottom: 7, borderRadius: 10,
                      border: '1.5px solid #e5e7eb', background: '#fafafa',
                      cursor: 'pointer', transition: 'all 0.12s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#7c3aed'; e.currentTarget.style.background = '#faf5ff'; e.currentTarget.style.boxShadow = '0 2px 10px rgba(124,58,237,0.08)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#e5e7eb'; e.currentTarget.style.background = '#fafafa'; e.currentTarget.style.boxShadow = 'none' }}
                    onClick={() => handleUseTemplate(tpl)}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                      <span style={{ fontSize: 20, lineHeight: 1, flexShrink: 0, marginTop: 2 }}>{tpl.icon}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                          <span style={{ fontSize: 12.5, fontWeight: 700, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {tpl.name}
                          </span>
                          <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 99, background: catColor.bg, color: catColor.text, flexShrink: 0 }}>
                            {CATEGORIES.find(c => c.id === tpl.category)?.label}
                          </span>
                        </div>
                        <p style={{ fontSize: 11, color: '#64748b', margin: '4px 0 6px', lineHeight: 1.4 }}>
                          {tpl.description}
                        </p>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 10, color: '#94a3b8' }}>
                            <i className="fas fa-bolt" style={{ marginRight: 3 }} />
                            {getTriggerLabel(tpl.trigger)}
                          </span>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleUseTemplate(tpl) }}
                            disabled={!!usingTemplate}
                            style={{
                              padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                              background: isUsing ? '#ede9fe' : '#7c3aed', color: isUsing ? '#7c3aed' : '#ffffff',
                              border: 'none', cursor: usingTemplate ? 'not-allowed' : 'pointer',
                              transition: 'all 0.12s',
                            }}
                          >
                            {isUsing ? <><i className="fas fa-spinner fa-spin" style={{ marginRight: 4 }} />Oluşturuluyor</> : 'Kullan'}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </>
      )}

      {/* ── Template picker modal ── */}
      {showTemplateModal && (
        <TemplateModal
          templates={templates}
          loading={templatesLoading}
          onUse={handleUseTemplate}
          onClose={() => setShowTemplateModal(false)}
        />
      )}
    </div>
  )
}
