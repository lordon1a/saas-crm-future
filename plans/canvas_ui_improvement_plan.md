# Canvas UI İyileştirme Planı

## 🎯 Hedef
Workflow canvas'ı profesyonel bir n8n-benzeri deneyime dönüştürmek.

## Mevcut Durum
- React Flow tabanlı canvas ✅
- Temel node görünümü ✅
- Drag & drop (sınırlı) ✅
- Node properties panel ✅

## Yapılacak İyileştirmeler

### 1. Merkezi "Add First Step" Placeholder
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                    ┌──────────────────┐                    │
│                    │   + Add First    │                    │
│                    │      Step        │                    │
│                    └──────────────────┘                    │
│                                                             │
│              (Trigger eklemek için tıkla)                   │
└─────────────────────────────────────────────────────────────┘
```
- Canvas ortasında büyük placeholder
- Tıklandığında node seçim menüsü açılır
- Trigger eklendikten sonra sabit pozisyona gider

### 2. Sürükle Bırak (Drag & Drop) İyileştirmesi
- Palette'den node sürükleme
- Drop zones gösterimi
- Node'u canvas üzerinde serbest taşıma
- Snap to grid (opsiyonel)

### 3. Node Bağlantıları (Edges)
- Ok/çizgi ile gösterim
- Sürükleyerek bağlama
- Bağlantıyı silme (tıklayıp delete)
- Birden fazla çıkış noktası (branch/if-else için)
- Bağlantı üzerinde animasyon (çalışırken)

### 4. Node Ekleme Paneli
```
┌────────────────┐
│   + Node Ekle   │  ← Sabit buton (sağ alt)
└────────────────┘

Sağ tık menüsü:
┌──────────────────┐
│ ➕ Node Ekle      │
├──────────────────┤
│ 🔵 Trigger       │ → Webhook, Schedule, etc.
│ 🟢 Action        │ → Email, HTTP, etc.
│ 🟡 Logic         │ → If, Switch, etc.
└──────────────────┘
```

### 5. Node Ayar Paneli (Side Panel)
```
┌──────────────────────────────┐
│  ✕                              │
│ ┌────┐                         │
│ │ 🔵 │  Email Gönder          │
│ └────┘                         │
├──────────────────────────────┤
│  Alıcı                          │
│  ┌──────────────────────────┐  │
│  │ {{contact.email}}        │  │
│  └──────────────────────────┘  │
│                               │
│  Konu                          │
│  ┌──────────────────────────┐  │
│  │ Hoş geldin!              │  │
│  └──────────────────────────┘  │
│                               │
│  İçerik                         │
│  ┌──────────────────────────┐  │
│  │ Merhaba {{contact.name}} │  │
│  │ ...                      │  │
│  └──────────────────────────┘  │
│                               │
│  ┌──────────────────────────┐  │
│  │   ▶ Test Et              │  │
│  └──────────────────────────┘  │
├──────────────────────────────┤
│  ID: step-123456             │
└──────────────────────────────┘
```

### 6. Run / Execute Butonu
```
┌─────────────────────────────────────────┐
│  ☰  Workflow Name        [◐ Active] [▶ Run] │
└─────────────────────────────────────────┘

Dropdown menüsü:
- ▶ Bu Node'u Çalıştır (tek node test)
- ▶ Tüm Workflow'u Çalıştır
- ⏹ Durdur
```

### 7. Execution Output Paneli
```
┌─────────────────────────────────────────┐
│  ▶ Execution Output              [×]    │
├─────────────────────────────────────────┤
│  ✅ Email Gönder - Başarılı            │
│  ⏱ 245ms                              │
│  ┌─────────────────────────────────┐   │
│  │ {                               │   │
│  │   "to": "test@mail.com",       │   │
│  │   "status": "sent",            │   │
│  │   "message_id": "abc123"       │   │
│  │ }                               │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ❌ HTTP İsteği - Hata                 │
│  ⏱ 1200ms                              │
│  ┌─────────────────────────────────┐   │
│  │ Connection timeout              │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### 8. Save / Active Toggle
```
┌─────────────────────────────────────────┐
│  Workflow Name            [◐ Aktif] [💾] │
└─────────────────────────────────────────┘
```

## Teknik Gereksinimler

### React Flow Özellikleri
- `nodeTypes` - custom node render
- `edgeTypes` - custom edge render  
- `ConnectionLine` - bağlantı çizgisi
- `Controls` - zoom/pan kontrolleri
- `Background` - grid arka plan
- `MiniMap` - opsiyonel navigasyon

### State Management
```typescript
interface WorkflowEditorState {
  nodes: Node[]
  edges: Edge[]
  selectedNode: string | null
  executingNode: string | null
  executionLogs: ExecutionLog[]
  isDirty: boolean
  isActive: boolean
}
```

## Dosya Yapısı
```
vite/workflow-ui/src/
├── components/
│   ├── WorkflowCanvas.tsx      ← Ana canvas
│   ├── WorkflowNode.tsx       ← Custom node render
│   ├── NodePalette.tsx         ← Node seçim menüsü
│   ├── NodePropertiesPanel.tsx ← Ayar paneli (mevcut)
│   ├── ExecutionOutput.tsx     ← Çıktı paneli
│   └── WorkflowToolbar.tsx     ← Run/Save toolbar
├── store/
│   └── workflowStore.ts       ← State management
└── types.ts                   ← Type definitions
```

## Öncelik Sırası
1. Merkezi placeholder ve trigger ekleme
2. Node ekleme paneli (+ butonu)
3. Execution output paneli
4. Run butonu (tek node test)
5. Bağlantı iyileştirmeleri
6. Sağ tık menüsü
7. MiniMap (opsiyonel)

## Not
Mevcut React Flow canvas zaten iyi bir temel sunuyor. Yapılacaklar daha çok UI/UX iyileştirmeleri ve yeni bileşenler eklemek.