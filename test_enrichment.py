"""
Test script for Auto-Enrichment Engine
"""
from app import app
from services.enrichment import enrich_contact

# Test mesajları
test_messages = [
    {
        'text': 'Merhaba, ben Ahmet Yılmaz. Tekno A.Ş den arıyorum. Numaram 0532 111 22 33, mail: ahmet@tekno.com',
        'expected': ['phone', 'email', 'company_name']
    },
    {
        'text': 'İletişim bilgilerim: +90 555 444 33 22 ve info@example.com',
        'expected': ['phone', 'email']
    },
    {
        'text': 'Merhaba, Digital Solutions Ltd şirketinden yazıyorum.',
        'expected': ['company_name']
    }
]

def test_enrichment():
    """Manuel test - contact_id ve workspace_id'yi kendiniz girin"""
    
    print("=" * 60)
    print("AUTO-ENRICHMENT ENGINE TEST")
    print("=" * 60)
    
    # Gerçek değerler
    contact_id = 12604  # Ahmet Yılmaz
    workspace_id = 1
    
    with app.app_context():
        for i, test in enumerate(test_messages, 1):
            print(f"\n[Test {i}] Mesaj: {test['text'][:50]}...")
            print(f"Beklenen alanlar: {', '.join(test['expected'])}")
            
            result = enrich_contact(
                contact_id=contact_id,
                workspace_id=workspace_id,
                message_text=test['text'],
                source='test'
            )
            
            if result:
                print(f"✅ Güncellenen alanlar: {', '.join(result)}")
            else:
                print("❌ Hiçbir alan güncellenmedi")
    
    print("\n" + "=" * 60)
    print("Test tamamlandı!")
    print("DB'de enrichment_logs tablosunu kontrol edin:")
    print("  SELECT * FROM enrichment_logs ORDER BY created_at DESC LIMIT 5;")
    print("=" * 60)

if __name__ == '__main__':
    test_enrichment()
