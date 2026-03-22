"""
DocGen API Test Script
Local test için kullan: python test_docgen_api.py
"""
import requests
import json
import os

BASE_URL = "http://localhost:5000"
API_URL = f"{BASE_URL}/api/docgen"

# Test için session oluştur (login gerekli)
session = requests.Session()

def login():
    """Login yap ve session al"""
    print("🔐 Login yapılıyor...")
    response = session.post(f"{BASE_URL}/login", data={
        "email": "test@example.com",  # Kendi email'ini yaz
        "password": "test123"  # Kendi şifreni yaz
    }, allow_redirects=False)
    
    if response.status_code in [200, 302]:
        print("✅ Login başarılı")
        return True
    else:
        print(f"❌ Login başarısız: {response.status_code}")
        print("⚠️  Email ve şifreyi test_docgen_api.py dosyasında güncelle")
        return False

def test_list_templates():
    """Template listesini getir"""
    print("\n📋 Template listesi getiriliyor...")
    response = session.get(f"{API_URL}/templates")
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {len(data.get('templates', []))} template bulundu")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"❌ Hata: {response.text}")
    
    return response

def test_create_template():
    """Yeni template oluştur (dosya upload testi)"""
    print("\n📤 Template upload testi...")
    
    # Test için dummy DOCX dosyası oluştur
    test_file_path = "test_template.docx"
    if not os.path.exists(test_file_path):
        print(f"⚠️  Test dosyası bulunamadı: {test_file_path}")
        print("   Manuel test için uploads/templates/ klasörüne bir .docx dosyası koy")
        return None
    
    with open(test_file_path, 'rb') as f:
        files = {'file': ('test_template.docx', f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
        data = {
            'name': 'Test Template',
            'description': 'API test için oluşturuldu',
            'object_type': 'deal',
            'field_map': json.dumps({
                'deal_name': '{{deal.name}}',
                'deal_value': '{{deal.value}}',
                'contact_name': '{{contact.name}}'
            })
        }
        
        response = session.post(f"{API_URL}/templates", files=files, data=data)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        print(f"✅ Template oluşturuldu: ID={data.get('template', {}).get('id')}")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data.get('template', {}).get('id')
    else:
        print(f"❌ Hata: {response.text}")
        return None

def test_generate_document(template_id=None):
    """Doküman oluştur"""
    if not template_id:
        print("\n⚠️  Template ID yok, generate testi atlanıyor")
        return
    
    print(f"\n📄 Doküman oluşturuluyor (template_id={template_id})...")
    
    payload = {
        'template_id': template_id,
        'record_type': 'deal',
        'record_id': 1,  # Mevcut bir deal ID'si kullan
        'output_type': 'pdf',
        'context_data': {
            'deal': {
                'name': 'Test Deal',
                'value': 50000,
                'stage': 'Proposal'
            },
            'contact': {
                'name': 'Test Contact',
                'email': 'test@example.com',
                'phone': '+90 555 123 4567'
            }
        }
    }
    
    response = session.post(f"{API_URL}/generate", json=payload)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        doc_id = data.get('document', {}).get('id')
        print(f"✅ Doküman oluşturuldu: ID={doc_id}")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return doc_id
    else:
        print(f"❌ Hata: {response.text}")
        return None

def test_list_documents():
    """Oluşturulan dokümanları listele"""
    print("\n📚 Oluşturulan dokümanlar getiriliyor...")
    response = session.get(f"{API_URL}/documents")
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ {len(data.get('documents', []))} doküman bulundu")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"❌ Hata: {response.text}")
    
    return response

def test_download_document(doc_id):
    """Doküman indir"""
    if not doc_id:
        print("\n⚠️  Document ID yok, download testi atlanıyor")
        return
    
    print(f"\n⬇️  Doküman indiriliyor (doc_id={doc_id})...")
    response = session.get(f"{API_URL}/documents/{doc_id}/download")
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        filename = f"downloaded_doc_{doc_id}.pdf"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✅ Doküman indirildi: {filename}")
    else:
        print(f"❌ Hata: {response.text}")

def main():
    print("=" * 60)
    print("🧪 DocGen API Test Suite")
    print("=" * 60)
    
    # Login
    if not login():
        print("\n❌ Test başarısız: Login yapılamadı")
        return
    
    # Test 1: Template listesi
    test_list_templates()
    
    # Test 2: Template oluştur (opsiyonel - dosya gerekli)
    template_id = test_create_template()
    
    # Test 3: Doküman oluştur
    doc_id = test_generate_document(template_id)
    
    # Test 4: Doküman listesi
    test_list_documents()
    
    # Test 5: Doküman indir
    test_download_document(doc_id)
    
    print("\n" + "=" * 60)
    print("✅ Test tamamlandı")
    print("=" * 60)

if __name__ == "__main__":
    main()
