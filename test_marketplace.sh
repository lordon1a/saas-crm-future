#!/bin/bash

echo "=========================================="
echo "MARKETPLACE MIDDLEWARE TEST"
echo "=========================================="
echo ""
echo "NOTE: You must be logged in via browser first!"
echo "Open http://localhost:5000 and login, then run this test."
echo ""
read -p "Press Enter to continue..."

echo ""
echo "=========================================="
echo "TEST 1: Uninstall DocGen"
echo "=========================================="
curl -X POST http://localhost:5000/api/marketplace/uninstall \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"app_slug": "docgen"}' \
  -w "\nHTTP Status: %{http_code}\n"

echo ""
echo ""
echo "=========================================="
echo "TEST 2: Access DocGen endpoint (should fail with 403)"
echo "=========================================="
curl http://localhost:5000/api/docgen/templates \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -w "\nHTTP Status: %{http_code}\n"

echo ""
echo ""
echo "=========================================="
echo "TEST 3: Install DocGen"
echo "=========================================="
curl -X POST http://localhost:5000/api/marketplace/install \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"app_slug": "docgen"}' \
  -w "\nHTTP Status: %{http_code}\n"

echo ""
echo ""
echo "=========================================="
echo "TEST 4: Access DocGen endpoint (should succeed with 200)"
echo "=========================================="
curl http://localhost:5000/api/docgen/templates \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -w "\nHTTP Status: %{http_code}\n"

echo ""
echo ""
echo "=========================================="
echo "TEST COMPLETE"
echo "=========================================="
