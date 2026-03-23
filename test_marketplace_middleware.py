"""
Test script for marketplace middleware functionality
Tests if @require_app decorator properly blocks/allows access
"""
import requests
import json

BASE_URL = "http://localhost:5000"

# You need to be logged in - get session cookie first
# For this test, we'll use a session
session = requests.Session()

print("=" * 60)
print("MARKETPLACE MIDDLEWARE TEST")
print("=" * 60)

# First, login to get session
print("\n[STEP 0] Logging in...")
login_response = session.post(
    f"{BASE_URL}/login",
    data={
        "email": "test@example.com",  # Replace with your test credentials
        "password": "password"
    }
)
if login_response.status_code == 200:
    print("✓ Login successful")
else:
    print(f"✗ Login failed: {login_response.status_code}")
    print("Please update credentials in test script and ensure app is running")
    exit(1)

print("\n" + "=" * 60)
print("TEST 1: Uninstall DocGen")
print("=" * 60)

response = session.post(
    f"{BASE_URL}/api/marketplace/uninstall",
    json={"app_slug": "docgen"}
)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

print("\n" + "=" * 60)
print("TEST 2: Try to access DocGen endpoint (should fail with 403)")
print("=" * 60)

response = session.get(f"{BASE_URL}/api/docgen/templates")
print(f"Status Code: {response.status_code}")
if response.status_code == 403:
    print("✓ PASS: Access denied as expected")
    print(f"Response: {response.text}")
else:
    print(f"✗ FAIL: Expected 403, got {response.status_code}")
    print(f"Response: {response.text}")

print("\n" + "=" * 60)
print("TEST 3: Install DocGen")
print("=" * 60)

response = session.post(
    f"{BASE_URL}/api/marketplace/install",
    json={"app_slug": "docgen"}
)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

print("\n" + "=" * 60)
print("TEST 4: Try to access DocGen endpoint again (should succeed with 200)")
print("=" * 60)

response = session.get(f"{BASE_URL}/api/docgen/templates")
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    print("✓ PASS: Access granted as expected")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response: {response.text[:200]}")
else:
    print(f"✗ FAIL: Expected 200, got {response.status_code}")
    print(f"Response: {response.text}")

print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print("If both tests passed, middleware is working correctly!")
print("=" * 60)
