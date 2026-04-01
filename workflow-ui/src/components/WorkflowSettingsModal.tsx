import { useState } from 'react'
import type { WorkflowItem } from '../types'

interface WorkflowSettingsModalProps {
  workflow: WorkflowItem
  onSave: (updates: Partial<WorkflowItem>) => void
  onClose: () => void
}

const RE_ENROLLMENT_OPTIONS = [
  { value: 'always', label: 'Her zaman tekrar kaydet', description: 'Kişi her tetiklendiğinde tekrar kaydedilir' },
  { value: 'once_per_day', label: 'Günde bir kez', description: 'Kişi aynı gün içinde sadece bir kez kaydedilir' },
  { value: 'once_per_week', label: 'Haftada bir kez', description: 'Kişi aynı hafta içinde sadece bir kez kaydedilir' },
  { value: 'never', label: 'Hiçbir zaman', description: 'Kişi sadece ilk kayıtta kaydedilir' },
]

export default function WorkflowSettingsModal({ workflow, onSave, onClose }: WorkflowSettingsModalProps) {
  const [reEnrollmentMode, setReEnrollmentMode] = useState(workflow.re_enrollment_mode || 'always')

  const handleSave = () => {
    onSave({ re_enrollment_mode: reEnrollmentMode })
    onClose()
  }

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
          width: '100%', maxWidth: 480,
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #f3f4f6' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                İş Akışı Ayarları
              </h2>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                {workflow.name}
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
        </div>

        {/* Modal body */}
        <div style={{ padding: '20px 24px', flex: 1 }}>
          {/* Re-enrollment mode */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
              Tekrar Kayıt Modu
            </label>
            <p style={{ fontSize: 11.5, color: '#64748b', margin: '0 0 12px' }}>
              Bir kişi iş akışını tekrar tetiklediğinde ne olur
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {RE_ENROLLMENT_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                    padding: '10px 12px', borderRadius: 8,
                    border: `1.5px solid ${reEnrollmentMode === option.value ? '#7c3aed' : '#e5e7eb'}`,
                    background: reEnrollmentMode === option.value ? '#f5f3ff' : '#ffffff',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  <input
                    type="radio"
                    name="re_enrollment_mode"
                    value={option.value}
                    checked={reEnrollmentMode === option.value}
                    onChange={(e) => setReEnrollmentMode(e.target.value as typeof reEnrollmentMode)}
                    style={{ marginTop: 2 }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>
                      {option.label}
                    </div>
                    <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 2 }}>
                      {option.description}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* Modal footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid #f3f4f6', display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px', borderRadius: 8,
              background: '#f1f5f9', color: '#64748b',
              border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: 600,
            }}
          >
            İptal
          </button>
          <button
            onClick={handleSave}
            style={{
              padding: '8px 16px', borderRadius: 8,
              background: '#7c3aed', color: '#ffffff',
              border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: 600,
            }}
          >
            Kaydet
          </button>
        </div>
      </div>
    </div>
  )
}
