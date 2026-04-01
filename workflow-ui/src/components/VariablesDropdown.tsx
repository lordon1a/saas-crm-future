import { useState, useRef, useEffect, useCallback } from 'react'

// ═══════════════════════════════════════════════════════════════════
// VariablesDropdown — Two-level variable picker for workflow fields
// Fetches from /api/v1/workflows/<id>/variables-schema
// ═══════════════════════════════════════════════════════════════════

interface VarEntry {
  path: string
  label: string
  type: string
}

interface VarGroup {
  group: string
  vars: VarEntry[]
}

interface Props {
  workflowId: number | null
  onSelect: (expression: string) => void
}

const GROUP_ICONS: Record<string, string> = {
  'Kişi': 'fa-user',
  'Anlaşma': 'fa-handshake',
  'Görev': 'fa-tasks',
  'Sistem': 'fa-cog',
}

const TYPE_ICONS: Record<string, string> = {
  string: 'fa-font',
  number: 'fa-hashtag',
  datetime: 'fa-calendar',
  boolean: 'fa-toggle-on',
}

export default function VariablesDropdown({ workflowId, onSelect }: Props) {
  const [open, setOpen] = useState(false)
  const [groups, setGroups] = useState<VarGroup[]>([])
  const [activeGroup, setActiveGroup] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const fetchSchema = useCallback(async () => {
    if (!workflowId) {
      // Fallback static schema when no workflow ID
      setGroups(STATIC_SCHEMA)
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`/api/v1/workflows/${workflowId}/variables-schema`, {
        credentials: 'include',
      })
      if (res.ok) {
        const data = await res.json()
        setGroups(data.groups || [])
        if (data.groups?.length) setActiveGroup(data.groups[0].group)
      } else {
        setGroups(STATIC_SCHEMA)
      }
    } catch {
      setGroups(STATIC_SCHEMA)
    } finally {
      setLoading(false)
    }
  }, [workflowId])

  useEffect(() => {
    if (open && groups.length === 0) fetchSchema()
    if (open && groups.length > 0 && !activeGroup) setActiveGroup(groups[0].group)
  }, [open, groups.length, fetchSchema, activeGroup])

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const filteredGroups = search.trim()
    ? groups.map(g => ({
        ...g,
        vars: g.vars.filter(
          v =>
            v.path.toLowerCase().includes(search.toLowerCase()) ||
            v.label.toLowerCase().includes(search.toLowerCase())
        ),
      })).filter(g => g.vars.length > 0)
    : groups

  const activeVars = search.trim()
    ? filteredGroups.flatMap(g => g.vars)
    : filteredGroups.find(g => g.group === activeGroup)?.vars || []

  const handleSelect = (v: VarEntry) => {
    onSelect(`{{${v.path}}}`)
    setOpen(false)
    setSearch('')
  }

  return (
    <div ref={dropdownRef} style={{ position: 'relative', display: 'inline-block' }}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        title="Değişken ekle"
        style={{
          padding: '4px 8px', borderRadius: 6,
          border: '1.5px solid #e0e7ff', background: '#f0f4ff',
          color: '#4338ca', cursor: 'pointer', fontSize: 11,
          fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4,
          transition: 'all 0.15s',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = '#e0e7ff' }}
        onMouseLeave={e => { e.currentTarget.style.background = '#f0f4ff' }}
      >
        <i className="fas fa-bolt" style={{ fontSize: 10 }} />
        {'{{x}}'}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 4,
          width: 320, background: '#fff',
          border: '1.5px solid #e5e7eb', borderRadius: 10,
          boxShadow: '0 10px 30px rgba(0,0,0,0.12)',
          zIndex: 9999, overflow: 'hidden',
          animation: 'fadeInDown 0.1s ease-out',
        }}>
          {/* Header */}
          <div style={{
            padding: '10px 12px 8px',
            borderBottom: '1px solid #f3f4f6',
            background: '#f8fafc',
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              <i className="fas fa-code" style={{ marginRight: 5, color: '#6366f1' }} />
              Değişken Seç
            </div>
            <input
              autoFocus
              placeholder="Ara..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                width: '100%', padding: '5px 10px',
                border: '1.5px solid #e5e7eb', borderRadius: 7,
                fontSize: 12, outline: 'none', boxSizing: 'border-box',
                background: '#fff',
              }}
            />
          </div>

          {loading ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
              <i className="fas fa-spinner fa-spin" style={{ marginRight: 6 }} />Yükleniyor...
            </div>
          ) : (
            <div style={{ display: 'flex', height: 240 }}>
              {/* Group tabs */}
              {!search.trim() && (
                <div style={{
                  width: 90, borderRight: '1px solid #f3f4f6',
                  overflowY: 'auto', background: '#fafafa',
                }}>
                  {filteredGroups.map(g => (
                    <button
                      key={g.group}
                      onClick={() => setActiveGroup(g.group)}
                      style={{
                        width: '100%', padding: '9px 8px',
                        background: activeGroup === g.group ? '#ede9fe' : 'transparent',
                        border: 'none', borderRight: activeGroup === g.group ? '2px solid #7c3aed' : '2px solid transparent',
                        cursor: 'pointer', textAlign: 'left',
                        fontSize: 10, fontWeight: activeGroup === g.group ? 700 : 500,
                        color: activeGroup === g.group ? '#7c3aed' : '#64748b',
                        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                        transition: 'all 0.1s',
                      }}
                    >
                      <i className={`fas ${GROUP_ICONS[g.group] || 'fa-circle'}`} style={{ fontSize: 12 }} />
                      {g.group}
                    </button>
                  ))}
                </div>
              )}

              {/* Variables list */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
                {activeVars.length === 0 ? (
                  <div style={{ padding: '16px', textAlign: 'center', color: '#94a3b8', fontSize: 11 }}>
                    Değişken bulunamadı
                  </div>
                ) : activeVars.map(v => (
                  <button
                    key={v.path}
                    onClick={() => handleSelect(v)}
                    style={{
                      width: '100%', padding: '7px 12px',
                      background: 'none', border: 'none', cursor: 'pointer',
                      textAlign: 'left', display: 'flex', alignItems: 'center', gap: 8,
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = '#f5f3ff' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'none' }}
                  >
                    <i
                      className={`fas ${TYPE_ICONS[v.type] || 'fa-circle'}`}
                      style={{ color: '#a78bfa', fontSize: 10, width: 12, flexShrink: 0 }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: '#1e293b', lineHeight: 1.2 }}>
                        {v.label}
                      </div>
                      <div style={{
                        fontSize: 9, color: '#7c3aed', fontFamily: 'monospace',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {`{{${v.path}}}`}
                      </div>
                    </div>
                    <span style={{
                      fontSize: 8, padding: '1px 4px', borderRadius: 3,
                      background: '#f1f5f9', color: '#94a3b8', fontWeight: 600,
                      textTransform: 'uppercase', flexShrink: 0,
                    }}>
                      {v.type}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Footer hint */}
          <div style={{
            padding: '6px 12px', borderTop: '1px solid #f3f4f6',
            background: '#fafafa', fontSize: 10, color: '#94a3b8',
          }}>
            Seçilen değişken <code style={{ background: '#f3e8ff', color: '#7c3aed', padding: '0 3px', borderRadius: 2 }}>{'{{değişken.yol}}'}</code> olarak eklenir
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Static fallback schema when no workflow ID is available ───────
const STATIC_SCHEMA: VarGroup[] = [
  {
    group: 'Kişi',
    vars: [
      { path: 'contact.first_name', label: 'Ad', type: 'string' },
      { path: 'contact.last_name', label: 'Soyad', type: 'string' },
      { path: 'contact.email', label: 'E-posta', type: 'string' },
      { path: 'contact.phone', label: 'Telefon', type: 'string' },
      { path: 'contact.lead_score', label: 'Lead Skoru', type: 'number' },
      { path: 'contact.labels', label: 'Etiketler', type: 'string' },
    ],
  },
  {
    group: 'Anlaşma',
    vars: [
      { path: 'deal.name', label: 'Anlaşma Adı', type: 'string' },
      { path: 'deal.deal_value', label: 'Değer', type: 'number' },
      { path: 'deal.stage_id', label: 'Aşama ID', type: 'number' },
      { path: 'deal.assigned_to', label: 'Atanan', type: 'number' },
    ],
  },
  {
    group: 'Sistem',
    vars: [
      { path: 'trigger.type', label: 'Tetikleyici Tipi', type: 'string' },
      { path: 'entity_type', label: 'Varlık Tipi', type: 'string' },
      { path: 'entity_id', label: 'Varlık ID', type: 'number' },
    ],
  },
]
