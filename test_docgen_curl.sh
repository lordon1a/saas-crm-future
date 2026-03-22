#!/bin/bash
# DocGen API Curl Test Script
# Kullanım: bash test_docgen_curl.sh

BASE_URL="http://localhost:5000"
API_URL="$BASE_URL/api/docgen"

echo "======================================"
echo "🧪 DocGen API Curl Test"
echo "======================================"

# Cookie dosyası (session için)
COOKIE_FILE="test_cookies.txt"

echo ""
echo "🔐 1. Login yapılıyor..."
curl -c $COOKIE_FILE -X POST "$BASE_URL/login" \
  -d "email=test@example.com" \
  -d "password=test123" \
  -L -s -o /dev/null -w "HTTP Status: %{http_code}\n"

echo ""
echo "📋 2. Template listesi getiriliyor..."
curl -b $COOKIE_FILE -X GET "$API_URL/templates" \
  -H "Content-Type: application/json" \
  -s | python -m json.tool

echo ""
echo "📚 3. Oluşturulan dokümanlar getiriliyor..."
curl -b $COOKIE_FILE -X GET "$API_URL/documents" \
  -H "Content-Type: application/json" \
  -s | python -m json.tool

echo ""
echo "======================================"
echo "✅ Test tamamlandı"
echo "======================================"
echo ""
echo "📝 Not: Email/şifre hatalıysa test_docgen_curl.sh dosyasını düzenle"

# Cookie dosyasını temizle
rm -f $COOKIE_FILE
