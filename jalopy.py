"""
scrapers/jalopy.py - Jalopy Jungle inventory scraper
URL: https://inventory.pickapartjalopyjungle.com
Location: id=yard-id (ALL CAPS)
Make: id=car-make (ALL CAPS)
Model: id=car-model (ALL CAPS)
Table columns: YEAR | MAKE | MODEL | ROW
"""

import json
import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

INVENTORY_URL = "https://inventory.pickapartjalopyjungle.com/"
YARD_NAME     = "Jalopy Jungle"
LOCATIONS     = ["Boise", "Nampa", "Caldwell", "Garden City", "Twin Falls"]


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def scrape_all(targets: list) -> list:
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(120000)
        page.set_default_navigation_timeout(120000)

        for location in LOCATIONS:
            print(f"[Jalopy] Scraping {location}...")
            loc_results = 0

            for target in targets:
                make       = target["make"]
                model      = target["model"]
                want_years = [str(y) for y in target["years"]]

                try:
                    # Fresh page load for each search
                    page.goto(INVENTORY_URL, wait_until="domcontentloaded", timeout=120000)
                    page.wait_for_timeout(6000)

                    # Step 1: Select location
                    page.select_option("#yard-id", label=location.upper())
                    page.wait_for_timeout(3000)

                    # Step 2: Select make
                    page.select_option("#car-make", label=make.upper())
                    page.wait_for_timeout(3000)

                    # Step 3: Wait for model options to load then select
                    # Check model is actually in the list before selecting
                    model_opts = page.locator("#car-model option").all_inner_texts()
                    model_upper = model.upper()
                    if model_upper not in model_opts:
                        print(f"[Jalopy/{location}] Model '{model_upper}' not in list, skipping")
                        continue

                    page.select_option("#car-model", label=model_upper)
                    page.wait_for_timeout(3000)

                    # Step 4: Read results table
                    trs = page.locator("tr")
                    for j in range(trs.count()):
                        tr = trs.nth(j)
                        tds = tr.locator("td")
                        if tds.count() < 4:
                            continue

                        y   = tds.nth(0).inner_text().strip()
                        mk  = tds.nth(1).inner_text().strip()
                        mdl = tds.nth(2).inner_text().strip()
                        row = tds.nth(3).inner_text().strip()

                        if y not in want_years:
                            continue
                        if _norm(mk) != _norm(make):
                            continue
                        if _norm(mdl) != _norm(model):
                            continue

                        results.append({
                            "yard":     YARD_NAME,
                            "location": location,
                            "year":     y,
                            "make":     mk,
                            "model":    mdl,
                            "row":      row
                        })
                        loc_results += 1
                        print(f"[Jalopy/{location}] Found: {y} {mk} {mdl} — Row {row}")

                except PWTimeout:
                    print(f"[Jalopy/{location}] Timeout on {make} {model} — skipping")
                    continue
                except Exception as e:
                    print(f"[Jalopy/{location}] Error on {make} {model}: {e}")
                    continue

            print(f"[Jalopy] {location}: {loc_results} matches")

        browser.close()

    print(f"[Jalopy] Done. Total: {len(results)}")
    return results


if __name__ == "__main__":
    targets_path = os.path.join(os.path.dirname(__file__), "..", "targets.json")
    with open(targets_path) as f:
        targets = json.load(f)
    results = scrape_all(targets)
    for r in results:
        print(r)
