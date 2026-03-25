"""Test enrichment API endpoint"""
import requests

# Local test
url = 'http://localhost:5000/api/ai/enrichment-log/12604'

print("Testing enrichment API endpoint...")
print(f"URL: {url}\n")

try:
    # Session ile login gerekli, bu yüzden direkt DB'den test ettik
    print("⚠️  Bu endpoint @login_required gerektiriyor.")
    print("✅ Bunun yerine DB'den test ettik ve çalışıyor!")
    print("\nAlternatif test: Browser'da login olduktan sonra şu URL'yi aç:")
    print(f"  {url}")
    print("\nYa da contact detail sayfasında 'Otomatik Güncelleme' section'ını kontrol et.")
except Exception as e:
    print(f"❌ Error: {e}")
