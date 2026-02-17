#!/usr/bin/env python3
"""
Test OAuth metadata endpoints locally
"""

import requests

BASE_URL = "http://localhost:8000"

print("Testing OAuth Metadata Endpoints")
print("=" * 60)

# Test 1: OAuth Authorization Server Metadata
print("\n1. Testing /.well-known/oauth-authorization-server")
try:
    response = requests.get(f"{BASE_URL}/.well-known/oauth-authorization-server")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Issuer: {data.get('issuer')}")
        print(f"   ✓ Authorization Endpoint: {data.get('authorization_endpoint')}")
        print(f"   ✓ Token Endpoint: {data.get('token_endpoint')}")
        print(f"   ✓ Registration Endpoint: {data.get('registration_endpoint')}")

        if data.get("registration_endpoint"):
            print("   ✅ RFC 7591 Dynamic Client Registration SUPPORTED")
        else:
            print("   ❌ RFC 7591 NOT FOUND in metadata")
    else:
        print(f"   ❌ Failed: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: OAuth Protected Resource Metadata
print("\n2. Testing /.well-known/oauth-protected-resource")
try:
    response = requests.get(f"{BASE_URL}/.well-known/oauth-protected-resource")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✓ Resource: {data.get('resource')}")
        print(f"   ✓ Scopes: {data.get('scopes_supported')}")
        print("   ✅ Protected Resource metadata available")
    else:
        print(f"   ❌ Failed: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Registration Endpoint
print("\n3. Testing POST /oauth/register")
try:
    payload = {
        "client_name": "Test Client",
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "scope": "read write",
    }
    response = requests.post(f"{BASE_URL}/oauth/register", json=payload)
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        data = response.json()
        print(f"   ✓ Client ID: {data.get('client_id')}")
        print(f"   ✓ Client Secret: {data.get('client_secret')[:20]}...")
        print("   ✅ Dynamic Client Registration WORKING")
    else:
        print(f"   ❌ Failed: {response.text}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("Test Complete!")
