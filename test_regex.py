"""Test company regex patterns"""
from services.enrichment import extract_with_regex

tests = [
    'Tekno A.Ş den arıyorum',
    'şirketinden yazıyorum',
    'ABC Corp çalışanıyım',
    'Merhaba ben Ali, Garanti Bankası IT departmanından',
    'Digital Solutions Ltd ile çalışıyorum',
    'şirket: Turkcell',
    'firma: Vodafone Türkiye',
]

print("=" * 60)
print("COMPANY REGEX TEST")
print("=" * 60)

for t in tests:
    result = extract_with_regex(t)
    company = result.get('company_name', {})
    
    if company:
        print(f"✅ Input: {t}")
        print(f"   Company: {company.get('value')} (confidence: {company.get('confidence')})")
    else:
        print(f"❌ Input: {t}")
        print(f"   Company: YOK")
    print()

print("=" * 60)
