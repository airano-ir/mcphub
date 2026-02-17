#!/usr/bin/env python3
"""
Test OAuth client registration endpoint security.

Verifies that:
1. Registration endpoint requires Master API Key
2. Unauthorized requests are rejected with 401
3. Valid Master API Key allows registration
"""

import os

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
MASTER_API_KEY = os.getenv("MASTER_API_KEY", "your_master_key_here")

print("Testing OAuth Client Registration Security")
print("=" * 60)

# Test 1: Registration without Authorization header
print("\n1. Testing registration WITHOUT Authorization header")
try:
    payload = {
        "client_name": "Unauthorized Test Client",
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code"],
        "scope": "read",
    }

    response = requests.post(f"{BASE_URL}/oauth/register", json=payload)
    print(f"   Status: {response.status_code}")

    if response.status_code == 401:
        data = response.json()
        print(f"   ✅ Correctly rejected: {data.get('error')}")
        print(f"   Message: {data.get('error_description')}")
    else:
        print(f"   ❌ SECURITY ISSUE: Should return 401, got {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Registration with invalid API key
print("\n2. Testing registration WITH invalid API key")
try:
    payload = {
        "client_name": "Unauthorized Test Client 2",
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code"],
        "scope": "read",
    }

    headers = {"Authorization": "Bearer invalid_api_key_12345"}

    response = requests.post(f"{BASE_URL}/oauth/register", json=payload, headers=headers)
    print(f"   Status: {response.status_code}")

    if response.status_code == 401:
        data = response.json()
        print(f"   ✅ Correctly rejected: {data.get('error')}")
        print(f"   Message: {data.get('error_description')}")
    else:
        print(f"   ❌ SECURITY ISSUE: Should return 401, got {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Registration with valid Master API Key
print("\n3. Testing registration WITH valid Master API Key")
try:
    payload = {
        "client_name": "Authorized Test Client",
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "scope": "read write",
    }

    headers = {"Authorization": f"Bearer {MASTER_API_KEY}"}

    response = requests.post(f"{BASE_URL}/oauth/register", json=payload, headers=headers)
    print(f"   Status: {response.status_code}")

    if response.status_code == 201:
        data = response.json()
        print("   ✅ Successfully registered client")
        print(f"   Client ID: {data.get('client_id')}")
        print(f"   Client Secret: {data.get('client_secret', '')[:20]}...")
        print(f"   Client Name: {data.get('client_name')}")
    else:
        print(f"   ❌ Registration failed: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Attempt registration with wrong Authorization format
print("\n4. Testing registration with wrong Authorization format")
try:
    payload = {
        "client_name": "Test Client Wrong Format",
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code"],
        "scope": "read",
    }

    headers = {"Authorization": MASTER_API_KEY}  # Missing "Bearer " prefix

    response = requests.post(f"{BASE_URL}/oauth/register", json=payload, headers=headers)
    print(f"   Status: {response.status_code}")

    if response.status_code == 401:
        data = response.json()
        print(f"   ✅ Correctly rejected: {data.get('error')}")
        print(f"   Message: {data.get('error_description')}")
    else:
        print(f"   ❌ Should return 401, got {response.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("Security Test Complete!")
print("\nExpected Results:")
print("  ✅ Test 1 & 2 & 4: Should return 401 Unauthorized")
print("  ✅ Test 3: Should return 201 Created with client credentials")
