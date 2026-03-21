# IDOR Güvenlik Açığı Düzeltme Kılavuzu

## Özet
Bu kılavuz, SECURITY_AUDIT_REPORT.md'deki BULGU #4, #5, #6'yı (IDOR zafiyetleri) düzeltmek için adım adım talimatlar içerir.

## Yapılan Değişiklikler

### 1. `utils/permissions.py` - Merkezi Güvenlik Fonksiyonları Eklendi

Aşağıdaki fonksiyonlar eklendi:
- `check_entity_access(user, entity, action)` - Entity'ye erişim kontrolü
- `require_entity_access(entity_getter, action)` - Decorator for automatic access check
- `get_accessible_entities_query(user, entity_class)` - Query filtering for list endpoints

## Uygulanması Gereken Endpoint'ler

### Öncelik 1: CRITICAL - Deal Endpoints (routes/pipeline.py)

#### ✅ Düzeltilmesi Gereken:
```python
# ÖNCE (Güvensiz):
@bp.route('/deals/<int:deal_id>', methods=['GET'])
@login_required_api
def get_deal(deal_id):
    workspace_id = session.get('workspace_id')
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first()
    # ❌ Kullanıcının bu deal'e erişim yetkisi kontrol edilmiyor!

# SONRA (Güvenli):
from utils.permissions import check_entity_access, get_current_user_from_session

@bp.route('/deals/<int:deal_id>', methods=['GET'])
@login_required_api
def get_deal(deal_id):
    workspace_id = session.get('workspace_id')
    user = get_current_user_from_session()
    
    deal = Deal.query.filter_by(id=deal_id, workspace_id=workspace_id).first()
    if not deal:
        return jsonify({'error': 'Deal not found'}), 404
    
    # ✅ Erişim kontrolü eklendi
    if not check_entity_access(user, deal, 'read'):
        return jsonify({'error': 'Access denied to this deal'}), 403
    
    # ... devam
```

#### Düzeltilecek Endpoint'ler:
- [ ] `GET /api/v1/deals/<deal_id>` - get_deal()
- [ ] `PATCH /api/v1/deals/<deal_id>` - update_deal()
- [ ] `PATCH /api/v1/deals/<deal_id>/stage` - move_deal_stage()
- [ ] `POST /api/v1/deals/<deal_id>/close` - close_deal()
- [ ] `DELETE /api/v1/deals/<deal_id>` - delete_deal()
- [ ] `GET /api/v1/deals` - get_deals() (list endpoint - use get_accessible_entities_query)

### Öncelik 2: CRITICAL - Task Endpoints (routes/tasks.py)

#### Düzeltilecek Endpoint'ler:
- [ ] `GET /api/v1/tasks/<task_id>` - get_task()
- [ ] `PATCH /api/v1/tasks/<task_id>` - update_task()
- [ ] `DELETE /api/v1/tasks/<task_id>` - delete_task()
- [ ] `POST /api/v1/tasks/<task_id>/complete` - complete_task()
- [ ] `GET /api/v1/tasks` - list_tasks() (use get_accessible_entities_query)

### Öncelik 3: CRITICAL - Contact/Company Endpoints (routes/contacts.py)

#### Düzeltilecek Endpoint'ler:
- [ ] `GET /api/v1/companies/<company_id>` - get_company()
- [ ] `PATCH /api/v1/companies/<company_id>` - update_company()
- [ ] `DELETE /api/v1/companies/<company_id>` - delete_company()
- [ ] `GET /api/v1/contacts/<contact_id>` - get_contact()
- [ ] `PATCH /api/v1/contacts/<contact_id>` - update_contact()
- [ ] `DELETE /api/v1/contacts/<contact_id>` - delete_contact()
- [ ] `GET /api/v1/companies` - get_companies() (use get_accessible_entities_query)
- [ ] `GET /api/v1/contacts` - get_contacts() (use get_accessible_entities_query)

## Implementation Pattern

### Pattern 1: Single Entity Endpoint (GET/PATCH/DELETE)

```python
from utils.permissions import check_entity_access, get_current_user_from_session

@bp.route('/resource/<int:resource_id>', methods=['GET'])
@login_required
def get_resource(resource_id):
    user = get_current_user_from_session()
    
    # 1. Get entity with workspace filter
    resource = Resource.query.filter_by(
        id=resource_id,
        workspace_id=user.workspace_id
    ).first()
    
    if not resource:
        return jsonify({'error': 'Resource not found'}), 404
    
    # 2. Check access (CRITICAL)
    if not check_entity_access(user, resource, 'read'):
        return jsonify({'error': 'Access denied'}), 403
    
    # 3. Return data
    return jsonify({...}), 200
```

### Pattern 2: List Endpoint (GET with filters)

```python
from utils.permissions import get_accessible_entities_query, get_current_user_from_session

@bp.route('/resources', methods=['GET'])
@login_required
def list_resources():
    user = get_current_user_from_session()
    
    # 1. Start with access-filtered query
    query = get_accessible_entities_query(user, Resource)
    
    # 2. Apply additional filters
    if request.args.get('status'):
        query = query.filter_by(status=request.args.get('status'))
    
    # 3. Paginate and return
    pagination = query.paginate(page=page, per_page=per_page)
    return jsonify({...}), 200
```

### Pattern 3: Write/Delete Operations

```python
@bp.route('/resource/<int:resource_id>', methods=['PATCH'])
@login_required
def update_resource(resource_id):
    user = get_current_user_from_session()
    
    resource = Resource.query.filter_by(
        id=resource_id,
        workspace_id=user.workspace_id
    ).first()
    
    if not resource:
        return jsonify({'error': 'Resource not found'}), 404
    
    # Use 'write' action for updates
    if not check_entity_access(user, resource, 'write'):
        return jsonify({'error': 'Access denied'}), 403
    
    # Update logic...
    return jsonify({...}), 200
```

## Test Checklist

Her endpoint düzeltildikten sonra test et:

### Test 1: Cross-Workspace Access (CRITICAL)
```bash
# User A (workspace 1) tries to access User B's (workspace 2) resource
curl -X GET http://localhost:5000/api/v1/deals/123 \
  -H "Cookie: session=user_a_session"
# Expected: 404 Not Found (entity filtered by workspace)
```

### Test 2: Same-Workspace Unauthorized Access
```bash
# Member user tries to access admin's deal
curl -X GET http://localhost:5000/api/v1/deals/456 \
  -H "Cookie: session=member_session"
# Expected: 403 Access Denied
```

### Test 3: Authorized Access
```bash
# User accesses their own resource
curl -X GET http://localhost:5000/api/v1/deals/789 \
  -H "Cookie: session=owner_session"
# Expected: 200 OK with data
```

### Test 4: Admin Override
```bash
# Admin accesses any resource in workspace
curl -X GET http://localhost:5000/api/v1/deals/456 \
  -H "Cookie: session=admin_session"
# Expected: 200 OK with data
```

## Rollout Plan

### Phase 1: Core Entities (Bu Hafta)
1. ✅ `utils/permissions.py` - Merkezi fonksiyonlar eklendi
2. ⏳ `routes/pipeline.py` - Deal endpoints
3. ⏳ `routes/tasks.py` - Task endpoints
4. ⏳ `routes/contacts.py` - Contact/Company endpoints

### Phase 2: Secondary Entities (Gelecek Hafta)
5. `routes/documents.py` - Document endpoints
6. `routes/api.py` - Conversation/Message endpoints
7. `routes/automation.py` - Automation endpoints

### Phase 3: Validation (Test Week)
8. Automated security tests
9. Manual penetration testing
10. Code review

## Monitoring

Düzeltmelerden sonra log'larda şunları izle:

```python
# utils/permissions.py içinde eklenen log'lar:
logger.warning("SECURITY: Cross-workspace access attempt blocked")
logger.warning("SECURITY: Access denied - user X attempted Y on Z")
```

Bu log'lar saldırı girişimlerini gösterir.

## Notlar

- ⚠️ Her endpoint'e `check_entity_access()` eklemek ZORUNLU
- ⚠️ List endpoint'lerinde `get_accessible_entities_query()` kullan
- ⚠️ Workspace isolation kontrolü HER ZAMAN yapılmalı
- ✅ Admin/owner rolleri tüm workspace'e erişebilir
- ✅ Member rolleri sadece kendilerine atanan entity'lere erişebilir
- ✅ Viewer rolleri sadece okuma yapabilir

## Sonraki Adımlar

1. `routes/pipeline.py` dosyasını düzelt (en kritik)
2. `routes/tasks.py` dosyasını düzelt
3. `routes/contacts.py` dosyasını düzelt
4. Test suite'i çalıştır
5. Production'a deploy et
