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
  manual: {
    label: 'Tetikleyici', title: 'Manuel Başlat',
    icon: 'hand-pointer', faIcon: 'fa-hand-pointer',
    color: 'trigger', iconBg: '#6366f1', iconColor: '#ffffff',
    fields: [
      { key: 'description', label: 'Açıklama', type: 'text', placeholder: 'Ne zaman manuel çalıştırılmalı?' },
    ]
  },
  schedule: {
    label: 'Tetikleyici', title: 'Zamanlama',
    icon: 'calendar-alt', faIcon: 'fa-calendar-alt',
    color: 'trigger', iconBg: '#3b82f6', iconColor: '#ffffff',
    fields: [
      { key: 'interval_type', label: 'Sıklık', type: 'select', options: [
        { value: 'every_hour', label: 'Her Saat' },
        { value: 'every_day', label: 'Her Gün' },
        { value: 'every_week', label: 'Her Hafta' },
        { value: 'custom_cron', label: 'Özel Cron' },
      ]},
      { key: 'run_time', label: 'Saat (HH:MM)', type: 'text', placeholder: '09:00' },
      { key: 'cron_expression', label: 'Cron İfadesi', type: 'text', placeholder: '0 9 * * 1-5' },
    ]
  },
  webhook_trigger: {
    label: 'Tetikleyici', title: 'Webhook Tetikleyici',
    icon: 'plug', faIcon: 'fa-plug',
    color: 'trigger', iconBg: '#7c3aed', iconColor: '#ffffff',
    fields: [
      { key: 'method', label: 'HTTP Metot', type: 'select', options: [
        { value: 'POST', label: 'POST' },
        { value: 'GET', label: 'GET' },
      ]},
      { key: 'secret', label: 'Secret (opsiyonel)', type: 'text', placeholder: 'güvenlik anahtarı' },
    ]
  },

  // ─── CONDITIONS ────────────────────────────────────────────────
  if_else: {
    label: 'Koşul', title: 'IF / ELSE',
    icon: 'git-branch', faIcon: 'fa-code-branch',
    color: 'condition', iconBg: '#f59e0b', iconColor: '#ffffff',
    fields: [
      { key: 'field_name', label: 'Alan', type: 'text', placeholder: 'deal.amount, contact.email...' },
      { key: 'operator', label: 'Operatör', type: 'select', options: [
        { value: 'equals', label: 'Eşittir' },
        { value: 'not_equals', label: 'Eşit Değil' },
        { value: 'greater_than', label: 'Büyüktür' },
        { value: 'less_than', label: 'Küçüktür' },
        { value: 'contains', label: 'İçerir' },
        { value: 'not_contains', label: 'İçermez' },
        { value: 'is_empty', label: 'Boş' },
        { value: 'is_not_empty', label: 'Boş Değil' },
      ]},
      { key: 'value', label: 'Değer', type: 'text', placeholder: '1000, vip, true...' },
      { key: 'logic', label: 'Mantık', type: 'select', options: [
        { value: 'AND', label: 'Tümü (AND)' },
        { value: 'OR', label: 'Herhangi biri (OR)' },
      ]},
    ]
  },
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
  delay: {
    label: 'Aksiyon', title: 'Bekle',
    icon: 'clock', faIcon: 'fa-hourglass-half',
    color: 'action', iconBg: '#64748b', iconColor: '#ffffff',
    fields: [
      { key: 'duration', label: 'Süre', type: 'number', default: 1 },
      { key: 'unit', label: 'Birim', type: 'select', options: [
        { value: 'minutes', label: 'Dakika' },
        { value: 'hours', label: 'Saat' },
        { value: 'days', label: 'Gün' },
      ]},
    ]
  },
  find_records: {
    label: 'Aksiyon', title: 'Kayıt Bul',
    icon: 'search', faIcon: 'fa-search',
    color: 'action', iconBg: '#0ea5e9', iconColor: '#ffffff',
    fields: [
      { key: 'entity_type', label: 'Varlık Tipi', type: 'select', options: [
        { value: 'contact', label: 'Kişi' },
        { value: 'deal', label: 'Anlaşma' },
        { value: 'task', label: 'Görev' },
      ]},
      { key: 'filter_field', label: 'Filtre Alanı', type: 'text', placeholder: 'email, stage_id...' },
      { key: 'filter_operator', label: 'Operatör', type: 'select', options: [
        { value: 'equals', label: 'Eşittir' },
        { value: 'contains', label: 'İçerir' },
        { value: 'greater_than', label: 'Büyüktür' },
        { value: 'less_than', label: 'Küçüktür' },
        { value: 'is_empty', label: 'Boş' },
      ]},
      { key: 'filter_value', label: 'Filtre Değeri', type: 'text', placeholder: '{{contact.email}}' },
      { key: 'limit', label: 'Maks. Sonuç', type: 'number', default: 10 },
      { key: 'output_variable', label: 'Çıktı Değişkeni', type: 'text', placeholder: 'found_records', default: 'found_records' },
    ]
  },
  delete_record: {
    label: 'Aksiyon', title: 'Kayıt Sil',
    icon: 'trash', faIcon: 'fa-trash',
    color: 'action', iconBg: '#ef4444', iconColor: '#ffffff',
    fields: [
      { key: 'entity_type', label: 'Varlık Tipi', type: 'select', options: [
        { value: 'contact', label: 'Kişi' },
        { value: 'deal', label: 'Anlaşma' },
        { value: 'task', label: 'Görev' },
      ]},
      { key: 'entity_id', label: 'Kayıt ID', type: 'text', placeholder: '{{entity.id}}' },
      { key: 'confirm', label: 'Onay', type: 'select', options: [
        { value: 'true', label: 'Evet, Sil' },
        { value: 'false', label: 'Hayır' },
      ]},
    ]
  },
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

  // ─── N8N-STYLE NODES ──────────────────────────────────────────────
  code: {
    label: 'Aksiyon', title: 'Kod Çalıştır',
    icon: 'code', faIcon: 'fa-code',
    color: 'action', iconBg: '#8b5cf6', iconColor: '#ffffff',
    fields: [
      { key: 'language', label: 'Dil', type: 'select',
        options: [
          { value: 'javascript', label: 'JavaScript' },
          { value: 'python', label: 'Python' }
        ]
      },
      { key: 'code', label: 'Kod', type: 'textarea',
        placeholder: '// Değişkenler: items, entity\nreturn items;' }
    ]
  },
  loop_over_items: {
    label: 'Logic', title: 'Döngü (Loop)',
    icon: 'repeat', faIcon: 'fa-redo',
    color: 'condition', iconBg: '#f59e0b', iconColor: '#ffffff',
    fields: [
      { key: 'max_concurrency', label: 'Eşzamanlı İşlem', type: 'number', default: 1 }
    ]
  },
  if: {
    label: 'Logic', title: 'IF/Else',
    icon: 'code-branch', faIcon: 'fa-code-branch',
    color: 'condition', iconBg: '#f59e0b', iconColor: '#ffffff',
    fields: [
      { key: 'conditions', label: 'Koşullar', type: 'textarea',
        placeholder: '[{"field": "email", "operator": "contains", "value": "@"}]' }
    ]
  },
  error_trigger: {
    label: 'Logic', title: 'Hata Yakalama',
    icon: 'exclamation-triangle', faIcon: 'fa-exclamation-triangle',
    color: 'condition', iconBg: '#ef4444', iconColor: '#ffffff',
    fields: [
      { key: 'on_error_action', label: 'Hata Sonrası', type: 'select',
        options: [
          { value: 'stop', label: 'Durdur' },
          { value: 'continue', label: 'Devam Et' },
          { value: 'retry', label: 'Tekrar Dene' }
        ]
      },
      { key: 'max_retries', label: 'Max Tekrar', type: 'number', default: 3 }
    ]
  },
  split_in_batches: {
    label: 'Logic', title: 'Batch İşleme',
    icon: 'layer-group', faIcon: 'fa-layer-group',
    color: 'condition', iconBg: '#0ea5e9', iconColor: '#ffffff',
    fields: [
      { key: 'batch_size', label: 'Batch Büyüklüğü', type: 'number', default: 10 }
    ]
  },
  wait_until: {
    label: 'Aksiyon', title: 'Tarihe Kadar Bekle',
    icon: 'calendar-alt', faIcon: 'fa-calendar-alt',
    color: 'action', iconBg: '#64748b', iconColor: '#ffffff',
    fields: [
      { key: 'timestamp_field', label: 'Tarih Alanı', type: 'text',
        placeholder: '{{contact.next_follow_up}}' },
      { key: 'timeout_hours', label: 'Timeout (saat)', type: 'number', default: 72 }
    ]
  },
  set_node: {
    label: 'Aksiyon', title: 'Değer Ayarla',
    icon: 'pen', faIcon: 'fa-pen',
    color: 'action', iconBg: '#10b981', iconColor: '#ffffff',
    fields: [
      { key: 'field_name', label: 'Alan Adı', type: 'text' },
      { key: 'field_value', label: 'Değer', type: 'text',
        placeholder: '{{contact.email}}' }
    ]
  },
  
  // ─── AI AGENT ─────────────────────────────────────────────────────
  ai_agent: {
    label: 'AI Agent', title: 'AI Agent (MiniMax/LangChain)',
    icon: 'bot', faIcon: 'fa-robot',
    color: 'action', iconBg: '#8b5cf6', iconColor: '#ffffff',
    fields: [
      { key: 'provider', label: 'AI Sağlayıcı', type: 'select',
        options: [
          { value: 'minimax', label: 'MiniMax (Önerilen)' },
          { value: 'anthropic', label: 'Anthropic Claude' },
          { value: 'gemini', label: 'Google Gemini' },
          { value: 'groq', label: 'Groq' }
        ]
      },
      { key: 'model', label: 'Model', type: 'text',
        placeholder: 'MiniMax-M2.7', default: 'MiniMax-M2.7' },
      { key: 'system_prompt', label: 'Sistem Talimatı', type: 'textarea',
        placeholder: 'Sen bir satış asistanısın. Müşterilere yardımcı ve profesyonel davran.' },
      { key: 'user_prompt', label: 'Kullanıcı İstegi', type: 'textarea',
        placeholder: '{{contact.first_name}} için özel bir email taslağı oluştur.' },
      { key: 'max_tokens', label: 'Max Token', type: 'number', default: 2048 },
      { key: 'output_variable', label: 'Çıktı Değişkeni', type: 'text',
        placeholder: 'ai_response', default: 'ai_response' },
      { key: 'temperature', label: 'Temperature', type: 'number', default: 0.7 }
    ]
  },

  // ─── SUB-WORKFLOW ─────────────────────────────────────────────────
  call_workflow: {
    label: 'Aksiyon', title: 'İş Akışı Çağır',
    icon: 'sitemap', faIcon: 'fa-sitemap',
    color: 'action', iconBg: '#7c3aed', iconColor: '#ffffff',
    fields: [
      { key: 'workflow_id', label: 'İş Akışı ID', type: 'number',
        placeholder: 'Alt iş akışının ID numarası' }
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
      'manual', 'schedule', 'webhook_trigger',
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
    items: ['if_else', 'check_field', 'check_score', 'loop_over_items', 'if', 'error_trigger', 'split_in_batches']
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
      'create_note', 'webhook', 'delay', 'wait', 'http_request',
      'find_records', 'delete_record',
      'code', 'wait_until', 'set_node', 'ai_agent', 'call_workflow'
    ]
  }
]

// Helper: get label for a trigger_type key
export function getTriggerLabel(triggerType: string): string {
  return NODE_CONFIGS[triggerType]?.title || triggerType.replace(/_/g, ' ')
}
