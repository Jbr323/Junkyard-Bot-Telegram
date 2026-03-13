"""
scrapers/trusty.py - Trusty Pick-A-Part inventory scraper
URL: https://inventory.trustypickapart.com
Make select: id=car-make, name=VehicleMake
Model select: id=car-model, name=VehicleModel
Table columns: YEAR | MAKE | MODEL | ROW
"""

import json
import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

INVENTORY_URL = ""
YARD_NAME     = ""
LOCATION_NAME = ""


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def scrape_all(targets: list) -> list:
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(120000)
        page.set_default_navigation_timeout(120000)

        for target in targets:
            make       = target["make"]
            model      = target["model"]
            want_years = [str(y) for y in target["years"]]

            try:
                print(f"[Trusty] Searching {make} {model}...")

                page.goto(INVENTORY_URL, wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(6000)

                # Select make by exact ID
                page.select_option("#car-make", label=make.upper())
                page.wait_for_timeout(2000)

                # Select model by exact ID
                page.select_option("#car-model", label=model.upper())
                page.wait_for_timeout(1000)

                # Click SEARCH button
                page.click("input[type=submit]")
                page.wait_for_timeout(6000)

                # Read results table
                trs = page.locator("tr")
                found = 0
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
                        "location": LOCATION_NAME,
                        "year":     y,
                        "make":     mk,
                        "model":    mdl,
                        "row":      row
                    })
                    found += 1
                    print(f"[Trusty] Found: {y} {mk} {mdl} — Row {row}")

                print(f"[Trusty] {make} {model}: {found} matches")

            except PWTimeout:
                print(f"[Trusty] Timeout on {make} {model} — skipping")
                continue
            except Exception as e:
                print(f"[Trusty] Error on {make} {model}: {e}")
                continue

        browser.close()

    print(f"[Trusty] Done. Total: {len(results)}")
    return results


def debug_page():
    debug_dir = os.path.join(os.path.dirname(__file__), "..", "data", "debug")
    os.makedirs(debug_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shot_path = os.path.join(debug_dir, f"trusty_debug_{stamp}.png")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(INVENTORY_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(6000)
            page.screenshot(path=shot_path, full_page=True)
            print(f"[Trusty] Screenshot saved to: {shot_path}")
            selects = page.locator("select")
            for i in range(selects.count()):
                sel = selects.nth(i)
                print(f"Select {i}: id={sel.get_attribute('id')} name={sel.get_attribute('name')}")
                opts = sel.locator("option").all_inner_texts()
                print(f"  Options: {opts[:5]}")
        except Exception as e:
            print(f"[Trusty] Debug error: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    if "--debug" in sys.argv:
        debug_page()
    else:
        targets_path = os.path.join(os.path.dirname(__file__), "..", "targets.json")
        with open(targets_path) as f:
            targets = json.load(f)
        results = scrape_all(targets)
        for r in results:
            print(r)
