import { useState } from 'react'
import { PALETTE_GROUPS, NODE_CONFIGS } from '../constants/nodeConfigs'

// ═══════════════════════════════════════════════════════════════════
// NodePalette — Left sidebar with draggable node items
// ═══════════════════════════════════════════════════════════════════

export default function NodePalette() {
  const [searchQuery, setSearchQuery] = useState('')
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({})

  const toggleGroup = (label: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [label]: !prev[label] }))
  }

  const onDragStart = (event: React.DragEvent, subtype: string) => {
    event.dataTransfer.setData('application/reactflow/subtype', subtype)
    event.dataTransfer.effectAllowed = 'move'
  }

  const filteredGroups = PALETTE_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((subtype) => {
      if (!searchQuery) return true
      const config = NODE_CONFIGS[subtype]
      if (!config) return false
      return (
        config.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        subtype.toLowerCase().includes(searchQuery.toLowerCase())
      )
    })
  })).filter((group) => group.items.length > 0)

  return (
    <div style={{
      width: 220,
      background: '#ffffff',
      borderRight: '1px solid #e5e7eb',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
      flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 14px 10px',
        borderBottom: '1px solid #f3f4f6',
      }}>
        <div style={{
          fontSize: 12, fontWeight: 700, color: '#0f172a',
          marginBottom: 8,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <i className="fas fa-puzzle-piece" style={{ color: '#7c3aed', fontSize: 11 }} />
          Adımlar
        </div>
        {/* Search */}
        <div style={{ position: 'relative' }}>
          <i className="fas fa-search" style={{
            position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)',
            color: '#94a3b8', fontSize: 10,
          }} />
          <input
            type="text"
            placeholder="Ara..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%', padding: '6px 8px 6px 28px',
              border: '1px solid #e5e7eb', borderRadius: 6,
              fontSize: 12, color: '#374151', outline: 'none',
              background: '#f9fafb',
              transition: 'border-color 0.15s',
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = '#7c3aed' }}
            onBlur={(e) => { e.currentTarget.style.borderColor = '#e5e7eb' }}
          />
        </div>
      </div>

      {/* Groups */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 10px' }}>
        {filteredGroups.map((group) => {
          const isCollapsed = collapsedGroups[group.label]
          return (
            <div key={group.label} style={{ marginBottom: 12 }}>
              {/* Group header */}
              <button
                onClick={() => toggleGroup(group.label)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  width: '100%', padding: '6px 4px',
                  background: 'none', border: 'none', cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span style={{
                  fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.6px', color: group.textColor,
                }}>
                  {group.label}
                </span>
                <i
                  className={`fas fa-chevron-${isCollapsed ? 'right' : 'down'}`}
                  style={{ fontSize: 8, color: '#94a3b8' }}
                />
              </button>

              {/* Items */}
              {!isCollapsed && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 4 }}>
                  {group.items.map((subtype) => {
                    const config = NODE_CONFIGS[subtype]
                    if (!config) return null

                    return (
                      <div
                        key={subtype}
                        draggable
                        onDragStart={(e) => onDragStart(e, subtype)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 8,
                          padding: '6px 8px',
                          background: '#f9fafb',
                          border: '1px solid #f3f4f6',
                          borderRadius: 7,
                          cursor: 'grab',
                          fontSize: 12, fontWeight: 500, color: '#374151',
                          transition: 'all 0.12s ease',
                          userSelect: 'none',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = group.lightColor
                          e.currentTarget.style.borderColor = group.color + '60'
                          e.currentTarget.style.transform = 'translateX(2px)'
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#f9fafb'
                          e.currentTarget.style.borderColor = '#f3f4f6'
                          e.currentTarget.style.transform = 'translateX(0)'
                        }}
                      >
                        {/* Icon */}
                        <div style={{
                          width: 22, height: 22, borderRadius: 5, flexShrink: 0,
                          background: config.iconBg,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <i
                            className={`fas ${config.faIcon}`}
                            style={{ color: '#ffffff', fontSize: 10 }}
                          />
                        </div>
                        <span style={{
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap', flex: 1,
                        }}>
                          {config.title}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
