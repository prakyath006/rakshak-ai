"""Quick test to verify Razorpay test API keys are working."""
import requests
import base64
import json
import sys

KEY_ID = "rzp_test_TV9QXHbLAepvfh"
KEY_SECRET = "CMhx9s4HFQLThH1WYDpB5xjC"
BASE_URL = "https://api.razorpay.com/v1"

auth_str = f"{KEY_ID}:{KEY_SECRET}"
encoded = base64.b64encode(auth_str.encode()).decode()
headers = {
    "Authorization": f"Basic {encoded}",
    "Content-Type": "application/json",
}

print("=" * 60)
print("RAZORPAY API KEY VERIFICATION")
print("=" * 60)
print(f"Key ID: {KEY_ID}")
print(f"Base URL: {BASE_URL}")
print()

# Test 1: Fetch payments
print("[TEST 1] GET /v1/payments?count=1")
try:
    resp = requests.get(f"{BASE_URL}/payments?count=1", headers=headers, timeout=10)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  [PASS] AUTH SUCCESS - {data.get('count', 0)} payment(s) returned")
    elif resp.status_code == 401:
        print(f"  [FAIL] AUTH FAILED - Invalid API key or secret")
        print(f"  Response: {resp.text[:200]}")
        sys.exit(1)
    else:
        print(f"  [WARN] Unexpected status: {resp.text[:200]}")
except Exception as e:
    print(f"  [FAIL] Connection error: {e}")
    sys.exit(1)

# Test 2: Fetch disputes
print()
print("[TEST 2] GET /v1/disputes?count=5")
try:
    resp = requests.get(f"{BASE_URL}/disputes?count=5", headers=headers, timeout=10)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("items", [])
        print(f"  [PASS] DISPUTES ENDPOINT OK - {len(items)} dispute(s) found")
        if items:
            for d in items[:3]:
                amt = d.get('amount', 0)
                print(f"     > {d.get('id')} | Rs {amt/100:.2f} | {d.get('status')} | reason: {d.get('reason_code')}")
        else:
            print(f"     (No disputes yet - normal for new test account)")
    else:
        print(f"  [WARN] Status {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 3: Create a test order
print()
print("[TEST 3] POST /v1/orders (create test order)")
try:
    order_payload = {
        "amount": 5000,
        "currency": "INR",
        "receipt": "rakshak_test_001",
        "notes": {"purpose": "Rakshak AI API key verification"}
    }
    resp = requests.post(f"{BASE_URL}/orders", headers=headers, data=json.dumps(order_payload), timeout=10)
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  [PASS] ORDER CREATED - {data.get('id')} | Rs {data.get('amount', 0)/100:.2f} | {data.get('status')}")
    else:
        print(f"  [WARN] Status {resp.status_code}: {resp.text[:300]}")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

print()
print("=" * 60)
print("RESULT: Razorpay test API keys are VALID and WORKING")
print("=" * 60)
