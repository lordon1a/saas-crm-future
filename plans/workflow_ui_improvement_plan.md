# Workflow UI İyileştirme ve Bug Düzeltme Planı

## Durum Analizi

### Mevcut Sistem
- **Backend**: Flask/Python - `WorkflowAutomation`, `WorkflowCondition`, `WorkflowAction` modelleri
- **Frontend**: Vanilla JS + ReactFlow CDN
- **API**: REST (`/api/v1/workflows`)
- **Trigger Türleri**: `deal_stage_changed`, `deal_created`, `deal_won`, `deal_lost`, `contact_created`, `contact_no_activity`, `deal_no_activity`
- **Action Türleri**: `create_task`, `notify_owner`, `send_email`, `add_tag`, `update_deal_field`, `update_contact_field`

### Bildirilen Sorunlar
1. Trigger koşulları düzgün çalışmıyor
2. Action adımları yarım kalıyor
3. UI kötü görünüyor (Twenty tarzı olsun istiyor)

---

## Aşama 1: Bug Düzeltme (Backend)

### 1.1 Trigger/Condition Düzeltmeleri

**Sorun**: Koşul değerlendirmesi sırasında field değerleri düzgün alınamıyor olabilir.

**Dosya**: `services/workflow_service.py`

**Düzeltmeler**:
```python
# _get_field_value() fonksiyonunu güçlendir
# - Dot notation desteği (contact.company.name)
# - Context değerleri için prefix kontrolü  
# - Enum fields için özel işlem
```

**Test**: `test_workflow_e2e.py` çalıştırarak doğrula

### 1.2 Action Düzeltmeleri

**Sorun**: Action config JSON parse hatası veya eksik alan

**Kontrol Edilecekler**:
- `action.action_config` null/string kontrolü
- Template variable resolution (`{{contact.first_name}}`)
- Assign_to field'ı için default değer

**Düzeltmeler**:
```python
# _action_create_task() - config parse güvenliği
config = json.loads(action.action_config) if action.action_config else {}

# _action_send_email() - template resolution
subject = WorkflowService.resolve_template(config.get('subject', ''), entity, context)
```

### 1.3 Trigger Event Güvenliği

**Kontrol Edilecekler**:
- `trigger_event()` exception handling
- Entity loading başarısızlık durumu
- Workspace isolation

---

## Aşama 2: UI İyileştirme (Frontend)

### 2.1 ReactFlow Entegrasyonu

**Mevcut**: ReactFlow CDN ile temel kullanım

**İyileştirmeler**:
1. **Custom Node Styling** - Twenty tarzı:
   - Trigger node: Mavi border, ikon
   - Condition node: Sarı border
   - Action node: Yeşil border
   - Node padding, border-radius, shadow

2. **Canvas İyileştirmeleri**:
   - Zoom kontrolleri
   - Mini-map
   - Fit view on load
   - Grid snapping

3. **Edge Styling**:
   - Animated edges (Twenty tarzı)
   - Edge label'lar
   - Renk kodlaması (success=red, failure=green)

### 2.2 Side Panel İyileştirmesi

**Twenty Tarzı Öğeler**:
```
┌─────────────────────────────────────┐
│  Workflow Name            [Publish]│
├─────────────────────────────────────┤
│  [Trigger] [Steps] [History]        │
├─────────────────────────────────────┤
│  Step Configuration                 │
│  ├─ Action Type: [Send Email    ▼] │
│  ├─ To: {{contact.email}}           │
│  ├─ Subject: ...                    │
│  └─ Body: ...                       │
└─────────────────────────────────────┘
```

### 2.3 Node Paleti

**Ekle**: Drag-drop node ekleme
- Trigger types listesi (soldaki sidebar)
- Action types listesi
- Condition node

### 2.4 Değişken Picker

**Twenty Tarzı**:
```
{{contact.first_name}} → "John"
{{deal.value}} → "1000"
```

**İmplementasyon**:
- `{{` yazınca dropdown açılır
- Entity listesi (contact, deal, task)
- Field listesi
- Insert on click

---

## Aşama 3: Veri Modeli Güncelleme (Opsiyonel)

### 3.1 Canvas Data Yapısı

**Mevcut**:
```javascript
canvas_data: {
  nodes: [{ id, position, data }],
  edges: [{ id, source, target }]
}
```

**İyileştirilmiş** (Twenty uyumlu):
```javascript
canvas_data: {
  nodes: [...],
  edges: [...],
  viewport: { x, y, zoom },
  selectedNodeId: null
}
```

### 3.2 Version Desteği (İleri)

Twenty gibi draft/active/version desteği eklenebilir:
- `status: 'DRAFT' | 'ACTIVE' | 'DEACTIVATED'`
- Version history
- Draft autosave

---

## Aşama 4: Dosya Yapısı

```
static/
├── css/
│   └── workflow.css          # Yeni - Twenty tarzı stiller
├── js/
│   ├── workflow-app.js       # Güncelleniyor - Ana uygulama
│   ├── workflow-canvas.js    # ReactFlow canvas
│   ├── workflow-nodes.js     # Yeni - Custom node renderers
│   ├── workflow-sidebar.js   # Yeni - Side panel
│   ├── workflow-variables.js # Yeni - Variable picker
│   └── workflow-api.js      # Yeni - API wrapper
└── libs/
    └── reactflow/            # CDN değil local

templates/
└── workflows.html            # Güncelleniyor
```

---

## Aşama 5: CSS Stilleri (Twenty Tarzı)

### Node Stilleri
```css
.workflow-node {
  background: white;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 16px;
  min-width: 240px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  transition: all 0.2s;
}

.workflow-node:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.workflow-node.trigger {
  border-color: #3b82f6; /* blue */
}

.workflow-node.action {
  border-color: #22c55e; /* green */
}

.workflow-node.condition {
  border-color: #f59e0b; /* amber */
}
```

### Typography
```css
.workflow-node h4 {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.workflow-node p {
  font-size: 12px;
  color: #64748b;
}
```

---

## Uygulama Sırası

1. **Hata Ayıklama** (Debug mode)
   - Backend test çalıştır
   - Log'ları incele
   - Sorunları tespit et

2. **Backend Düzeltmeleri**
   - `_get_field_value()` güçlendir
   - Action config parse düzelt
   - Exception handling ekle

3. **Frontend Geliştirme**
   - CSS dosyası oluştur
   - Custom node renderers
   - Side panel component
   - Variable picker

4. **Entegrasyon**
   - Template güncelle
   - JS dosyalarını bağla
   - Test et

---

## Kritik Dosyalar

| Dosya | İşlem |
|-------|-------|
| `services/workflow_service.py` | Bug düzeltme, condition/action iyileştirme |
| `models_crm.py` | Workflow modelleri (değişiklik yok) |
| `routes/workflows.py` | API (değişiklik yok) |
| `static/workflow-canvas.js` | ReactFlow canvas (iyileştirme) |
| `static/workflow-builder.js` | List management (değişiklik yok) |
| `static/css/workflow.css` | **YENİ** - Twenty tarzı stiller |
| `static/js/workflow-nodes.js` | **YENİ** - Custom nodes |
| `static/js/workflow-variables.js` | **YENİ** - Variable picker |
| `templates/workflows.html` | Template (güncelleme) |

---

## Notlar

- Twenty CRM tamamen React/TypeScript yazılmış, bu yüzden direkt entegrasyon çok zor
- Vanilla JS + ReactFlow ile Twenty tarzı UX oluşturacağız
- Backend API'ler değişmeyecek, sadece frontend güncellenecek
- Mevcut veritabanı yapısı korunacak