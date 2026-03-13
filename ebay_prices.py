"""
ebay_prices.py - Fetch listing prices from eBay and calculate averages ourselves
"""

import os
import base64
import requests
import time

EBAY_APP_ID  = os.getenv("EBAY_APP_ID", "YOUR_EBAY_APP_ID_HERE")
EBAY_CERT_ID = os.getenv("EBAY_CERT_ID", "YOUR_EBAY_CERT_ID_HERE")

PART_SEARCH_TERMS = {
    "driver mirror":    "{year} {make} {model} driver side mirror OEM",
    "passenger mirror": "{year} {make} {model} passenger side mirror OEM",
    "tail light":       "{year} {make} {model} tail light OEM",
    "head light":       "{year} {make} {model} headlight OEM",
    "BCM module":       "{year} {make} {model} body control module BCM",
    "modules":          "{year} {make} {model} module ECM TCM BCM",
    "trim pieces":      "{year} {make} {model} interior trim OEM",
}


def get_oauth_token():
    credentials = base64.b64encode(f"{EBAY_APP_ID}:{EBAY_CERT_ID}".encode()).decode()
    r = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope"
    )
    if r.status_code == 200:
        return r.json()["access_token"]
    print(f"[eBay] Auth failed: {r.status_code} {r.text}")
    return None


def search_prices(query: str, token: str, limit: int = 50) -> list:
    """Search eBay listings and return list of prices."""
    r = requests.get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        headers={
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
        },
        params={
            "q": query,
            "limit": limit,
            "filter": "buyingOptions:{FIXED_PRICE}"
        },
        timeout=15
    )

    if r.status_code != 200:
        print(f"[eBay] Search failed: {r.status_code}")
        return []

    items = r.json().get("itemSummaries", [])
    prices = []
    for item in items:
        price = item.get("price", {}).get("value")
        if price:
            try:
                prices.append(float(price))
            except ValueError:
                pass
    return prices


def calc_stats(prices: list) -> dict:
    if not prices:
        return {"avg": None, "min": None, "max": None, "count": 0}
    return {
        "avg":   round(sum(prices) / len(prices), 2),
        "min":   round(min(prices), 2),
        "max":   round(max(prices), 2),
        "count": len(prices)
    }


def fetch_prices_for_vehicle(make: str, model: str, year: int, parts: list) -> dict:
    """Fetch and average eBay prices for all parts of a vehicle."""
    if EBAY_APP_ID == "YOUR_EBAY_APP_ID_HERE":
        return {}

    token = get_oauth_token()
    if not token:
        return {}

    results = {}
    for part in parts:
        if part not in PART_SEARCH_TERMS:
            continue
        query = PART_SEARCH_TERMS[part].format(year=year, make=make, model=model)
        print(f"[eBay] Searching: {query}")
        prices = search_prices(query, token)
        results[part] = calc_stats(prices)
        print(f"[eBay] {part}: {results[part]}")
        time.sleep(0.5)

    return results


def format_price_line(part: str, stats: dict) -> str:
    if not stats or stats["avg"] is None:
        return f"  • {part.title()}: no data"
    return (
        f"  ✅ {part.title()}\n"
        f"     Avg: ${stats['avg']:.2f}  |  "
        f"Min: ${stats['min']:.2f}  |  "
        f"Max: ${stats['max']:.2f}  |  "
        f"{stats['count']} listings"
    )


def build_price_block(make: str, model: str, year: int, parts: list) -> str:
    """Build price section for Telegram alert."""
    try:
        from database import get_ebay_prices, save_ebay_price
        cached = get_ebay_prices(make, model, year)
    except Exception:
        cached = {}

    lines = []
    parts_to_fetch = []

    for part in parts:
        if part in cached:
            stats = {
                "avg":   cached[part]["avg_price"],
                "min":   cached[part]["min_price"],
                "max":   cached[part]["max_price"],
                "count": cached[part]["sold_count"]
            }
            lines.append(format_price_line(part, stats))
        else:
            parts_to_fetch.append(part)

    if parts_to_fetch:
        fresh = fetch_prices_for_vehicle(make, model, year, parts_to_fetch)
        for part, stats in fresh.items():
            lines.append(format_price_line(part, stats))
            try:
                save_ebay_price(
                    make, model, str(year), part,
                    stats["avg"], stats["min"], stats["max"], stats["count"]
                )
            except Exception:
                pass

    return "\n".join(lines) if lines else "  No pricing data available"


if __name__ == "__main__":
    make, model, year = "Ford", "F-150", 2018
    parts = ["driver mirror", "tail light", "BCM module"]
    print(f"\nFetching prices for {year} {make} {model}...")
    prices = fetch_prices_for_vehicle(make, model, year, parts)
    for part, stats in prices.items():
        print(format_price_line(part, stats))
