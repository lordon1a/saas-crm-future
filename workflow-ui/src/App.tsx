import { useRef, useState, useEffect, useCallback } from 'react'
import { useWorkflowStore } from './store/workflowStore'
import { workflowApi } from './api/workflows'
import WorkflowList from './components/WorkflowList'
import WorkflowCanvas, { type WorkflowCanvasHandle } from './components/WorkflowCanvas'
import NodePalette from './components/NodePalette'
import NodePropertiesPanel from './components/NodePropertiesPanel'
import ExecutionHistory from './components/ExecutionHistory'
import ExecutionOutputPanel from './components/ExecutionOutputPanel'
import WorkflowSettingsModal from './components/WorkflowSettingsModal'
import { NODE_CONFIGS } from './constants/nodeConfigs'
import type { WorkflowItem, WorkflowVersion, WorkflowUsage } from './types'

// ═══════════════════════════════════════════════════════════════════
// App — Main workflow builder application
// n8n / Twenty CRM quality layout
// ═══════════════════════════════════════════════════════════════════

function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error'; onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3500)
    return () => clearTimeout(timer)
  }, [onClose])

  return (
    <div style={{
      position: 'fixed', bottom: 20, right: 20, zIndex: 9999,
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '10px 16px', borderRadius: 10,
      background: type === 'success' ? '#059669' : '#dc2626',
      color: '#ffffff',
      boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
      fontSize: 13, fontWeight: 500,
      animation: 'slideInUp 0.25s ease-out',
    }}>
      <i className={`fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}`} style={{ fontSize: 14 }} />
      {message}
    </div>
  )
}

// ── Add Step Modal (appears when "+" is clicked on a node) ──
function AddStepModal({ parentId: _parentId, onSelect, onClose }: {
  parentId: string
  onSelect: (subtype: string) => void
  onClose: () => void
}) {
  const [search, setSearch] = useState('')

  // Filter action/condition types (not triggers) when adding steps
  const items = Object.entries(NODE_CONFIGS).filter(([, config]) => {
    if (config.color === 'trigger') return false
    if (!search) return true
    return config.title.toLowerCase().includes(search.toLowerCase())
  })

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9998,
        background: 'rgba(15,23,42,0.3)',
        backdropFilter: 'blur(2px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#ffffff', borderRadius: 14,
          border: '1px solid #e5e7eb',
          boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
          width: 380, maxHeight: '70vh',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
          animation: 'scaleIn 0.15s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '16px 18px 12px',
          borderBottom: '1px solid #f3f4f6',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: 0 }}>Adım Ekle</h3>
            <button
              onClick={onClose}
              style={{
                width: 26, height: 26, borderRadius: 6,
                border: 'none', background: '#f1f5f9', color: '#64748b',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11,
              }}
            >
              <i className="fas fa-times" />
            </button>
          </div>
          <input
            type="text"
            placeholder="Adım ara..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
            style={{
              width: '100%', padding: '8px 12px',
              border: '1.5px solid #e5e7eb', borderRadius: 8,
              fontSize: 13, outline: 'none', boxSizing: 'border-box',
              background: '#f9fafb',
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
            onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
          />
        </div>

        {/* Items */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
          {items.map(([subtype, config]) => (
            <button
              key={subtype}
              onClick={() => { onSelect(subtype); onClose() }}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                padding: '8px 10px', marginBottom: 3,
                background: 'transparent', border: 'none', borderRadius: 8,
                cursor: 'pointer', textAlign: 'left',
                transition: 'background 0.1s',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = '#f8fafc' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
            >
              <div style={{
                width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                background: config.iconBg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <i className={`fas ${config.faIcon}`} style={{ color: '#fff', fontSize: 12 }} />
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: '#0f172a' }}>{config.title}</div>
                <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.3px' }}>{config.label}</div>
              </div>
            </button>
          ))}
          {items.length === 0 && (
            <div style={{ textAlign: 'center', padding: 20, color: '#94a3b8', fontSize: 13 }}>
              Sonuç bulunamadı
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const {
    selectedWorkflow, setSelectedWorkflow,
    setWorkflows, workflows,
    activeTab, setActiveTab,
    isBuilderOpen, setBuilderOpen,
    isSaving, setIsSaving,
    selectedNodeId, setSelectedNode,
    setStages,
    isExecuting, setIsExecuting,
    addExecutionLog, clearExecutionLogs,
  } = useWorkflowStore()

  const canvasRef = useRef<WorkflowCanvasHandle>(null)
  const [workflowName, setWorkflowName] = useState('')
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [addMenuParentId, setAddMenuParentId] = useState<string | null>(null)
  const [showOutput, setShowOutput] = useState(false)
  const [showVersions, setShowVersions] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showUsage, setShowUsage] = useState(false)
  const [versions, setVersions] = useState<WorkflowVersion[]>([])
  const [usage, setUsage] = useState<WorkflowUsage | null>(null)
  const [isPublishing, setIsPublishing] = useState(false)

  // Load stages for stage_select fields
  useEffect(() => {
    workflowApi.stages().then(setStages).catch(() => {})
  }, [setStages])

  // Listen for add-menu request from canvas
  useEffect(() => {
    const onShowAddMenu = (e: Event) => {
      const { parentId } = (e as CustomEvent).detail as { parentId: string }
      setAddMenuParentId(parentId)
    }
    window.addEventListener('wf:show-add-menu', onShowAddMenu)
    return () => window.removeEventListener('wf:show-add-menu', onShowAddMenu)
  }, [])

  // Load workflow into canvas when selected
  useEffect(() => {
    if (selectedWorkflow) {
      setWorkflowName(selectedWorkflow.name)
      // Small delay to ensure canvas is mounted
      setTimeout(() => {
        if (selectedWorkflow.canvas_data) {
          canvasRef.current?.loadFromWorkflow(selectedWorkflow.canvas_data)
        } else {
          canvasRef.current?.clearCanvas()
        }
      }, 50)
    }
  }, [selectedWorkflow])

  const handleSave = async () => {
    if (!selectedWorkflow) return
    if (!workflowName.trim()) {
      setToast({ message: 'İş akışı adı gereklidir', type: 'error' })
      return
    }

    setIsSaving(true)
    try {
      const canvasData = canvasRef.current?.getCanvasData()

      // Extract trigger_type from the canvas trigger node so the backend
      // always matches what is actually drawn on the canvas.
      const triggerNode = canvasData?.nodes?.find((n) => n.data.nodeType === 'trigger' && !n.data.isEmpty)
      const canvasTriggerType = triggerNode?.data.subtype || selectedWorkflow.trigger_type

      const payload: Partial<WorkflowItem> = {
        name: workflowName,
        trigger_type: canvasTriggerType,
        trigger_config: selectedWorkflow.trigger_config,
        is_active: selectedWorkflow.is_active,
        canvas_data: canvasData,
        re_enrollment_mode: selectedWorkflow.re_enrollment_mode,
      }

      await workflowApi.update(selectedWorkflow.id, payload)

      setWorkflows(
        workflows.map((w) =>
          w.id === selectedWorkflow.id
            ? { ...w, name: workflowName, canvas_data: canvasData, trigger_type: canvasTriggerType }
            : w
        )
      )

      setToast({ message: 'İş akışı kaydedildi', type: 'success' })
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Kaydetme başarısız', type: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedWorkflow) return
    if (!confirm('Bu iş akışını silmek istediğinize emin misiniz?')) return

    try {
      await workflowApi.delete(selectedWorkflow.id)
      setWorkflows(workflows.filter((w) => w.id !== selectedWorkflow.id))
      setSelectedWorkflow(null)
      setBuilderOpen(false)
      setToast({ message: 'İş akışı silindi', type: 'success' })
    } catch {
      setToast({ message: 'Silme başarısız', type: 'error' })
    }
  }

  const handleToggle = async () => {
    if (!selectedWorkflow) return
    try {
      await workflowApi.toggle(selectedWorkflow.id)
      const updated = { ...selectedWorkflow, is_active: !selectedWorkflow.is_active }
      setSelectedWorkflow(updated)
      setWorkflows(workflows.map((w) => w.id === updated.id ? updated : w))
    } catch {
      setToast({ message: 'Durum değiştirme başarısız', type: 'error' })
    }
  }

  const handleSaveSettings = (updates: Partial<WorkflowItem>) => {
    if (!selectedWorkflow) return
    const updated = { ...selectedWorkflow, ...updates }
    setSelectedWorkflow(updated)
    setWorkflows(workflows.map((w) => w.id === updated.id ? updated : w))
  }

  const handleBack = () => {
    setBuilderOpen(false)
    setSelectedWorkflow(null)
    setSelectedNode(null)
  }

  const handleRun = async () => {
    if (!selectedWorkflow || isExecuting) return

    setIsExecuting(true)
    clearExecutionLogs()
    setShowOutput(true)

    const canvasData = canvasRef.current?.getCanvasData()
    if (!canvasData?.nodes?.length) {
      setToast({ message: 'Çalıştırılacak adım yok', type: 'error' })
      setIsExecuting(false)
      return
    }

    // Save canvas first so backend has latest version
    try {
      await workflowApi.update(selectedWorkflow.id, {
        canvas_data: canvasData,
        name: selectedWorkflow.name,
      })
    } catch {
      // non-fatal — continue with run
    }

    try {
      // Use runManual for live SSE-streamed execution
      const result = await workflowApi.runManual(selectedWorkflow.id)

      // Seed initial logs from the synchronous result
      const seenNodeIds = new Set<string>()
      for (const nr of result.node_results ?? []) {
        seenNodeIds.add(nr.node_id)
        addExecutionLog({
          id: `log-${nr.node_id}-${Date.now()}`,
          nodeId: nr.node_id,
          nodeName: nr.subtype || nr.node_type,
          nodeType: nr.node_type,
          status: nr.status,
          startedAt: nr.started_at,
          completedAt: nr.completed_at,
          durationMs: nr.duration_ms,
          output: nr.output,
          error: nr.error,
        })
      }

      // If we got an execution_id, open SSE stream for live updates
      const execId = (result as unknown as Record<string, unknown>).execution_id as number | undefined
      if (execId) {
        const stopStream = workflowApi.streamExecution(execId, (update) => {
          for (const nr of update.node_results ?? []) {
            if (!seenNodeIds.has(nr.node_id)) {
              seenNodeIds.add(nr.node_id)
              addExecutionLog({
                id: `log-${nr.node_id}-${Date.now()}`,
                nodeId: nr.node_id,
                nodeName: nr.subtype || nr.node_type,
                nodeType: nr.node_type,
                status: nr.status,
                startedAt: nr.started_at,
                completedAt: nr.completed_at,
                durationMs: nr.duration_ms,
                output: nr.output,
                error: nr.error,
              })
            }
          }
          if (update.status === 'completed' || update.status === 'failed' || update.error) {
            setIsExecuting(false)
            stopStream()
            setToast({
              message: update.status === 'completed' ? 'Çalıştırma tamamlandı' : 'Çalıştırma başarısız',
              type: update.status === 'completed' ? 'success' : 'error',
            })
          }
        })
        // Safety timeout — stop stream after 3 min
        setTimeout(() => { stopStream(); setIsExecuting(false) }, 180_000)
        return
      }

      setToast({
        message: result.status === 'success' ? 'Çalıştırma tamamlandı' : 'Çalıştırma başarısız',
        type: result.status === 'success' ? 'success' : 'error',
      })
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Çalıştırma başarısız', type: 'error' })
    } finally {
      setIsExecuting(false)
    }
  }

  const handleUpdateNode = useCallback((nodeId: string, patch: Record<string, unknown>) => {
    canvasRef.current?.updateNodeData(nodeId, patch)
    // Also update store's selectedNodeData if this is the selected node
    const store = useWorkflowStore.getState()
    if (store.selectedNodeId === nodeId && store.selectedNodeData) {
      store.setSelectedNode(nodeId, { ...store.selectedNodeData, ...patch })
    }
  }, [])

  const handleAddStep = useCallback((subtype: string) => {
    if (addMenuParentId) {
      canvasRef.current?.addNode(subtype, addMenuParentId)
    }
  }, [addMenuParentId])

  const handlePublish = async () => {
    if (!selectedWorkflow) return
    setIsPublishing(true)
    try {
      await workflowApi.publish(selectedWorkflow.id)
      setToast({ message: 'İş akışı yayınlandı', type: 'success' })
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Yayınlama başarısız', type: 'error' })
    } finally {
      setIsPublishing(false)
    }
  }

  const handleShowVersions = async () => {
    if (!selectedWorkflow) return
    try {
      const v = await workflowApi.versions(selectedWorkflow.id)
      setVersions(v)
      setShowVersions(true)
    } catch {
      setToast({ message: 'Versiyonlar yüklenemedi', type: 'error' })
    }
  }

  const handleRevert = async (versionId: number) => {
    if (!selectedWorkflow) return
    if (!confirm('Bu versiyona geri dönmek istediğinize emin misiniz?')) return
    try {
      await workflowApi.revert(selectedWorkflow.id, versionId)
      setToast({ message: 'Versiyona geri dönüldü', type: 'success' })
      setShowVersions(false)
      // Reload workflow
      const updated = await workflowApi.get(selectedWorkflow.id)
      setSelectedWorkflow(updated)
      setWorkflowName(updated.name)
      setTimeout(() => {
        if (updated.canvas_data) {
          canvasRef.current?.loadFromWorkflow(updated.canvas_data)
        }
      }, 100)
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Geri alma başarısız', type: 'error' })
    }
  }

  const handleShowUsage = async () => {
    try {
      const u = await workflowApi.usage()
      setUsage(u)
      setShowUsage(true)
    } catch {
      setToast({ message: 'Kullanım bilgisi yüklenemedi', type: 'error' })
    }
  }

  return (
    <div style={{
      height: '100%', display: 'flex', overflow: 'hidden',
      background: '#f8fafc',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      fontSize: 14, color: '#0f172a',
    }}>
      {/* Left Panel — Workflow List */}
      <div style={{
        width: 300, flexShrink: 0,
        background: '#ffffff',
        borderRight: '1px solid #e5e7eb',
        display: 'flex', flexDirection: 'column',
      }}>
        <WorkflowList />
      </div>

      {/* Right Panel — Builder or Empty State */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {isBuilderOpen && selectedWorkflow ? (
          <>
            {/* Builder Header */}
            <div style={{
              height: 52, flexShrink: 0,
              background: '#ffffff',
              borderBottom: '1px solid #e5e7eb',
              padding: '0 16px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <button
                  onClick={handleBack}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: 'transparent', border: 'none',
                    color: '#64748b', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                  title="Geri"
                >
                  <i className="fas fa-arrow-left" style={{ fontSize: 13 }} />
                </button>

                <input
                  type="text"
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  style={{
                    fontSize: 15, fontWeight: 600, color: '#0f172a',
                    background: 'transparent', border: '1.5px solid transparent',
                    borderRadius: 6, padding: '4px 8px', outline: 'none',
                    transition: 'border-color 0.15s',
                    minWidth: 200,
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = 'transparent' }}
                  placeholder="İş akışı adı"
                />
              </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {/* Output toggle */}
                <button
                  onClick={() => setShowOutput(!showOutput)}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: showOutput ? '#dbeafe' : 'transparent',
                    border: 'none', cursor: 'pointer',
                    color: showOutput ? '#1e40af' : '#94a3b8',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = showOutput ? '#dbeafe' : 'transparent' }}
                  title="Çıktı Paneli"
                >
                  <i className="fas fa-terminal" style={{ fontSize: 13 }} />
                </button>

                {/* Usage */}
                <button
                  onClick={handleShowUsage}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    color: '#94a3b8',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9'; e.currentTarget.style.color = '#6366f1' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#94a3b8' }}
                  title="Kullanım"
                >
                  <i className="fas fa-chart-bar" style={{ fontSize: 13 }} />
                </button>

                {/* Versions */}
                <button
                  onClick={handleShowVersions}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    color: '#94a3b8',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9'; e.currentTarget.style.color = '#3b82f6' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#94a3b8' }}
                  title="Versiyonlar"
                >
                  <i className="fas fa-code-branch" style={{ fontSize: 13 }} />
                </button>

                {/* Publish */}
                <button
                  onClick={handlePublish}
                  disabled={isPublishing}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '6px 12px', borderRadius: 8,
                    background: isPublishing ? '#64748b' : '#0ea5e9',
                    color: '#ffffff', border: 'none',
                    cursor: isPublishing ? 'not-allowed' : 'pointer',
                    fontSize: 12, fontWeight: 600,
                    opacity: isPublishing ? 0.7 : 1,
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { if (!isPublishing) e.currentTarget.style.background = '#0284c7' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = isPublishing ? '#64748b' : '#0ea5e9' }}
                >
                  <i className={`fas ${isPublishing ? 'fa-spinner fa-spin' : 'fa-rocket'}`} style={{ fontSize: 11 }} />
                  Yayınla
                </button>

                {/* Run button */}
                <button
                  onClick={() => setShowOutput(!showOutput)}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: showOutput ? '#dbeafe' : 'transparent',
                    border: 'none', cursor: 'pointer',
                    color: showOutput ? '#1e40af' : '#94a3b8',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = showOutput ? '#dbeafe' : 'transparent' }}
                  title="Çıktı Paneli"
                >
                  <i className="fas fa-terminal" style={{ fontSize: 13 }} />
                </button>

                {/* Run button */}
                <button
                  onClick={handleRun}
                  disabled={isExecuting}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '7px 16px', borderRadius: 8,
                    background: isExecuting ? '#64748b' : '#22c55e',
                    color: '#ffffff', border: 'none',
                    cursor: isExecuting ? 'not-allowed' : 'pointer',
                    fontSize: 13, fontWeight: 600,
                    boxShadow: '0 2px 4px rgba(34,197,94,0.25)',
                    opacity: isExecuting ? 0.7 : 1,
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { if (!isExecuting) e.currentTarget.style.background = '#16a34a' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = isExecuting ? '#64748b' : '#22c55e' }}
                >
                  <i className={`fas ${isExecuting ? 'fa-spinner fa-spin' : 'fa-play'}`} style={{ fontSize: 12 }} />
                  {isExecuting ? 'Çalışıyor...' : 'Çalıştır'}
                </button>

                {/* Active toggle button */}
                <button
                  onClick={handleToggle}
                  style={{
                    padding: '5px 12px', borderRadius: 6,
                    border: 'none', cursor: 'pointer',
                    fontSize: 12, fontWeight: 600,
                    background: selectedWorkflow.is_active ? '#dcfce7' : '#f1f5f9',
                    color: selectedWorkflow.is_active ? '#166534' : '#64748b',
                    transition: 'all 0.15s',
                  }}
                >
                  {selectedWorkflow.is_active ? 'Aktif' : 'Pasif'}
                </button>

                {/* Settings */}
                <button
                  onClick={() => setShowSettings(true)}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: 'transparent', border: 'none',
                    color: '#94a3b8', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f1f5f9' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                  title="Ayarlar"
                >
                  <i className="fas fa-cog" style={{ fontSize: 13 }} />
                </button>

                {/* Delete */}
                <button
                  onClick={handleDelete}
                  style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: 'transparent', border: 'none',
                    color: '#94a3b8', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#fef2f2'
                    e.currentTarget.style.color = '#dc2626'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = '#94a3b8'
                  }}
                  title="Sil"
                >
                  <i className="fas fa-trash-alt" style={{ fontSize: 13 }} />
                </button>

                {/* Save */}
                <button
                  onClick={handleSave}
                  disabled={isSaving}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '7px 16px', borderRadius: 8,
                    background: '#7c3aed', color: '#ffffff',
                    border: 'none', cursor: isSaving ? 'not-allowed' : 'pointer',
                    fontSize: 13, fontWeight: 600,
                    boxShadow: '0 2px 4px rgba(124,58,237,0.25)',
                    opacity: isSaving ? 0.7 : 1,
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { if (!isSaving) e.currentTarget.style.background = '#6d28d9' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = '#7c3aed' }}
                >
                  <i className={`fas ${isSaving ? 'fa-spinner fa-spin' : 'fa-save'}`} style={{ fontSize: 12 }} />
                  Kaydet
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div style={{
              height: 40, flexShrink: 0,
              background: '#ffffff',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex', alignItems: 'center', padding: '0 16px', gap: 4,
            }}>
              {(['canvas', 'history'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: '6px 14px',
                    fontSize: 12, fontWeight: 600,
                    background: 'none', border: 'none',
                    borderBottom: `2px solid ${activeTab === tab ? '#7c3aed' : 'transparent'}`,
                    color: activeTab === tab ? '#7c3aed' : '#64748b',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    marginBottom: -1,
                  }}
                >
                  <i className={`fas ${tab === 'canvas' ? 'fa-project-diagram' : 'fa-history'}`} style={{ marginRight: 5, fontSize: 10 }} />
                  {tab === 'canvas' ? 'Canvas' : 'Geçmiş'}
                </button>
              ))}
            </div>

            {/* Content */}
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
              {activeTab === 'canvas' ? (
                <>
                  <NodePalette />
                  <div style={{ flex: 1, position: 'relative' }}>
                    <WorkflowCanvas ref={canvasRef} />
                  </div>
                  {selectedNodeId && (
                    <NodePropertiesPanel onUpdateNode={handleUpdateNode} />
                  )}
                  {showOutput && <ExecutionOutputPanel />}
                </>
              ) : (
                <ExecutionHistory />
              )}
            </div>
          </>
        ) : (
          /* Empty State */
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            color: '#94a3b8',
          }}>
            <div style={{
              width: 80, height: 80, borderRadius: '50%',
              background: '#f1f5f9',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 16,
            }}>
              <i className="fas fa-project-diagram" style={{ fontSize: 32, color: '#cbd5e1' }} />
            </div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: '#475569', margin: '0 0 6px' }}>
              İş Akışı Oluşturucu
            </h2>
            <p style={{ fontSize: 13, color: '#94a3b8', margin: 0 }}>
              Bir iş akışı seçin veya yeni bir tane oluşturun
            </p>
          </div>
        )}
      </div>

      {/* Add Step Modal */}
      {addMenuParentId && (
        <AddStepModal
          parentId={addMenuParentId}
          onSelect={handleAddStep}
          onClose={() => setAddMenuParentId(null)}
        />
      )}

      {/* Version History Modal */}
      {showVersions && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 9998,
            background: 'rgba(15,23,42,0.3)',
            backdropFilter: 'blur(2px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={() => setShowVersions(false)}
        >
          <div
            style={{
              background: '#ffffff', borderRadius: 14,
              border: '1px solid #e5e7eb',
              boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
              width: 480, maxHeight: '70vh',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
              animation: 'scaleIn 0.15s ease-out',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{
              padding: '16px 18px 12px',
              borderBottom: '1px solid #f3f4f6',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                <i className="fas fa-code-branch" style={{ marginRight: 8, color: '#3b82f6' }} />
                Versiyon Geçmişi
              </h3>
              <button
                onClick={() => setShowVersions(false)}
                style={{
                  width: 26, height: 26, borderRadius: 6,
                  border: 'none', background: '#f1f5f9', color: '#64748b',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11,
                }}
              >
                <i className="fas fa-times" />
              </button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
              {versions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 30, color: '#94a3b8', fontSize: 13 }}>
                  <i className="fas fa-inbox" style={{ fontSize: 28, marginBottom: 8, display: 'block' }} />
                  Henüz versiyon yok. "Yayınla" butonuna basarak ilk versiyonu oluşturun.
                </div>
              ) : (
                versions.map((v) => (
                  <div
                    key={v.id}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 12px', marginBottom: 6,
                      border: '1px solid #e5e7eb', borderRadius: 8,
                      background: v.status === 'published' ? '#f0fdf4' : '#f9fafb',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>
                        v{v.version_number}
                        {v.status === 'published' && (
                          <span style={{
                            marginLeft: 8, padding: '1px 6px', borderRadius: 4,
                            fontSize: 10, fontWeight: 600,
                            background: '#dcfce7', color: '#166534',
                          }}>Yayında</span>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                        {new Date(v.created_at).toLocaleString('tr-TR')}
                      </div>
                    </div>
                    <button
                      onClick={() => handleRevert(v.id)}
                      style={{
                        padding: '4px 10px', borderRadius: 6,
                        border: '1px solid #3b82f6', background: 'transparent',
                        color: '#3b82f6', cursor: 'pointer',
                        fontSize: 11, fontWeight: 600,
                        transition: 'all 0.15s',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = '#3b82f6'; e.currentTarget.style.color = '#fff' }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#3b82f6' }}
                    >
                      Geri Al
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Usage Modal */}
      {showUsage && usage && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 9998,
            background: 'rgba(15,23,42,0.3)',
            backdropFilter: 'blur(2px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={() => setShowUsage(false)}
        >
          <div
            style={{
              background: '#ffffff', borderRadius: 14,
              border: '1px solid #e5e7eb',
              boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
              width: 420, maxHeight: '70vh',
              display: 'flex', flexDirection: 'column',
              overflow: 'hidden',
              animation: 'scaleIn 0.15s ease-out',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{
              padding: '16px 18px 12px',
              borderBottom: '1px solid #f3f4f6',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                <i className="fas fa-chart-bar" style={{ marginRight: 8, color: '#6366f1' }} />
                Kullanım İstatistikleri
              </h3>
              <button
                onClick={() => setShowUsage(false)}
                style={{
                  width: 26, height: 26, borderRadius: 6,
                  border: 'none', background: '#f1f5f9', color: '#64748b',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11,
                }}
              >
                <i className="fas fa-times" />
              </button>
            </div>
            <div style={{ padding: '16px 18px' }}>
              {/* Usage bar */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12, color: '#64748b' }}>
                  <span>Aylık Kullanım</span>
                  <span>{usage.total_executions} / {usage.max_executions}</span>
                </div>
                <div style={{ height: 8, borderRadius: 4, background: '#f1f5f9', overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', borderRadius: 4,
                    width: `${Math.min(usage.usage_percent, 100)}%`,
                    background: usage.usage_percent > 80 ? '#ef4444' : usage.usage_percent > 50 ? '#f59e0b' : '#22c55e',
                    transition: 'width 0.3s',
                  }} />
                </div>
                <div style={{ textAlign: 'right', fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  %{usage.usage_percent}
                </div>
              </div>

              {/* Stats grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 16 }}>
                <div style={{ textAlign: 'center', padding: 12, background: '#f0fdf4', borderRadius: 8 }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#166534' }}>{usage.total_executions}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>Çalıştırma</div>
                </div>
                <div style={{ textAlign: 'center', padding: 12, background: '#eff6ff', borderRadius: 8 }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#1e40af' }}>{usage.total_actions}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>Aksiyon</div>
                </div>
                <div style={{ textAlign: 'center', padding: 12, background: '#fef2f2', borderRadius: 8 }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: '#991b1b' }}>{usage.total_errors}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>Hata</div>
                </div>
              </div>

              {/* Action breakdown */}
              {Object.keys(usage.action_breakdown).length > 0 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#0f172a', marginBottom: 8 }}>Aksiyon Dağılımı</div>
                  {Object.entries(usage.action_breakdown)
                    .sort(([, a], [, b]) => (b as number) - (a as number))
                    .map(([action, count]) => (
                      <div key={action} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '6px 0', borderBottom: '1px solid #f3f4f6',
                      }}>
                        <span style={{ fontSize: 12, color: '#475569' }}>{action}</span>
                        <span style={{
                          fontSize: 11, fontWeight: 600, color: '#6366f1',
                          padding: '2px 8px', borderRadius: 4, background: '#eef2ff',
                        }}>{count as number}</span>
                      </div>
                    ))}
                </div>
              )}

              {/* Total duration */}
              <div style={{ marginTop: 12, fontSize: 11, color: '#94a3b8', textAlign: 'center' }}>
                Toplam süre: {(usage.total_duration_ms / 1000).toFixed(1)}s
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Workflow Settings Modal */}
      {showSettings && selectedWorkflow && (
        <WorkflowSettingsModal
          workflow={selectedWorkflow}
          onSave={handleSaveSettings}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  )
}
