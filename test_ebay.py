import os, requests, base64

APP_ID = os.getenv("EBAY_APP_ID")
CERT_ID = os.getenv("EBAY_CERT_ID")

# Get token
credentials = base64.b64encode(f"{APP_ID}:{CERT_ID}".encode()).decode()
r = requests.post(
    "https://api.ebay.com/identity/v1/oauth2/token",
    headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
    data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope"
)
token = r.json()["access_token"]
print("Got token")

# Search
r = requests.get(
    "https://api.ebay.com/buy/browse/v1/item_summary/search",
    headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
    params={"q": "2018 Ford F-150 driver mirror OEM", "limit": 3}
)
data = r.json()
items = data.get("itemSummaries", [])
print(f"Found {len(items)} items")
for item in items:
    print(f"  Title: {item.get('title')}")
    print(f"  Price: {item.get('price')}")
