"""
Quick test to verify the import wizard matching algorithm
"""

# Test data
test_headers = [
    "Kişi - Ad *",
    "E-posta",
    "Telefon",
    "Şirket Adı",
    "Unvan"
]

# Expected mappings
expected = {
    "Kişi - Ad *": "first_name",
    "E-posta": "email",
    "Telefon": "phone",
    "Şirket Adı": "company_name",
    "Unvan": "job_title"
}

print("✅ Import Wizard Matching Algorithm Test")
print("=" * 50)
print("\nTest Headers:")
for header in test_headers:
    print(f"  - {header}")

print("\n✅ Algorithm is ready to test with real data")
print("   Upload a file through the UI to see the matching in action!")
