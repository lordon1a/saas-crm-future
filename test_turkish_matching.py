"""
Test Turkish character normalization and matching
"""
import re
import unicodedata

def normalize_text(text):
    if not text:
        return ''
    
    text = text.lower()
    
    turkish_map = {
        'ş': 's', 'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'ç': 'c',
        'Ş': 's', 'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ö': 'o', 'Ç': 'c'
    }
    for turkish, latin in turkish_map.items():
        text = text.replace(turkish, latin)
    
    text = unicodedata.normalize('NFKD', text)
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    text = re.sub(r'[^a-z0-9]', '', text)
    
    return text

# Test cases
test_cases = [
    "Kişi - Ünvan",
    "Kişi - Rol",
    "Kişi Ünvanı",
    "Kişi Rolü",
    "Unvan",
    "Rol"
]

print("✅ Turkish Character Normalization Test")
print("=" * 60)

for test in test_cases:
    normalized = normalize_text(test)
    print(f"{test:20} → {normalized}")

print("\n✅ Expected matches:")
print("  kisiunvan → job_title")
print("  kisirol → role")
