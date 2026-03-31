import type { NodeConfig } from '../types'

// ═══════════════════════════════════════════════════════════════════
// TYPE COLORS — consistent palette
// ═══════════════════════════════════════════════════════════════════
export const TYPE_COLORS = {
  trigger:   { bg: '#3b82f6', light: '#dbeafe', text: '#1e40af', border: '#93c5fd', gradient: 'linear-gradient(135deg, #eff6ff, #dbeafe40)' },
  condition: { bg: '#f59e0b', light: '#fef3c7', text: '#92400e', border: '#fcd34d', gradient: 'linear-gradient(135deg, #fffbeb, #fef3c740)' },
  action:    { bg: '#22c55e', light: '#dcfce7', text: '#166534', border: '#86efac', gradient: 'linear-gradient(135deg, #f0fdf4, #dcfce740)' },
} as const

// ═══════════════════════════════════════════════════════════════════
// NODE CONFIGURATIONS — Full catalog with Turkish labels
// ═══════════════════════════════════════════════════════════════════
export const NODE_CONFIGS: Record<string, NodeConfig> = {

  // ─── TRIGGERS ──────────────────────────────────────────────────
  contact_created: {
    label: 'Tetikleyici', title: 'Kişi Oluşturuldu',
    icon: 'user-plus', faIcon: 'fa-user-plus',
    color: 'trigger', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: []
  },
  contact_updated: {
    label: 'Tetikleyici', title: 'Kişi Güncellendi',
    icon: 'user-pen', faIcon: 'fa-user-edit',
    color: 'trigger', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: []
  },
  contact_tag_added: {
    label: 'Tetikleyici', title: 'Etiket Eklendi',
    icon: 'tag', faIcon: 'fa-tag',
    color: 'trigger', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'tag_name', label: 'Etiket Adı', type: 'text', placeholder: 'VIP, Potansiyel...' }
    ]
  },
  contact_no_activity: {
    label: 'Tetikleyici', title: 'Kişi Aktivitesiz',
    icon: 'clock', faIcon: 'fa-user-clock',
    color: 'trigger', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'days', label: 'Gün Sayısı', type: 'number', default: 30 },
      { key: 'min_lead_score', label: 'Min Lead Skoru', type: 'number', default: 0 }
    ]
  },
  deal_created: {
    label: 'Tetikleyici', title: 'Anlaşma Oluşturuldu',
    icon: 'briefcase', faIcon: 'fa-briefcase',
    color: 'trigger', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: []
  },
  deal_stage_changed: {
    label: 'Tetikleyici', title: 'Aşama Değişti',
    icon: 'arrow-right-arrow-left', faIcon: 'fa-exchange-alt',
    color: 'trigger', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: [
      { key: 'from_stage_id', label: 'Kaynak Aşama', type: 'stage_select' },
      { key: 'to_stage_id', label: 'Hedef Aşama', type: 'stage_select' }
    ]
  },
  deal_won: {
    label: 'Tetikleyici', title: 'Anlaşma Kazanıldı',
    icon: 'trophy', faIcon: 'fa-trophy',
    color: 'trigger', iconBg: '#22c55e', iconColor: '#ffffff',
    fields: []
  },
  deal_lost: {
    label: 'Tetikleyici', title: 'Anlaşma Kaybedildi',
    icon: 'circle-xmark', faIcon: 'fa-times-circle',
    color: 'trigger', iconBg: '#ef4444', iconColor: '#ffffff',
    fields: []
  },
  deal_amount_changed: {
    label: 'Tetikleyici', title: 'Tutar Değişti',
    icon: 'dollar-sign', faIcon: 'fa-dollar-sign',
    color: 'trigger', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: []
  },
  deal_no_activity: {
    label: 'Tetikleyici', title: 'Anlaşma Aktivitesiz',
    icon: 'clock', faIcon: 'fa-clock',
    color: 'trigger', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'days', label: 'Gün Sayısı', type: 'number', default: 14 }
    ]
  },
  task_created: {
    label: 'Tetikleyici', title: 'Görev Oluşturuldu',
    icon: 'list-check', faIcon: 'fa-tasks',
    color: 'trigger', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: []
  },
  task_completed: {
    label: 'Tetikleyici', title: 'Görev Tamamlandı',
    icon: 'circle-check', faIcon: 'fa-check-circle',
    color: 'trigger', iconBg: '#22c55e', iconColor: '#ffffff',
    fields: []
  },
  deal_close_date_approaching: {
    label: 'Tetikleyici', title: 'Kapanış Tarihi Yaklaşıyor',
    icon: 'calendar', faIcon: 'fa-calendar-check',
    color: 'trigger', iconBg: '#f59e0b', iconColor: '#ffffff',
    fields: [
      { key: 'days_before', label: 'Kaç Gün Önce', type: 'number', default: 7 }
    ]
  },

  // ─── CONDITIONS ────────────────────────────────────────────────
  check_field: {
    label: 'Koşul', title: 'Alan Kontrol Et',
    icon: 'git-branch', faIcon: 'fa-code-branch',
    color: 'condition', iconBg: '#f59e0b', iconColor: '#ffffff',
    fields: [
      { key: 'field_name', label: 'Alan Adı', type: 'text', placeholder: 'lead_score, email...' },
      { key: 'operator', label: 'Operatör', type: 'select', options: [
        { value: 'equals', label: 'Eşittir' },
        { value: 'not_equals', label: 'Eşit Değil' },
        { value: 'greater_than', label: 'Büyüktür' },
        { value: 'less_than', label: 'Küçüktür' },
        { value: 'contains', label: 'İçerir' },
        { value: 'is_empty', label: 'Boş' },
        { value: 'is_not_empty', label: 'Boş Değil' },
      ]},
      { key: 'value', label: 'Değer', type: 'text' }
    ]
  },
  check_score: {
    label: 'Koşul', title: 'Skor Kontrol Et',
    icon: 'chart-line', faIcon: 'fa-chart-line',
    color: 'condition', iconBg: '#f59e0b', iconColor: '#ffffff',
    fields: [
      { key: 'operator', label: 'Operatör', type: 'select', options: [
        { value: 'greater_than', label: 'Büyüktür' },
        { value: 'less_than', label: 'Küçüktür' },
        { value: 'equals', label: 'Eşittir' },
      ]},
      { key: 'value', label: 'Skor Değeri', type: 'number', default: 50 }
    ]
  },

  // ─── ACTIONS ───────────────────────────────────────────────────
  create_task: {
    label: 'Aksiyon', title: 'Görev Oluştur',
    icon: 'list-check', faIcon: 'fa-clipboard-list',
    color: 'action', iconBg: '#22c55e', iconColor: '#ffffff',
    fields: [
      { key: 'title', label: 'Görev Başlığı', type: 'text',
        placeholder: '{{contact.first_name}} ile iletişime geç' },
      { key: 'due_in_days', label: 'Bitiş (gün)', type: 'number', default: 2 },
      { key: 'assign_to', label: 'Atanacak Kişi', type: 'select', options: [
        { value: 'contact_owner', label: 'Kişi Sahibi' },
        { value: 'deal_owner', label: 'Anlaşma Sahibi' },
      ]}
    ]
  },
  send_email: {
    label: 'Aksiyon', title: 'Email Gönder',
    icon: 'mail', faIcon: 'fa-envelope',
    color: 'action', iconBg: '#ef4444', iconColor: '#ffffff',
    fields: [
      { key: 'subject', label: 'Konu', type: 'text', placeholder: 'Hoş geldiniz!' },
      { key: 'body', label: 'İçerik', type: 'textarea', placeholder: 'Email içeriğini yazın...' }
    ]
  },
  send_whatsapp: {
    label: 'Aksiyon', title: 'WhatsApp Mesajı',
    icon: 'message-circle', faIcon: 'fa-comment-dots',
    color: 'action', iconBg: '#22c55e', iconColor: '#ffffff',
    fields: [
      { key: 'message', label: 'Mesaj', type: 'textarea', placeholder: 'Merhaba {{contact.first_name}}...' }
    ]
  },
  notify_owner: {
    label: 'Aksiyon', title: 'Bildirim Gönder',
    icon: 'bell', faIcon: 'fa-bell',
    color: 'action', iconBg: '#f59e0b', iconColor: '#ffffff',
    fields: [
      { key: 'message', label: 'Bildirim Mesajı', type: 'textarea',
        placeholder: '{{contact.full_name}} için aksiyon gerekli' }
    ]
  },
  update_deal_stage: {
    label: 'Aksiyon', title: 'Aşama Güncelle',
    icon: 'arrow-right-arrow-left', faIcon: 'fa-exchange-alt',
    color: 'action', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: [
      { key: 'stage_id', label: 'Hedef Aşama', type: 'stage_select' }
    ]
  },
  update_deal_field: {
    label: 'Aksiyon', title: 'Anlaşma Alanı Güncelle',
    icon: 'pencil', faIcon: 'fa-edit',
    color: 'action', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'field_name', label: 'Alan Adı', type: 'text' },
      { key: 'field_value', label: 'Yeni Değer', type: 'text' }
    ]
  },
  update_contact_field: {
    label: 'Aksiyon', title: 'Kişi Alanı Güncelle',
    icon: 'pencil', faIcon: 'fa-user-edit',
    color: 'action', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'field_name', label: 'Alan Adı', type: 'text' },
      { key: 'field_value', label: 'Yeni Değer', type: 'text' }
    ]
  },
  add_tag: {
    label: 'Aksiyon', title: 'Etiket Ekle',
    icon: 'tag', faIcon: 'fa-tag',
    color: 'action', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'tag_name', label: 'Etiket Adı', type: 'text', placeholder: 'VIP' }
    ]
  },
  remove_tag: {
    label: 'Aksiyon', title: 'Etiket Kaldır',
    icon: 'tag', faIcon: 'fa-tag',
    color: 'action', iconBg: '#9ca3af', iconColor: '#ffffff',
    fields: [
      { key: 'tag_name', label: 'Etiket Adı', type: 'text' }
    ]
  },
  assign_owner: {
    label: 'Aksiyon', title: 'Sahip Ata',
    icon: 'user', faIcon: 'fa-user-check',
    color: 'action', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: [
      { key: 'assign_to', label: 'Atanacak Kişi', type: 'select', options: [
        { value: 'round_robin', label: 'Sıralı Dağıtım' },
        { value: 'contact_owner', label: 'Kişi Sahibi' },
      ]}
    ]
  },
  create_note: {
    label: 'Aksiyon', title: 'Not Oluştur',
    icon: 'sticky-note', faIcon: 'fa-sticky-note',
    color: 'action', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'content', label: 'Not İçeriği', type: 'textarea' }
    ]
  },
  webhook: {
    label: 'Aksiyon', title: 'Webhook Gönder',
    icon: 'zap', faIcon: 'fa-bolt',
    color: 'action', iconBg: '#ea580c', iconColor: '#ffffff',
    fields: [
      { key: 'url', label: 'Webhook URL', type: 'text', placeholder: 'https://...' },
      { key: 'method', label: 'HTTP Metodu', type: 'select', options: [
        { value: 'POST', label: 'POST' },
        { value: 'GET', label: 'GET' },
        { value: 'PUT', label: 'PUT' },
      ]}
    ]
  },
  wait: {
    label: 'Aksiyon', title: 'Bekle',
    icon: 'hourglass', faIcon: 'fa-hourglass-half',
    color: 'action', iconBg: '#64748b', iconColor: '#ffffff',
    fields: [
      { key: 'delay_minutes', label: 'Dakika', type: 'number', default: 60 }
    ]
  },
  http_request: {
    label: 'Aksiyon', title: 'HTTP İsteği',
    icon: 'globe', faIcon: 'fa-globe',
    color: 'action', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'url', label: 'URL', type: 'text',
        placeholder: 'https://api.example.com/endpoint' },
      { key: 'method', label: 'HTTP Metodu', type: 'select',
        options: [
          { value: 'GET', label: 'GET' },
          { value: 'POST', label: 'POST' },
          { value: 'PUT', label: 'PUT' },
          { value: 'PATCH', label: 'PATCH' },
          { value: 'DELETE', label: 'DELETE' }
        ]
      },
      { key: 'auth_type', label: 'Kimlik Doğrulama', type: 'select',
        options: [
          { value: 'none', label: 'Yok' },
          { value: 'bearer', label: 'Bearer Token' },
          { value: 'basic', label: 'Basic Auth' },
          { value: 'api_key', label: 'API Key' }
        ]
      },
      { key: 'header_key', label: 'Header Key', type: 'text',
        placeholder: 'Authorization' },
      { key: 'header_value', label: 'Header Value', type: 'text',
        placeholder: 'Bearer your-token-here' },
      { key: 'body', label: 'Body (JSON)', type: 'textarea',
        placeholder: '{"key": "{{contact.email}}"}' },
      { key: 'timeout', label: 'Timeout (saniye)', type: 'number', default: 30 }
    ]
  },
}

// ═══════════════════════════════════════════════════════════════════
// PALETTE GROUPS — for the left sidebar
// ═══════════════════════════════════════════════════════════════════
export const PALETTE_GROUPS = [
  {
    label: 'Tetikleyiciler',
    color: TYPE_COLORS.trigger.bg,
    lightColor: TYPE_COLORS.trigger.light,
    textColor: TYPE_COLORS.trigger.text,
    items: [
      'contact_created', 'contact_updated', 'contact_tag_added', 'contact_no_activity',
      'deal_created', 'deal_stage_changed', 'deal_won', 'deal_lost',
      'deal_amount_changed', 'deal_no_activity',
      'task_created', 'task_completed', 'deal_close_date_approaching'
    ]
  },
  {
    label: 'Koşullar',
    color: TYPE_COLORS.condition.bg,
    lightColor: TYPE_COLORS.condition.light,
    textColor: TYPE_COLORS.condition.text,
    items: ['check_field', 'check_score']
  },
  {
    label: 'Aksiyonlar',
    color: TYPE_COLORS.action.bg,
    lightColor: TYPE_COLORS.action.light,
    textColor: TYPE_COLORS.action.text,
    items: [
      'create_task', 'send_email', 'send_whatsapp', 'notify_owner',
      'update_deal_stage', 'update_deal_field', 'update_contact_field',
      'add_tag', 'remove_tag', 'assign_owner',
      'create_note', 'webhook', 'wait', 'http_request'
    ]
  }
]

// Helper: get label for a trigger_type key
export function getTriggerLabel(triggerType: string): string {
  return NODE_CONFIGS[triggerType]?.title || triggerType.replace(/_/g, ' ')
}
